"""Preference-based fixed selection and bounded distributional suffix rollouts.

Future suffixes are fixed plans when scored, not clairvoyant per-draw choices.
Only the first action is executed, then the policy replans at the next stop.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math

import numpy as np

from .adaptive import SharedSuffixPolicy
from .benchmark import execute
from .routing import SearchBudgetExceeded, route_key


@dataclass(frozen=True)
class Preference:
    mode: str
    extra_wait_weight: float = 2.0
    transfer_penalty: float = 3.0
    quantile: float = .95

    def __post_init__(self):
        if self.mode not in {"fast", "cool", "reliable"}:
            raise ValueError("Unknown preference")
        if any(not math.isfinite(x) or x < 0 for x in (self.extra_wait_weight, self.transfer_penalty)):
            raise ValueError("Preference costs must be finite and nonnegative")
        if not math.isfinite(self.quantile) or not 0 < self.quantile <= 1:
            raise ValueError("Quantile must be in (0, 1]")

    def rank(self, durations, waits, transfers):
        """Completion first; then the requested objective, mean and transfers.

        Incomplete journeys retain infinite duration, never successful-only mean.
        All arguments are one-dimensional arrays describing the same worlds.
        """
        durations, waits, transfers = map(np.asarray, (durations, waits, transfers))
        if not len(durations) or durations.ndim != 1 or waits.shape != durations.shape or transfers.shape != durations.shape:
            raise ValueError("Nonempty, equally sized sample vectors required")
        if np.isnan(durations).any() or (durations < 0).any() or not np.isfinite(waits).all() or (waits < 0).any() or not np.isfinite(transfers).all() or (transfers < 0).any():
            raise ValueError("Invalid journey samples")
        failure = float((~np.isfinite(durations)).mean())
        mean = float(durations.mean())
        changes = float(transfers.mean())
        if self.mode == "reliable":
            index = math.ceil(self.quantile * len(durations)) - 1
            objective = float(np.partition(durations, index)[index])
        elif self.mode == "cool":
            objective = mean + self.extra_wait_weight * float(waits.mean()) + self.transfer_penalty * changes
        else:
            objective = mean
        return failure, objective, mean, changes


def select_fixed_preferences(routes, network, parameters, training_worlds, preferences):
    """All preferences reuse the same training outcomes, never the test worlds."""
    if not routes or not preferences:
        raise ValueError("Routes and preferences are required")
    rows = []
    for route in routes:
        trial = execute(SharedSuffixPolicy(network, [route], parameters), training_worlds, controller="first")
        rows.append({"route": route_key(route), "summary": trial.summary(),
                     "ranks": {label: preference.rank(trial.durations, trial.waits, trial.transfers)
                               for label, preference in preferences.items()}})
    selected = {label: routes[min(range(len(routes)), key=lambda i: (rows[i]["ranks"][label], rows[i]["route"]))]
                for label in preferences}
    return selected, rows


@dataclass(frozen=True)
class SuffixCosts:
    durations: np.ndarray
    waits: np.ndarray
    transfers: np.ndarray


class DistributionalPolicy(SharedSuffixPolicy):
    """Receding-horizon fixed-suffix distribution heuristic, NOT optimal P95 DP.

    Future waits and boarding delays use stationary independent stratified draws.
    Their seed is separate from training and held-out evaluation worlds. History
    remains in the path-cache key; observed departure clocks are never cached.
    """

    def __init__(self, network, routes, parameters=None, *, preference=None,
                 rollout_samples=256, rollout_seed=2309, max_suffix_paths=1000,
                 max_suffix_states=10000):
        super().__init__(network, routes, parameters)
        if any(not isinstance(v, int) or v < 1 for v in (rollout_samples, max_suffix_paths, max_suffix_states)):
            raise ValueError("Positive integer rollout and suffix budgets required")
        self.preference = preference or Preference("fast")
        self.rollout_samples = rollout_samples
        self.rollout_seed = rollout_seed
        self.max_suffix_paths = max_suffix_paths
        self.max_suffix_states = max_suffix_states
        self._suffixes = {}
        self._rollout_waits, self._rollout_delays = {}, {}
        for sid, service in network.services.items():
            for kind, target, upper in (("wait", self._rollout_waits, service.headway_minutes),
                                        ("delay", self._rollout_delays, service.delay_max_minutes)):
                digest = hashlib.sha256(f"{rollout_seed}:{kind}:{sid}".encode()).digest()
                rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
                # Equal marginal distributions do not get arbitrary mean advantages.
                target[sid] = rng.permutation((np.arange(rollout_samples) + .5) / rollout_samples) * upper
                target[sid].flags.writeable = False
        self.last_diagnostics = []

    def suffixes(self, structure):
        if structure in self._suffixes:
            return self._suffixes[structure]
        # Reserve a cache slot before descending, so the budget bounds recursion too.
        if len(self._suffixes) >= self.max_suffix_states:
            raise SearchBudgetExceeded("Distributional suffix-state budget exceeded")
        self._suffixes[structure] = None
        try:
            if structure.stop == self.destination:
                paths = [()]
            else:
                paths = []
                for transition in self.transitions(structure):
                    for tail in self.suffixes(transition[1]):
                        paths.append((transition, *tail))
                        if len(paths) > self.max_suffix_paths:
                            raise SearchBudgetExceeded("Distributional suffix-path budget exceeded")
            self._suffixes[structure] = tuple(paths)
        except Exception:
            self._suffixes.pop(structure, None)
            raise
        return self._suffixes[structure]

    def project(self, state, decision, tail):
        """Project one precommitted suffix under model draws, never test arrays."""
        size, p = self.rollout_samples, self.parameters
        now = np.full(size, state.now)
        waits = np.zeros(size)
        changes = np.zeros(size)
        valid = np.ones(size, dtype=bool)
        structure = state.structure
        for index, (arc, following, continuing) in enumerate(((decision.arc, decision.following, decision.continuing), *tail)):
            if continuing:
                now = now + arc.ride_minutes
            else:
                transfer = bool(structure.used)
                buffer = p.transfer_walk_minutes if transfer else 0.0
                if index == 0:
                    alighted = state.alighted_at if transfer and structure.onboard is None else state.now
                    ready = max(state.now, alighted + buffer) if transfer else state.now
                    board = np.full(size, decision.board_time)
                    wait = np.full(size, max(0.0, decision.board_time - ready))
                    gap = board - alighted
                else:
                    wait = self._rollout_waits[arc.service_id]
                    board = now + buffer + wait
                    gap = buffer + wait
                if transfer:
                    changes += 1
                    valid &= gap <= p.max_transfer_gap + 1e-9
                waits += wait
                now = board + arc.ride_minutes + self._rollout_delays[arc.service_id]
            valid &= now - state.departure_time <= p.max_trip_minutes + 1e-9
            structure = following
        durations = np.where(valid, now - state.now, math.inf)
        return SuffixCosts(durations, waits, changes)

    def update(self, state, departures, *, event="arrival", allowed_arcs=None):
        options = []
        self.last_diagnostics = []
        for arc, _, _ in self.transitions(state.structure):
            if allowed_arcs is not None and (arc.service_id, arc.end) not in allowed_arcs:
                continue
            # Reuse exactly the existing feasibility checks, not its mean score.
            decision = super().update(state, departures, event=event, allowed_arcs={(arc.service_id, arc.end)})
            if decision is None:
                continue
            for tail in self.suffixes(decision.following):
                costs = self.project(state, decision, tail)
                rank = self.preference.rank(costs.durations, costs.waits, costs.transfers)
                path = ((arc.service_id, arc.start, arc.end),
                        *[(a.service_id, a.start, a.end) for a, _, _ in tail])
                self.last_diagnostics.append({"path": path, "rank": rank,
                                              "mean_remaining_minutes": float(costs.durations.mean()),
                                              "mean_remaining_wait": float(costs.waits.mean())})
                options.append((rank, not decision.continuing, path, decision))
        if not options:
            return None
        rank, _, _, decision = min(options, key=lambda item: item[:3])
        return replace(decision, estimated_remaining_score=rank[1])

"""Shared directed suffix structure and non-clairvoyant local decisions.

Future values use stationary uniform waits, not future realized ETA or delays.
Only the current stop's departures enter a local update.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Mapping

import numpy as np

from .corridors import CandidateSearch, DestinationIndex
from .models import Route, TransitNetwork, validate_route
from .routing import RoutingParameters, SearchBudgetExceeded
from .simulation import evaluate, next_departure


@dataclass(frozen=True)
class RideArc:
    service_id: str
    start: str
    end: str
    ride_minutes: float


@dataclass(frozen=True)
class SuffixNode:
    stop: str
    options: tuple[RideArc, ...]


@dataclass(frozen=True)
class StructuralState:
    stop: str
    onboard: str | None
    used: frozenset[str]
    visited: frozenset[str]


@dataclass(frozen=True)
class JourneyState:
    structure: StructuralState
    now: float
    departure_time: float
    # Fixed across waiting/ETA updates; do not reset the transfer window.
    alighted_at: float | None = None


@dataclass(frozen=True)
class LocalDecision:
    arc: RideArc
    following: StructuralState
    board_time: float
    continuing: bool
    estimated_remaining_score: float


class SharedSuffixPolicy:
    """One node per retained stop, with history-aware cached downstream values.

    Joining retained edges may create additional route combinations. Each decision
    checks visited stops, used services and remaining transfers before using them.
    """

    def __init__(self, network: TransitNetwork, routes: list[Route],
                 parameters: RoutingParameters | None = None, *,
                 value_samples: int = 64, value_seed: int = 29,
                 max_value_states: int = 100000):
        if not routes:
            raise ValueError("A policy needs at least one route")
        if value_samples < 1 or max_value_states < 1:
            raise ValueError("Value budgets must be positive")
        endpoints = {(route.origin, route.destination, route.walk_minutes) for route in routes}
        if len(endpoints) != 1 or routes[0].walk_minutes != 0:
            raise ValueError("Adaptive experiments require identical stop-to-stop endpoints")
        self.network = network
        self.origin, self.destination = routes[0].origin, routes[0].destination
        self.parameters = parameters or RoutingParameters()
        arcs: dict[str, set[RideArc]] = {}
        for route in routes:
            validate_route(route, network)
            if route.transfers > self.parameters.max_transfers:
                raise ValueError("Candidate exceeds transfer bound")
            for leg in route.legs:
                service = network.services[leg.service_id]
                start, end = service.stops.index(leg.board_stop), service.stops.index(leg.alight_stop)
                for i in range(start, end):
                    arc = RideArc(service.id, service.stops[i], service.stops[i + 1],
                                  service.ride_minutes[i])
                    arcs.setdefault(arc.start, set()).add(arc)
        self.nodes = {
            stop: SuffixNode(stop, tuple(sorted(options, key=lambda arc: (arc.service_id, arc.end))))
            for stop, options in arcs.items()
        }
        self.nodes.setdefault(self.destination, SuffixNode(self.destination, ()))
        self._wait_draws = {}
        for service_id, service in network.services.items():
            digest = hashlib.sha256(f"{value_seed}:{service_id}".encode()).digest()
            rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
            self._wait_draws[service_id] = rng.random(value_samples) * service.headway_minutes
        self.value_samples = value_samples
        self.max_value_states = max_value_states
        self._values: dict[StructuralState, tuple[float, float]] = {}
        self._building: set[StructuralState] = set()
        self.local_updates = 0
        self.value_cache_hits = 0

    @property
    def value_state_count(self):
        return len(self._values)

    def initial_state(self, departure_time=0.0):
        if not math.isfinite(departure_time):
            raise ValueError("Invalid departure time")
        return JourneyState(StructuralState(self.origin, None, frozenset(),
                                           frozenset({self.origin})),
                            departure_time, departure_time)

    def transitions(self, state: StructuralState):
        if state.stop == self.destination:
            return ()
        result = []
        node = self.nodes.get(state.stop)
        if node is None:
            return ()
        for arc in node.options:
            continuing = state.onboard == arc.service_id
            if arc.end in state.visited:
                continue
            if not continuing and (arc.service_id in state.used or
                                   len(state.used) >= self.parameters.max_transfers + 1):
                continue
            following = StructuralState(arc.end, arc.service_id, state.used | {arc.service_id},
                                        state.visited | {arc.end})
            result.append((arc, following, continuing))
        return tuple(result)

    def value(self, state: StructuralState) -> tuple[float, float]:
        """Return stationary expected score and an admissible ride/buffer bound.

        History is part of the cache key. Actual arrival times and observed ETAs
        are deliberately NOT cached in this stationary approximation.
        """
        if state in self._values:
            self.value_cache_hits += 1
            return self._values[state]
        if len(self._values) + len(self._building) >= self.max_value_states:
            raise SearchBudgetExceeded("Suffix value-state budget exceeded")
        self._building.add(state)
        if state.stop == self.destination:
            value = (0.0, 0.0)
        else:
            scores, bounds = [], []
            for arc, following, continuing in self.transitions(state):
                future, minimum = self.value(following)
                service = self.network.services[arc.service_id]
                transfer = bool(state.used) and not continuing
                buffer = self.parameters.transfer_walk_minutes if transfer else 0.0
                delay = 0.0 if continuing else service.delay_max_minutes / 2
                penalty = self.parameters.transfer_penalty if transfer else 0.0
                wait = np.zeros(self.value_samples) if continuing else self._wait_draws[service.id]
                scores.append(wait + buffer + arc.ride_minutes + delay + penalty + future)
                bounds.append(buffer + arc.ride_minutes + minimum)
            value = (float(np.min(np.stack(scores), axis=0).mean()), min(bounds)) if scores else (math.inf, math.inf)
        self._building.remove(state)
        self._values[state] = value
        return value

    def update(self, state: JourneyState, departures: Mapping[str, float],
               *, event: str = "arrival",
               allowed_arcs: set[tuple[str, str]] | None = None) -> LocalDecision | None:
        """Re-evaluate this stop only after arrival, a miss or an ETA change.

        Departures are absolute times at this stop, after the boarding buffer.
        Missing services are unavailable in this observation. Past departures
        are rejected, not silently advanced to an invented next bus.
        Optional (service_id, end_stop) pairs restrict current executable arcs;
        this does not refit or replace the stationary downstream value model.
        """
        if event not in {"arrival", "missed_bus", "eta_change"}:
            raise ValueError("Unknown local update event")
        if not math.isfinite(state.now) or not math.isfinite(state.departure_time) or state.now < state.departure_time:
            raise ValueError("Invalid journey clock")
        structure = state.structure
        if structure.stop not in self.network.stops or structure.stop not in structure.visited:
            raise ValueError("Invalid journey stop/history")
        if structure.onboard is not None and structure.onboard not in structure.used:
            raise ValueError("Onboard service must be in used history")
        if structure.used and structure.onboard is None and state.alighted_at is None:
            raise ValueError("A waiting transfer needs its original alighting time")
        if state.alighted_at is not None and (
            not math.isfinite(state.alighted_at) or not state.departure_time <= state.alighted_at <= state.now
        ):
            raise ValueError("Invalid alighting time")
        self.local_updates += 1
        p = self.parameters
        options = []
        for arc, following, continuing in self.transitions(structure):
            if allowed_arcs is not None and (arc.service_id, arc.end) not in allowed_arcs:
                continue
            transfer = bool(structure.used) and not continuing
            if continuing:
                board = state.now
            else:
                board = departures.get(arc.service_id)
                if board is None:
                    continue
                if not math.isfinite(board):
                    raise ValueError("Departure times must be finite")
                alighted = state.now if structure.onboard is not None else state.alighted_at
                ready = max(state.now, (alighted + p.transfer_walk_minutes) if transfer else state.now)
                if board < ready - 1e-9:
                    continue
                if transfer and board - alighted > p.max_transfer_gap + 1e-9:
                    continue
            future, minimum = self.value(following)
            if board - state.departure_time + arc.ride_minutes + minimum > p.max_trip_minutes + 1e-9:
                continue
            service = self.network.services[arc.service_id]
            score = (board - state.now + arc.ride_minutes + future
                     + (0 if continuing else service.delay_max_minutes / 2)
                     + (p.transfer_penalty if transfer else 0))
            options.append(LocalDecision(arc, following, float(board), continuing, score))
        return min(options, key=lambda choice: (
            choice.estimated_remaining_score, not choice.continuing, choice.arc.service_id,
        )) if options else None


@dataclass
class AdaptiveEvaluation:
    durations: np.ndarray
    waits: np.ndarray
    missed: np.ndarray
    transfer_counts: np.ndarray
    branch_counts: dict[str, int]
    stopped: np.ndarray
    over_limit: np.ndarray

    @property
    def summary(self):
        # Uncompleted journeys remain infinite in unconditional risk metrics.
        # JSON reports encode those metrics as null, alongside completion rates.
        ordered = np.sort(self.durations)
        quantile = lambda q: float(ordered[max(0, math.ceil(q * len(ordered)) - 1)])
        finite = self.durations[np.isfinite(self.durations)]
        return {
            "samples": len(ordered),
            "mean_minutes": float(self.durations.mean()),
            "p90_minutes": quantile(0.90),
            "p95_minutes": quantile(0.95),
            "mean_wait_minutes": float(self.waits.mean()),
            "failure_probability": float(self.missed.mean()),
            "completion_probability": float(np.isfinite(self.durations).mean()),
            "stopped_probability": float(self.stopped.mean()),
            "over_trip_limit_probability": float(self.over_limit.mean()),
            "completed_mean_minutes": float(finite.mean()) if finite.size else None,
            "mean_transfers": float(self.transfer_counts.mean()),
        }


@dataclass
class AdaptivePlan:
    index: DestinationIndex
    search: CandidateSearch
    policy: SharedSuffixPolicy | None
    baselines: dict[str, Route]


def plan_adaptive(network, origin, destination, parameters=None, corridors=None, *,
                  index=None, value_samples=64, value_seed=29, max_value_states=100000):
    """Build an experimental bounded plan; call policy.update for later events.

    Baselines here are best within the retained set, not full-network optima.
    A DestinationIndex can be reused only with the same immutable network snapshot.
    """
    from .corridors import discover_candidates
    from .routing import _baseline
    p = parameters or RoutingParameters()
    if index is None:
        index = DestinationIndex(network, destination)
    elif index.network is not network or index.destination != destination:
        raise ValueError("Destination index belongs to a different network or destination")
    search = discover_candidates(index, origin, p, corridors)
    if not search.routes:
        return AdaptivePlan(index, search, None, {})
    policy = SharedSuffixPolicy(network, search.routes, p, value_samples=value_samples,
                                value_seed=value_seed, max_value_states=max_value_states)
    policy.value(policy.initial_state().structure)
    baselines = {
        name: _baseline(search.routes, network, mode)
        for name, mode in (("shortest_expected_time", "time"),
                           ("minimum_transfers", "transfers"), ("minimum_ride_time", "ride"))
    }
    return AdaptivePlan(index, search, policy, baselines)


def evaluate_adaptive(policy: SharedSuffixPolicy, samples=10000, seed=100,
                      departure_time=0.0, *, phase_correlation=0.0) -> AdaptiveEvaluation:
    """Use the legacy simulator's keyed worlds, without exposing future worlds."""
    if not isinstance(samples, int) or samples < 1 or not math.isfinite(departure_time):
        raise ValueError("Invalid sample count or departure time")
    if not 0 <= phase_correlation <= 1:
        raise ValueError("Invalid phase correlation")
    network, p = policy.network, policy.parameters
    common = np.random.default_rng(seed).random((samples, 2))
    phases, delays = {}, {}
    for service_id, service in network.services.items():
        digest = hashlib.sha256(f"{seed}:{service_id}".encode()).digest()
        draws = np.random.default_rng(int.from_bytes(digest[:8], "big")).random((samples, 2))
        phase = np.where(common[:, 1] < phase_correlation, common[:, 0], draws[:, 0])
        phases[service_id] = phase * service.headway_minutes
        delays[service_id] = draws[:, 1] * service.delay_max_minutes
    durations = np.full(samples, math.inf)
    waits = np.zeros(samples)
    missed = np.zeros(samples, dtype=bool)
    stopped = np.zeros(samples, dtype=bool)
    over_limit = np.zeros(samples, dtype=bool)
    transfers = np.zeros(samples, dtype=int)
    branches: dict[str, int] = {}
    for sample in range(samples):
        state = policy.initial_state(departure_time)
        nominal = departure_time
        while state.structure.stop != policy.destination:
            observation, nominal_boards = {}, {}
            for arc, _, continuing in policy.transitions(state.structure):
                if continuing:
                    continue
                service = network.services[arc.service_id]
                offset = sum(service.ride_minutes[:service.stops.index(arc.start)])
                phase = phases[service.id][sample] + offset
                buffer = p.transfer_walk_minutes if state.structure.used else 0.0
                observation[service.id] = float(next_departure(state.now + buffer, phase, service.headway_minutes))
                nominal_boards[service.id] = float(next_departure(nominal + buffer, phase, service.headway_minutes))
            choice = policy.update(state, observation)
            if choice is None:
                stopped[sample] = True
                break
            arc = choice.arc
            if choice.continuing:
                now = state.now + arc.ride_minutes
                nominal += arc.ride_minutes
            else:
                buffer = p.transfer_walk_minutes if state.structure.used else 0.0
                waits[sample] += max(0, choice.board_time - state.now - buffer)
                if state.structure.used:
                    missed[sample] |= state.now + buffer > nominal_boards[arc.service_id] + 1e-9
                now = choice.board_time + arc.ride_minutes + delays[arc.service_id][sample]
                nominal = nominal_boards[arc.service_id] + arc.ride_minutes
                key = f"{arc.service_id}:{arc.start}"
                branches[key] = branches.get(key, 0) + 1
            state = JourneyState(choice.following, now, departure_time)
            transfers[sample] = max(0, len(state.structure.used) - 1)
            if now - departure_time > p.max_trip_minutes + 1e-9:
                over_limit[sample] = True
                stopped[sample] = True
                break
        if not stopped[sample]:
            durations[sample] = state.now - departure_time
    return AdaptiveEvaluation(durations, waits, missed, transfers, branches, stopped, over_limit)


def select_fixed_reference(routes, network, parameters=None, *, samples=512,
                           seed=7, departure_time=0.0):
    """A held-out evaluation must use a different seed from this selection."""
    from .routing import reliability_score
    if not routes:
        return None
    return min(routes, key=lambda route: reliability_score(
        evaluate(route, network, samples, seed, departure_time, parameters).summary, parameters,
    ))

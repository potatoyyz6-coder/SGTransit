"""Common-world, common-executor synthetic policy comparisons.

This is a controlled simulator, not an ETA calibration or fleet simulation.
Controllers see only next departures at their current stop and static costs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math

import numpy as np

from .adaptive import JourneyState, SharedSuffixPolicy
from .models import Route, TransitNetwork
from .routing import RoutingParameters, SearchBudgetExceeded, route_key
from .simulation import next_departure


@dataclass(frozen=True)
class WorldModel:
    phase_groups: dict[str, str] = field(default_factory=dict)
    delay_groups: dict[str, str] = field(default_factory=dict)
    phase_offsets: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Worlds:
    phases: dict[str, np.ndarray]
    delays: dict[str, np.ndarray]
    samples: int
    seed: int

    @classmethod
    def generate(cls, network, samples, seed, model=None):
        if not isinstance(samples, int) or samples < 1:
            raise ValueError("Positive integer sample count required")
        model = model or WorldModel()
        for mapping in (model.phase_groups, model.delay_groups, model.phase_offsets):
            if set(mapping) - network.services.keys():
                raise ValueError("World model references an unknown service")
        if any(not math.isfinite(x) for x in model.phase_offsets.values()):
            raise ValueError("Phase offsets must be finite")

        def draws(kind, group):
            digest = hashlib.sha256(f"{seed}:{kind}:{group}".encode()).digest()
            return np.random.default_rng(int.from_bytes(digest[:8], "big")).random(samples)

        phases, delays = {}, {}
        for sid, service in sorted(network.services.items()):
            phases[sid] = (draws("phase", model.phase_groups.get(sid, sid))
                           * service.headway_minutes + model.phase_offsets.get(sid, 0))
            delays[sid] = draws("delay", model.delay_groups.get(sid, sid)) * service.delay_max_minutes
            phases[sid].flags.writeable = False
            delays[sid].flags.writeable = False
        return cls(phases, delays, samples, seed)

    def fingerprint(self):
        digest = hashlib.sha256()
        for sid in sorted(self.phases):
            digest.update(sid.encode())
            digest.update(self.phases[sid].astype("<f8").tobytes())
            digest.update(self.delays[sid].astype("<f8").tobytes())
        return digest.hexdigest()


def audit_candidate_closure(policy, routes, max_expansions=100000):
    """Reject experiments where graph recombination gives adaptive extra paths."""
    expected = set(map(route_key, routes))
    actual = set()
    expansions = 0

    def visit(state, path):
        nonlocal expansions
        expansions += 1
        if expansions > max_expansions:
            raise SearchBudgetExceeded("Candidate-closure audit budget exceeded")
        if state.stop == policy.destination:
            actual.add(tuple(path))
            return
        for arc, following, continuing in policy.transitions(state):
            if continuing:
                new_path = [*path[:-1], (arc.service_id, path[-1][1], arc.end)]
            else:
                new_path = [*path, (arc.service_id, arc.start, arc.end)]
            visit(following, new_path)

    visit(policy.initial_state().structure, [])
    if actual != expected:
        raise ValueError(f"Unequal executable candidate sets: extra={len(actual - expected)}, "
                         f"missing={len(expected - actual)}")
    return {"enumerated_routes": len(expected), "executable_routes": len(actual),
            "expansions": expansions, "equal": True}


@dataclass
class Trial:
    durations: np.ndarray
    waits: np.ndarray
    buffers: np.ndarray
    rides: np.ndarray
    max_transfer_wait: np.ndarray
    transfers: np.ndarray
    missed: np.ndarray
    branches: dict[str, int]

    def summary(self, threshold=10.0):
        if not math.isfinite(threshold) or threshold < 0:
            raise ValueError("Invalid long-wait threshold")
        complete = np.isfinite(self.durations)
        ordered = np.sort(self.durations)
        quantile = lambda q: float(ordered[max(0, math.ceil(q * len(ordered)) - 1)])
        return {
            "samples": len(ordered), "completion_probability": float(complete.mean()),
            "mean_minutes": float(self.durations.mean()),
            "median_minutes": quantile(.5), "p90_minutes": quantile(.9),
            "p95_minutes": quantile(.95),
            "completed_mean_minutes": float(self.durations[complete].mean()) if complete.any() else None,
            "mean_recorded_wait_minutes": float(self.waits.mean()),
            "mean_recorded_transfer_buffer_minutes": float(self.buffers.mean()),
            "mean_recorded_transfers": float(self.transfers.mean()),
            "nominal_connection_miss_probability": float(self.missed.mean()),
            "long_wait_threshold_minutes": threshold,
            # For incomplete trips only an observed positive is decisive.
            "long_transfer_wait_probability": float((self.max_transfer_wait > threshold).mean()) if complete.all() else None,
            "long_transfer_wait_probability_lower": float((self.max_transfer_wait > threshold).mean()),
            "long_transfer_wait_probability_upper": float(((self.max_transfer_wait > threshold) | ~complete).mean()),
        }


def execute(policy: SharedSuffixPolicy, worlds: Worlds, *, controller="scored",
            departure_time=0.0) -> Trial:
    """Fixed, first-eligible and scored decisions share all transition accounting.

    A fixed route is a single-route policy with controller='first'. A continuation
    wins equal-time ties and pays no buffer, new delay, or transfer. Wait excludes
    the explicitly accounted transfer buffer. Incomplete durations stay infinite.
    """
    if controller not in {"first", "scored"} or not math.isfinite(departure_time):
        raise ValueError("Invalid controller or departure time")
    p, network = policy.parameters, policy.network
    duration = np.full(worlds.samples, math.inf)
    waits, buffers, rides, max_wait = (np.zeros(worlds.samples) for _ in range(4))
    transfers = np.zeros(worlds.samples, dtype=int)
    missed = np.zeros(worlds.samples, dtype=bool)
    branches = {}
    for sample in range(worlds.samples):
        state = policy.initial_state(departure_time)
        nominal = departure_time
        while state.structure.stop != policy.destination:
            observed, nominal_boards = {}, {}
            for arc, _, continuing in policy.transitions(state.structure):
                if continuing:
                    continue
                service = network.services[arc.service_id]
                offset = sum(service.ride_minutes[:service.stops.index(arc.start)])
                phase = worlds.phases[service.id][sample] + offset
                buffer = p.transfer_walk_minutes if state.structure.used else 0.0
                observed[service.id] = float(next_departure(state.now + buffer, phase, service.headway_minutes))
                nominal_boards[service.id] = float(next_departure(nominal + buffer, phase, service.headway_minutes))
            if controller == "scored":
                choice = policy.update(state, observed)
            else:
                choices = [policy.update(state, observed, allowed_arcs={(arc.service_id, arc.end)})
                           for arc, _, _ in policy.transitions(state.structure)]
                choice = min((c for c in choices if c is not None), default=None,
                             key=lambda c: (c.board_time, not c.continuing, c.arc.service_id, c.arc.end))
            if choice is None:
                break
            arc = choice.arc
            if choice.continuing:
                now = state.now + arc.ride_minutes
                nominal += arc.ride_minutes
                rides[sample] += arc.ride_minutes
            else:
                transfer = bool(state.structure.used)
                buffer = p.transfer_walk_minutes if transfer else 0.0
                wait = max(0.0, choice.board_time - state.now - buffer)
                waits[sample] += wait
                buffers[sample] += buffer
                if transfer:
                    max_wait[sample] = max(max_wait[sample], wait)
                    missed[sample] |= state.now + buffer > nominal_boards[arc.service_id] + 1e-9
                ride = arc.ride_minutes + worlds.delays[arc.service_id][sample]
                rides[sample] += ride
                now = choice.board_time + ride
                nominal = nominal_boards[arc.service_id] + arc.ride_minutes
                key = f"{arc.service_id}:{arc.start}"
                branches[key] = branches.get(key, 0) + 1
            state = JourneyState(choice.following, now, departure_time)
            transfers[sample] = max(0, len(state.structure.used) - 1)
            if now - departure_time > p.max_trip_minutes + 1e-9:
                break
        if state.structure.stop == policy.destination and state.now - departure_time <= p.max_trip_minutes + 1e-9:
            duration[sample] = state.now - departure_time
    return Trial(duration, waits, buffers, rides, max_wait, transfers, missed, branches)


def select_fixed(routes, network, parameters, worlds):
    """Select once on training worlds. Never optimize against held-out outcomes."""
    rows = []
    for route in routes:
        trial = execute(SharedSuffixPolicy(network, [route], parameters), worlds, controller="first")
        s = trial.summary()
        score = s["mean_minutes"] + parameters.transfer_penalty * s["mean_recorded_transfers"]
        rows.append({"route": route_key(route), "mean_plus_transfer_score": score,
                     "p95_minutes": s["p95_minutes"], "mean_minutes": s["mean_minutes"]})
    if not rows:
        raise ValueError("No fixed candidates")
    mean_i = min(range(len(rows)), key=lambda i: (rows[i]["mean_plus_transfer_score"], rows[i]["route"]))
    tail_i = min(range(len(rows)), key=lambda i: (rows[i]["p95_minutes"], rows[i]["mean_minutes"], rows[i]["route"]))
    return {"fixed_mean": routes[mean_i], "fixed_p95": routes[tail_i]}, rows


def paired_difference(a: Trial, b: Trial, *, bootstrap_samples=300, seed=811):
    """Within-world differences; Monte Carlo uncertainty, not real-world validity."""
    if len(a.durations) != len(b.durations) or bootstrap_samples < 1:
        raise ValueError("Paired trials need equal sizes and positive bootstrap count")
    if not (np.isfinite(a.durations).all() and np.isfinite(b.durations).all()):
        return {"mean_delta": None, "mean_ci95": None, "p95_delta": None, "p95_ci95": None,
                "reason": "Incomplete journeys: unconditional duration differences are not finite"}
    delta = a.durations - b.durations
    n = len(delta)
    mean = float(delta.mean())
    if n < 2:
        return {"mean_delta": mean, "mean_ci95": None, "p95_delta": float(delta[0]), "p95_ci95": None}
    half = 1.96 * float(delta.std(ddof=1)) / math.sqrt(n)
    rank = math.ceil(.95 * n) - 1
    p95 = lambda x: float(np.partition(x, rank)[rank])
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(bootstrap_samples):
        ids = rng.integers(0, n, n)
        draws.append(p95(a.durations[ids]) - p95(b.durations[ids]))
    return {"mean_delta": mean, "mean_ci95": [mean - half, mean + half],
            "p95_delta": p95(a.durations) - p95(b.durations),
            "p95_ci95": [float(x) for x in np.quantile(draws, [.025, .975])]}

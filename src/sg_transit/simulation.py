from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

import numpy as np

from .models import Route, Strategy, TransitNetwork, compile_policy, validate_route


@dataclass(frozen=True)
class SimulationSummary:
    samples: int
    mean_minutes: float
    median_minutes: float
    p90_minutes: float
    p95_minutes: float
    mean_wait_minutes: float
    failure_probability: float
    invalid_transfer_probability: float
    over_two_hours_probability: float
    transfers: float
    max_minutes: float
    over_trip_limit_probability: float
    fare_invalid_probability: float


@dataclass
class SimulationResult:
    summary: SimulationSummary
    durations: np.ndarray
    waits: np.ndarray
    missed: np.ndarray
    invalid: np.ndarray
    transfer_counts: np.ndarray
    branch_counts: dict[str, int]
    fare_invalid: np.ndarray


def _percentile(values, percentile):
    if len(values) == 0 or not 0 <= percentile <= 1:
        raise ValueError("Invalid quantile")
    return float(np.quantile(values, percentile))


def next_departure(ready, phase, headway):
    """Boarding at the exact departure time is allowed after transfer buffer."""
    return phase + np.ceil((ready - phase) / headway - 1e-12) * headway


def evaluate(strategy: Route | Strategy, network: TransitNetwork, samples=10000, seed=7, departure_time=0.0, parameters=None, phase_correlation=0.0) -> SimulationResult:
    from .routing import RoutingParameters
    p = parameters or RoutingParameters()
    if not isinstance(samples, int) or samples < 1 or not math.isfinite(departure_time) or not 0 <= phase_correlation <= 1:
        raise ValueError("Invalid sample count, departure time or correlation")
    if isinstance(strategy, Route):
        strategy = Strategy("fixed", (strategy,))
    for route in strategy.routes:
        validate_route(route, network)
    policy = compile_policy(strategy)
    common = np.random.default_rng(seed).random((samples, 2))
    phases, delays = {}, {}
    # Keys and sample indices are independent of route traversal and option ordering.
    for service_id, service in network.services.items():
        digest = hashlib.sha256(f"{seed}:{service_id}".encode()).digest()
        draws = np.random.default_rng(int.from_bytes(digest[:8], "big")).random((samples, 2))
        phase_draw = np.where(common[:, 1] < phase_correlation, common[:, 0], draws[:, 0])
        phases[service_id] = phase_draw * service.headway_minutes
        delays[service_id] = draws[:, 1] * service.delay_max_minutes
    durations = np.zeros(samples)
    waits = np.zeros(samples)
    missed = np.zeros(samples, dtype=bool)
    invalid = np.zeros(samples, dtype=bool)
    fare_invalid = np.zeros(samples, dtype=bool)
    transfer_counts = np.zeros(samples, dtype=int)
    first_board = np.full(samples, np.nan)
    last_board = np.full(samples, np.nan)
    branch_counts = {}

    def traverse(node, ids, actual, nominal, depth):
        if not node.options:
            durations[ids] = actual - departure_time
            transfer_counts[ids] = max(0, depth - 1)
            return
        boards, targets = [], []
        for leg, _ in node.options:
            service = network.services[leg.service_id]
            offset = sum(service.ride_minutes[:service.stops.index(leg.board_stop)])
            phase = phases[service.id][ids] + offset
            boards.append(next_departure(actual + leg.transfer_minutes, phase, service.headway_minutes))
            targets.append(next_departure(nominal + leg.transfer_minutes, phase, service.headway_minutes))
        # This uses only departures at this stop, never a downstream realized travel time.
        choice = np.argmin(np.stack(boards), axis=0)
        for index, (leg, child) in enumerate(node.options):
            mask = choice == index
            selected = ids[mask]
            if not selected.size:
                continue
            board, target = boards[index][mask], targets[index][mask]
            waits[selected] += np.maximum(0.0, board - actual[mask] - leg.transfer_minutes)
            if depth:
                missed[selected] |= actual[mask] + leg.transfer_minutes > target + 1e-9
                invalid[selected] |= board - actual[mask] > p.max_transfer_gap + 1e-9
                fare_invalid[selected] |= board - actual[mask] > p.max_transfer_gap + 1e-9
            else:
                first_board[selected] = board
            last_board[selected] = board
            key = f"{leg.service_id}:{leg.board_stop}>{leg.alight_stop}"
            branch_counts[key] = branch_counts.get(key, 0) + int(selected.size)
            arrive = board + leg.ride_minutes + delays[leg.service_id][selected]
            expected_arrive = target + leg.ride_minutes
            traverse(child, selected, arrive, expected_arrive, depth + 1)

    access = strategy.routes[0].walk_minutes
    start = np.full(samples, departure_time + access)
    traverse(policy, np.arange(samples), start, start.copy(), 0)
    # Fare continuity is evaluated over the complete realized journey, including
    # direct trips where first_board == last_board.
    fare_invalid |= (durations > p.max_trip_minutes + 1e-9) | (transfer_counts > p.max_transfers)
    summary = SimulationSummary(
        samples, float(durations.mean()), float(np.median(durations)),
        _percentile(durations, 0.90), _percentile(durations, 0.95), float(waits.mean()),
        float(missed.mean()), float(invalid.mean()), float((durations > 120.0 + 1e-9).mean()),
        float(transfer_counts.mean()), float(durations.max()),
        float((durations > p.max_trip_minutes + 1e-9).mean()), float(fare_invalid.mean()),
    )
    return SimulationResult(summary, durations, waits, missed, invalid, transfer_counts, branch_counts, fare_invalid)


def simulate_route(route, network, samples=1000, seed=7, **kwargs):
    return evaluate(route, network, samples, seed, **kwargs).summary

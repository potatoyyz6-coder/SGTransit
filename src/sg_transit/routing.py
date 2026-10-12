from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations

import networkx as nx

from .models import Leg, Route, Strategy, TransitNetwork, compile_policy


@dataclass(frozen=True)
class RoutingParameters:
    max_transfers: int = 5
    max_trip_minutes: float = 120.0
    max_transfer_gap: float = 45.0
    transfer_walk_minutes: float = 3.0
    reliability_weight_p90: float = 0.5
    reliability_weight_p95: float = 1.0
    transfer_penalty: float = 5.0
    invalid_transfer_penalty: float = 20.0
    strict_bounds: bool = True
    max_candidates: int = 300
    max_expansions: int = 100000

    def __post_init__(self):
        if not isinstance(self.max_transfers, int) or self.max_transfers < 0:
            raise ValueError("max_transfers must be a nonnegative integer")
        if self.max_candidates < 1 or self.max_expansions < 1:
            raise ValueError("Search budgets must be positive")
        for name in ("max_trip_minutes", "max_transfer_gap", "transfer_walk_minutes", "reliability_weight_p90", "reliability_weight_p95", "transfer_penalty", "invalid_transfer_penalty"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError(f"Invalid parameter: {name}")


class SearchBudgetExceeded(RuntimeError):
    """Do not silently label a truncated search optimal."""


def route_key(route: Route) -> tuple:
    return tuple((x.service_id, x.board_stop, x.alight_stop) for x in route.legs)


def enumerate_routes(network: TransitNetwork, origin: str, destination: str, parameters: RoutingParameters | None = None, *, stats: dict | None = None) -> list[Route]:
    p = parameters or RoutingParameters()
    if stats is not None:
        stats.update(expansions=0, candidates=0)
    if origin not in network.stops or destination not in network.stops:
        raise ValueError("Unknown endpoint; resolve stop names before routing")
    if origin == destination:
        if stats is not None:
            stats["candidates"] = 1
        return [Route(origin, destination)]
    graph = nx.DiGraph()
    graph.add_nodes_from(network.stops)
    adjacency = {stop: network.neighbors(stop) for stop in network.stops}
    for start, edges in adjacency.items():
        for end, _, ride in edges:
            if not graph.has_edge(start, end) or ride < graph[start][end]["weight"]:
                graph.add_edge(start, end, weight=ride)
    lower = nx.single_source_dijkstra_path_length(graph.reverse(copy=False), destination)
    routes, expansions = [], 0

    def visit(stop, legs, used, visited, elapsed):
        nonlocal expansions
        expansions += 1
        if stats is not None:
            stats["expansions"] = expansions
        if expansions > p.max_expansions:
            raise SearchBudgetExceeded("Expansion budget exceeded; reduce the network or raise max_expansions")
        if stop == destination:
            routes.append(Route(origin, destination, legs))
            if stats is not None:
                stats["candidates"] = len(routes)
            if len(routes) > p.max_candidates:
                raise SearchBudgetExceeded("Candidate budget exceeded; reduce the network or raise max_candidates")
            return
        if len(legs) >= p.max_transfers + 1:
            return
        for end, service, ride in adjacency[stop]:
            segment = service.stops[service.stops.index(stop) + 1:service.stops.index(end) + 1]
            if service.id in used or visited.intersection(segment):
                continue
            transfer = p.transfer_walk_minutes if legs else 0.0
            # Keep routes whose minimum travel time is feasible even when a
            # long headway can make some simulated journeys invalid. Those
            # tails are the reliability signal this project measures.
            minimum_bound = elapsed + transfer + ride + lower.get(end, math.inf)
            if minimum_bound > p.max_trip_minutes:
                continue
            leg = Leg(service.id, stop, end, ride, service.headway_minutes / 2, transfer)
            visit(end, [*legs, leg], used | {service.id}, visited | set(segment), elapsed + transfer + ride)

    visit(origin, [], set(), {origin}, 0.0)
    return sorted(routes, key=route_key)


def expected_time(route: Route, network: TransitNetwork) -> float:
    return route.total_minutes + sum(network.services[x.service_id].delay_max_minutes / 2 for x in route.legs)


def _baseline(routes, network, mode):
    if not routes:
        return None
    if mode == "transfers":
        key = lambda r: (r.transfers, expected_time(r, network), route_key(r))
    elif mode == "ride":
        key = lambda r: (r.ride_minutes, expected_time(r, network), route_key(r))
    else:
        key = lambda r: (expected_time(r, network), r.transfers, route_key(r))
    return min(routes, key=key)


def route_shortest_time(network, origin, destination, parameters=None):
    return _baseline(enumerate_routes(network, origin, destination, parameters), network, "time")


def route_min_transfers(network, origin, destination, parameters=None):
    return _baseline(enumerate_routes(network, origin, destination, parameters), network, "transfers")


def route_min_ride_time(network, origin, destination, parameters=None):
    return _baseline(enumerate_routes(network, origin, destination, parameters), network, "ride")


def reliability_score(summary, parameters=None):
    p = parameters or RoutingParameters()
    return summary.mean_minutes + p.reliability_weight_p90 * summary.p90_minutes + p.reliability_weight_p95 * summary.p95_minutes + p.transfer_penalty * summary.transfers + p.invalid_transfer_penalty * summary.invalid_transfer_probability


_reliability_score = reliability_score


@dataclass
class PlanningResult:
    candidates: list[Route]
    baselines: dict[str, Route]
    recommended_strategy: Strategy | None
    candidate_strategies: list[Strategy]


def plan(network, origin, destination, parameters=None, samples=512, seed=7, departure_time=0.0):
    from .simulation import evaluate
    p = parameters or RoutingParameters()
    routes = enumerate_routes(network, origin, destination, p)
    if not routes:
        return PlanningResult([], {}, None, [])
    baselines = {"shortest_expected_time": _baseline(routes, network, "time"), "minimum_transfers": _baseline(routes, network, "transfers"), "minimum_ride_time": _baseline(routes, network, "ride")}
    # Route enumeration is exact within bounds; policy-set search is a documented heuristic.
    strategies = [Strategy(f"fixed_{i}", (r,)) for i, r in enumerate(routes)]
    singles = [(reliability_score(evaluate(s, network, samples, seed, departure_time, p).summary, p), i) for i, s in enumerate(strategies)]
    shortlist = sorted(singles)[:12]
    pool = [routes[i] for _, i in shortlist]
    for i, pair in enumerate(combinations(pool, 2)):
        candidate = Strategy(f"pair_{i}", tuple(pair))
        try:
            compile_policy(candidate)
        except ValueError:
            continue
        strategies.append(candidate)
    if len(pool) > 2:
        candidate = Strategy("first_arrival_pool", tuple(pool))
        try:
            compile_policy(candidate)
        except ValueError:
            pass
        else:
            strategies.append(candidate)
    scores = [reliability_score(evaluate(s, network, samples, seed, departure_time, p).summary, p) for s in strategies]
    chosen = strategies[min(range(len(scores)), key=lambda i: (scores[i], i))]
    return PlanningResult(routes, baselines, chosen, strategies)


def route_reliable(network, origin, destination, parameters=None, samples=1000, seed=7):
    """Legacy fixed-route ranking; use plan() for an executable branching policy."""
    from .simulation import simulate_route
    routes = enumerate_routes(network, origin, destination, parameters)
    return min(routes, key=lambda r: reliability_score(simulate_route(r, network, samples, seed), parameters)) if routes else None

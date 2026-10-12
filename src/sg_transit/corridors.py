"""Destination-oriented candidate discovery; no timetable or optimality claim."""
from __future__ import annotations

from dataclasses import dataclass, field
import heapq
from itertools import count
import math

import networkx as nx

from .models import Leg, Route, TransitNetwork, validate_route
from .routing import RoutingParameters, route_key


@dataclass(frozen=True)
class CorridorParameters:
    max_hubs: int = 3
    ordinary_candidates: int = 6
    prefixes_per_hub: int = 4
    bypass_candidates: int = 1

    def __post_init__(self):
        for name in ("max_hubs", "ordinary_candidates", "prefixes_per_hub", "bypass_candidates"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < (0 if name == "max_hubs" else 1):
                raise ValueError(f"Invalid {name}")


@dataclass(frozen=True)
class Hub:
    stop: str
    tails: tuple[Leg, ...]
    common_segments: tuple[tuple[str, str], ...]


class DestinationIndex:
    """Reverse queries inspect incoming *directed* edges, never opposite buses."""

    def __init__(self, network: TransitNetwork, destination: str):
        if destination not in network.stops:
            raise ValueError("Unknown destination")
        self.network = network
        self.destination = destination
        self.adjacency = {stop: network.neighbors(stop) for stop in network.stops}
        self.graph = nx.DiGraph()
        self.graph.add_nodes_from(network.stops)
        for start, edges in self.adjacency.items():
            for end, _, ride in edges:
                if not self.graph.has_edge(start, end) or ride < self.graph[start][end]["weight"]:
                    self.graph.add_edge(start, end, weight=ride)
        self._distances: dict[str, dict[str, float]] = {}
        self.lower = self.distances_to(destination)
        self.tails: dict[str, tuple[Leg, ...]] = {}
        for stop, edges in self.adjacency.items():
            self.tails[stop] = tuple(sorted(
                (Leg(service.id, stop, end, ride, service.headway_minutes / 2)
                 for end, service, ride in edges if end == destination),
                key=lambda leg: leg.service_id,
            ))
        self.hubs = tuple(
            Hub(stop, tails, self._common_segments(tails))
            for stop, tails in sorted(self.tails.items()) if len(tails) >= 2
        )

    def distances_to(self, stop: str) -> dict[str, float]:
        if stop not in self._distances:
            self._distances[stop] = dict(nx.single_source_dijkstra_path_length(
                self.graph.reverse(copy=False), stop, weight="weight",
            ))
        return self._distances[stop]

    def _common_segments(self, tails):
        counts: dict[tuple[str, str], int] = {}
        for tail in tails:
            service = self.network.services[tail.service_id]
            segment = service.stops[service.stops.index(tail.board_stop):service.stops.index(tail.alight_stop) + 1]
            for pair in zip(segment, segment[1:]):
                counts[pair] = counts.get(pair, 0) + 1
        return tuple(sorted(pair for pair, amount in counts.items() if amount >= 2))


@dataclass
class CandidateSearch:
    routes: list[Route]
    selected_hubs: tuple[Hub, ...]
    expansions: int = 0
    ordinary_route_keys: list[tuple] = field(default_factory=list)
    bypass_route_keys: list[tuple] = field(default_factory=list)
    truncated: bool = False
    truncation_reasons: list[str] = field(default_factory=list)


def discover_candidates(index: DestinationIndex, origin: str,
                        parameters: RoutingParameters | None = None,
                        corridors: CorridorParameters | None = None) -> CandidateSearch:
    """Reserve ordinary routes, then search prefixes to a few destination hubs.

    Bounds limit work, not quality loss. The returned flags must accompany results.
    """
    p, c = parameters or RoutingParameters(), corridors or CorridorParameters()
    network, destination = index.network, index.destination
    if origin not in network.stops:
        raise ValueError("Unknown origin")
    if origin == destination:
        return CandidateSearch([Route(origin, destination)], ())
    reachable = nx.single_source_dijkstra_path_length(index.graph, origin, weight="weight")
    ranked = sorted(
        (hub for hub in index.hubs if hub.stop in reachable),
        key=lambda hub: (
            reachable[hub.stop] + min(
                tail.ride_minutes + tail.wait_minutes
                + network.services[tail.service_id].delay_max_minutes / 2
                for tail in hub.tails),
            -len(hub.tails), hub.stop,
        ),
    )
    # Adjacent stops offering the identical service set are one corridor proposal.
    selected, signatures = [], set()
    for hub in ranked:
        signature = tuple(tail.service_id for tail in hub.tails)
        if signature not in signatures and len(selected) < c.max_hubs:
            selected.append(hub)
            signatures.add(signature)
    result = CandidateSearch([], tuple(selected))
    seen: set[tuple] = set()

    def truncated(reason):
        result.truncated = True
        if reason not in result.truncation_reasons:
            result.truncation_reasons.append(reason)

    if len(selected) < len(ranked):
        truncated("hub_or_corridor_limit")

    def retain(legs):
        route = Route(origin, destination, list(legs))
        try:
            validate_route(route, network)
        except ValueError:
            return
        if route.transfers > p.max_transfers or (
            route.ride_minutes + sum(leg.transfer_minutes for leg in legs) > p.max_trip_minutes
        ):
            return
        key = route_key(route)
        if key in seen:
            return
        if len(result.routes) >= p.max_candidates:
            truncated("candidate_limit")
            return
        seen.add(key)
        result.routes.append(route)

    def search(target, limit, budget, tails=(), avoid=frozenset()):
        serial = count()
        lower = index.distances_to(target)
        queue = [(lower.get(origin, math.inf), next(serial), origin, (), frozenset(),
                  frozenset({origin}), 0.0, 0.0)]
        popped, completed = 0, 0
        while queue and popped < budget:
            _, _, stop, legs, used, visited, minimum, mean = heapq.heappop(queue)
            popped += 1
            result.expansions += 1
            if stop == target:
                if tails:
                    for tail in tails:
                        transfer = p.transfer_walk_minutes if legs else 0.0
                        retain((*legs, Leg(tail.service_id, stop, destination,
                                           tail.ride_minutes, tail.wait_minutes, transfer)))
                else:
                    retain(legs)
                completed += 1
                if completed >= limit:
                    if queue:
                        truncated("prefix_or_ordinary_limit")
                    break
                continue
            if len(legs) >= p.max_transfers + 1 - bool(tails):
                continue
            for end, service, ride in index.adjacency[stop]:
                segment = service.stops[service.stops.index(stop) + 1:service.stops.index(end) + 1]
                if service.id in used or (visited | avoid).intersection(segment):
                    continue
                transfer = p.transfer_walk_minutes if legs else 0.0
                next_min = minimum + transfer + ride
                if next_min + lower.get(end, math.inf) > p.max_trip_minutes:
                    continue
                next_mean = mean + transfer + ride + service.headway_minutes / 2 + service.delay_max_minutes / 2
                leg = Leg(service.id, stop, end, ride, service.headway_minutes / 2, transfer)
                heapq.heappush(queue, (
                    next_mean + lower.get(end, math.inf), next(serial), end,
                    (*legs, leg), used | {service.id}, visited | set(segment),
                    next_min, next_mean,
                ))
        if queue and popped >= budget:
            truncated("expansion_limit")

    # The ordinary pass is independent of hub membership and cannot be displaced.
    ordinary_budget = max(1, p.max_expansions // (2 if selected else 1))
    avoid = frozenset(hub.stop for hub in selected) - {origin, destination}
    reserve = min(c.bypass_candidates, max(0, p.max_candidates - 1)) if avoid else 0
    first_budget = max(1, ordinary_budget // 2) if reserve else ordinary_budget
    search(destination, min(c.ordinary_candidates, p.max_candidates - reserve), first_budget)
    result.ordinary_route_keys = [route_key(route) for route in result.routes]
    if reserve:
        # Keep a corridor-independent alternative even if all fast ordinary
        # candidates happen to pass through the selected hubs.
        search(destination, reserve, max(0, ordinary_budget - first_budget), avoid=avoid)
        for route in result.routes:
            path_stops = set()
            for leg in route.legs:
                service = network.services[leg.service_id]
                path_stops.update(service.stops[service.stops.index(leg.board_stop):service.stops.index(leg.alight_stop) + 1])
            if not avoid.intersection(path_stops):
                result.bypass_route_keys.append(route_key(route))
    elif avoid:
        truncated("no_capacity_for_bypass")
    for i, hub in enumerate(selected):
        remaining = p.max_expansions - result.expansions
        if remaining <= 0:
            truncated("expansion_limit")
            break
        search(hub.stop, c.prefixes_per_hub, max(1, remaining // (len(selected) - i)), hub.tails)
    result.routes.sort(key=route_key)
    return result

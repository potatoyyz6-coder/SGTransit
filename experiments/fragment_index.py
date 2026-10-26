"""Experimental reusable indexes, deliberately separate from production routing.

Indexes own a snapshot of immutable stop/service records. Rebuild after changing
topology or modeled timing. No ETA, destination value, or query result is cached.
Both searches enumerate the same bounded, loop-free, service-distinct routes as
enumerate_routes; fragment continuation is merged into the current ride leg.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math

import networkx as nx

from sg_transit.models import Leg, Route, TransitNetwork
from sg_transit.routing import RoutingParameters, SearchBudgetExceeded, route_key


def network_record(network):
    return {'stops': [asdict(network.stops[k]) for k in sorted(network.stops)],
            'services': [asdict(network.services[k]) for k in sorted(network.services)]}


def network_hash(network):
    return hashlib.sha256(json.dumps(network_record(network), sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Connection:
    service_id: str
    start_index: int
    end_index: int
    end: str
    traversed: tuple[str, ...]
    ride: float


class _ReusableIndex:
    def __init__(self, network, *, fragments):
        self._network = TransitNetwork(network.stops.values(), network.services.values())
        self.snapshot_hash = network_hash(self._network)
        self._fragments = fragments
        graph = nx.DiGraph()
        graph.add_nodes_from(self._network.stops)
        adjacency = {stop: [] for stop in self._network.stops}
        for service in self._network.services.values():
            for i, start in enumerate(service.stops[:-1]):
                ends = (i + 1,) if fragments else range(i + 1, len(service.stops))
                for j in ends:
                    end = service.stops[j]
                    ride = sum(service.ride_minutes[i:j])
                    adjacency[start].append(Connection(service.id, i, j, end,
                                                        service.stops[i + 1:j + 1], ride))
                    if not graph.has_edge(start, end) or ride < graph[start][end]['weight']:
                        graph.add_edge(start, end, weight=ride)
        self._adjacency = {stop: tuple(edges) for stop, edges in adjacency.items()}
        self._reverse = nx.freeze(graph.reverse(copy=False))
        self.connection_count = sum(len(edges) for edges in self._adjacency.values())

    def query(self, origin, destination, parameters=None, *, stats=None):
        p = parameters or RoutingParameters()
        if stats is not None:
            stats.update(expansions=0, candidates=0)
        if origin not in self._network.stops or destination not in self._network.stops:
            raise ValueError('Unknown endpoint; resolve stop names before routing')
        if origin == destination:
            if stats is not None:
                stats['candidates'] = 1
            return [Route(origin, destination)]
        # This ignores waits and service compatibility, so it is an optimistic
        # bound, not a promised arrival time. Never prune by compass direction.
        lower = nx.single_source_dijkstra_path_length(self._reverse, destination)
        routes, expansions = [], 0

        def visit(stop, legs, used, visited, elapsed):
            nonlocal expansions
            expansions += 1
            if stats is not None:
                stats['expansions'] = expansions
            if expansions > p.max_expansions:
                raise SearchBudgetExceeded('Expansion budget exceeded in experimental index')
            if stop == destination:
                routes.append(Route(origin, destination, legs))
                if stats is not None:
                    stats['candidates'] = len(routes)
                if len(routes) > p.max_candidates:
                    raise SearchBudgetExceeded('Candidate budget exceeded in experimental index')
                return
            for edge in self._adjacency[stop]:
                continuing = bool(self._fragments and legs and legs[-1].service_id == edge.service_id)
                if not continuing and (edge.service_id in used or len(legs) >= p.max_transfers + 1):
                    continue
                if visited.intersection(edge.traversed):
                    continue
                service = self._network.services[edge.service_id]
                if continuing:
                    last = legs[-1]
                    # Use the original segment sum, like the baseline, rather
                    # than accumulating a differently rounded sequence of rides.
                    i = service.stops.index(last.board_stop)
                    extended = Leg(service.id, last.board_stop, edge.end,
                                   sum(service.ride_minutes[i:edge.end_index]),
                                   last.wait_minutes, last.transfer_minutes)
                    following = [*legs[:-1], extended]
                    duration = 0.0
                    for leg in following:
                        duration = duration + leg.transfer_minutes + leg.ride_minutes
                else:
                    buffer = p.transfer_walk_minutes if legs else 0.0
                    following = [*legs, Leg(service.id, stop, edge.end, edge.ride,
                                            service.headway_minutes / 2, buffer)]
                    duration = elapsed + buffer + edge.ride
                bound = duration + lower.get(edge.end, math.inf)
                # Different edge groupings can round the optimistic bound up.
                # Only pruning gets a tolerance; completed paths get none.
                over = (duration > p.max_trip_minutes if edge.end == destination else
                        bound > p.max_trip_minutes and
                        not math.isclose(bound, p.max_trip_minutes, rel_tol=1e-12, abs_tol=1e-12))
                if over:
                    continue
                visit(edge.end, following, used | {service.id}, visited | set(edge.traversed), duration)

        visit(origin, [], set(), {origin}, 0.0)
        return sorted(routes, key=route_key)


class CachedLegIndex(_ReusableIndex):
    """Caching control: retain every downstream ride, not just adjacent stops."""

    def __init__(self, network):
        super().__init__(network, fragments=False)


class FragmentIndex(_ReusableIndex):
    """One labeled connection per adjacent stop pair per directed service."""

    def __init__(self, network):
        super().__init__(network, fragments=True)

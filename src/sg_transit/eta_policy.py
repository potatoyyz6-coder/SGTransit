"""Adapter to the existing stationary shared-suffix policy, not a new optimizer."""
from __future__ import annotations

from .adaptive import JourneyState, SharedSuffixPolicy, StructuralState
from .eta_replay import Ride
from .models import Leg, Route, validate_route


def expand_paths(paths, network):
    """Expose recorded intermediate stops so same-vehicle continuation is explicit."""
    expanded, routes = [], []
    for path in paths:
        actions, legs = [], []
        for action in path:
            if not isinstance(action, Ride):
                raise ValueError("Shared-suffix adapter currently requires bus-only paths")
            service = network.services[action.service]
            if not service.can_ride(action.start, action.end):
                raise ValueError("Path is not forward in the supplied service network")
            i, j = service.stops.index(action.start), service.stops.index(action.end)
            actions.extend(Ride(action.service, a, b) for a, b in zip(service.stops[i:j], service.stops[i + 1:j + 1]))
            legs.append(Leg(action.service, action.start, action.end,
                            service.ride_time(action.start, action.end)))
        route = Route(path[0].start, path[-1].end, legs)
        validate_route(route, network)
        expanded.append(actions)
        routes.append(route)
    return expanded, routes


class SuffixReplaySelector:
    def __init__(self, network, routes, parameters):
        self.policy = SharedSuffixPolicy(network, routes, parameters)

    def choose(self, candidates, *, stop, now, departure, onboard, used, visited, alighted, limits):
        p = self.policy.parameters
        if (p.max_transfers != limits.max_transfers or p.max_trip_minutes * 60 != limits.max_trip_seconds
                or p.max_transfer_gap * 60 != limits.max_transfer_seconds
                or p.transfer_walk_minutes * 60 != limits.transfer_seconds):
            raise ValueError("Replay constraints and policy constraints must agree")
        minutes = lambda t: (t - departure).total_seconds() / 60
        state = JourneyState(StructuralState(stop, onboard, used, visited), minutes(now), 0,
                             minutes(alighted) if alighted is not None else None)
        departures = {}
        for candidate in candidates:
            board, service = candidate[:2]
            if not candidate[6]:
                departures[service] = min(departures.get(service, float("inf")), minutes(board))
        allowed = {(c[1], c[2]) for c in candidates}
        decision = self.policy.update(state, departures, event="eta_change", allowed_arcs=allowed)
        detail = {"at": now.isoformat(), "stop": stop,
                  "policy": "SharedSuffixPolicy.update_stationary_expected_score",
                  "departures_minutes_from_query": departures, "allowed_arcs": sorted(allowed)}
        if decision is None:
            return None, {**detail, "selected": None}
        matching = [c for c in candidates if c[1] == decision.arc.service_id and c[2] == decision.arc.end
                    and abs(minutes(c[0]) - decision.board_time) < 1e-7]
        if not matching:
            raise ValueError("Policy selected an action absent from the observation candidates")
        chosen = min(matching, key=lambda c: (c[4] is not None, c[0]))
        return chosen, {**detail, "selected": [chosen[1], chosen[2]],
                        "stationary_expected_remaining_score": decision.estimated_remaining_score,
                        "continuing": decision.continuing}

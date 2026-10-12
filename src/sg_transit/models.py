from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
import math


@dataclass(frozen=True)
class Stop:
    id: str
    name: str
    x: float = 0.0
    y: float = 0.0


@dataclass(frozen=True)
class TransitService:
    id: str
    stops: tuple[str, ...]
    ride_minutes: tuple[float, ...]
    headway_minutes: float
    delay_max_minutes: float = 0.0

    def __post_init__(self) -> None:
        if len(self.stops) < 2 or len(self.ride_minutes) != len(self.stops) - 1:
            raise ValueError("A service needs N stops and N-1 ride times")
        if self.headway_minutes <= 0 or any(t <= 0 for t in self.ride_minutes):
            raise ValueError("Headway and ride times must be positive")
        if any(not math.isfinite(x) for x in (*self.ride_minutes, self.headway_minutes, self.delay_max_minutes)) or self.delay_max_minutes < 0:
            raise ValueError("Times must be finite and delay nonnegative")
        if len(set(self.stops)) != len(self.stops):
            raise ValueError("Split circular services into non-repeating patterns")

    def can_ride(self, start: str, end: str) -> bool:
        try:
            return self.stops.index(start) < self.stops.index(end)
        except ValueError:
            return False

    def ride_time(self, start: str, end: str) -> float:
        i, j = self.stops.index(start), self.stops.index(end)
        if i >= j:
            raise ValueError(f"{self.id} cannot travel from {start} to {end}")
        return sum(self.ride_minutes[i:j])


@dataclass(frozen=True)
class Leg:
    service_id: str
    board_stop: str
    alight_stop: str
    ride_minutes: float
    wait_minutes: float = 0.0
    transfer_minutes: float = 0.0


@dataclass
class Route:
    origin: str
    destination: str
    legs: list[Leg] = field(default_factory=list)
    walk_minutes: float = 0.0

    @property
    def transfers(self) -> int:
        return max(0, len(self.legs) - 1)

    @property
    def ride_minutes(self) -> float:
        return sum(leg.ride_minutes for leg in self.legs)

    @property
    def scheduled_wait_minutes(self) -> float:
        return sum(leg.wait_minutes for leg in self.legs)

    @property
    def total_minutes(self) -> float:
        return self.ride_minutes + self.scheduled_wait_minutes + self.walk_minutes + sum(leg.transfer_minutes for leg in self.legs)

    @property
    def services(self) -> tuple[str, ...]:
        return tuple(leg.service_id for leg in self.legs)


class TransitNetwork:
    def __init__(self, stops: Iterable[Stop], services: Iterable[TransitService]):
        stops, services = list(stops), list(services)
        self.stops = {stop.id: stop for stop in stops}
        self.services = {service.id: service for service in services}
        if len(self.stops) != len(stops) or len(self.services) != len(services):
            raise ValueError("Duplicate stop or service IDs")
        if any(stop not in self.stops for service in services for stop in service.stops):
            raise ValueError("Service references an unknown stop")

    def neighbors(self, stop_id: str) -> list[tuple[str, TransitService, float]]:
        result = []
        for service in self.services.values():
            if stop_id not in service.stops:
                continue
            i = service.stops.index(stop_id)
            for j in range(i + 1, len(service.stops)):
                result.append((service.stops[j], service, service.ride_time(stop_id, service.stops[j])))
        return result


@dataclass(frozen=True)
class Strategy:
    name: str
    routes: tuple[Route, ...]


@dataclass(frozen=True)
class PolicyNode:
    options: tuple[tuple[Leg, "PolicyNode"], ...] = ()


def compile_policy(strategy: Strategy) -> PolicyNode:
    """Merge common prefixes; choose an alighting stop before observing any bus."""
    if not strategy.routes:
        raise ValueError("A strategy needs at least one route")
    endpoints = {(r.origin, r.destination, r.walk_minutes) for r in strategy.routes}
    if len(endpoints) != 1:
        raise ValueError("Strategy routes must have identical endpoints and access walk")

    def build(paths: list[list[Leg]]) -> PolicyNode:
        if any(not path for path in paths):
            if not all(not path for path in paths):
                raise ValueError("A policy cannot both terminate and continue")
            return PolicyNode()
        grouped: dict[Leg, list[list[Leg]]] = {}
        for path in paths:
            grouped.setdefault(path[0], []).append(path[1:])
        variants_by_service: dict[str, set[tuple[str, str]]] = {}
        for leg in grouped:
            variants_by_service.setdefault(leg.service_id, set()).add((leg.board_stop, leg.alight_stop))
        conflicting = [service_id for service_id, variants in variants_by_service.items() if len(variants) > 1]
        if conflicting:
            raise ValueError(
                "A policy cannot choose different alighting stops for the same service at one decision node: "
                + ", ".join(sorted(conflicting))
            )
        chosen: dict[str, Leg] = {}
        for leg in grouped:
            residual = lambda item: item.ride_minutes + min(sum(x.ride_minutes + x.wait_minutes + x.transfer_minutes for x in tail) for tail in grouped[item])
            previous = chosen.get(leg.service_id)
            if previous is None or (residual(leg), leg.alight_stop) < (residual(previous), previous.alight_stop):
                chosen[leg.service_id] = leg
        return PolicyNode(tuple((leg, build(grouped[leg])) for leg in sorted(chosen.values(), key=lambda x: (x.service_id, x.alight_stop))))

    return build([r.legs for r in strategy.routes])


def validate_route(route: Route, network: TransitNetwork) -> None:
    if route.origin not in network.stops or route.destination not in network.stops:
        raise ValueError("Unknown route endpoint")
    visited, used, current = {route.origin}, set(), route.origin
    if not math.isfinite(route.walk_minutes) or route.walk_minutes < 0:
        raise ValueError("Invalid access walk")
    for leg in route.legs:
        service = network.services.get(leg.service_id)
        if service is None or current != leg.board_stop or not service.can_ride(leg.board_stop, leg.alight_stop):
            raise ValueError("Disconnected or invalid route leg")
        if service.id in used or not math.isclose(leg.ride_minutes, service.ride_time(leg.board_stop, leg.alight_stop)):
            raise ValueError("Repeated service or inconsistent ride time")
        if any(not math.isfinite(x) or x < 0 for x in (leg.wait_minutes, leg.transfer_minutes)):
            raise ValueError("Invalid wait or transfer time")
        segment = service.stops[service.stops.index(leg.board_stop) + 1:service.stops.index(leg.alight_stop) + 1]
        if visited.intersection(segment):
            raise ValueError("Route revisits a stop")
        visited.update(segment)
        used.add(service.id)
        current = leg.alight_stop
    if current != route.destination:
        raise ValueError("Route does not reach destination")

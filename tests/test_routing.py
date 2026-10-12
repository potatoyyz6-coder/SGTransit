from examples.demo import build_demo_network
from sg_transit.routing import RoutingParameters, route_min_transfers, route_shortest_time


def test_route_is_found_and_has_no_repeated_service():
    route = route_shortest_time(build_demo_network(), "S1", "S8")
    assert route is not None
    assert route.transfers <= 5
    assert len(route.services) == len(set(route.services))


def test_same_origin_is_not_a_transit_route():
    assert route_shortest_time(build_demo_network(), "S1", "S1") is not None


def test_unreachable_destination_returns_none():
    assert route_shortest_time(build_demo_network(), "S8", "S1") is None


def test_transfer_limit_is_enforced():
    params = RoutingParameters(max_transfers=0)
    route = route_min_transfers(build_demo_network(), "S1", "S8", params)
    assert route is None


def test_trip_time_limit_is_enforced():
    params = RoutingParameters(max_trip_minutes=10)
    assert route_shortest_time(build_demo_network(), "S1", "S8", params) is None

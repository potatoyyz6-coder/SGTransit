from examples.demo import build_demo_network
from sg_transit.routing import route_shortest_time
from sg_transit.simulation import simulate_route


def test_simulation_is_reproducible():
    network = build_demo_network()
    route = route_shortest_time(network, "S1", "S8")
    first = simulate_route(route, network, 500, seed=42)
    second = simulate_route(route, network, 500, seed=42)
    assert first == second


def test_simulation_has_variability():
    network = build_demo_network()
    route = route_shortest_time(network, "S1", "S8")
    summary = simulate_route(route, network, 500, seed=42)
    assert summary.p95_minutes >= summary.mean_minutes
    assert summary.mean_wait_minutes > 0

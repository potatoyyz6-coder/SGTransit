import numpy as np
import pytest

from sg_transit.models import Leg, Route, Stop, Strategy, TransitNetwork, TransitService, compile_policy, validate_route
from sg_transit.routing import RoutingParameters, SearchBudgetExceeded, enumerate_routes, plan, route_min_transfers, route_shortest_time
from sg_transit.simulation import _percentile, evaluate, next_departure


def network(services):
    ids = sorted({stop for s in services for stop in s.stops})
    return TransitNetwork([Stop(s, s) for s in ids], services)


def test_equal_cost_candidates():
    n = network([TransitService(s, ("A", "B"), (10,), 12) for s in ("1", "2")])
    assert len(enumerate_routes(n, "A", "B")) == 2
    assert route_shortest_time(n, "A", "B").total_minutes == 16


def test_unknown_endpoints_and_zero_trip():
    n = network([TransitService("1", ("A", "B"), (10,), 12)])
    with pytest.raises(ValueError):
        plan(n, "missing", "missing")
    r = route_shortest_time(n, "A", "A")
    result = evaluate(r, n, samples=10)
    assert result.summary.mean_minutes == 0
    assert result.summary.fare_invalid_probability == 0


def test_first_arrival_policy_beats_fixed_on_independent_services():
    n = network([TransitService(s, ("A", "B"), (10,), 20) for s in ("1", "2")])
    routes = enumerate_routes(n, "A", "B")
    fixed = evaluate(routes[0], n, samples=10000, seed=123)
    combined = evaluate(Strategy("first", tuple(routes)), n, samples=10000, seed=123)
    assert combined.summary.p95_minutes < fixed.summary.p95_minutes - 2
    assert len(combined.branch_counts) == 2
    assert np.all(combined.durations <= fixed.durations + 1e-9)
    decision = plan(n, "A", "B", samples=256)
    assert len(decision.recommended_strategy.routes) == 2


def test_correlated_services_remove_waiting_advantage():
    n = network([TransitService(s, ("A", "B"), (10,), 20) for s in ("1", "2")])
    routes = enumerate_routes(n, "A", "B")
    fixed = evaluate(routes[0], n, samples=1000, phase_correlation=1)
    combined = evaluate(Strategy("first", tuple(routes)), n, samples=1000, phase_correlation=1)
    np.testing.assert_allclose(combined.durations, fixed.durations)


def test_policy_does_not_choose_by_future_realized_ride_delay():
    n = network([TransitService(s, ("A", "B"), (10,), 20, d) for s, d in (("1", 40), ("2", 0))])
    routes = enumerate_routes(n, "A", "B")
    combined = evaluate(Strategy("first", tuple(routes)), n, samples=1000, phase_correlation=1)
    # Equal departures resolve to service 1, despite its inferior realized delay.
    assert combined.branch_counts == {"1:A>B": 1000}


def test_shared_prefix_alternatives_and_constraints():
    n = network([TransitService("feeder", ("A", "X"), (5,), 8), *[TransitService(s, ("X", "B"), (10,), 20) for s in ("1", "2")]])
    routes = enumerate_routes(n, "A", "B")
    r = evaluate(Strategy("branch", tuple(routes)), n, samples=1000)
    assert r.branch_counts["feeder:A>X"] == 1000
    assert sum(v for k, v in r.branch_counts.items() if k != "feeder:A>X") == 1000
    assert r.summary.transfers == 1
    assert r.summary.over_trip_limit_probability == 0
    assert r.summary.invalid_transfer_probability == 0


def test_policy_rejects_same_service_with_different_alighting_stops():
    n = network([
        TransitService("S", ("A", "B", "C"), (1, 1), 5),
        TransitService("B", ("B", "D"), (1,), 5),
        TransitService("C", ("C", "D"), (1,), 5),
    ])
    routes = enumerate_routes(n, "A", "D")
    assert {r.services for r in routes} == {("S", "B"), ("S", "C")}
    with pytest.raises(ValueError, match="different alighting"):
        compile_policy(Strategy("conflicting", tuple(routes)))


def test_delay_causes_missed_target_not_uniform_wait_alone():
    services = [TransitService("1", ("A", "X"), (5,), 8, 20), TransitService("2", ("X", "B"), (5,), 8)]
    n = network(services)
    route = enumerate_routes(n, "A", "B")[0]
    assert evaluate(route, n, 10000).summary.failure_probability > 0.5
    no_delay = network([TransitService(s.id, s.stops, s.ride_minutes, s.headway_minutes) for s in services])
    assert evaluate(route, no_delay, 1000).summary.failure_probability == 0


def test_invalid_probability_counts_journeys_not_events():
    services = [TransitService(str(i), (str(i), str(i+1)), (1,), 100) for i in range(3)]
    n = network(services)
    route = Route("0", "3", [Leg(s.id, s.stops[0], s.stops[1], 1) for s in services])
    summary = evaluate(route, n, 10000).summary
    assert 0 < summary.invalid_transfer_probability <= 1
    assert summary.over_two_hours_probability > 0
    # A long-headway route is retained so its invalid-tail probability can be
    # measured instead of being removed during candidate enumeration.
    assert route_shortest_time(n, "0", "3") is not None


def test_risky_long_headway_route_is_kept_for_simulation():
    n = network([TransitService("slow", ("A", "B"), (10,), 50)])
    assert route_shortest_time(n, "A", "B") is not None


def test_fare_invalid_uses_complete_duration_and_configured_limits():
    n = network([TransitService("slow", ("A", "B"), (130,), 5)])
    route = Route("A", "B", [Leg("slow", "A", "B", 130)])
    params = RoutingParameters(max_trip_minutes=120)
    result = evaluate(route, n, samples=100, seed=3, parameters=params)
    assert result.summary.over_trip_limit_probability == 1
    assert result.summary.fare_invalid_probability == 1


def test_transfer_window_uses_configured_parameter():
    services = [
        TransitService("A", ("A", "X"), (1,), 2),
        TransitService("B", ("X", "B"), (1,), 20),
    ]
    n = network(services)
    route = enumerate_routes(n, "A", "B")[0]
    params = RoutingParameters(max_transfer_gap=5)
    result = evaluate(route, n, samples=2000, seed=12, parameters=params)
    assert result.summary.invalid_transfer_probability > 0
    assert result.summary.fare_invalid_probability > 0


def test_boundary_boarding():
    np.testing.assert_allclose(next_departure(np.array([12, 12.01]), 2, 10), [12, 22])
    assert _percentile([0, 10], 0.95) == pytest.approx(9.5)


def test_minimum_transfers_ties_use_full_duration():
    n = network([TransitService("slow", ("A", "X"), (40,), 2), TransitService("s1", ("X", "B"), (1,), 2), TransitService("fast", ("A", "Y"), (1,), 2), TransitService("s2", ("Y", "B"), (5,), 2)])
    assert route_min_transfers(n, "A", "B").services == ("fast", "s2")


def test_more_than_five_transfers_and_intermediate_loops():
    n = network([TransitService(str(i), (str(i), str(i+1)), (1,), 1) for i in range(7)])
    assert route_shortest_time(n, "0", "7") is None
    n = network([TransitService("1", ("A", "X", "B"), (1, 1), 2), TransitService("2", ("B", "X", "D"), (1, 1), 2)])
    assert all(r.services != ("1", "2") or r.legs[0].alight_stop != "B" for r in enumerate_routes(n, "A", "D"))


def test_search_limit_is_explicit_and_parameters_validated():
    n = network([TransitService(s, ("A", "B"), (1,), 2) for s in ("1", "2")])
    with pytest.raises(SearchBudgetExceeded):
        enumerate_routes(n, "A", "B", RoutingParameters(max_candidates=1))
    with pytest.raises(ValueError):
        RoutingParameters(max_transfers=-1)
    with pytest.raises(ValueError):
        TransitService("bad", ("A", "B"), (float("nan"),), 1)


def test_route_validation_and_repeatability():
    n = network([TransitService("1", ("A", "B"), (1,), 2)])
    with pytest.raises(ValueError):
        validate_route(Route("A", "B", [Leg("1", "A", "B", 2)]), n)
    r = route_shortest_time(n, "A", "B")
    a, b = evaluate(r, n, 123, 5), evaluate(r, n, 123, 5)
    np.testing.assert_array_equal(a.durations, b.durations)
    with pytest.raises(ValueError):
        evaluate(r, n, 0)

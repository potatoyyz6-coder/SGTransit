from dataclasses import replace

import numpy as np
import pytest

from sg_transit.adaptive import (
    JourneyState, SharedSuffixPolicy, StructuralState, evaluate_adaptive, plan_adaptive,
)
from sg_transit.corridors import CorridorParameters, DestinationIndex, discover_candidates
from sg_transit.models import Stop, TransitNetwork, TransitService, validate_route
from sg_transit.routing import RoutingParameters, SearchBudgetExceeded, enumerate_routes, route_key
from sg_transit.simulation import evaluate


def network(*services, isolated=()):
    ids = sorted(set(isolated) | {stop for service in services for stop in service.stops})
    return TransitNetwork([Stop(stop, stop) for stop in ids], services)


def branching_network():
    return network(
        TransitService("F1", ("O", "A", "H"), (2, 2), 10),
        TransitService("F2", ("O", "B", "H"), (2, 2), 10),
        TransitService("T1", ("H", "X", "D"), (3, 3), 20),
        TransitService("T2", ("H", "X", "D"), (3, 3), 20),
        TransitService("ordinary", ("O", "D"), (30,), 5),
        TransitService("wrong", ("D", "H"), (1,), 1),
    )


def test_reverse_index_retains_direction_and_common_segment():
    n = branching_network()
    index = DestinationIndex(n, "D")
    assert {tail.service_id for tail in index.tails["H"]} == {"T1", "T2"}
    hub = next(hub for hub in index.hubs if hub.stop == "H")
    assert hub.common_segments == (("H", "X"), ("X", "D"))
    assert "wrong" not in {tail.service_id for tail in hub.tails}
    backward = DestinationIndex(n, "O")
    assert not backward.tails["D"]


def test_hub_search_keeps_ordinary_and_legal_alternatives():
    n = branching_network()
    p = RoutingParameters(max_transfers=2, max_candidates=1000)
    result = discover_candidates(DestinationIndex(n, "D"), "O", p)
    exact = enumerate_routes(n, "O", "D", p)
    assert set(map(route_key, result.routes)) <= set(map(route_key, exact))
    assert result.ordinary_route_keys
    assert any(route.services == ("ordinary",) for route in result.routes)
    assert any(route.services == ("F1", "T1") for route in result.routes)
    assert any(route.services == ("F1", "T2") for route in result.routes)
    for route in result.routes:
        validate_route(route, n)


def test_bypass_is_reserved_even_when_all_fast_routes_use_hub():
    n = network(
        *[TransitService(f"F{i}", ("O", "H"), (1,), 2) for i in range(7)],
        TransitService("T1", ("H", "D"), (1,), 2),
        TransitService("T2", ("H", "D"), (1,), 2),
        TransitService("bypass", ("O", "D"), (40,), 2),
    )
    result = discover_candidates(DestinationIndex(n, "D"), "O")
    assert all(key[0][0] != "bypass" for key in result.ordinary_route_keys)
    assert any(key[0][0] == "bypass" for key in result.bypass_route_keys)
    assert any(route.services == ("bypass",) for route in result.routes)


def test_candidate_limits_are_explicit_and_no_hidden_exhaustive_pass():
    n = branching_network()
    p = RoutingParameters(max_expansions=3, max_candidates=1)
    result = discover_candidates(DestinationIndex(n, "D"), "O", p)
    assert result.expansions <= 3
    assert len(result.routes) <= 1
    assert result.truncated
    assert result.truncation_reasons


def test_hub_limit_zero_and_unknown_or_equal_endpoints():
    n = branching_network()
    index = DestinationIndex(n, "D")
    result = discover_candidates(index, "O", corridors=CorridorParameters(max_hubs=0))
    assert not result.selected_hubs
    assert result.routes
    assert discover_candidates(index, "D").routes[0].legs == []
    with pytest.raises(ValueError):
        discover_candidates(index, "missing")
    with pytest.raises(ValueError):
        DestinationIndex(n, "missing")
    with pytest.raises(ValueError):
        CorridorParameters(prefixes_per_hub=0)


def test_no_route_and_wrong_direction():
    n = network(TransitService("wrong", ("D", "O"), (1,), 1), isolated=("alone",))
    assert not discover_candidates(DestinationIndex(n, "D"), "O").routes
    assert not discover_candidates(DestinationIndex(n, "D"), "alone").routes


def test_exact_search_statistics_preserve_results():
    n = branching_network()
    stats = {}
    a = enumerate_routes(n, "O", "D")
    b = enumerate_routes(n, "O", "D", stats=stats)
    assert list(map(route_key, a)) == list(map(route_key, b))
    assert stats["candidates"] == len(a)
    assert stats["expansions"] >= len(a)


def test_shared_node_not_duplicate_suffix_tree():
    n = branching_network()
    policy = SharedSuffixPolicy(n, enumerate_routes(n, "O", "D"))
    a = StructuralState("H", "F1", frozenset({"F1"}), frozenset({"O", "A", "H"}))
    b = StructuralState("H", "F2", frozenset({"F2"}), frozenset({"O", "B", "H"}))
    assert policy.nodes[a.stop] is policy.nodes[b.stop]
    assert {arc.service_id for arc, _, _ in policy.transitions(a)} == {"T1", "T2"}
    policy.value(a)
    policy.value(b)
    assert a in policy._values and b in policy._values
    assert len(policy.nodes) == len({node.stop for node in policy.nodes.values()})


def test_local_eta_update_changes_choice_without_rebuilding_topology():
    n = network(*[TransitService(s, ("O", "D"), (5,), 20) for s in ("A", "B")])
    policy = SharedSuffixPolicy(n, enumerate_routes(n, "O", "D"))
    topology = policy.nodes
    state = policy.initial_state(10)
    a = policy.update(state, {"A": 11, "B": 15})
    cached = policy.value_state_count
    b = policy.update(state, {"A": 20, "B": 12}, event="eta_change")
    c = policy.update(replace(state, now=12), {"A": 11, "B": 15}, event="missed_bus")
    assert (a.arc.service_id, b.arc.service_id, c.arc.service_id) == ("A", "B", "B")
    assert policy.nodes is topology
    assert policy.value_state_count == cached
    assert policy.local_updates == 3
    assert policy.update(replace(state, now=16), {"A": 11, "B": 15}) is None


def test_new_arrival_clock_is_not_reused_from_cached_value():
    n = network(TransitService("A", ("O", "D"), (5,), 20))
    policy = SharedSuffixPolicy(n, enumerate_routes(n, "O", "D"))
    a = policy.update(policy.initial_state(10), {"A": 15})
    b = policy.update(replace(policy.initial_state(10), now=14), {"A": 15})
    assert a.estimated_remaining_score - b.estimated_remaining_score == pytest.approx(4)


def test_continue_onboard_without_wait_delay_or_extra_transfer():
    n = network(TransitService("A", ("O", "H", "D"), (2, 3), 20, 4),
                TransitService("B", ("H", "D"), (3,), 20))
    policy = SharedSuffixPolicy(n, enumerate_routes(n, "O", "D"))
    state = JourneyState(StructuralState("H", "A", frozenset({"A"}), frozenset({"O", "H"})), 10, 0)
    decision = policy.update(state, {"B": 13})
    assert decision.continuing
    assert decision.arc.service_id == "A"
    assert decision.board_time == 10
    single = network(TransitService("A", ("O", "H", "D"), (2, 3), 20, 4))
    routes = enumerate_routes(single, "O", "D")
    result = evaluate_adaptive(SharedSuffixPolicy(single, routes), 200, seed=9)
    fixed = evaluate(routes[0], single, 200, seed=9)
    np.testing.assert_allclose(result.durations, fixed.durations)
    assert np.all(result.transfer_counts == 0)
    assert result.branch_counts == {"A:O": 200}


def test_can_leave_slow_onboard_bus_but_not_force_a_transfer():
    n = network(TransitService("A", ("O", "H", "D"), (2, 50), 5),
                TransitService("B", ("H", "D"), (3,), 5))
    policy = SharedSuffixPolicy(n, enumerate_routes(n, "O", "D"))
    state = JourneyState(StructuralState("H", "A", frozenset({"A"}), frozenset({"O", "H"})), 10, 0)
    assert policy.update(state, {"B": 13}).arc.service_id == "B"
    assert policy.update(state, {}).continuing


def test_waiting_updates_preserve_original_transfer_window():
    n = network(TransitService("F", ("O", "H"), (2,), 5),
                TransitService("B", ("H", "D"), (3,), 5))
    policy = SharedSuffixPolicy(n, enumerate_routes(n, "O", "D"))
    structure = StructuralState("H", None, frozenset({"F"}), frozenset({"O", "H"}))
    state = JourneyState(structure, 50, 0, alighted_at=10)
    assert policy.update(state, {"B": 55}) is not None
    assert policy.update(state, {"B": 55.01}, event="eta_change") is None
    with pytest.raises(ValueError, match="alighting"):
        policy.update(replace(state, alighted_at=None), {"B": 55})


def test_hard_constraints_prevent_repeat_loop_transfer_overflow_and_known_late_board():
    n = branching_network()
    p = RoutingParameters(max_transfers=1, max_trip_minutes=40)
    policy = SharedSuffixPolicy(n, enumerate_routes(n, "O", "D", p), p)
    state = StructuralState("H", None, frozenset({"F1", "T1"}), frozenset({"O", "A", "H"}))
    assert not policy.transitions(state)
    state = StructuralState("H", "F1", frozenset({"F1"}), frozenset({"O", "A", "H", "X"}))
    assert not policy.transitions(state)
    state = StructuralState("H", None, frozenset({"T1"}), frozenset({"O", "H"}))
    assert all(arc.service_id != "T1" for arc, _, _ in policy.transitions(state))
    start = policy.initial_state()
    assert policy.update(start, {"ordinary": 20}) is None


def test_value_budget_fails_explicitly():
    n = branching_network()
    policy = SharedSuffixPolicy(n, enumerate_routes(n, "O", "D"), max_value_states=1)
    with pytest.raises(SearchBudgetExceeded, match="value-state"):
        policy.value(policy.initial_state().structure)


def test_set_policy_improves_independent_waits_and_preserves_correlation_pressure():
    n = network(*[TransitService(s, ("O", "D"), (5,), 20) for s in ("A", "B")])
    routes = enumerate_routes(n, "O", "D")
    policy = SharedSuffixPolicy(n, routes)
    fixed = evaluate(routes[0], n, 2000, seed=10)
    adaptive = evaluate_adaptive(policy, 2000, seed=10)
    assert adaptive.summary["p95_minutes"] < fixed.summary.p95_minutes - 2
    assert len(adaptive.branch_counts) == 2
    np.testing.assert_array_equal(adaptive.durations, evaluate_adaptive(policy, 2000, seed=10).durations)
    correlated = evaluate_adaptive(policy, 500, seed=10, phase_correlation=1)
    np.testing.assert_allclose(correlated.durations,
                               evaluate(routes[0], n, 500, seed=10, phase_correlation=1).durations)


def test_current_stop_eta_not_future_sample_delay_decides():
    n = network(*[TransitService(s, ("O", "D"), (5,), 20, 10) for s in ("A", "B")])
    policy = SharedSuffixPolicy(n, enumerate_routes(n, "O", "D"))
    result = evaluate_adaptive(policy, 200, seed=12, phase_correlation=1)
    assert result.branch_counts == {"A:O": 200}


def test_missed_transfer_metric_and_uncompleted_journeys_are_explicit():
    n = network(TransitService("F", ("O", "H"), (2,), 5, 10),
                TransitService("T", ("H", "D"), (3,), 5))
    routes = enumerate_routes(n, "O", "D")
    result = evaluate_adaptive(SharedSuffixPolicy(n, routes), 500)
    assert result.summary["failure_probability"] > 0
    strict = RoutingParameters(max_trip_minutes=7)
    stopped = evaluate_adaptive(SharedSuffixPolicy(n, routes, strict), 500)
    assert stopped.summary["completion_probability"] < 1
    assert np.isinf(stopped.summary["mean_minutes"])
    assert stopped.summary["stopped_probability"] > 0


def test_zero_trip():
    n = branching_network()
    policy = SharedSuffixPolicy(n, enumerate_routes(n, "O", "O"))
    result = evaluate_adaptive(policy, 10, departure_time=960)
    assert result.summary["mean_minutes"] == 0
    assert result.summary["completion_probability"] == 1


def test_public_planner_reuses_index_and_handles_no_route():
    n = branching_network()
    index = DestinationIndex(n, "D")
    result = plan_adaptive(n, "O", "D", index=index)
    assert result.index is index
    assert result.policy is not None
    assert result.policy.value_state_count > 0
    assert len(result.baselines) == 3
    with pytest.raises(ValueError, match="different"):
        plan_adaptive(n, "O", "H", index=index)
    unreachable = network(TransitService("reverse", ("D", "O"), (1,), 1))
    assert plan_adaptive(unreachable, "O", "D").policy is None


def test_waiting_buffer_not_restarted_after_a_missed_bus():
    n = network(TransitService("F", ("O", "H"), (2,), 5),
                TransitService("B", ("H", "D"), (3,), 5))
    policy = SharedSuffixPolicy(n, enumerate_routes(n, "O", "D"))
    structure = StructuralState("H", None, frozenset({"F"}), frozenset({"O", "H"}))
    state = JourneyState(structure, 14, 0, alighted_at=10)
    assert policy.update(state, {"B": 14}, event="missed_bus") is not None

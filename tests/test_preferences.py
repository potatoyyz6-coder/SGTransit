import math

import numpy as np
import pytest

from experiments.preference_benchmark import run_case, scenario, write_report
from sg_transit.adaptive import JourneyState, SharedSuffixPolicy, StructuralState
from sg_transit.benchmark import Worlds, audit_candidate_closure, execute
from sg_transit.models import Stop, TransitNetwork, TransitService
from sg_transit.preferences import DistributionalPolicy, Preference, select_fixed_preferences
from sg_transit.routing import RoutingParameters, SearchBudgetExceeded, enumerate_routes


def policy_case(name, mode, **kwargs):
    net, p, model = scenario(name)
    routes = enumerate_routes(net, "O", "D", p)
    return DistributionalPolicy(net, routes, p, preference=Preference(mode), **kwargs), model


def test_preference_validation_and_incomplete_ranking():
    with pytest.raises(ValueError):
        Preference("unknown")
    with pytest.raises(ValueError):
        Preference("cool", extra_wait_weight=-1)
    with pytest.raises(ValueError):
        Preference("reliable", quantile=0)
    pref = Preference("fast")
    incomplete = pref.rank([1, math.inf], [0, 0], [0, 0])
    assert incomplete[0] == .5 and math.isinf(incomplete[1])
    assert pref.rank([100, 100], [0, 0], [0, 0]) < incomplete
    with pytest.raises(ValueError):
        pref.rank([math.nan], [0], [0])


def test_fixed_preferences_really_choose_different_routes():
    net, p, model = scenario("wait_ride_tradeoff")
    routes = enumerate_routes(net, "O", "D", p)
    selected, _ = select_fixed_preferences(routes, net, p, Worlds.generate(net, 1000, 7001, model),
                                           {s: Preference(s) for s in ("fast", "cool", "reliable")})
    assert selected["fast"].services == ("short_infrequent",)
    assert selected["cool"].services == ("long_frequent",)
    assert selected["reliable"].services == ("long_frequent",)


def test_dynamic_reliable_avoids_heavy_tail():
    fast, _ = policy_case("mean_tail_conflict", "fast")
    reliable, _ = policy_case("mean_tail_conflict", "reliable")
    departures = {"risky": 1., "stable": 2.}
    assert fast.update(fast.initial_state(), departures).arc.service_id == "risky"
    assert reliable.update(reliable.initial_state(), departures).arc.service_id == "stable"
    assert reliable.last_diagnostics[0]["rank"] != reliable.last_diagnostics[1]["rank"]


def test_dynamic_comfort_weight_changes_action_not_just_output():
    fast, _ = policy_case("wait_ride_tradeoff", "fast")
    cool, _ = policy_case("wait_ride_tradeoff", "cool")
    departures = {"short_infrequent": 10., "long_frequent": 1.}
    assert fast.update(fast.initial_state(), departures).arc.service_id == "short_infrequent"
    assert cool.update(cool.initial_state(), departures).arc.service_id == "long_frequent"
    cool.preference = Preference("cool", extra_wait_weight=0, transfer_penalty=0)
    assert cool.update(cool.initial_state(), departures).arc.service_id == "short_infrequent"


def test_later_stop_replans_from_local_departures():
    policy, _ = policy_case("independent_alternatives", "reliable")
    state = JourneyState(StructuralState("H", "feeder", frozenset({"feeder"}), frozenset({"O", "H"})), 7, 0)
    first = policy.update(state, {"tail0": 10., "tail1": 13., "tail2": 14., "tail3": 15.})
    second = policy.update(state, {"tail0": 17., "tail1": 10., "tail2": 14., "tail3": 15.})
    assert first.arc.service_id == "tail0"
    assert second.arc.service_id == "tail1"
    assert first.board_time == second.board_time == 10


def test_current_delays_are_distributions_not_future_realizations():
    policy, _ = policy_case("mean_tail_conflict", "reliable")
    phases = {"risky": np.array([1.]), "stable": np.array([2.])}
    a = Worlds(phases, {"risky": np.array([0.]), "stable": np.array([0.])}, 1, 1)
    b = Worlds(phases, {"risky": np.array([40.]), "stable": np.array([0.])}, 1, 2)
    assert execute(policy, a).branches == execute(policy, b).branches == {"stable:O": 1}


def test_single_service_continuation_charges_delay_once():
    policy, model = policy_case("single_service", "reliable")
    worlds = Worlds.generate(policy.network, 100, 9001, model)
    trial = execute(policy, worlds)
    np.testing.assert_allclose(trial.durations, worlds.phases["only"] + 14 + worlds.delays["only"])
    assert not trial.transfers.any()
    assert trial.branches == {"only:O": 100}
    decision = policy.update(policy.initial_state(), {"only": 2.})
    cost = policy.project(policy.initial_state(), decision, policy.suffixes(decision.following)[0])
    assert cost.durations.mean() == pytest.approx(17.5)
    assert cost.waits.mean() == 2
    assert cost.transfers.mean() == 0


def test_projected_constraints_and_executable_constraints():
    net = TransitNetwork([Stop(x, x) for x in ("O", "H", "D")], [
        TransitService("F", ("O", "H"), (5,), 10), TransitService("T", ("H", "D"), (5,), 80)])
    p = RoutingParameters()
    routes = enumerate_routes(net, "O", "D", p)
    policy = DistributionalPolicy(net, routes, p, preference=Preference("reliable"))
    decision = policy.update(policy.initial_state(), {"F": 0.})
    cost = policy.project(policy.initial_state(), decision, policy.suffixes(decision.following)[0])
    assert np.isinf(cost.durations).any()
    state = JourneyState(decision.following, 5, 0)
    assert policy.update(state, {"T": 51.}) is None
    assert policy.update(state, {"T": 7.}) is None  # Three-minute buffer.


def test_waiting_update_does_not_reset_buffer():
    policy, _ = policy_case("independent_alternatives", "cool")
    state = JourneyState(StructuralState("H", None, frozenset({"feeder"}), frozenset({"O", "H"})), 12, 0, 7)
    decision = policy.update(state, {"tail0": 13.})
    assert decision.board_time == 13
    costs = policy.project(state, decision, ())
    np.testing.assert_array_equal(costs.waits, np.ones(policy.rollout_samples))


def test_distributions_scored_before_selecting_suffix_not_oracle_minimum():
    policy, _ = policy_case("independent_alternatives", "reliable", rollout_samples=128)
    decision = policy.update(policy.initial_state(), {"feeder": 0.})
    # A suffix is chosen as a whole, not the best tail independently in each draw.
    diagnostics = policy.last_diagnostics
    assert len(diagnostics) == 4
    assert decision.estimated_remaining_score == min(d["rank"][1] for d in diagnostics)
    projections = [policy.project(policy.initial_state(), decision, tail).durations
                   for tail in policy.suffixes(decision.following)]
    oracle_p95 = np.sort(np.min(projections, axis=0))[math.ceil(.95 * 128) - 1]
    assert decision.estimated_remaining_score > oracle_p95


def test_budgets_fail_explicitly_and_paths_are_legal():
    policy, _ = policy_case("detour_transfers", "fast", max_suffix_paths=1)
    with pytest.raises(SearchBudgetExceeded):
        policy.suffixes(policy.initial_state().structure)
    policy, _ = policy_case("single_service", "fast", max_suffix_states=1)
    with pytest.raises(SearchBudgetExceeded):
        policy.suffixes(policy.initial_state().structure)
    policy, _ = policy_case("detour_transfers", "fast")
    routes = enumerate_routes(policy.network, "O", "D", policy.parameters)
    assert audit_candidate_closure(policy, routes)["equal"]
    for suffix in policy.suffixes(policy.initial_state().structure):
        assert suffix[-1][1].stop == "D"
        assert len(suffix[-1][1].used) <= policy.parameters.max_transfers + 1


def test_rollouts_reproducible_and_restricted_arcs_respected():
    a, _ = policy_case("wait_ride_tradeoff", "cool")
    b, _ = policy_case("wait_ride_tradeoff", "cool")
    observed = {"short_infrequent": 10., "long_frequent": 1.}
    assert a.update(a.initial_state(), observed) == b.update(b.initial_state(), observed)
    assert a.update(a.initial_state(), observed, allowed_arcs={("short_infrequent", "D")}).arc.service_id == "short_infrequent"


def test_training_is_frozen_and_artifacts_reproduce(tmp_path):
    args = dict(samples=20, training_samples=30, rollout_samples=32, bootstrap_samples=10, output=tmp_path)
    a = run_case("wait_ride_tradeoff", **args)
    assert a == run_case("wait_ride_tradeoff", **args)
    b = run_case("wait_ride_tradeoff", test_seed=9002, **args)
    assert a["selected_fixed"] == b["selected_fixed"]
    assert a["training_scores"] == b["training_scores"]
    assert a["test_world_sha256"] != b["test_world_sha256"]
    write_report([b], tmp_path)
    assert (tmp_path / "report.md").exists()
    with pytest.raises(ValueError):
        run_case("single_service", test_seed=2309, **args)


def test_heldout_reliability_gain_has_a_mean_time_cost():
    fast, model = policy_case("mean_tail_conflict", "fast")
    reliable, _ = policy_case("mean_tail_conflict", "reliable")
    worlds = Worlds.generate(fast.network, 500, 9001, model)
    a, b = execute(fast, worlds).summary(), execute(reliable, worlds).summary()
    assert b["mean_minutes"] > a["mean_minutes"] + 2
    assert b["p95_minutes"] < a["p95_minutes"] - 8


def test_heldout_comfort_reduces_wait_without_hiding_extra_time():
    fast, model = policy_case("wait_ride_tradeoff", "fast")
    cool, _ = policy_case("wait_ride_tradeoff", "cool")
    worlds = Worlds.generate(fast.network, 500, 9001, model)
    a, b = execute(fast, worlds), execute(cool, worlds)
    assert b.waits.mean() < a.waits.mean() - 2
    assert b.durations.mean() > a.durations.mean() + 1
    np.testing.assert_allclose(b.durations, b.waits + b.buffers + b.rides)


def test_independent_benefit_and_synchronized_null_are_preserved():
    for name in ("independent_alternatives", "synchronized_alternatives"):
        policy, model = policy_case(name, "reliable", rollout_samples=64)
        routes = enumerate_routes(policy.network, "O", "D", policy.parameters)
        worlds = Worlds.generate(policy.network, 300, 9001, model)
        dynamic = execute(policy, worlds)
        fixed = execute(SharedSuffixPolicy(policy.network, [routes[0]], policy.parameters), worlds, controller="first")
        if name == "synchronized_alternatives":
            np.testing.assert_array_equal(dynamic.durations, fixed.durations)
        else:
            assert dynamic.summary()["p95_minutes"] < fixed.summary()["p95_minutes"] - 4


def test_suffix_and_training_counts_do_not_change_policy_candidate_set():
    a, _ = policy_case("detour_transfers", "reliable", rollout_samples=16)
    b, _ = policy_case("detour_transfers", "reliable", rollout_samples=512)
    assert a.nodes == b.nodes
    assert a.suffixes(a.initial_state().structure) == b.suffixes(b.initial_state().structure)


def test_plot_can_be_generated_from_saved_experiment(tmp_path):
    from experiments.preference_benchmark import write_plot
    doc = run_case("mean_tail_conflict", samples=10, training_samples=20,
                   rollout_samples=16, bootstrap_samples=5, output=tmp_path)
    write_plot([doc], tmp_path)
    assert (tmp_path / "preferences.png").stat().st_size > 1000

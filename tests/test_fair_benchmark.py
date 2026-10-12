from dataclasses import replace

import numpy as np
import pytest

from experiments.fair_benchmark import SCENARIOS, run_case, scenario, write_report
from sg_transit.adaptive import SharedSuffixPolicy
from sg_transit.benchmark import WorldModel, Worlds, audit_candidate_closure, execute, paired_difference, select_fixed
from sg_transit.models import Stop, TransitNetwork, TransitService
from sg_transit.routing import RoutingParameters, SearchBudgetExceeded, enumerate_routes
from sg_transit.simulation import evaluate


def network(*services):
    stops = sorted({s for service in services for s in service.stops})
    return TransitNetwork([Stop(s, s) for s in stops], services)


@pytest.mark.parametrize("name", SCENARIOS)
def test_all_cases_have_equal_candidate_closure(name):
    net, p, _ = scenario(name)
    routes = enumerate_routes(net, "O", "D", p)
    assert audit_candidate_closure(SharedSuffixPolicy(net, routes, p), routes)["equal"]


def test_worlds_are_reproducible_order_independent_and_frozen():
    net, _, model = scenario("common_delay")
    a = Worlds.generate(net, 20, 42, model)
    b = Worlds.generate(TransitNetwork(net.stops.values(), reversed(list(net.services.values()))), 20, 42, model)
    assert a.fingerprint() == b.fingerprint()
    assert a.fingerprint() != Worlds.generate(net, 20, 43, model).fingerprint()
    np.testing.assert_array_equal(a.delays["feeder"], a.delays["tail0"])
    np.testing.assert_array_equal(a.phases["tail0"], a.phases["tail1"])
    with pytest.raises(ValueError):
        a.phases["feeder"][0] = 0
    with pytest.raises(ValueError, match="unknown service"):
        Worlds.generate(net, 10, 1, WorldModel(phase_offsets={"unknown": 1}))


def test_delay_control_changes_dependence_not_network_or_marginals():
    a, p, independent = scenario("independent_delay")
    b, q, common = scenario("common_delay")
    assert a.services == b.services and p == q
    assert independent.phase_groups == common.phase_groups
    assert independent.phase_offsets == common.phase_offsets
    assert independent.delay_groups == {}
    assert len(set(common.delay_groups.values())) == 1


def test_single_service_identical_continuation_and_accounting():
    net, p, model = scenario("single_service")
    routes = enumerate_routes(net, "O", "D", p)
    worlds = Worlds.generate(net, 100, 5, model)
    fixed = execute(SharedSuffixPolicy(net, routes, p), worlds, controller="first")
    scored = execute(SharedSuffixPolicy(net, routes, p), worlds)
    np.testing.assert_array_equal(fixed.durations, scored.durations)
    np.testing.assert_allclose(scored.durations, worlds.phases["only"] + 14 + worlds.delays["only"])
    np.testing.assert_allclose(scored.durations, scored.waits + scored.buffers + scored.rides)
    assert not scored.transfers.any()
    assert scored.branches == {"only:O": 100}


def test_hand_computed_tight_connection_and_no_delay_control():
    net = network(TransitService("F", ("O", "H"), (8,), 15, 6),
                  TransitService("T", ("H", "D"), (8,), 15))
    routes = enumerate_routes(net, "O", "D")
    worlds = Worlds({"F": np.array([0., 0.]), "T": np.array([12., 12.])},
                    {"F": np.array([2., 0.]), "T": np.zeros(2)}, 2, 1)
    trial = execute(SharedSuffixPolicy(net, routes), worlds)
    np.testing.assert_allclose(trial.durations, [35, 20])
    np.testing.assert_allclose(trial.waits, [14, 1])
    np.testing.assert_array_equal(trial.missed, [True, False])
    np.testing.assert_array_equal(trial.transfers, [1, 1])
    assert trial.summary()["long_transfer_wait_probability"] == .5


def test_same_executor_matches_legacy_on_one_fixed_route_with_same_worlds():
    net = network(TransitService("F", ("O", "H"), (8,), 15, 6),
                  TransitService("T", ("H", "D"), (8,), 15))
    route = enumerate_routes(net, "O", "D")[0]
    # Reconstruct the legacy keyed draws for a cross-implementation check.
    import hashlib
    phases, delays = {}, {}
    for sid, service in net.services.items():
        seed = int.from_bytes(hashlib.sha256(f"7:{sid}".encode()).digest()[:8], "big")
        draws = np.random.default_rng(seed).random((80, 2))
        phases[sid], delays[sid] = draws[:, 0] * service.headway_minutes, draws[:, 1] * service.delay_max_minutes
    trial = execute(SharedSuffixPolicy(net, [route]), Worlds(phases, delays, 80, 7), controller="first")
    legacy = evaluate(route, net, 80, 7)
    np.testing.assert_allclose(trial.durations, legacy.durations)
    np.testing.assert_allclose(trial.waits, legacy.waits)
    np.testing.assert_array_equal(trial.missed, legacy.missed)


def test_independent_alternatives_reduce_wait_but_synchronized_do_not():
    net = network(*[TransitService(f"T{i}", ("O", "D"), (1,), 20) for i in range(4)])
    routes = enumerate_routes(net, "O", "D")
    policy = SharedSuffixPolicy(net, routes)
    independent = execute(policy, Worlds.generate(net, 3000, 10), controller="first")
    synced = execute(policy, Worlds.generate(net, 3000, 10,
                     WorldModel(phase_groups={s: "same" for s in net.services})), controller="first")
    # Minimum of four independent Uniform(0,20) waits: mean 20/(4+1), not 20/4.
    assert independent.waits.mean() == pytest.approx(4, abs=.25)
    assert synced.waits.mean() == pytest.approx(10, abs=.35)


def test_candidate_recombination_is_rejected_not_silently_advantaged():
    net = network(TransitService("F", ("O", "H"), (2,), 5),
                  TransitService("G", ("O", "H"), (2,), 5),
                  TransitService("T", ("H", "D"), (2,), 5),
                  TransitService("U", ("H", "D"), (2,), 5))
    routes = enumerate_routes(net, "O", "D")
    subset = [r for r in routes if r.services in {("F", "T"), ("G", "U")}]
    with pytest.raises(ValueError, match="extra=2"):
        audit_candidate_closure(SharedSuffixPolicy(net, subset), subset)
    with pytest.raises(SearchBudgetExceeded):
        audit_candidate_closure(SharedSuffixPolicy(net, routes), routes, max_expansions=1)


def test_constraints_do_not_drop_uncompleted_worlds():
    net = network(TransitService("F", ("O", "H"), (8,), 15),
                  TransitService("T", ("H", "D"), (8,), 15))
    p = RoutingParameters(max_transfer_gap=2)
    routes = enumerate_routes(net, "O", "D", p)
    worlds = Worlds.generate(net, 10, 1)
    for mode in ("first", "scored"):
        trial = execute(SharedSuffixPolicy(net, routes, p), worlds, controller=mode)
        assert np.isinf(trial.durations).all()
        assert trial.summary()["completion_probability"] == 0
        assert trial.summary()["long_transfer_wait_probability"] is None
        assert paired_difference(trial, trial)["mean_delta"] is None
    assert enumerate_routes(net, "O", "D", replace(p, max_transfers=0)) == []


def test_realized_trip_overrun_is_infinite_for_every_controller():
    net = network(TransitService("T", ("O", "D"), (10,), 1, 20))
    p = RoutingParameters(max_trip_minutes=20)
    routes = enumerate_routes(net, "O", "D", p)
    worlds = Worlds({"T": np.zeros(1)}, {"T": np.array([15.])}, 1, 1)
    for controller in ("first", "scored"):
        result = execute(SharedSuffixPolicy(net, routes, p), worlds, controller=controller)
        assert np.isinf(result.durations[0])


def test_decision_cannot_see_hidden_realized_delays():
    net = network(TransitService("A", ("O", "D"), (2,), 10, 8),
                  TransitService("B", ("O", "D"), (3,), 10, 8))
    routes = enumerate_routes(net, "O", "D")
    phases = {"A": np.array([1.]), "B": np.array([2.])}
    a = Worlds(phases, {"A": np.array([0.]), "B": np.array([8.])}, 1, 1)
    b = Worlds(phases, {"A": np.array([8.]), "B": np.array([0.])}, 1, 2)
    for controller in ("first", "scored"):
        trial_a = execute(SharedSuffixPolicy(net, routes), a, controller=controller)
        trial_b = execute(SharedSuffixPolicy(net, routes), b, controller=controller)
        assert trial_a.branches == trial_b.branches == {"A:O": 1}
        assert trial_b.durations[0] - trial_a.durations[0] == 8


def test_mean_and_p95_fixed_controls_are_selected_on_training_only():
    net, p, model = scenario("mean_tail_conflict")
    routes = enumerate_routes(net, "O", "D", p)
    selected, _ = select_fixed(routes, net, p, Worlds.generate(net, 1000, 7001, model))
    assert selected["fixed_mean"].services == ("risky",)
    assert selected["fixed_p95"].services == ("stable",)


def test_negative_controls_remain_negative_on_heldout_worlds():
    net, p, model = scenario("synchronized_alternatives")
    routes = enumerate_routes(net, "O", "D", p)
    worlds = Worlds.generate(net, 500, 9001, model)
    fixed = execute(SharedSuffixPolicy(net, [routes[0]], p), worlds, controller="first")
    scored = execute(SharedSuffixPolicy(net, routes, p), worlds)
    np.testing.assert_array_equal(fixed.durations, scored.durations)

    net, p, model = scenario("mean_tail_conflict")
    routes = enumerate_routes(net, "O", "D", p)
    worlds = Worlds.generate(net, 1000, 9001, model)
    scored = execute(SharedSuffixPolicy(net, routes, p), worlds).summary()
    stable = next(r for r in routes if r.services == ("stable",))
    fixed = execute(SharedSuffixPolicy(net, [stable], p), worlds, controller="first").summary()
    assert scored["mean_minutes"] < fixed["mean_minutes"]
    assert scored["p95_minutes"] > fixed["p95_minutes"] + 8


def test_early_bus_can_cost_more_than_remaining_onboard():
    net, p, model = scenario("detour_transfers")
    routes = enumerate_routes(net, "O", "D", p)
    worlds = Worlds.generate(net, 500, 9001, model)
    first = execute(SharedSuffixPolicy(net, routes, p), worlds, controller="first")
    scored = execute(SharedSuffixPolicy(net, routes, p), worlds)
    assert first.durations.mean() > scored.durations.mean() + 5
    assert not scored.transfers.any()
    assert scored.branches == {"through:O": 500}


def test_origin_equals_destination_and_unreachable():
    net = network(TransitService("T", ("O", "D"), (3,), 10))
    routes = enumerate_routes(net, "O", "O")
    trial = execute(SharedSuffixPolicy(net, routes), Worlds.generate(net, 10, 1))
    assert not trial.durations.any()
    assert trial.summary()["completion_probability"] == 1
    assert enumerate_routes(net, "D", "O") == []


def test_policy_observes_only_current_stop_departures():
    net, p, model = scenario("tight_connection")
    routes = enumerate_routes(net, "O", "D", p)

    class Observer(SharedSuffixPolicy):
        def update(self, state, departures, **kwargs):
            allowed = {arc.service_id for arc, _, continuing in self.transitions(state.structure) if not continuing}
            assert set(departures) <= allowed
            assert ("connection" not in departures and "backup" not in departures) if state.structure.stop == "O" else True
            return super().update(state, departures, **kwargs)

    worlds = Worlds.generate(net, 30, 9001, model)
    before = worlds.fingerprint()
    execute(Observer(net, routes, p), worlds)
    assert worlds.fingerprint() == before


def test_reproducible_artifacts_and_heldout_selection(tmp_path):
    args = dict(samples=30, training_samples=40, bootstrap_samples=10, output=tmp_path)
    a = run_case("single_service", **args)
    b = run_case("single_service", **args)
    assert a == b
    c = run_case("single_service", **{**args, "test_seed": 9002})
    assert c["fixed_selection"] == a["fixed_selection"]
    assert c["training_scores"] == a["training_scores"]
    assert c["test_world_sha256"] != a["test_world_sha256"]
    write_report([a], tmp_path)
    assert (tmp_path / "summary.csv").exists()
    with np.load(tmp_path / "single_service.samples.npz", allow_pickle=False) as samples:
        assert len(samples.files) == 28
    with pytest.raises(ValueError, match="seeds must differ"):
        run_case("single_service", training_seed=1, test_seed=1, **args)


def test_no_choice_paired_intervals_are_exactly_zero():
    net, p, model = scenario("single_service")
    routes = enumerate_routes(net, "O", "D", p)
    trial = execute(SharedSuffixPolicy(net, routes, p), Worlds.generate(net, 100, 1, model))
    difference = paired_difference(trial, trial, bootstrap_samples=20)
    assert difference == {"mean_delta": 0, "mean_ci95": [0, 0], "p95_delta": 0, "p95_ci95": [0, 0]}

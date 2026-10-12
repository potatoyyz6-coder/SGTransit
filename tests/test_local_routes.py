from collections import Counter

import numpy as np
import pytest

from experiments.local_routes import HOME, HUBS, build_network, project, sample_queries, run_query
from sg_transit.models import Leg, Route, validate_route
from sg_transit.routing import RoutingParameters, enumerate_routes


@pytest.fixture(scope="module")
def full():
    return build_network()[0]


def test_sampling_is_stratified_reproducible_without_home_duplication(full):
    a = sample_queries(full)
    assert a == sample_queries(full)
    assert a != sample_queries(full, seed=123)
    queries = a["queries"]
    assert len(queries) == 21
    assert len({(q["origin"], q["destination"]) for q in queries}) == 21
    assert Counter(q["stratum"] for q in queries) == {"specified": 1, 0: 7, 1: 7, 2: 6}
    assert (queries[0]["origin"], queries[0]["destination"]) == HOME


def test_every_stratum_matches_enumerated_minimum_transfers(full):
    p = RoutingParameters(max_transfers=2, max_candidates=500, max_expansions=30000)
    for q in sample_queries(full)["queries"]:
        net = project(full, q["origin"], q["destination"])
        routes = enumerate_routes(net, q["origin"], q["destination"], p)
        assert routes
        for route in routes:
            validate_route(route, full)
        if q["stratum"] != "specified":
            assert min(r.transfers for r in routes) == q["stratum"]


def test_home_contains_four_blk109_choices_and_onboard_61(full):
    net = project(full, *HOME)
    for service in ("61-D2", "52-D2", "184-D1", "75-D2"):
        assert net.services[service].can_ride("12061", "42071")
        assert not net.services[service].can_ride("42071", "12061")
    routes = enumerate_routes(net, *HOME, RoutingParameters(max_transfers=2, max_candidates=500))
    keys = {tuple((l.service_id, l.board_stop, l.alight_stop) for l in r.legs) for r in routes}
    assert (("151-D2", "16189", "12061"), ("61-D2", "12061", "42171")) in keys
    for sid in ("52-D2", "184-D1", "75-D2"):
        assert (("151-D2", "16189", "12061"), (sid, "12061", "42071"),
                ("174-D2", "42071", "42171")) in keys


def test_projection_preserves_distances_and_names(full):
    net = project(full, *HOME)
    assert set(net.stops) <= HUBS | set(HOME)
    for sid, service in net.services.items():
        for a,b,t in zip(service.stops, service.stops[1:], service.ride_minutes):
            assert t == pytest.approx(full.services[sid].ride_time(a,b))
    assert full.stops["12061"].name == "Blk 109"


def test_query_artifacts_traces_and_no_data_calls(full, tmp_path, monkeypatch):
    import urllib.request
    def reject_network(*args, **kwargs):
        raise AssertionError("Offline experiment attempted a network request")
    monkeypatch.setattr(urllib.request, "urlopen", reject_network)
    q = sample_queries(full)["queries"][0]
    r = run_query(full, q, samples=8, training_samples=8, rollout_samples=16, output=tmp_path)
    assert r["status"] == "completed" and r["candidate_search_complete"]
    assert r["candidate_audit"]["equal"]
    assert len(r["evaluations"]) == 8
    for e in r["dynamic_examples"].values():
        value = e["route"]
        route = Route(value["origin"], value["destination"], [Leg(**leg) for leg in value["legs"]])
        validate_route(route, full)
        assert all(a.service_id != b.service_id for a,b in zip(route.legs, route.legs[1:]))
    with np.load(tmp_path / "home_base.npz") as arr:
        for label in r["evaluations"]:
            d = arr[label+"__durations"]
            complete = np.isfinite(d)
            np.testing.assert_allclose(d[complete], (arr[label+"__waits"]+arr[label+"__buffers"]+arr[label+"__rides"])[complete])
        for mode, e in r["dynamic_examples"].items():
            assert arr[f"dynamic_{mode}__transfers"][0] == max(0, len(e["route"]["legs"])-1)
            assert arr[f"dynamic_{mode}__durations"][0] == e["minutes"]


def test_invalid_sample_counts_rejected(full, tmp_path):
    with pytest.raises(ValueError, match="positive"):
        run_query(full, sample_queries(full)["queries"][0], samples=0, output=tmp_path)


def test_budget_failures_remain_in_results(full, tmp_path, monkeypatch):
    import experiments.local_routes as module
    from sg_transit.routing import SearchBudgetExceeded
    def fail(*args, **kwargs):
        raise SearchBudgetExceeded("Test search budget")
    monkeypatch.setattr(module, "enumerate_routes", fail)
    r = run_query(full, sample_queries(full)["queries"][0], output=tmp_path)
    assert r["status"] == "budget_exceeded"
    assert not r["candidate_search_complete"]
    assert r["stage"] == "search"
    assert (tmp_path / "home_base.json").exists()


def test_execution_budget_failure_does_not_relabel_complete_search(full, tmp_path, monkeypatch):
    import experiments.local_routes as module
    from sg_transit.routing import SearchBudgetExceeded
    def fail(*args, **kwargs):
        raise SearchBudgetExceeded("Test simulation budget")
    monkeypatch.setattr(module, "select_fixed_preferences", fail)
    r = run_query(full, sample_queries(full)["queries"][0], output=tmp_path)
    assert r["status"] == "budget_exceeded"
    assert r["candidate_search_complete"]
    assert r["stage"] == "training_selection"

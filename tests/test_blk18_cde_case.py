from copy import deepcopy
from dataclasses import replace
import json
import socket
import urllib.request

import pytest

from experiments.blk18_cde_case import (
    DESTINATION, LIMITED, ORIGIN, SEGMENTS, Settings, build_network, compare_local,
    prefix_state, run,
)
from sg_transit.adaptive import SharedSuffixPolicy
from sg_transit.models import Leg, Route, validate_route
from sg_transit.reference import clock_minutes, estimate, shortlist, window_status
from sg_transit.routing import enumerate_routes, route_key


@pytest.fixture(scope="module")
def built():
    return build_network()


@pytest.fixture(scope="module")
def routes(built):
    return enumerate_routes(built[0], ORIGIN, DESTINATION, Settings().routing())


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    return run(tmp_path_factory.mktemp("blk18_report"), make_plot=False)


def test_full_original_stops_direction_and_provenance(built):
    network, windows, patterns, source = built
    assert len(network.stops) == 25
    assert len(network.services) == 9
    assert network.stops[DESTINATION].name == "Coll of Design & Engrg"
    for service in network.services.values():
        rows = patterns[service.id]["ordered_source_rows"]
        assert service.stops == tuple(r["BusStopCode"] for r in rows)
        assert len(set(service.stops)) == len(service.stops)
        assert set(windows[service.id]) == set(service.stops)
        assert all(r["Direction"] == service.id.split("-D")[1] for r in rows)
        for a, b, duration in zip(rows, rows[1:], service.ride_minutes):
            assert duration == pytest.approx(max(.5, (float(b["Distance"])-float(a["Distance"]))*3))
        assert not service.can_ride(service.stops[-1], service.stops[0])
    assert source["api_calls"] == 0 and source["new_collection_scheduled"] is False
    assert source["accessed_at"] and len(source["raw_sha256"]) == 2


def test_automatic_search_discovers_requested_paths_and_extra_interchanges(routes, built):
    network = built[0]
    keys = {route_key(r) for r in routes}
    for last in ("183-D1", "188-D1"):
        assert (("173-D1", ORIGIN, "28019"), (last, "28019", DESTINATION)) in keys
    assert (("173-D1", ORIGIN, "17009"), ("96-D1", "17009", DESTINATION)) in keys
    for last in ("96-D1", "183-D1"):
        assert (("41-D1", ORIGIN, "28109"), ("106-D1", "28109", "17159"),
                (last, "17159", DESTINATION)) in keys
    assert (("173-D1", ORIGIN, "17189"), ("183-D1", "17189", DESTINATION)) in keys
    for route in routes:
        validate_route(route, network)
        assert route.transfers <= 5
        assert len(route.services) == len(set(route.services))


def test_aggregate_candidates_components_and_shortlist(report):
    assert report["status"] == "completed" and report["candidate_search_complete"]
    assert len(report["candidates"]) == 7212
    assert report["recommendable_count"] == 4558
    lookup = {r["id"]: r for r in report["candidates"]}
    assert len(report["shortlist"]) == 8
    assert len({tuple(f["services"]) for f in report["shortlist"]}) == 8
    for row in lookup.values():
        assert sum(row[k] for k in ("ride_minutes", "wait_minutes", "buffer_minutes", "delay_minutes")) == pytest.approx(row["estimated_total_minutes"])
        assert row["buffer_minutes"] == row["transfers"]*3
        if row["recommendable"]:
            assert not set(LIMITED).intersection(row["services"])
            assert all(l["operating_status"] == "within_historical_window" for l in row["legs"])
            assert row["estimated_total_minutes"] <= 120
    for family in report["shortlist"]:
        assert family["representative_id"] in family["variant_ids"]
        assert set(family["variant_ids"]) == {r["id"] for r in lookup.values()
            if r["recommendable"] and r["services"] == family["services"]}
    assert report["local_choices"]["candidate_count"] == report["recommendable_count"] > len(report["shortlist"])


def test_limited_service_retained_but_not_default(routes, built):
    network, windows = built[:2]
    route = next(r for r in routes if "106A-D1" in r.services)
    row = estimate(route, network, windows, Settings().routing(), limited=LIMITED)
    assert not row["recommendable"]
    assert {"limited_service_not_default", "outside_historical_window"} <= set(row["exclusion_reasons"])
    assert window_status(windows["106A-D1"]["28109"], 8*60+15) == "within_historical_window"
    assert window_status(windows["106A-D1"]["28109"], 8*60+15, "sunday") == "not_operating"


def test_missing_operating_window_does_not_erase_candidate(routes, built):
    network, windows = built[:2]
    route = next(r for r in routes if r.services == ("173-D1", "96-D1"))
    unknown = deepcopy(windows)
    unknown["96-D1"]["17009"] = {}
    row = estimate(route, network, unknown, Settings().routing())
    assert row["exclusion_reasons"] == ["unknown"]
    assert row["route"]["destination"] == DESTINATION
    assert row["estimated_total_minutes"] > 0


def test_operating_window_uses_estimated_transfer_board_time(routes, built):
    network, windows = built[:2]
    route = next(r for r in routes if r.services == ("173-D1", "96-D1"))
    windows = deepcopy(windows)
    windows["96-D1"]["17009"] = {"WD_FirstBus": "0600", "WD_LastBus": "1005"}
    assert window_status(windows["96-D1"]["17009"], 600) == "within_historical_window"
    row = estimate(route, network, windows, Settings().routing())
    assert row["legs"][1]["board_minute"] > 605
    assert "outside_historical_window" in row["exclusion_reasons"]


def test_expected_time_and_gap_limits_do_not_claim_no_topology(routes, built):
    network, windows = built[:2]
    route = next(r for r in routes if r.services == ("173-D1", "96-D1"))
    row = estimate(route, network, windows, replace(Settings().routing(), max_trip_minutes=30, max_transfer_gap=5))
    assert {"estimated_trip_limit_exceeded", "estimated_transfer_gap_exceeded"} <= set(row["exclusion_reasons"])
    assert row["legs"]


def test_service_day_clock_boundaries():
    assert clock_minutes("24:30") == 1470
    window = {"WD_FirstBus": "2330", "WD_LastBus": "0130"}
    for t in (1410, 1470, 1530):
        assert window_status(window, t) == "within_historical_window"
    assert window_status(window, 30) == "outside_historical_window"
    assert window_status(window, 1531) == "outside_historical_window"
    assert window_status({"WD_FirstBus": "broken"}, 600) == "unknown"
    assert window_status({"WD_FirstBus": "-", "WD_LastBus": "1000"}, 600) == "unknown"
    with pytest.raises(ValueError):
        clock_minutes("10:70")


def test_local_choices_change_and_same_vehicle_has_no_extra_charges(report):
    cases = {e["id"]: e for e in report["local_choices"]["examples"]}
    for case, service in (("onboard_173_at_depot", "173-D1"),
                          ("onboard_106_at_toh_tuck", "106-D1"),
                          ("onboard_183_at_blk365", "183-D1")):
        chosen = cases[case]["selected"]
        assert chosen["service"] == service and chosen["continuing"]
        assert chosen["wait_including_buffer_minutes"] == chosen["new_boarding_delay_minutes"] == 0
        assert chosen["new_transfer"] is False
    assert cases["direct_services_soon"]["selected"]["service"] in {"183-D1", "188-D1"}
    assert cases["feeder_services_soon"]["selected"]["service"] in {"105-D2", "106-D1"}
    assert all(e["status"] == "synthetic_reference" for e in cases.values())


def test_local_inputs_do_not_require_future_vehicle_identity(routes, built):
    network, windows = built[:2]
    pool = [r for r in routes if not set(LIMITED).intersection(r.services)]
    policy = SharedSuffixPolicy(network, pool, Settings().routing())
    state, _ = prefix_state(pool, network, "28019", "173-D1", 630, 600, waiting=True)
    eta = {"183-D1": 634, "188-D1": 637, "105-D2": 640}
    first = compare_local(policy, state, eta, windows, "weekday")
    assert first == compare_local(policy, state, {**eta, "not_at_this_stop": 10000}, windows, "weekday")
    assert first["selected"] is not None
    expired = compare_local(policy, state, {"183-D1": 631}, windows, "weekday")
    assert expired["selected"] is None


def test_transfer_bound_cycle_and_repeated_service_rejection(built):
    network = built[0]
    one = enumerate_routes(network, ORIGIN, DESTINATION, Settings(max_transfers=1).routing())
    assert one and all(r.transfers == 1 for r in one)
    s = network.services["173-D1"]
    repeated = Route(ORIGIN, "28019", [Leg(s.id, ORIGIN, "28109", s.ride_time(ORIGIN, "28109")),
                    Leg(s.id, "28109", "28019", s.ride_time("28109", "28019"))])
    with pytest.raises(ValueError, match="Repeated"):
        validate_route(repeated, network)
    reversed_leg = Route("28019", ORIGIN, [Leg(s.id, "28019", ORIGIN, 1)])
    with pytest.raises(ValueError):
        validate_route(reversed_leg, network)


def test_all_artifacts_offline_reproducible_and_no_input_mutation(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected network call")
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    settings = Settings(max_transfers=2)
    a, b = tmp_path / "a", tmp_path / "b"
    first = run(a, settings)
    second = run(b, settings)
    assert first == second
    for name in ("reference.json", "candidates.csv", "report.md", "routes.png"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
    assert (a / "routes.png").stat().st_size > 10000
    assert json.loads((a / "reference.json").read_text())["provenance"]["api_calls"] == 0
    text = (a / "report.md").read_text()
    assert "<details>" in text and "limited-service" in text


def test_no_route_same_endpoint_and_budget_are_distinct(tmp_path):
    same = run(tmp_path / "same", origin=ORIGIN, destination=ORIGIN, make_plot=False)
    assert same["status"] == "completed" and len(same["candidates"]) == 1
    assert same["candidates"][0]["estimated_total_minutes"] == 0
    none = run(tmp_path / "none", origin=DESTINATION, destination=ORIGIN, make_plot=False)
    assert none["status"] == "no_route_in_declared_network" and none["candidate_search_complete"]
    cap = run(tmp_path / "cap", Settings(max_candidates=1), make_plot=False)
    assert cap["status"] == "search_budget_exceeded" and not cap["candidate_search_complete"]
    assert cap["shortlist"] == [] and cap["error"]
    expansion = run(tmp_path / "expand", Settings(max_expansions=1), make_plot=False)
    assert expansion["status"] == "search_budget_exceeded"


@pytest.mark.parametrize("kwargs", [{"speed_kmh": 0}, {"headway": float("nan")}, {"delay_max": -1},
                                  {"transfer_buffer": -1}, {"day": "holiday"}, {"departure": "24:00"},
                                  {"max_candidates": 0}, {"max_transfers": -1}])
def test_invalid_settings(kwargs):
    with pytest.raises(ValueError):
        Settings(**kwargs)


def test_shortlist_dedup_does_not_modify_candidate_pool(report):
    records = deepcopy(report["candidates"])
    original = deepcopy(records)
    shown = shortlist(records)
    assert records == original
    eligible = [r for r in records if r["recommendable"]]
    fastest = min(eligible, key=lambda r: (r["estimated_total_minutes"], r["transfers"], r["id"]))
    assert fastest["id"] in {f["representative_id"] for f in shown}
    assert len(shortlist(records, limit=1)) == 1

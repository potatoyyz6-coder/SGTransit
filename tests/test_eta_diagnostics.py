from datetime import timedelta
import json
import shutil
import urllib.request

import pytest

from experiments.analyze_eta_window import replay_groups, reverse_search_audit, validate_outcome
from experiments.match_eta_pilot import ROOT
from data.real.build_subset import load_rows
from sg_transit.eta_diagnostics import distribution, revision_diagnostics, snapshot_at, waiting_probe
from sg_transit.eta_matching import build_associations, instant


START = instant("2026-10-07T10:00:00+08:00")


def row(seconds=0, stop="A", status="ok", predictions=()):
    return {"type": "observation", "received_at": (START + timedelta(seconds=seconds)).isoformat(),
            "status": status, "bus_stop_code": stop,
            "arrivals": [{"service_no": service, "estimated_arrival": (START + timedelta(seconds=eta)).isoformat(),
                          "monitored": monitored, "latitude": 1.3, "longitude": 103.77,
                          "origin_code": "X", "destination_code": "Y", "visit_number": "1",
                          "arrival_slot": "NextBus"} for service, eta, monitored in predictions]}


def test_snapshot_never_uses_future_or_hides_latest_error():
    rows = [("a", row(-30)), ("b", row(0, status="error")), ("c", row(1))]
    assert snapshot_at(rows, "A", START)["status"] == "error"
    assert snapshot_at(rows[:1], "A", START - timedelta(seconds=31))["status"] == "missing"
    assert snapshot_at(rows[:1], "A", START + timedelta(seconds=61))["status"] == "stale"
    assert snapshot_at(rows[:1], "A", START + timedelta(seconds=60))["status"] == "available"


def test_probe_monitored_flags_separated_and_threshold_inclusive():
    rows = [("a", row(predictions=[("61", 600, True), ("52", 180, True), ("75", 60, False)]))]
    fixed = waiting_probe(rows, "A", START, ["61"], monitored=True)
    multi = waiting_probe(rows, "A", START, ["61", "52", "75"], monitored=True)
    assert fixed["predicted_wait_minutes"] == 10
    assert multi["predicted_wait_minutes"] == 3
    assert multi["slack_after_buffer_minutes"] == 0
    assert multi["selected_service"] == "52"
    unmon = waiting_probe(rows, "A", START, ["61", "52", "75"], monitored=False)
    assert unmon["predicted_wait_minutes"] is None


def test_connection_probe_uses_incoming_eta_not_current_time():
    rows = [("a", row(predictions=[("151", 300, True), ("61", 301, True), ("52", 500, True)]))]
    fixed = waiting_probe(rows, "A", START, ["61"], monitored=True, incoming_service="151")
    multi = waiting_probe(rows, "A", START, ["61", "52"], monitored=True, incoming_service="151")
    assert fixed["status"] == "no_eligible_prediction"
    assert fixed["predicted_wait_minutes"] is None
    assert multi["predicted_wait_minutes"] == pytest.approx(200 / 60)
    assert multi["slack_after_buffer_minutes"] == pytest.approx(20 / 60)
    assert waiting_probe(rows, "A", START, ["61"], monitored=False, incoming_service="151")["status"] == "no_incoming_prediction"


def test_probe_is_prefix_invariant_and_missing_is_not_infinity():
    past = [("a", row(predictions=[("61", 600, True)]))]
    future = past + [("b", row(1, predictions=[("61", 180, True)]))]
    assert waiting_probe(past, "A", START, ["61"], monitored=True) == waiting_probe(future, "A", START, ["61"], monitored=True)
    assert waiting_probe([], "A", START, ["61"], monitored=True)["predicted_wait_minutes"] is None
    with pytest.raises(ValueError):
        waiting_probe([], "A", START, [], monitored=True, buffer_seconds=-1)


def test_revisions_are_absolute_eta_changes_not_countdown_and_not_slots():
    rows = [("a", row(predictions=[("61", 600, True)])),
            ("b", row(60, predictions=[("61", 620, True)]))]
    rows[1][1]["arrivals"][0]["arrival_slot"] = "NextBus2"
    result = revision_diagnostics(build_associations(rows, []))
    assert result["groups"][0]["signed_seconds"]["mean"] == 20
    assert result["evidence"][0]["revision_seconds"] == 20
    rows[1][1]["arrivals"][0]["monitored"] = False
    assert revision_diagnostics(build_associations(rows, []))["groups"] == []


def test_quantiles_empty_and_nearest_rank():
    assert distribution([])["mean"] is None
    assert distribution([1, 2, 3, 4])["p50"] == 2
    assert distribution([1, 2, 3, 4])["p95"] == 4


def test_replay_pool_preserves_fixed_paths_and_same_vehicle_continuation():
    stops = {"16189", "12061", "12071", "42141", "42071", "11401", "11261", "42171"}
    groups, network, routes = replay_groups(load_rows(ROOT / "data/real/raw/BusRoutes.csv"), stops)
    assert groups["first_eligible"] == groups["stationary_suffix"]
    for name, paths in groups.items():
        if name.startswith("fixed"):
            assert all(p in groups["first_eligible"] for p in paths)
    assert len(routes) > 3
    assert "fixed_151_walk_174" not in groups
    path = groups["fixed_151_61_blk109"][0]
    assert any(a.service == b.service == "61" and a.end == b.start == "42071"
               for a, b in zip(path, path[1:]))
    assert all(a.start in stops and a.end in stops for p in groups["first_eligible"] for a in p)
    search = reverse_search_audit(network)
    assert search["full_routes"] == 21
    assert search["bounded_routes"] == 18
    assert len(search["missed_routes"]) == 3
    assert search["truncated"] and search["truncation_reasons"]
    assert search["selected_hubs"] == ["42071"]
    assert search["both_searches_use_reverse_ride_bounds"]
    assert search["changes_replay_candidates"] is False


def test_output_audit_rejects_unknown_scores_and_bad_time_accounting():
    class EmptyTape:
        entries = {}
    unknown = {"actual_outcome": "unknown", "status": "unknown", "duration_minutes": None,
               "long_transfer_wait": None, "events": []}
    validate_outcome(unknown, EmptyTape())
    with pytest.raises(AssertionError):
        validate_outcome({**unknown, "duration_minutes": 10}, EmptyTape())
    with pytest.raises(AssertionError):
        validate_outcome({**unknown, "status": "modeled_complete", "duration_minutes": 10,
                          "prefix_wait_minutes": 1, "prefix_ride_minutes": 2, "prefix_walk_minutes": 0}, EmptyTape())


def test_offline_runner_reproducible_and_preserves_unknowns(tmp_path, monkeypatch):
    import experiments.analyze_eta_window as experiment

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline experiment made a network call")
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    topology = tmp_path / "data/real/raw/BusRoutes.csv"
    topology.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "data/real/raw/BusRoutes.csv", topology)
    monkeypatch.setattr(experiment, "ROOT", tmp_path)
    stops = ["16189", "12061", "12071", "42141", "42071", "11401", "11261", "42171"]
    records = [{"type": "metadata", "source": "synthetic empty fixture", "endpoint": "none",
                "started_at": START.isoformat(), "deadline": (START + timedelta(hours=2)).isoformat(),
                "processing": "test fixture"}]
    records += [row(-10 + i, stop=s) for i, s in enumerate(stops)]
    records += [{"type": "completion", "requests": 8, "successful_requests": 8, "status": "request_budget"}]
    raw = tmp_path / "input.jsonl"
    raw.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"raw_output": "input.jsonl", "stops": stops,
                                  "departures": [START.isoformat()]}), encoding="utf-8")
    before = raw.read_bytes(), config.read_bytes(), topology.read_bytes()
    first = experiment.run(config, tmp_path / "one")
    second = experiment.run(config, tmp_path / "two")
    assert first == second
    assert (raw.read_bytes(), config.read_bytes(), topology.read_bytes()) == before
    assert len(first["runs"]) == 45
    assert all(r["result"]["duration_minutes"] is None for r in first["runs"])
    assert all(c["status"] == "available" for c in first["query_checks"])
    for name in ("analysis.json", "analysis.md", "replay.csv"):
        assert (tmp_path / "one" / name).read_bytes() == (tmp_path / "two" / name).read_bytes()
    records[-1]["requests"] = 9
    raw.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    with pytest.raises(ValueError, match="completion"):
        experiment.run(config, tmp_path / "bad")

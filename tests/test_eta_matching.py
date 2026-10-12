from dataclasses import replace

import pytest

from sg_transit.eta_matching import (
    Entry, MatchParameters, associate, build_associations, instant, parse_entries, follow_temporal,
)


def entry(id="a", stop="A", time="14:30:00", eta="14:40:00", **kwargs):
    base = Entry(id, stop, "151", "X", "Y", "1", instant(f"2026-10-04T{time}+08:00"),
                 instant(f"2026-10-04T{eta}+08:00"), 1.3, 103.77, "NextBus")
    return replace(base, **kwargs)


def record(stop, time, eta, slot="NextBus", **arrival):
    return {"type": "observation", "status": "ok", "bus_stop_code": stop,
            "received_at": f"2026-10-04T{time}+08:00", "arrivals": [{
                "service_no": "151", "origin_code": "X", "destination_code": "Y",
                "visit_number": "1", "monitored": True, "latitude": 1.3,
                "longitude": 103.77, "estimated_arrival": f"2026-10-04T{eta}+08:00",
                "arrival_slot": slot, **arrival}]}


def test_cross_match_ignores_rank():
    result = associate([entry()], [entry("b", "B", "14:30:02", "14:45:00", slot="NextBus3")], "cross_stop")
    assert len(result["accepted"]) == 1
    assert result["accepted"][0]["eta_delta_seconds"] == 300
    assert result["accepted"][0]["available_at"].endswith("14:30:02+08:00")


@pytest.mark.parametrize("other", [entry("b", "B", "14:30:10", "14:45:00"),
    entry("b", "B", eta="14:39:00"), entry("b", "B", destination="Z"),
    entry("b", "B", visit="2"), entry("b", "B", latitude=1.4)])
def test_cross_match_rejects_wrong_direction_time_position_or_order(other):
    assert not associate([entry()], [other], "cross_stop")["accepted"]


def test_colocated_buses_are_ambiguous_not_arbitrarily_assigned():
    result = associate([entry(), entry("a2")], [entry("b", "B")], "cross_stop")
    assert not result["accepted"]
    assert len(result["ambiguous_candidates"]) == 2


def test_temporal_match_and_gap():
    assert associate([entry()], [entry("b", time="14:31:00")], "temporal")["accepted"]
    assert not associate([entry()], [entry("b", time="14:32:00")], "temporal")["accepted"]
    assert not associate([entry()], [entry("b", time="14:31:00", eta="14:43:00")], "temporal")["accepted"]


@pytest.mark.parametrize("change", [{"monitored": False}, {"latitude": 0, "longitude": 0},
    {"latitude": float("nan")}, {"estimated_arrival": ""}, {"origin_code": ""}])
def test_bad_observations_are_not_identity_evidence(change):
    entries, reasons = parse_entries(record("A", "14:30:00", "14:40:00", **change), "row:1")
    assert not entries
    assert sum(reasons.values()) == 1


def test_stream_is_prefix_invariant_and_causal():
    rows = [("1", record("A", "14:30:00", "14:40:00")),
            ("2", record("B", "14:30:02", "14:45:00")),
            ("3", record("A", "14:31:00", "14:40:10"))]
    pairs = [("151", "A", "B")]
    cutoff = instant("2026-10-04T14:30:03+08:00")
    prefix = build_associations(rows[:2], pairs)
    capped = build_associations(rows, pairs, cutoff=cutoff)
    assert prefix == capped
    full = build_associations(rows, pairs)
    assert all(e in full["accepted"] for e in prefix["accepted"])


def test_error_breaks_temporal_link():
    rows = [("1", record("A", "14:30:00", "14:40:00")),
            ("2", {"status": "error", "bus_stop_code": "A", "received_at": "2026-10-04T14:30:30+08:00"}),
            ("3", record("A", "14:31:00", "14:40:00"))]
    assert not build_associations(rows, []) ["accepted"]


def test_bad_thresholds():
    with pytest.raises(ValueError):
        MatchParameters(cross_distance_m=float("inf"))


def test_trace_does_not_use_future_links_or_promote_eta_to_actual_arrival():
    rows = [("1", record("A", "14:30:00", "14:40:00")),
            ("2", record("A", "14:31:00", "14:40:20"))]
    result = build_associations(rows, [])
    early = follow_temporal(result, "1:0", instant("2026-10-04T14:30:30+08:00"))
    late = follow_temporal(result, "1:0", instant("2026-10-04T14:32:00+08:00"))
    assert early == {"status": "no_successor_in_prefix", "entry_ids": ["1:0"]}
    assert late == {"status": "no_successor_in_prefix", "entry_ids": ["1:0", "2:0"]}
    assert follow_temporal(result, "2:0", instant("2026-10-04T14:30:30+08:00"))["entry_ids"] == []


def test_trace_stops_at_ambiguous_bunching():
    second = record("A", "14:31:00", "14:40:00")
    second["arrivals"].append(dict(second["arrivals"][0], arrival_slot="NextBus2"))
    result = build_associations([("1", record("A", "14:30:00", "14:40:00")), ("2", second)], [])
    assert follow_temporal(result, "1:0", instant("2026-10-04T14:32:00+08:00")) == {
        "status": "ambiguous", "entry_ids": ["1:0"]}

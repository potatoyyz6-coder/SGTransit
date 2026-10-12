from datetime import timedelta

import pytest

from sg_transit.eta_matching import build_associations, instant
from sg_transit.eta_replay import ReplayLimits, Ride, Tape, Walk, replay

START = instant("2026-10-04T14:30:00+08:00")


def row(stop, received, arrivals):
    return {"type": "observation", "status": "ok", "bus_stop_code": stop,
            "received_at": (START + timedelta(seconds=received)).isoformat(),
            "arrivals": [{"service_no": service, "origin_code": "X", "destination_code": "Y",
                          "visit_number": "1", "monitored": True, "latitude": latitude,
                          "longitude": 103.77, "arrival_slot": "NextBus",
                          "estimated_arrival": (START + timedelta(seconds=eta)).isoformat()}
                         for service, eta, latitude in arrivals]}


def tape(rows, pairs):
    snapshots = [(str(i), r) for i, r in enumerate(rows)]
    return Tape(snapshots, build_associations(snapshots, pairs))


def direct_rows():
    return [row("A", 0, [("1", 20, 1.3)]), row("B", 1, [("1", 40, 1.3)]),
            row("A", 120, []), row("B", 121, [])]


def test_direct_conditional_trip_and_accounting():
    result = replay(tape(direct_rows(), [("1", "A", "B")]), [[Ride("1", "A", "B")]], START)
    assert result["status"] == "modeled_complete"
    assert result["actual_outcome"] == "unknown"
    assert result["duration_minutes"] == pytest.approx(40 / 60)
    assert result["prefix_wait_minutes"] + result["prefix_ride_minutes"] == pytest.approx(40 / 60)
    assert result["events"][0]["evidence_received_at"] <= result["events"][0]["at"]


def test_new_observation_before_boarding_revises_decision():
    rows = direct_rows()[:2] + [row("A", 10, [("1", 35, 1.3)]),
            row("B", 11, [("1", 55, 1.3)])] + direct_rows()[2:]
    result = replay(tape(rows, [("1", "A", "B")]), [[Ride("1", "A", "B")]], START)
    assert result["duration_minutes"] == pytest.approx(55 / 60)
    assert result["events"][0]["at"] == (START + timedelta(seconds=35)).isoformat()


def test_future_observation_cannot_change_earlier_boarding():
    baseline = replay(tape(direct_rows(), [("1", "A", "B")]), [[Ride("1", "A", "B")]], START)
    rows = direct_rows() + [row("A", 50, [("1", 100, 1.4)])]
    result = replay(tape(rows, [("1", "A", "B")]), [[Ride("1", "A", "B")]], START)
    assert result == baseline


def test_identity_loss_during_ride_is_unknown_not_imputed_arrival():
    rows = direct_rows()[:2] + [row("B", 30, [])] + direct_rows()[2:]
    result = replay(tape(rows, [("1", "A", "B")]), [[Ride("1", "A", "B")]], START)
    assert result["status"] == "missing_or_stale_vehicle"
    assert result["duration_minutes"] is None
    assert result["long_transfer_wait_over_10min"] is None


def test_ambiguity_during_ride_is_unknown():
    rows = direct_rows()[:2] + [row("B", 30, [("1", 40, 1.3), ("1", 45, 1.3)])] + direct_rows()[2:]
    result = replay(tape(rows, [("1", "A", "B")]), [[Ride("1", "A", "B")]], START)
    assert result["status"] == "ambiguous_identity"


def transfer_tape():
    rows = [row("A", 0, [("1", 20, 1.3)]),
            row("B", 1, [("1", 40, 1.3), ("2", 60, 1.4), ("3", 55, 1.5)]),
            row("C", 2, [("2", 80, 1.4), ("3", 85, 1.5)]), row("C", 120, [])]
    return tape(rows, [("1", "A", "B"), ("2", "B", "C"), ("3", "B", "C")])


def test_legal_transfer_with_buffer_and_alternative():
    paths = [[Ride("1", "A", "B"), Ride(s, "B", "C")] for s in ("2", "3")]
    result = replay(transfer_tape(), paths, START, limits=ReplayLimits(transfer_seconds=10))
    assert result["status"] == "modeled_complete"
    assert result["transfer_count"] == 1
    assert [e["service"] for e in result["events"] if e["kind"] == "modeled_board"] == ["1", "3"]
    assert result["duration_minutes"] == pytest.approx(85 / 60)
    assert result["prefix_wait_minutes"] + result["prefix_ride_minutes"] == pytest.approx(85 / 60)


def test_tight_connection_not_boarded_and_transfer_limit():
    paths = [[Ride("1", "A", "B"), Ride("2", "B", "C")]]
    result = replay(transfer_tape(), paths, START, limits=ReplayLimits(transfer_seconds=30))
    assert result["duration_minutes"] is None
    assert result["transfer_count"] == 0
    limited = replay(transfer_tape(), paths, START, limits=ReplayLimits(transfer_seconds=10, max_transfers=0))
    assert limited["duration_minutes"] is None


def test_same_vehicle_continuation_is_not_another_wait_or_transfer():
    rows = [row("A", 0, [("1", 20, 1.3)]), row("B", 1, [("1", 40, 1.3)]),
            row("C", 2, [("1", 60, 1.3)]), row("C", 120, [])]
    result = replay(tape(rows, [("1", "A", "B"), ("1", "B", "C")]),
                    [[Ride("1", "A", "B"), Ride("1", "B", "C")]], START)
    assert result["status"] == "modeled_complete"
    assert result["transfer_count"] == 0
    assert result["prefix_wait_minutes"] == pytest.approx(20 / 60)
    assert sum(e["kind"] == "modeled_board" for e in result["events"]) == 1
    assert any(e["kind"] == "stay_onboard" for e in result["events"])


def test_walk_is_counted_once_and_cannot_teleport():
    rows = [row("A", 0, [("1", 20, 1.3)]), row("B", 1, [("1", 40, 1.3)]),
            row("D", 2, [("2", 70, 1.4)]), row("C", 3, [("2", 80, 1.4)]), row("C", 120, [])]
    result = replay(tape(rows, [("1", "A", "B"), ("2", "D", "C")]),
                    [[Ride("1", "A", "B"), Walk("B", "D", 0.25), Ride("2", "D", "C")]],
                    START, limits=ReplayLimits(transfer_seconds=10))
    assert result["status"] == "modeled_complete"
    assert result["prefix_walk_minutes"] == 0.25
    assert sum(result[k] for k in ("prefix_walk_minutes", "prefix_wait_minutes", "prefix_ride_minutes")) == pytest.approx(80 / 60)


def test_trip_limit_and_capture_end_censor():
    short = replay(tape(direct_rows(), [("1", "A", "B")]), [[Ride("1", "A", "B")]], START,
                   limits=ReplayLimits(max_trip_seconds=30))
    assert short["duration_minutes"] is None
    clipped = replay(tape(direct_rows()[:2], [("1", "A", "B")]), [[Ride("1", "A", "B")]], START)
    assert clipped["duration_minutes"] is None


def test_forecast_crossing_poll_time_is_unknown_not_a_longer_wait():
    rows = direct_rows()[:2] + [row("A", 10, [("1", 9, 1.3)]),
            row("B", 11, [("1", 40, 1.3)])] + direct_rows()[2:]
    result = replay(tape(rows, [("1", "A", "B")]), [[Ride("1", "A", "B")]], START)
    assert result["status"] == "boarding_between_polls_unknown"
    assert result["duration_minutes"] is None


def test_unmatched_earlier_bus_not_silently_replaced_with_later_matched_one():
    rows = [row("A", 0, [("1", 10, 1.4), ("1", 20, 1.3)]),
            row("B", 1, [("1", 40, 1.3)]), row("B", 120, [])]
    result = replay(tape(rows, [("1", "A", "B")]), [[Ride("1", "A", "B")]], START)
    assert result["status"] == "earlier_boarding_without_cross_stop_evidence"
    assert not any(e["kind"] == "modeled_board" for e in result["events"])


def test_no_reboarding_same_service_after_walk():
    rows = [row("A", 0, [("1", 20, 1.3)]), row("B", 1, [("1", 40, 1.3)]),
            row("D", 2, [("1", 70, 1.4)]), row("C", 3, [("1", 80, 1.4)]), row("C", 120, [])]
    result = replay(tape(rows, [("1", "A", "B"), ("1", "D", "C")]),
                    [[Ride("1", "A", "B"), Walk("B", "D", 0.25), Ride("1", "D", "C")]],
                    START, limits=ReplayLimits(transfer_seconds=10))
    assert result["duration_minutes"] is None
    assert sum(e["kind"] == "modeled_board" for e in result["events"]) == 1


def test_continuation_preserves_earlier_bridge_with_independent_position_updates():
    rows = [row("A", 0, [("1", 20, 1.3)]), row("B", 1, [("1", 40, 1.3)]),
            row("C", 2, [("1", 60, 1.3)]), row("B", 30, [("1", 40, 1.3004)]),
            row("C", 31, [("1", 60, 1.3008)]), row("C", 120, [])]
    result = replay(tape(rows, [("1", "A", "B"), ("1", "B", "C")]),
        [[Ride("1", "A", "B"), Ride("1", "B", "C")]], START)
    assert result["status"] == "modeled_complete"
    continued = next(e for e in result["events"] if e["kind"] == "stay_onboard")
    bridge = continued["association_bridge"]
    assert bridge["cross_source"] != bridge["source_current"]
    assert instant(bridge["cross_available_at"]) <= instant(continued["at"])
    assert result["transfer_count"] == 0
    assert result["prefix_wait_minutes"] == pytest.approx(20 / 60)


def test_ambiguous_downstream_bridge_does_not_allow_same_service_reboarding():
    rows = [row("A", 0, [("1", 20, 1.3)]), row("B", 1, [("1", 40, 1.3)]),
            row("C", 2, [("1", 60, 1.3)]), row("B", 30, [("1", 40, 1.3004)]),
            row("C", 31, [("1", 60, 1.3008), ("1", 65, 1.30081)]), row("C", 120, [])]
    result = replay(tape(rows, [("1", "A", "B"), ("1", "B", "C")]),
        [[Ride("1", "A", "B"), Ride("1", "B", "C")]], START)
    assert result["status"] == "onboard_continuation_unknown"
    assert sum(e["kind"] == "modeled_board" for e in result["events"]) == 1


def test_equal_time_unmatched_candidate_is_not_hidden_by_matched_candidate():
    rows = [row("A", 0, [("1", 20, 1.4), ("1", 20, 1.3)]),
            row("B", 1, [("1", 40, 1.3)]), row("B", 120, [])]
    result = replay(tape(rows, [("1", "A", "B")]), [[Ride("1", "A", "B")]], START)
    assert result["status"] == "earlier_boarding_without_cross_stop_evidence"


def test_long_wait_threshold_is_configurable_and_unknown_stays_unknown():
    paths = [[Ride("1", "A", "B"), Ride("2", "B", "C")]]
    short = replay(transfer_tape(), paths, START,
                   limits=ReplayLimits(transfer_seconds=10, long_wait_seconds=15))
    assert short["long_transfer_wait"] is True
    assert short["max_transfer_wait_minutes"] == pytest.approx(20 / 60)
    equal = replay(transfer_tape(), paths, START,
                   limits=ReplayLimits(transfer_seconds=10, long_wait_seconds=20))
    assert equal["long_transfer_wait"] is False
    missing = replay(transfer_tape(), paths, START,
                     limits=ReplayLimits(transfer_seconds=40, long_wait_seconds=0))
    assert missing["long_transfer_wait"] is None

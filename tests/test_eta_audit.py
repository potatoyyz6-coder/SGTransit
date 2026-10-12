import pytest

from experiments.audit_eta_pilot import as_of, coverage, timestamp


def row(at, eta="2026-10-04T14:40:00+08:00", **extra):
    return {"type": "observation", "status": "ok", "bus_stop_code": "16189",
            "received_at": f"2026-10-04T{at}+08:00",
            "arrivals": [{"service_no": "151", "estimated_arrival": eta,
                          "monitored": False}], **extra}


def test_as_of_never_uses_future_response():
    result = as_of([row("14:29:42"), row("14:30:01")], "16189",
                   timestamp("2026-10-04T14:30:00+08:00"), ["151"])
    assert result["age_seconds"] == 18
    assert result["predictions"][0]["predicted_minutes_from_decision"] == 10
    assert result["predictions"][0]["monitored"] is False


def test_past_prediction_not_boardable_and_invalid_is_not_zero_wait():
    record = row("14:29:42", "2026-10-04T14:29:49+08:00")
    record["arrivals"].append({"service_no": "151", "estimated_arrival": ""})
    result = as_of([record], "16189", timestamp("2026-10-04T14:30:00+08:00"), ["151"])
    assert not result["predictions"]
    assert result["past_eta_entries_excluded"] == 1
    assert result["invalid_eta_entries"] == 1


def test_stale_and_missing_observations():
    decision = timestamp("2026-10-04T14:30:00+08:00")
    assert as_of([row("14:28:00")], "16189", decision, ["151"])["status"] == "stale"
    assert as_of([row("14:30:01")], "16189", decision, ["151"])["status"] == "missing"


def test_coverage_separates_errors_and_gaps():
    result = coverage([row("14:29:00"), row("14:31:00"),
                       row("14:32:00", status="error")])[0]
    assert result["successful_requests"] == 2
    assert result["failed_requests"] == 1
    assert result["max_gap_seconds"] == 120
    assert result["gaps_over_90_seconds"] == 1


def test_naive_timestamp_rejected():
    with pytest.raises(ValueError):
        timestamp("2026-10-04T14:30:00")

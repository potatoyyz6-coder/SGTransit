import json
from datetime import datetime, timedelta, timezone

import pytest

from sg_transit.eta_pilot import collect_pilot
from sg_transit.lta import LTAApiError, LTABusArrivalProvider, parse_bus_arrival_response


class Clock:
    seconds = 0.0

    def now(self):
        return datetime(2026, 10, 4, tzinfo=timezone.utc) + timedelta(seconds=self.seconds)

    def monotonic(self):
        return self.seconds

    def sleep(self, seconds):
        self.seconds += seconds


def run(tmp_path, transport, **kwargs):
    clock = Clock()
    output = tmp_path / "pilot.jsonl"
    provider = LTABusArrivalProvider("test-secret", transport=transport)
    result = collect_pilot(provider, ["16189", "12071"], output,
                           clock.now() + timedelta(seconds=121), now=clock.now,
                           monotonic=clock.monotonic, sleep=clock.sleep, **kwargs)
    return result, [json.loads(line) for line in output.read_text().splitlines()]


def test_pilot_deadline_and_request_timestamps(tmp_path):
    result, records = run(tmp_path, lambda *args: b'{"Services": []}')
    assert result["status"] == "deadline"
    assert result["requests"] == 6
    observations = [r for r in records if r["type"] == "observation"]
    assert all(r["status"] == "ok" for r in observations)
    assert observations[0]["requested_at"] != observations[2]["requested_at"]
    assert records[-1]["type"] == "completion"
    assert "test-secret" not in json.dumps(records)


def test_pilot_budget(tmp_path):
    result, _ = run(tmp_path, lambda *args: b'{"Services": []}', max_requests=3)
    assert result["status"] == "request_budget"
    assert result["requests"] == 3


def test_api_failure_stops_without_retry_or_secret_log(tmp_path):
    def fail(*args):
        raise LTAApiError("test-secret must never be logged")

    result, records = run(tmp_path, fail)
    assert result["status"] == "api_error"
    assert result["requests"] == 1
    assert "test-secret" not in json.dumps(records)


def test_pilot_exclusive_output(tmp_path):
    output = tmp_path / "pilot.jsonl"
    output.write_text("existing")
    with pytest.raises(FileExistsError):
        run(tmp_path, lambda *args: pytest.fail("Must not request"))
    assert output.read_text() == "existing"


def test_stop_file_prevents_requests(tmp_path):
    (tmp_path / "pilot.stop").touch()
    result, _ = run(tmp_path, lambda *args: pytest.fail("Must not request"))
    assert result["status"] == "user_stop"
    assert result["requests"] == 0


@pytest.mark.parametrize("interval", [0, 59, float("nan"), float("inf")])
def test_invalid_interval_never_calls_api(tmp_path, interval):
    with pytest.raises(ValueError):
        run(tmp_path, lambda *args: pytest.fail("Must not request"), interval=interval)


def test_retains_slot_without_treating_as_identity():
    arrivals = parse_bus_arrival_response({"Services": [{"ServiceNo": "151",
        "NextBus2": {"EstimatedArrival": "2026-10-04T13:03:00+08:00"}}]})
    assert arrivals[0].arrival_slot == "NextBus2"

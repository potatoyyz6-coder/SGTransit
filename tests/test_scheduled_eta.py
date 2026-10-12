import json
from datetime import datetime, timedelta, timezone

import pytest

from experiments.scheduled_eta import index_departures, run_window, validate
from sg_transit.lta import LTABusArrivalProvider


class Clock:
    seconds = 0

    def now(self):
        return datetime(2026, 10, 7, tzinfo=timezone.utc) + timedelta(seconds=self.seconds)

    def sleep(self, seconds):
        self.seconds += seconds

    def monotonic(self):
        return self.seconds


def plan(clock):
    stamp = lambda seconds: (clock.now() + timedelta(seconds=seconds)).isoformat()
    return {"start": stamp(60), "until": stamp(181), "departures": [stamp(70), stamp(150)],
            "stops": ["16189", "12061"], "interval_seconds": 60, "max_requests": 6,
            "start_grace_seconds": 90, "raw_output": "data/recorded/raw/test.jsonl",
            "query_index_output": "data/recorded/cleaned/test.json"}


def test_schedule_waits_then_stops_and_indexes_past_only(tmp_path):
    clock = Clock()
    p = plan(clock)
    requests = []
    def transport(*args):
        requests.append(clock.seconds)
        return b'{"Services": []}'
    result = run_window(p, root=tmp_path, provider_factory=lambda: LTABusArrivalProvider("secret", transport=transport),
                        now=clock.now, sleep=clock.sleep, monotonic=clock.monotonic)
    assert result["requests"] == 6
    assert min(requests) == 60 and max(requests) == 180
    assert clock.seconds <= 181
    data = json.loads((tmp_path / p["query_index_output"]).read_text())
    assert len(data["queries"]) == 2
    for query in data["queries"]:
        for state in query["stops"].values():
            assert datetime.fromisoformat(state["received_at"]) <= datetime.fromisoformat(query["departure"])
    assert "secret" not in (tmp_path / p["raw_output"]).read_text()


def test_sleeping_past_start_does_not_collect(tmp_path):
    clock = Clock()
    p = plan(clock)
    clock.seconds = 151
    def forbidden(*args):
        pytest.fail("Should not call API")
    result = run_window(p, root=tmp_path, provider_factory=lambda: LTABusArrivalProvider("secret", transport=forbidden), now=clock.now)
    assert result == {"status": "missed_start", "requests": 0}
    assert not (tmp_path / p["raw_output"]).exists()


def test_failure_logs_do_not_contain_sensitive_exception(tmp_path):
    clock = Clock()
    p = plan(clock)
    def fail():
        raise ValueError("secret-key-must-not-appear")
    result = run_window(p, root=tmp_path, provider_factory=fail, now=clock.now)
    assert result["status"] == "failed"
    log = (tmp_path / p["raw_output"]).with_suffix(".schedule.jsonl")
    assert "secret-key" not in log.read_text()
    with pytest.raises(FileExistsError):
        run_window(p, root=tmp_path, provider_factory=fail, now=clock.now)


def test_stop_before_start_issues_no_requests(tmp_path):
    clock = Clock()
    p = plan(clock)
    control = (tmp_path / p["raw_output"]).with_suffix(".stop")
    control.parent.mkdir(parents=True)
    control.touch()
    result = run_window(p, root=tmp_path, provider_factory=lambda: None, now=clock.now)
    assert result["status"] == "user_stop_before_start"


def test_bad_window_and_output_escape_rejected(tmp_path):
    clock = Clock()
    p = plan(clock)
    p["max_requests"] = 1201
    with pytest.raises(ValueError):
        validate(p)
    p = plan(clock)
    p["raw_output"] = "outside.jsonl"
    with pytest.raises(ValueError):
        run_window(p, root=tmp_path)


def test_error_or_stale_at_departure_not_replaced_by_future_good_record(tmp_path):
    clock = Clock()
    p = plan(clock)
    raw = tmp_path / "raw.jsonl"
    rows = []
    for seconds, status in ((50, "ok"), (65, "error"), (71, "ok")):
        rows.append({"type": "observation", "bus_stop_code": "16189", "status": status,
                     "received_at": (clock.now()+timedelta(seconds=seconds)).isoformat()})
    raw.write_text("\n".join(json.dumps(r) for r in rows)+"\n")
    result = index_departures(p, raw, tmp_path / "index.json")
    assert result[0]["stops"]["16189"]["source_line"] == 2
    assert not result[0]["stops"]["16189"]["usable"]
    assert not result[0]["stops"]["12061"]["usable"]

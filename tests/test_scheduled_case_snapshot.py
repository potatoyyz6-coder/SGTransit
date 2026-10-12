from datetime import timedelta
import json

import pytest

from experiments.scheduled_case_snapshot import run_snapshot
from sg_transit.eta_matching import instant

START = instant("2026-10-08T11:20:00+08:00")


class Clock:
    def __init__(self, at=START):
        self.at = at
    def now(self):
        return self.at
    def sleep(self, seconds):
        self.at += timedelta(seconds=seconds)


class Provider:
    endpoint = "synthetic://no-network"
    def __init__(self, clock, fail=False, seconds=0):
        self.clock, self.fail, self.seconds, self.calls = clock, fail, seconds, []
    def fetch(self, stop):
        assert self.clock.now() >= START
        self.calls.append(stop)
        self.clock.sleep(self.seconds)
        if self.fail:
            raise RuntimeError("SECRET-MUST-NOT-APPEAR")
        return []


def test_wait_and_exactly_one_round(tmp_path):
    clock = Clock(START-timedelta(minutes=2))
    provider = Provider(clock, seconds=.1)
    output = tmp_path / "data/recorded/raw/snapshot.jsonl"
    result = run_snapshot(START, output, root=tmp_path, now=clock.now, sleep=clock.sleep, provider_factory=lambda: provider)
    assert result["status"] == "completed_single_round"
    assert result["requests"] == result["successful_requests"] == len(set(provider.calls)) == 25
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert rows[0]["scheduled_start"] == START.isoformat()
    assert rows[1]["bus_stop_code"] == "42161"
    assert rows[-1]["type"] == "completion"
    assert all(instant(r["received_at"]) >= instant(r["requested_at"]) >= START for r in rows[1:-1])
    with pytest.raises(FileExistsError):
        run_snapshot(START, output, root=tmp_path, now=clock.now, provider_factory=lambda: provider)
    assert len(provider.calls) == 25


def test_failure_stops_no_retry_or_secret_leak(tmp_path):
    clock = Clock()
    provider = Provider(clock, fail=True)
    output = tmp_path / "data/recorded/raw/snapshot.jsonl"
    result = run_snapshot(START, output, root=tmp_path, now=clock.now, provider_factory=lambda: provider)
    assert result["status"] == "api_error" and result["requests"] == 1
    assert result["successful_requests"] == 0
    assert "SECRET" not in output.read_text()+output.with_suffix(".schedule.jsonl").read_text()


def test_missed_start_cancellation_and_deadline(tmp_path):
    for case in ("late", "stop", "slow"):
        clock = Clock(START+timedelta(seconds=91) if case == "late" else START-timedelta(seconds=1))
        provider = Provider(clock, seconds=50 if case == "slow" else 0)
        output = tmp_path / f"data/recorded/raw/{case}.jsonl"
        if case == "stop":
            output.parent.mkdir(parents=True, exist_ok=True)
            output.with_suffix(".stop").touch()
        result = run_snapshot(START, output, root=tmp_path, now=clock.now, sleep=clock.sleep, provider_factory=lambda: provider)
        assert result["status"] == {"late": "missed_start", "stop": "user_stop_before_start", "slow": "deadline"}[case]
        assert len(provider.calls) == (3 if case == "slow" else 0)


def test_escape_and_distant_start_rejected(tmp_path):
    for start, output in ((START, tmp_path / "elsewhere.jsonl"),
                          (START+timedelta(days=2), tmp_path / "data/recorded/raw/later.jsonl")):
        with pytest.raises(ValueError):
            run_snapshot(start, output, root=tmp_path, now=lambda: START)

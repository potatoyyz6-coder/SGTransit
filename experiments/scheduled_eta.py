"""One bounded local ETA collection window; no recurring task or automatic retry."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time

from sg_transit.eta_pilot import collect_pilot
from sg_transit.lta import provider_from_environment

ROOT = Path(__file__).resolve().parents[1]


def instant(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Timezone-aware timestamps required")
    return result


def validate(plan):
    start, until = instant(plan["start"]), instant(plan["until"])
    if not 0 < (until - start).total_seconds() <= 7200:
        raise ValueError("Window must be positive and no longer than two hours")
    interval = plan["interval_seconds"]
    if not math.isfinite(interval) or interval < 60:
        raise ValueError("Minimum interval is 60 seconds")
    budget = plan["max_requests"]
    if not isinstance(budget, int) or not 1 <= budget <= 1200:
        raise ValueError("Request budget must be 1..1200")
    stops = plan["stops"]
    if not 1 <= len(stops) <= 12 or len(set(stops)) != len(stops):
        raise ValueError("Need 1..12 unique stops")
    if any(not isinstance(s, str) or len(s) != 5 or not s.isascii() or not s.isdigit() for s in stops):
        raise ValueError("Invalid stop codes")
    departures = [instant(t) for t in plan["departures"]]
    if not departures or departures != sorted(set(departures)) or any(not start <= t < until for t in departures):
        raise ValueError("Unique ordered departures must lie within the collection window")
    grace = plan["start_grace_seconds"]
    if not math.isfinite(grace) or not 0 <= grace <= 90:
        raise ValueError("Start grace must be 0..90 seconds")
    return start, until


def index_departures(plan, raw, output):
    """Index preserved forecasts causally; never interpret the last ETA as truth."""
    observations = []
    with raw.open(encoding="utf-8") as stream:
        for line, value in enumerate(stream, 1):
            row = json.loads(value)
            if row.get("type") == "observation":
                observations.append((instant(row["received_at"]), line, row))
    queries = []
    for stamp in plan["departures"]:
        when = instant(stamp)
        stops = {}
        for stop in plan["stops"]:
            candidates = [(t, line, row) for t, line, row in observations if t <= when and row["bus_stop_code"] == stop]
            if not candidates:
                stops[stop] = {"usable": False, "reason": "no_prior_response"}
                continue
            received, line, row = max(candidates, key=lambda item: (item[0], item[1]))
            age = (when - received).total_seconds()
            usable = row["status"] == "ok" and age <= 90
            stops[stop] = {"source_line": line, "received_at": received.isoformat(),
                           "age_seconds": age, "usable": usable,
                           "reason": "available" if usable else "stale_or_error"}
        queries.append({"departure": stamp, "stops": stops})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump({"raw_file": str(raw), "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                   "kind": "causal_response_index_not_actual_trip_outcomes", "queries": queries}, stream, indent=2)
    return queries


def run_window(plan, *, root=ROOT, provider_factory=None,
               now=lambda: datetime.now(timezone.utc), sleep=time.sleep, monotonic=time.monotonic):
    start, until = validate(plan)
    root = Path(root).resolve()
    raw = (root / plan["raw_output"]).resolve()
    cleaned = (root / plan["query_index_output"]).resolve()
    if not raw.is_relative_to(root / "data/recorded/raw") or not cleaned.is_relative_to(root / "data/recorded/cleaned"):
        raise ValueError("Outputs must remain in local raw/cleaned recording directories")
    if raw.exists() or cleaned.exists():
        raise FileExistsError("Existing recording or query index; no duplicate collection")
    if (start - now()).total_seconds() > 86400:
        raise ValueError("Scheduled start must be within one day")
    raw.parent.mkdir(parents=True, exist_ok=True)
    log = raw.with_suffix(".schedule.jsonl")
    stop = raw.with_suffix(".stop")
    with log.open("x", encoding="utf-8") as stream:
        def emit(status, **fields):
            stream.write(json.dumps({"status": status, "at": now().isoformat(), "pid": os.getpid(), **fields})+"\n")
            stream.flush()
            os.fsync(stream.fileno())
        emit("registered", plan=plan)
        try:
            # This checks credential presence locally; it does not authenticate yet.
            provider = (provider_factory or (lambda: provider_from_environment(timeout=8)))()
            while now() < start:
                if stop.exists():
                    emit("user_stop_before_start")
                    return {"status": "user_stop_before_start", "requests": 0}
                emit("waiting", scheduled_start=start.isoformat(), requests=0)
                sleep(min(30, max(0, (start-now()).total_seconds())))
            if (now()-start).total_seconds() > plan["start_grace_seconds"]:
                emit("missed_start", requests=0)
                return {"status": "missed_start", "requests": 0}
            emit("collecting", deadline=until.isoformat())
            result = collect_pilot(provider, plan["stops"], raw, until,
                                   interval=plan["interval_seconds"], max_requests=plan["max_requests"],
                                   now=now, sleep=sleep, monotonic=monotonic)
            emit("collection_finished", result=result)
            index_departures(plan, raw, cleaned)
            emit("finished", result=result, query_index=str(cleaned))
            return result
        except Exception as exc:
            # Never persist an exception message, traceback, key or request headers.
            emit("failed", error_type=type(exc).__name__)
            return {"status": "failed", "error_type": type(exc).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        result = run_window(plan)
    except Exception as exc:
        result = {"status": "failed_to_start", "error_type": type(exc).__name__}
    print(json.dumps(result), flush=True)
    return 0 if result["status"] in {"deadline", "request_budget", "user_stop", "user_stop_before_start"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

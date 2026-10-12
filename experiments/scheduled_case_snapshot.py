"""One scheduled, bounded 25-stop snapshot for the Blk 18 case. No retries."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time

from experiments.blk18_cde_case import ROOT, ORIGIN, build_network
from sg_transit.eta_matching import instant
from sg_transit.lta import provider_from_environment


def run_snapshot(start, output, *, root=ROOT, now=lambda: datetime.now(timezone.utc),
                 sleep=time.sleep, provider_factory=None):
    if start.tzinfo is None or (start-now()).total_seconds() > 86400:
        raise ValueError("Offset required; start must be within one day")
    root, output = Path(root).resolve(), Path(output).resolve()
    if not output.is_relative_to(root / "data/recorded/raw"):
        raise ValueError("Raw snapshot must stay in data/recorded/raw")
    network, _, _, provenance = build_network()
    stops = [ORIGIN] + sorted(set(network.stops)-{ORIGIN})
    if len(stops) != 25:
        raise ValueError("Snapshot approval covers exactly the 25-stop case")
    log, stop_file = output.with_suffix(".schedule.jsonl"), output.with_suffix(".stop")
    if output.exists() or log.exists():
        raise FileExistsError("Existing run; do not start a duplicate")
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {"status": "waiting", "requests": 0, "successful_requests": 0}
    deadline = start + timedelta(seconds=120)
    with log.open("x", encoding="utf-8") as journal:
        def log_event(status, **fields):
            journal.write(json.dumps({"status": status, "at": now().isoformat(), "pid": os.getpid(), **fields})+"\n")
            journal.flush()
            os.fsync(journal.fileno())
        log_event("registered", start=start.isoformat(), deadline=deadline.isoformat(),
                  stops=stops, max_requests=25, rounds=1, retry=False)
        try:
            provider = (provider_factory or (lambda: provider_from_environment(timeout=8)))()
            while now() < start:
                if stop_file.exists():
                    result["status"] = "user_stop_before_start"
                    log_event(result["status"], result=result)
                    return result
                log_event("waiting", requests=0)
                sleep(min(30, max(0, (start-now()).total_seconds())))
            if (now()-start).total_seconds() > 90:
                result["status"] = "missed_start"
                log_event(result["status"], result=result)
                return result
            with output.open("x", encoding="utf-8") as stream:
                def emit(row):
                    stream.write(json.dumps(row, allow_nan=False)+"\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                emit({"type": "metadata", "schema_version": 1, "source": "LTA DataMall BusArrival v3",
                      "endpoint": provider.endpoint, "started_at": now().isoformat(), "scheduled_start": start.isoformat(),
                      "deadline": deadline.isoformat(), "stops": stops, "max_requests": 25, "rounds": 1,
                      "pid": os.getpid(), "data_kind": "ETA_predictions_not_actual_arrivals",
                      "topology_provenance": provenance, "processing": "Existing parser; each stop once; slot is rank, not identity"})
                log_event("collecting")
                result["status"] = "completed_single_round"
                for code in stops:
                    if stop_file.exists() or now() >= deadline:
                        result["status"] = "user_stop" if stop_file.exists() else "deadline"
                        break
                    record = {"type": "observation", "bus_stop_code": code, "requested_at": now().isoformat()}
                    result["requests"] += 1
                    try:
                        arrivals = provider.fetch(code)
                    except Exception as exc:
                        emit({**record, "status": "error", "error_type": type(exc).__name__, "received_at": now().isoformat()})
                        result["status"] = "api_error"
                        break
                    emit({**record, "status": "ok", "received_at": now().isoformat(), "arrivals": [asdict(a) for a in arrivals]})
                    result["successful_requests"] += 1
                result["ended_at"] = now().isoformat()
                emit({"type": "completion", **result})
            log_event("finished", result=result)
        except Exception as exc:
            result["status"] = "failed"
            log_event("failed", error_type=type(exc).__name__, result=result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_snapshot(instant(args.start), args.output)
    except Exception as exc:
        result = {"status": "failed_to_start", "error_type": type(exc).__name__}
    print(json.dumps(result), flush=True)
    return 0 if result["status"] in {"completed_single_round", "user_stop", "user_stop_before_start"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Bounded, checkpointed ETA observations, not measured vehicle arrivals."""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .lta import LTABusArrivalProvider, provider_from_environment


def utc_now():
    return datetime.now(timezone.utc)


def collect_pilot(
    provider: LTABusArrivalProvider,
    stops: list[str],
    output: Path,
    until: datetime,
    *,
    interval: float = 60,
    max_requests: int = 1200,
    now=utc_now,
    monotonic=time.monotonic,
    sleep=time.sleep,
) -> dict:
    start = now()
    if until.tzinfo is None or not 0 < (until - start).total_seconds() <= 7200:
        raise ValueError("Deadline must be timezone-aware, future, and within two hours")
    if not math.isfinite(interval) or interval < 60:
        raise ValueError("Interval must be finite and at least 60 seconds")
    if not isinstance(max_requests, int) or not 1 <= max_requests <= 1200:
        raise ValueError("Request budget must be between 1 and 1200")
    if not stops or len(stops) > 12 or len(set(stops)) != len(stops):
        raise ValueError("Provide 1-12 distinct stops")
    if any(len(code) != 5 or not code.isascii() or not code.isdigit() for code in stops):
        raise ValueError("Stop codes must contain five ASCII digits")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    control = output.with_suffix(".stop")
    summary = {"status": "running", "requests": 0, "successful_requests": 0}
    # Exclusive creation prevents accidental overwrite or duplicate collectors.
    with output.open("x", encoding="utf-8") as stream:
        def emit(record):
            stream.write(json.dumps(record, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

        emit({
            "type": "metadata", "schema_version": 1,
            "source": "LTA DataMall BusArrival v3", "endpoint": provider.endpoint,
            "data_kind": "normalized_eta_predictions_not_actual_arrivals",
            "started_at": start.isoformat(), "deadline": until.isoformat(),
            "interval_seconds": interval, "max_requests": max_requests,
            "stops": stops, "pid": os.getpid(), "stop_file": str(control),
            "processing": "Existing parser; slot is response rank, not vehicle identity",
        })
        previous_requests = {}
        reason = "deadline"
        try:
            while now() < until and summary["requests"] < max_requests:
                round_start = monotonic()
                for code in stops:
                    if control.exists():
                        reason = "user_stop"
                        break
                    if now() >= until:
                        break
                    if summary["requests"] >= max_requests:
                        reason = "request_budget"
                        break
                    # Pace each stop independently, including after a slow round.
                    previous = previous_requests.get(code)
                    if previous is not None:
                        remaining = interval - (monotonic() - previous)
                        if remaining > 0:
                            sleep(min(remaining, max(0, (until - now()).total_seconds())))
                    if now() >= until or control.exists():
                        reason = "user_stop" if control.exists() else "deadline"
                        break
                    requested = now()
                    previous_requests[code] = monotonic()
                    summary["requests"] += 1
                    record = {"type": "observation", "bus_stop_code": code,
                              "requested_at": requested.isoformat()}
                    try:
                        arrivals = provider.fetch(code)
                    except Exception as exc:
                        # Error messages can contain request details; never persist them.
                        record.update(status="error", error_type=type(exc).__name__,
                                      received_at=now().isoformat())
                        emit(record)
                        reason = "api_error"
                        break
                    record.update(status="ok", received_at=now().isoformat(),
                                  arrivals=[asdict(item) for item in arrivals])
                    emit(record)
                    summary["successful_requests"] += 1
                if reason in {"api_error", "user_stop", "request_budget"}:
                    break
                if summary["requests"] >= max_requests:
                    reason = "request_budget"
                    break
                delay = min(max(0, interval - (monotonic() - round_start)),
                            max(0, (until - now()).total_seconds()))
                if delay:
                    sleep(delay)
        except KeyboardInterrupt:
            reason = "interrupted"
        except Exception:
            reason = "internal_error"
            raise
        finally:
            summary.update(status=reason, ended_at=now().isoformat())
            emit({"type": "completion", **summary})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stop", action="append", required=True)
    parser.add_argument("--until", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, default=1200)
    args = parser.parse_args()
    result = collect_pilot(provider_from_environment(timeout=8), args.stop, args.output,
                           datetime.fromisoformat(args.until), max_requests=args.max_requests)
    print(json.dumps(result))
    return 1 if result["status"] == "api_error" else 0


if __name__ == "__main__":
    raise SystemExit(main())

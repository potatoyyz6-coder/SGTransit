"""Offline coverage and as-of ETA audit; deliberately not a journey replay."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

SGT = timezone(timedelta(hours=8))


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Observation timestamps must include an offset")
    return parsed


def as_of(records, stop, decision, services, max_age_seconds=90):
    """Select only responses available at decision time; no nearest/future row."""
    candidates = [r for r in records if r.get("type") == "observation"
                  and r.get("status") == "ok" and r["bus_stop_code"] == stop
                  and timestamp(r["received_at"]) <= decision]
    result = {"stop": stop, "decision_time": decision.isoformat(), "services": services}
    if not candidates:
        return {**result, "status": "missing", "predictions": []}
    row = max(candidates, key=lambda r: timestamp(r["received_at"]))
    age = (decision - timestamp(row["received_at"])).total_seconds()
    result.update(response_at=row["received_at"], age_seconds=age)
    if age > max_age_seconds:
        return {**result, "status": "stale", "predictions": []}
    predictions = []
    past = invalid = 0
    for arrival in row["arrivals"]:
        if arrival["service_no"] not in services:
            continue
        try:
            eta = timestamp(arrival["estimated_arrival"])
        except (ValueError, TypeError, KeyError):
            invalid += 1
            continue
        if eta < decision:
            past += 1
            continue
        predictions.append({
            "service": arrival["service_no"], "eta": eta.astimezone(SGT).isoformat(),
            "predicted_minutes_from_decision": (eta - decision).total_seconds() / 60,
            "slot": arrival.get("arrival_slot"), "monitored": arrival.get("monitored"),
            "origin_code": arrival.get("origin_code"),
            "destination_code": arrival.get("destination_code"),
            "visit_number": arrival.get("visit_number"),
        })
    return {**result, "status": "available", "past_eta_entries_excluded": past,
            "invalid_eta_entries": invalid,
            "predictions": sorted(predictions, key=lambda a: a["eta"])}


def coverage(records):
    groups = defaultdict(list)
    for row in records:
        if row.get("type") == "observation":
            groups[row["bus_stop_code"]].append(row)
    result = []
    for stop, rows in sorted(groups.items()):
        ok = sorted((r for r in rows if r["status"] == "ok"),
                    key=lambda r: timestamp(r["received_at"]))
        times = [timestamp(r["received_at"]) for r in ok]
        gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
        flags = Counter(str(a.get("monitored")) for r in ok for a in r["arrivals"])
        result.append({
            "stop": stop, "successful_requests": len(ok),
            "failed_requests": len(rows) - len(ok),
            "first_response": times[0].astimezone(SGT).isoformat() if times else None,
            "last_response": times[-1].astimezone(SGT).isoformat() if times else None,
            "max_gap_seconds": max(gaps, default=None),
            "gaps_over_90_seconds": sum(g > 90 for g in gaps),
            "empty_responses": sum(not r["arrivals"] for r in ok),
            "monitored_flag_entry_counts": dict(flags),
        })
    return result


def audit(paths):
    records, sources = [], []
    for path in paths:
        raw = path.read_bytes()
        parsed = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
        observations = [r for r in parsed if r["type"] == "observation"]
        complete = [r for r in parsed if r["type"] == "completion"]
        counts_match = bool(complete) and (
            complete[-1]["requests"] == len(observations)
            and complete[-1]["successful_requests"] == sum(r["status"] == "ok" for r in observations))
        sources.append({"path": path.as_posix(), "sha256": hashlib.sha256(raw).hexdigest(),
                        "observation_count": len(observations),
                        "completion": complete[-1] if complete else None,
                        "completion_counts_match": counts_match,
                        "errors": [r for r in observations if r["status"] != "ok"]})
        records.extend(parsed)
    checks = [
        ("16189", "14:30", ["151", "95", "96"]),
        ("12061", "14:30", ["61", "52", "184", "75"]),
        ("12071", "15:05", ["151", "61"]),
        ("12071", "15:29", ["151", "61"]),
        ("42059", "15:01", ["151"]),
        ("42061", "15:18", ["174"]),
        ("11261", "15:04", ["95", "970"]),
        ("11261", "15:20", ["970"]),
    ]
    return {"kind": "offline_eta_observation_audit_not_journey_replay",
            "sources": sources, "coverage": coverage(records),
            "as_of_checks": [as_of(records, stop, timestamp(f"2026-10-04T{time}:00+08:00"), services)
                             for stop, time, services in checks]}


def render(report):
    lines = ["# ETA pilot audit: October 4, 14:30", "",
             "This project is an independent research project and is not affiliated with,",
             "endorsed by, or sponsored by the Land Transport Authority of Singapore,",
             "Google, or Citymapper.", "", "## Collection integrity", "",
             "All times below are Singapore time. No live API requests are made by this audit.", ""]
    for source in report["sources"]:
        complete = source["completion"]
        lines.append(f"- {Path(source['path']).name}: {source['observation_count']} requests; "
                     f"completion={complete['status'] if complete else 'missing'}; "
                     f"completion counts match={source['completion_counts_match']}.")
    lines += ["", "| Stop | OK | Errors | First | Last | Max gap (sec) | Gaps >90s | Empty |",
              "| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |"]
    for row in report["coverage"]:
        first = row["first_response"][11:19] if row["first_response"] else "none"
        last = row["last_response"][11:19] if row["last_response"] else "none"
        gap = f"{row['max_gap_seconds']:.2f}" if row["max_gap_seconds"] is not None else "n/a"
        lines.append(f"| {row['stop']} | {row['successful_requests']} | {row['failed_requests']} | "
                     f"{first} | {last} | {gap} | {row['gaps_over_90_seconds']} | {row['empty_responses']} |")
    lines += ["", "## Predictions available at selected decision times", "",
              "These are fixed-time diagnostics, NOT reconstructed passenger arrival times.",
              "Select the latest response received at or before each decision; reject responses",
              "older than 90 seconds and exclude ETAs already before the decision time.",
              "Monitored flags are reported literally; rows are not verified arrival events.", ""]
    for check in report["as_of_checks"]:
        lines += [f"### {check['stop']} at {check['decision_time'][11:16]}", "",
                  f"Snapshot status: {check['status']}; age: {check.get('age_seconds', 'n/a')} seconds.", "",
                  "| Service | Predicted arrival | Minutes from decision | Monitored | Slot |",
                  "| --- | --- | ---: | --- | --- |"]
        for p in check["predictions"]:
            lines.append(f"| {p['service']} | {p['eta'][11:19]} | "
                         f"{p['predicted_minutes_from_decision']:.2f} | {p['monitored']} | {p['slot']} |")
        lines.append("")
    lines += ["## Interpretation limits", "",
              "- The main collector stopped on an LTAApiError; the safe log does not retain",
              "  HTTP status or underlying exception details. Root cause is unknown; do not",
              "  assert a timeout or exhausted quota from request duration alone.",
              "- The 90-second gap audit concerns cadence within each observed window, not",
              "  coverage after early termination. Main observations end before 15:50.",
              "- Repeated predictions are not independent bus events or actual arrival truth.",
              "- Missing or expired ETA entries do not prove a bus departed or was missed.",
              "- Rank slots cannot match vehicles between stations. No catch probabilities,",
              "  actual journey durations, or Google speedup are calculated here.",
              "- A fixed-time alternative service prediction alone does not prove a feasible",
              "  full route; direction, passenger arrival, and continuation must be checked.",
              "- Manual Google totals remain 44, 52, 63, 68 minutes from 14:30. They are",
              "  external forecasts, not observed outcomes or model calibration labels.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.input)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.output / "audit.md").write_text(render(report), encoding="utf-8")
    print(json.dumps({"sources": report["sources"], "coverage": report["coverage"]}, indent=2))


if __name__ == "__main__":
    main()

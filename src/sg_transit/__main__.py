from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from .io import load_network, resolve_stop
from .lta import collect_bus_arrival_series, collect_bus_arrivals, provider_from_environment
from .lta_calibration import apply_headways_file, calibrate_headways_file
from .models import Route, Strategy, compile_policy
from .routing import RoutingParameters, SearchBudgetExceeded, plan
from .simulation import evaluate


def policy_json(strategy):
    def visit(node):
        return [{"board": asdict(leg), "then": visit(child)} for leg, child in node.options]
    return {"name": strategy.name, "rule": "board first arriving accepted service at current stop", "options": visit(compile_policy(strategy))}


def plan_case(network_path, origin, destination, departure, output, samples=10000, seed=100, selection_seed=7, selection_samples=512, access_minutes=0.0, egress_minutes=0.0, max_trip_minutes=120.0):
    if seed == selection_seed:
        raise ValueError("Selection and held-out evaluation seeds must differ")
    if any(not math.isfinite(t) or t < 0 for t in (access_minutes, egress_minutes)):
        raise ValueError("Walking minutes must be finite and nonnegative")
    if samples < 1 or selection_samples < 1:
        raise ValueError("Sample counts must be positive")
    dt = datetime.fromisoformat(departure)
    if dt.utcoffset() != timedelta(hours=8):
        raise ValueError("Use an explicit Singapore +08:00 departure, e.g. 2026-09-28T16:00:00+08:00")
    network, source = load_network(network_path)
    o, d = resolve_stop(network, origin), resolve_stop(network, destination)
    walk = access_minutes + egress_minutes
    p = RoutingParameters(max_trip_minutes=max_trip_minutes - walk)
    bus_departure = dt.hour * 60 + dt.minute + dt.second / 60 + access_minutes
    result = plan(network, o, d, p, selection_samples, selection_seed, bus_departure)
    if result.recommended_strategy is None:
        raise ValueError("No route satisfies the declared bounds in this network subset")
    strategies = {**result.baselines, "reliability_policy": result.recommended_strategy}
    evaluations = {}
    raw = []
    for name, strategy in strategies.items():
        trial = evaluate(strategy, network, samples, seed, bus_departure, p)
        s = trial.summary
        summary = replace(s, mean_minutes=s.mean_minutes + walk, median_minutes=s.median_minutes + walk, p90_minutes=s.p90_minutes + walk, p95_minutes=s.p95_minutes + walk, max_minutes=s.max_minutes + walk, over_two_hours_probability=float((trial.durations + walk > 120).mean()))
        if isinstance(strategy, Route):
            strategy = Strategy(name, (strategy,))
        evaluations[name] = {"summary": asdict(summary), "policy": policy_json(strategy), "branch_counts": trial.branch_counts}
        for i in range(samples):
            raw.append({"strategy": name, "sample": i, "duration_minutes": float(trial.durations[i] + walk), "waiting_minutes": float(trial.waits[i]), "missed": bool(trial.missed[i]), "invalid": bool(trial.invalid[i])})
    document = {
        "schema_version": 1, "origin": o, "destination": d, "departure": dt.isoformat(),
        "origin_input": origin, "destination_input": destination, "mode": "bus_only",
        "network_sha256": hashlib.sha256(Path(network_path).read_bytes()).hexdigest(),
        "provenance": source.get("provenance", {}), "selection_seed": selection_seed, "evaluation_seed": seed,
        "selection_samples": selection_samples, "samples": samples, "parameters": asdict(p),
        "access_minutes": access_minutes, "egress_minutes": egress_minutes,
        "assumption": "Stationary headways, estimated timing unless explicitly sourced; not live navigation",
        "candidate_count": len(result.candidates), "candidate_routes": [asdict(r) for r in result.candidates],
        "evaluations": evaluations,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, allow_nan=False), encoding="utf-8")
    with output.with_suffix(".samples.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=raw[0].keys())
        writer.writeheader()
        writer.writerows(raw)
    return document


def compare_case(plan_path, observations_path, output):
    document = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    with Path(observations_path).open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    matched = []
    for row in rows:
        if not row.get("google_total_minutes"):
            continue
        if (row.get("origin_stop_id"), row.get("destination_stop_id"), row.get("mode")) != (document["origin"], document["destination"], document["mode"]):
            raise ValueError("Observation endpoints or mode differ from the frozen plan")
        if datetime.fromisoformat(row["departure"]) != datetime.fromisoformat(document["departure"]):
            raise ValueError("Departure differs from the frozen plan")
        if row.get("network_sha256") != document["network_sha256"]:
            raise ValueError("Observation must reference the frozen network hash")
        minutes = float(row["google_total_minutes"])
        if not math.isfinite(minutes) or minutes <= 0:
            raise ValueError("Google duration must be finite and positive")
        summary = document["evaluations"]["reliability_policy"]["summary"]
        matched.append(
            {
                "case_id": row["case_id"],
                "google_route_rank": row["google_route_rank"],
                "google_estimate": minutes,
                "model_mean": summary["mean_minutes"],
                "model_median": summary["median_minutes"],
                "model_p90": summary["p90_minutes"],
                "model_p95": summary["p95_minutes"],
                "model_failure_probability": summary["failure_probability"],
                "model_invalid_transfer_probability": summary["invalid_transfer_probability"],
                "prediction_difference_minutes": summary["mean_minutes"] - minutes,
                "observed_actual_minutes": row.get("observed_actual_minutes", ""),
            }
        )
    if not matched:
        raise ValueError("No completed Google observations; template rows are not validation evidence")
    report = {"interpretation": "Prediction comparison only, not measured speedup or causal evidence", "comparisons": matched}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reproducible transit-policy experiments")
    sub = parser.add_subparsers(dest="command", required=True)
    stops = sub.add_parser("stops")
    stops.add_argument("--network", required=True)
    stops.add_argument("--query", default="")
    route = sub.add_parser("plan")
    for name in ("network", "origin", "destination", "departure", "output"):
        route.add_argument(f"--{name}", required=True)
    route.add_argument("--samples", type=int, default=10000)
    route.add_argument("--seed", type=int, default=100)
    route.add_argument("--selection-seed", type=int, default=7)
    route.add_argument("--selection-samples", type=int, default=512)
    route.add_argument("--access-minutes", type=float, default=0)
    route.add_argument("--egress-minutes", type=float, default=0)
    route.add_argument("--max-trip-minutes", type=float, default=120)
    compare = sub.add_parser("compare")
    for name in ("plan", "observations", "output"):
        compare.add_argument(f"--{name}", required=True)
    arrivals = sub.add_parser("arrivals")
    arrivals.add_argument("--stop", action="append", required=True, dest="stops")
    arrivals.add_argument("--output", required=True)
    arrivals.add_argument("--timeout", type=float, default=10.0)
    arrivals.add_argument("--samples", type=int, default=1)
    arrivals.add_argument("--interval", type=float, default=0.0)
    calibrate = sub.add_parser("calibrate-headways")
    calibrate.add_argument("--input", required=True)
    calibrate.add_argument("--output", required=True)
    calibrate.add_argument("--tolerance", type=float, default=2.0)
    calibrate.add_argument("--min-headway", type=float, default=3.0)
    apply_headways = sub.add_parser("apply-headways")
    for name in ("network", "calibration", "output"):
        apply_headways.add_argument(f"--{name}", required=True)
    apply_headways.add_argument("--min-observations", type=int, default=1)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        if command == "stops":
            network, _ = load_network(args["network"])
            print(json.dumps([asdict(s) for s in network.stops.values() if args["query"].casefold() in (s.id + " " + s.name).casefold()], indent=2))
        elif command == "plan":
            args["network_path"] = args.pop("network")
            document = plan_case(**args)
            print(json.dumps({"output": args["output"], "candidates": document["candidate_count"], "recommended": document["evaluations"]["reliability_policy"]}, indent=2))
        elif command == "calibrate-headways":
            document = calibrate_headways_file(
                args["input"],
                args["output"],
                tolerance_minutes=args["tolerance"],
                min_headway_minutes=args["min_headway"],
            )
            print(json.dumps(document, indent=2))
        elif command == "apply-headways":
            document = apply_headways_file(
                args["network"],
                args["calibration"],
                args["output"],
                min_observations=args["min_observations"],
            )
            print(json.dumps(document["provenance"]["headway_calibration"], indent=2))
        else:
            if command == "compare":
                print(json.dumps(compare_case(args["plan"], args["observations"], args["output"]), indent=2))
            else:
                provider = provider_from_environment(timeout=args["timeout"])
                if args["samples"] == 1:
                    document = collect_bus_arrivals(provider, args["stops"], output_path=args["output"])
                else:
                    document = collect_bus_arrival_series(
                        provider,
                        args["stops"],
                        samples=args["samples"],
                        interval_seconds=args["interval"],
                        output_path=args["output"],
                    )
                print(json.dumps(document, indent=2))
    except (ValueError, KeyError, OSError, SearchBudgetExceeded, RuntimeError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()

"""Expanded, directed Information Technology -> Signature Pk research corridor."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

import numpy as np

from data.real.build_subset import RAW, load_rows, select_pattern
from experiments.corridor_search import _safe
from sg_transit.adaptive import SharedSuffixPolicy, evaluate_adaptive
from sg_transit.corridors import CorridorParameters, DestinationIndex, discover_candidates
from sg_transit.io import load_network
from sg_transit.routing import RoutingParameters, _baseline, enumerate_routes, expected_time, route_key
from sg_transit.simulation import evaluate

ROOT = Path(__file__).resolve().parents[1]
ORIGIN, DESTINATION = "16189", "42171"
STOPS_TO_SAMPLE = (ORIGIN, "11401", "12061", "42141", "42071")
DEPARTURES = tuple(f"2026-10-01T{hour:02d}:00:00+08:00" for hour in (10, 12, 14, 16, 18, 20))
OUTPUT = ROOT / "results/pei_hwa_20261001"
NETWORK = ROOT / "data/real/derived/pei_hwa_offline_20261001.json"
SEGMENTS = (
    ("151", "2", ORIGIN, "42141"),
    ("95", "1", ORIGIN, "11401"),
    ("52", "2", "12061", "42071"),
    ("61", "2", "11401", DESTINATION),
    ("154", "1", "12061", "42141"),
    ("184", "1", "12061", "42071"),
    ("157", "1", "42071", DESTINATION),
    ("174", "2", "42071", DESTINATION),
    ("970", "2", "11401", DESTINATION),
    ("985", "2", "42071", DESTINATION),
)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_offline(output=NETWORK, *, speed_kmh=20.0, headway=15.0, delay=3.0):
    """No credentials, API requests or recorded arrivals are read by this path."""
    if any(not math.isfinite(x) or x <= 0 for x in (speed_kmh, headway)) or not math.isfinite(delay) or delay < 0:
        raise ValueError("Invalid timing assumptions")
    rows = load_rows(RAW / "BusRoutes.csv")
    stops = {row["BusStopCode"]: row for row in load_rows(RAW / "BusStops.csv")}
    source = json.loads((ROOT / "data/real/sources.json").read_text(encoding="utf-8"))
    for name, digest in source["raw_sha256"].items():
        if file_hash(RAW / name) != digest:
            raise ValueError(f"Source hash mismatch: {name}; review provenance before rebuilding")
    services, used = [], set()
    for number, direction, start, end in SEGMENTS:
        pattern = select_pattern(rows, number, direction, start, end)
        codes = [row["BusStopCode"] for row in pattern]
        distances = [float(row["Distance"]) for row in pattern]
        if len(set(codes)) != len(codes) or any(b < a for a, b in zip(distances, distances[1:])):
            raise ValueError(f"Invalid ordered segment: {number}/{direction}")
        used.update(codes)
        services.append({
            "id": f"{number}-D{direction}", "source_service": number, "direction": direction,
            "stops": codes,
            "ride_minutes": [max(0.5, round((b - a) * 60 / speed_kmh, 4))
                             for a, b in zip(distances, distances[1:])],
            "headway_minutes": headway, "delay_max_minutes": delay,
            "timing_quality": "assumed_stationary_not_live_or_scheduled",
            "source_stop_sequences": [int(row["StopSequence"]) for row in pattern],
        })
    source["scope"] = (
        "Selected 10 directed service segments: 16189 -> 42171 via 12061/42141/42071 "
        "or 95/970. Not all area routes; cross-stop walks and service 96 are excluded."
    )
    source["timing_note"] = "All ride times/headways/delays assumed; no recorded ETA data loaded."
    document = {
        "schema_version": 1, "provenance": source,
        "data_kind": "historical_static_topology_with_assumed_timing",
        "timing_parameters": {
            "speed_kmh": speed_kmh, "uniform_headway_minutes": headway,
            "delay_max_minutes": delay, "minimum_segment_minutes": 0.5,
            "time_of_day_profiles": False, "live_api_used": False,
        },
        "query_departures": DEPARTURES,
        "stops": [{"id": code, "name": stops[code]["Description"],
                   "x": float(stops[code]["Longitude"]), "y": float(stops[code]["Latitude"])}
                  for code in sorted(used)],
        "services": services,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    load_network(output)
    return document


def route_text(route):
    return " | ".join(f"{leg.service_id}: {leg.board_stop}->{leg.alight_stop}" for leg in route.legs)


def paired_interval(left, right, seed=801, repetitions=400):
    """Paired held-out differences, not six independent time-of-day experiments."""
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        return {"unavailable": "Non-completed journeys; compare completion rates first."}
    rng = np.random.default_rng(seed)
    means, tails = [], []
    for _ in range(repetitions):
        ids = rng.integers(0, len(left), len(left))
        a, b = left[ids], right[ids]
        means.append(float(np.mean(a - b)))
        tails.append(float(np.quantile(a, 0.95) - np.quantile(b, 0.95)))
    return {
        "definition": "left minus right; negative means lower duration",
        "mean_difference": float(np.mean(left - right)),
        "mean_ci95": list(np.quantile(means, [0.025, 0.975])),
        "p95_difference": float(np.quantile(left, 0.95) - np.quantile(right, 0.95)),
        "p95_ci95": list(np.quantile(tails, [0.025, 0.975])),
        "resamples": repetitions, "seed": seed,
    }


def evaluate_case(network_path, *, samples=10000, seed=100, speed_label="base",
                  pressure=True, bootstrap_repetitions=400):
    network, document = load_network(network_path)
    p = RoutingParameters(max_candidates=300000, max_expansions=2000000)
    c = CorridorParameters()
    stats = {}
    started = perf_counter()
    routes = enumerate_routes(network, ORIGIN, DESTINATION, p, stats=stats)
    exact_ms = (perf_counter() - started) * 1000
    if not routes:
        raise ValueError("Expanded offline corridor has no feasible route")
    started = perf_counter()
    index = DestinationIndex(network, DESTINATION)
    index_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    bounded = discover_candidates(index, ORIGIN, p, c)
    bounded_ms = (perf_counter() - started) * 1000
    if not bounded.routes:
        raise ValueError("Bounded search returned no routes; do not report a successful comparison")
    print(f"{speed_label}: {len(routes)} full / {len(bounded.routes)} bounded candidates", flush=True)
    fixed = {label: _baseline(routes, network, mode) for label, mode in (
        ("shortest_expected", "time"), ("minimum_transfers", "transfers"), ("minimum_ride", "ride"),
    )}
    for label, pair in (
        ("reference_151_61", ("151-D2", "61-D2")),
        ("reference_95_970", ("95-D1", "970-D2")),
    ):
        matching = [route for route in routes if route.services == pair]
        if not matching:
            raise ValueError(f"Missing expected service pair: {pair}")
        fixed[label] = min(matching, key=lambda route: (expected_time(route, network), route_key(route)))
    evaluations, trials, pressure_results = {}, {}, {}
    for label, route in fixed.items():
        trial = evaluate(route, network, samples, seed, parameters=p)
        trials[label] = trial
        evaluations[label] = {
            "summary": {**asdict(trial.summary), "completion_probability": 1.0,
                        "within_constraints_probability": float((~trial.fare_invalid).mean()),
                        "stopped_probability": 0.0},
            "route": asdict(route), "route_text": route_text(route), "branch_counts": trial.branch_counts,
        }
        if pressure:
            pressure_results[label] = asdict(evaluate(
                route, network, samples, seed, parameters=p, phase_correlation=1).summary)
    for label, candidates in (("full_adaptive", routes), ("bounded_adaptive", bounded.routes)):
        started = perf_counter()
        policy = SharedSuffixPolicy(network, candidates, p, max_value_states=500000)
        policy.value(policy.initial_state().structure)
        compile_ms = (perf_counter() - started) * 1000
        started = perf_counter()
        trial = evaluate_adaptive(policy, samples, seed)
        trials[label] = trial
        evaluations[label] = {
            "summary": {**trial.summary,
                        "within_constraints_probability": float((~trial.stopped & ~trial.over_limit).mean())},
            "boarding_counts": trial.branch_counts,
            "shared_nodes": len(policy.nodes), "value_states": policy.value_state_count,
            "compile_ms": compile_ms, "evaluation_ms": (perf_counter() - started) * 1000,
        }
        if pressure:
            pressure_results[label] = evaluate_adaptive(
                policy, samples, seed, phase_correlation=1).summary
        print(f"{speed_label}/{label}: mean {trial.summary['mean_minutes']:.2f}, "
              f"P95 {trial.summary['p95_minutes']:.2f}", flush=True)
    full_keys = set(map(route_key, routes))
    bounded_keys = set(map(route_key, bounded.routes))
    paired = {
        label: paired_interval(trials[label].durations, trials[reference].durations,
                               repetitions=bootstrap_repetitions)
        for label, reference in (("bounded_adaptive", "shortest_expected"),
                                  ("full_adaptive", "shortest_expected"))
    }
    paired["bounded_minus_full_adaptive"] = paired_interval(
        trials["bounded_adaptive"].durations, trials["full_adaptive"].durations,
        repetitions=bootstrap_repetitions)
    result = {
        "network_sha256": file_hash(network_path),
        "samples": samples, "evaluation_seed": seed, "value_seed": 29, "value_samples": 64,
        "timing_parameters": document["timing_parameters"],
        "routing_parameters": asdict(p), "corridor_parameters": asdict(c),
        "search": {
            "full_candidates": len(routes), "bounded_candidates": len(bounded.routes),
            "full_expansions": stats["expansions"], "bounded_expansions": bounded.expansions,
            "full_search_ms": exact_ms, "index_ms": index_ms, "bounded_search_ms": bounded_ms,
            "candidate_recall": len(full_keys & bounded_keys) / len(full_keys),
            "full_route_keys_sha256": hashlib.sha256(
                json.dumps(sorted(full_keys)).encode()).hexdigest(),
            "shortest_expected_retained": route_key(fixed["shortest_expected"]) in bounded_keys,
            "full_transfer_count_histogram": dict(sorted(Counter(route.transfers for route in routes).items())),
            "selected_hubs": [asdict(hub) for hub in bounded.selected_hubs],
            "pei_hwa_direct_services": [tail.service_id for tail in index.tails["42071"]],
            "truncated": bounded.truncated, "truncation_reasons": bounded.truncation_reasons,
            "ordinary_candidates": len(bounded.ordinary_route_keys),
            "bypass_candidates": len(bounded.bypass_route_keys),
            "bounded_routes": [asdict(route) for route in bounded.routes],
        },
        "evaluations": evaluations, "paired_comparisons": paired,
        "fully_correlated_pressure": pressure_results,
    }
    return _safe(result), trials


def write_google_template(path, digest):
    """Never overwrite the user's later manual observations on a rerun."""
    path = Path(path)
    if path.exists():
        return
    fields = ["origin_stop_id", "destination_stop_id", "departure_sgt", "network_sha256",
              "observation_recorded_at", "service_sequence", "boarding_transfer_stop_ids",
              "displayed_total_minutes", "displayed_walk_minutes", "same_stop_endpoints",
              "notes"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for departure in DEPARTURES:
            writer.writerow({
                "origin_stop_id": ORIGIN, "destination_stop_id": DESTINATION,
                "departure_sgt": departure, "network_sha256": digest,
            })


def write_case_report(document, output):
    from experiments.corridor_search import plt

    base, source = document["base"], document["provenance"]
    number = lambda value: "uncompleted" if value is None else f"{value:.2f}"
    s = base["search"]
    lines = [
        "# Pei Hwa Offline Corridor: 2026-10-01", "",
        "Information Technology (16189) -> Signature Pk Condo (42171), bus stop to bus stop.",
        "**No API requests, credentials, new ETA samples, or Google content are used by this experiment.**",
        "Departure labels: 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, Singapore (+08:00).", "",
        "## What These Times Mean", "",
        "All six slots share one stationary simulation, NOT six measured or scheduled time-of-day predictions.",
        "The calendar date is comparison metadata. There is no date-specific timetable, rush-hour profile,",
        "service calendar or future ETA in this model. Identical slot values are intentional.",
        "Do not compare these means to a Google displayed duration and claim a speed advantage.", "",
        f"Static source access date: {source['accessed_at']}; pinned commit: `{source['commit']}`.",
        "This access date is not a guarantee that every route operates unchanged on 2026-10-01.",
        f"Network SHA256: `{base['network_sha256']}`.",
        "Topology uses the existing raw CSV files; no freshly collected nighttime arrivals were loaded.",
        f"Timing assumptions: {json.dumps(base['timing_parameters'], sort_keys=True)}.", "",
        "## Network and Search", "",
        "47 stops and 10 directed service segments in the base snapshot; not the complete local network.",
        "151 is allowed to continue to Bef Dunearn Rd (42141). 154 reaches 42141 but not Pei Hwa (42071).",
        "52/61/184 connect 12061 to 42071; 61/157/174/970/985 connect 42071 to 42171.",
        "95/970 provides a separate feeder corridor. Same-stop transfers only; no campus walking model.",
        f"Full route enumeration: {s['full_candidates']} candidates, {s['full_expansions']} expansions.",
        f"Bounded search: {s['bounded_candidates']} candidates, {s['bounded_expansions']} expansions.",
        f"Retained shortest-expected route: {s['shortest_expected_retained']}.",
        f"Candidate recall: {s['candidate_recall']:.6f}; truncation reasons: {s['truncation_reasons']}.",
        f"Automatically selected hub IDs: {[hub['stop'] for hub in s['selected_hubs']]}.",
        "Common downstream service sets can select another stop on the same corridor rather than 42071.",
        "Shared retained edges can recombine, so low route-description recall is not policy-path recall.",
        "Full means exhaustive in this selected network and bounds, not a globally optimal stochastic policy.", "",
        "## Common Held-Out Results", "",
        f"Samples per strategy: {base['samples']}; evaluation seed {base['evaluation_seed']};",
        "stationary downstream-value seed 29. Decisions see current-stop departures, not future delays.", "",
        "| Strategy | Mean | P90 | P95 | Missed target | Completed | Within model limits |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, evaluation in base["evaluations"].items():
        v = evaluation["summary"]
        lines.append(
            f"| {label} | {number(v['mean_minutes'])} | {number(v['p90_minutes'])} | "
            f"{number(v['p95_minutes'])} | {v['failure_probability']:.4f} | "
            f"{v['completion_probability']:.4f} | {v['within_constraints_probability']:.4f} |")
    lines.extend([
        "", "Missed target is a model-specific counterfactual nominal-departure diagnostic, not a field-measured",
        "probability of being stranded. Adaptive service switching changes the selected target.",
        "Fixed journeys finish even when limits are exceeded; adaptive journeys may stop. Compare",
        "within-model-limit/completion rates before interpreting duration. Uncompleted durations are",
        "infinite internally and non-finite JSON metrics are null; no failures are silently dropped.", "",
        "### Fixed route structures", "",
    ])
    for label, evaluation in base["evaluations"].items():
        if "route_text" in evaluation:
            lines.append(f"- {label}: {evaluation['route_text']}")
    lines.extend(["", "## Six Requested Departure Slots", "",
                  "| Departure (SGT) | Fixed mean / P95 | Full adaptive mean / P95 | Bounded mean / P95 |",
                  "| --- | ---: | ---: | ---: |"])
    for slot in document["slots"]:
        values = []
        for label in ("shortest_expected", "full_adaptive", "bounded_adaptive"):
            v = slot["metrics"][label]
            values.append(f"{number(v['mean_minutes'])} / {number(v['p95_minutes'])}")
        lines.append(f"| {slot['departure_sgt']} | " + " | ".join(values) + " |")
    lines.extend(["", "## Sensitivity, Not Fitted Traffic", "",
                  "The timing alternatives below are assumed scenarios, not measured peak/off-peak profiles.",
                  "Each is replanned and evaluated without Google data; none is assigned to a departure hour.", "",
                  "| Assumptions | Fixed mean / P95 | Full adaptive mean / P95 | Bounded mean / P95 |",
                  "| --- | ---: | ---: | ---: |"])
    for name, result in document["sensitivity"].items():
        values = []
        for label in ("shortest_expected", "full_adaptive", "bounded_adaptive"):
            v = result["evaluations"][label]["summary"]
            values.append(f"{number(v['mean_minutes'])} / {number(v['p95_minutes'])}")
        lines.append(f"| {name} | " + " | ".join(values) + " |")
    lines.extend(["", "## Paired Differences", "",
                  "Negative durations favor the left-hand strategy. Bootstrap intervals only describe",
                  "Monte Carlo uncertainty in this assumed model, not real-world timing uncertainty.", "",
                  "```json", json.dumps(base["paired_comparisons"], indent=2), "```", "",
                  "## Google Reference Pending", "",
                  "No new Google observations have been entered. The old 2026-09-28 screenshots are not",
                  "relabelled as October 1. `google_manual_template.csv` is intentionally blank except for",
                  "endpoints, departure times and the frozen model hash.",
                  "Manually record route services, boarding/transfer stops, displayed duration, walking",
                  "duration and observation time. Keep screenshots and large responses out of this repository.",
                  "Walking or a different boarding stop means the result is not a matched stop-to-stop comparison.",
                  "Future-date Google planned routes can be recorded before the departure date; this runner",
                  "does not access Google or turn its durations into model parameters.", "",
                  "## Limits and Reproduction", "",
                  "`python -m experiments.pei_hwa_case run` rebuilds the frozen offline snapshot, runs",
                  "the base/pressure/sensitivity comparisons and writes the six-slot report. Existing manual",
                  "Google entries are not overwritten. There is no network request on build/run paths.",
                  "All service calendars, congestion profiles and actual fares remain unmodeled.",
                  "Independent service phases can overstate the benefit of alternatives; JSON includes a",
                  "fully synchronized-phase pressure comparison (not a measured congestion model).",
                  "Local value heuristics optimize estimated remaining time plus transfer penalties, not global P95.",
                  "", "This project is an independent research project and is not affiliated with,",
                  "endorsed by, or sponsored by the Land Transport Authority of Singapore,",
                  "Google, or Citymapper."])
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    labels = ("shortest_expected", "full_adaptive", "bounded_adaptive")
    figure, axis = plt.subplots(figsize=(8, 4.8))
    for i, metric in enumerate(("mean_minutes", "p90_minutes", "p95_minutes")):
        axis.bar(np.arange(3) + i * 0.25,
                 [base["evaluations"][label]["summary"][metric] or math.nan for label in labels],
                 width=0.25, label=metric)
    axis.set_xticks(np.arange(3) + 0.25, ["Fixed baseline", "Full adaptive", "Bounded adaptive"])
    axis.set_ylabel("Simulated minutes")
    axis.set_title("47-stop corridor: assumed timing, all six slots")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output / "comparison.png", dpi=140)
    plt.close(figure)
    # A route diagram uses the actual selected stop coordinates, not Google tiles.
    path = Path(document["network_path"])
    network, _ = load_network(path if path.is_absolute() else ROOT / path)
    figure, axis = plt.subplots(figsize=(9, 6))
    for service in network.services.values():
        axis.plot([network.stops[stop].x for stop in service.stops],
                  [network.stops[stop].y for stop in service.stops], alpha=0.6, label=service.id)
    for stop in (ORIGIN, "11401", "12061", "42141", "42071", DESTINATION):
        node = network.stops[stop]
        axis.scatter(node.x, node.y, color="black", s=16)
        axis.annotate(stop, (node.x, node.y), xytext=(5, 5), textcoords="offset points")
    axis.set_xlabel("Longitude")
    axis.set_ylabel("Latitude")
    axis.set_title("Selected directed service corridors (static snapshot)")
    axis.legend(ncol=2, fontsize=8)
    figure.tight_layout()
    figure.savefig(output / "network.png", dpi=140)
    plt.close(figure)


def run_offline(output=OUTPUT, network_path=NETWORK, *, samples=10000,
                sensitivity_samples=2000, pressure=True, sensitivity=True,
                bootstrap_repetitions=400):
    if samples < 1 or sensitivity_samples < 1 or bootstrap_repetitions < 1:
        raise ValueError("Positive simulation and bootstrap sample counts required")
    output, network_path = Path(output), Path(network_path)
    output.mkdir(parents=True, exist_ok=True)
    source = build_offline(network_path)
    base, trials = evaluate_case(network_path, samples=samples, pressure=pressure,
                                bootstrap_repetitions=bootstrap_repetitions)
    sensitivity_results = {}
    if sensitivity:
        for name, speed, headway in (("slow_15kmh_headway20", 15.0, 20.0),
                                      ("fast_25kmh_headway10", 25.0, 10.0)):
            path = network_path.parent / f"pei_hwa_{name}.json"
            build_offline(path, speed_kmh=speed, headway=headway)
            sensitivity_results[name], _ = evaluate_case(
                path, samples=sensitivity_samples, seed=101, speed_label=name, pressure=False,
                bootstrap_repetitions=bootstrap_repetitions)
    resolved = network_path.resolve()
    portable_path = resolved.relative_to(ROOT).as_posix() if resolved.is_relative_to(ROOT) else str(resolved)
    document = {
        "schema_version": 1, "experiment": "pei_hwa_offline_20261001",
        "origin": ORIGIN, "destination": DESTINATION, "timezone": "Asia/Singapore",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "network_path": portable_path, "provenance": source["provenance"],
        "live_api_used": False, "recorded_eta_used": False, "google_observations_used": False,
        "slot_semantics": "One stationary distribution reused for six future query labels; no calendar/headway profiles.",
        "base": base, "sensitivity": sensitivity_results,
        "slots": [{
            "departure_sgt": departure, "distribution_id": "base_stationary",
            "metrics": {label: value["summary"] for label, value in base["evaluations"].items()},
        } for departure in DEPARTURES],
    }
    (output / "experiment.json").write_text(json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (output / "samples.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["strategy", "sample", "duration_minutes", "waiting_minutes",
                                                   "missed_target", "transfers", "completed"])
        writer.writeheader()
        for label, trial in trials.items():
            for i, duration in enumerate(trial.durations):
                writer.writerow({"strategy": label, "sample": i, "duration_minutes": float(duration),
                                 "waiting_minutes": float(trial.waits[i]), "missed_target": bool(trial.missed[i]),
                                 "transfers": int(trial.transfer_counts[i]), "completed": bool(np.isfinite(duration))})
    with (output / "slots.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["departure_sgt", "strategy", "mean_minutes", "p90_minutes",
                                                   "p95_minutes", "distribution_id"])
        writer.writeheader()
        for slot in document["slots"]:
            for label, summary in slot["metrics"].items():
                writer.writerow({"departure_sgt": slot["departure_sgt"], "strategy": label,
                                 "distribution_id": slot["distribution_id"],
                                 **{metric: summary[metric] for metric in ("mean_minutes", "p90_minutes", "p95_minutes")}})
    write_google_template(output / "google_manual_template.csv", base["network_sha256"])
    write_case_report(document, output)
    print(f"Offline report written: {output / 'report.md'}", flush=True)
    return document


def collect(directory):
    from sg_transit.lta import collect_bus_arrival_series, provider_from_environment
    from sg_transit.lta_static import collect_static

    directory = Path(directory)
    provider = provider_from_environment()
    for dataset in ("BusRoutes", "BusStops"):
        path = directory / f"{dataset}.json"
        if path.exists():
            raise ValueError(f"Choose a new raw directory; {path} already exists")
    for dataset in ("BusRoutes", "BusStops"):
        result = collect_static(provider.account_key, dataset, directory / f"{dataset}.json")
        print(f"{dataset}: {len(result['value'])} rows, {len(result['pagination'])} paced requests", flush=True)
    collect_bus_arrival_series(
        provider, STOPS_TO_SAMPLE, samples=4, interval_seconds=60,
        output_path=directory / "arrivals.json",
    )
    print(f"Four arrival snapshots saved in {directory}; not historical schedules.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["collect", "build", "run"])
    parser.add_argument("--network", type=Path, default=NETWORK)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--samples", type=int, default=10000)
    parser.add_argument("--sensitivity-samples", type=int, default=2000)
    parser.add_argument("--skip-sensitivity", action="store_true")
    parser.add_argument("--skip-pressure", action="store_true")
    parser.add_argument("--raw", type=Path, default=ROOT / "data/recorded/raw" /
                        ("pei_hwa_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")))
    args = parser.parse_args()
    if args.action == "collect":
        collect(args.raw)
    elif args.action == "build":
        document = build_offline(args.network)
        print(f"Offline network: {len(document['stops'])} stops, {len(document['services'])} services")
    else:
        run_offline(args.output, args.network, samples=args.samples, sensitivity_samples=args.sensitivity_samples,
                    pressure=not args.skip_pressure, sensitivity=not args.skip_sensitivity)


if __name__ == "__main__":
    main()

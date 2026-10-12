"""A bounded, same-stop-transfer experiment, not a full-area router."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from data.real.build_subset import RAW, estimated_ride_minutes, load_rows, select_pattern
from sg_transit.__main__ import policy_json
from sg_transit.io import load_network
from sg_transit.models import Strategy
from sg_transit.routing import RoutingParameters, expected_time, plan
from sg_transit.simulation import evaluate

ROOT = Path(__file__).resolve().parents[1]
NETWORK = ROOT / "data/real/network_information_technology.json"
SEGMENTS = (
    ("151", "2", "16189", "12101", 15.0),
    ("95", "1", "16189", "11261", 15.0),
    ("61", "2", "11401", "42171", 15.0),
    ("970", "2", "11401", "42171", 15.0),
)


def build_network():
    routes = load_rows(RAW / "BusRoutes.csv")
    metadata = {row["BusStopCode"]: row for row in load_rows(RAW / "BusStops.csv")}
    services = []
    used = set()
    for number, direction, start, end, headway in SEGMENTS:
        pattern = select_pattern(routes, number, direction, start, end)
        stops = [row["BusStopCode"] for row in pattern]
        used.update(stops)
        services.append({
            "id": f"{number}-D{direction}", "source_service": number,
            "direction": direction, "stops": stops,
            "ride_minutes": estimated_ride_minutes(pattern),
            "headway_minutes": headway, "delay_max_minutes": 3.0,
            "timing_quality": "estimated_from_distance_and_assumed_headway",
        })
    provenance = json.loads((ROOT / "data/real/sources.json").read_text())
    provenance["scope"] = (
        "16189 to 42171; selected 151/95 feeder and 61/970 onward corridors. "
        "At most one same-stop transfer; not an exhaustive area network."
    )
    document = {
        "schema_version": 1, "provenance": provenance, "services": services,
        "stops": [
            {"id": stop, "name": metadata[stop]["Description"],
             "x": float(metadata[stop]["Longitude"]),
             "y": float(metadata[stop]["Latitude"])}
            for stop in sorted(used)
        ],
    }
    NETWORK.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    load_network(NETWORK)
    print(f"Built {len(used)} stops and {len(services)} service segments")


def run_case(network_path, output, samples=10000):
    network, source = load_network(network_path)
    parameters = RoutingParameters(max_transfers=1)
    result = plan(network, "16189", "42171", parameters, 512, 7, 960)
    if result.recommended_strategy is None:
        raise ValueError("No feasible strategy")
    strategies = {
        name: Strategy(name, (route,)) for name, route in result.baselines.items()
    }
    for label, service_ids in (
        ("reference_151_61", ("151-D2", "61-D2")),
        ("reference_95_970", ("95-D1", "970-D2")),
    ):
        matching = [route for route in result.candidates if route.services == service_ids]
        if not matching:
            raise ValueError(f"Missing Google reference pair {label}")
        selected = min(matching, key=lambda route: (expected_time(route, network), route.legs[0].alight_stop))
        strategies[label] = Strategy(label, (selected,))
    strategies["reliability_policy"] = result.recommended_strategy
    evaluations = {}
    for name, strategy in strategies.items():
        trial = evaluate(strategy, network, samples, 100, 960, parameters)
        evaluations[name] = {
            "summary": asdict(trial.summary),
            "policy": policy_json(strategy),
            "branch_counts": trial.branch_counts,
        }
    document = {
        "origin": "16189", "destination": "42171",
        "departure": "2026-09-28T16:00:00+08:00",
        "network_sha256": hashlib.sha256(Path(network_path).read_bytes()).hexdigest(),
        "provenance": source["provenance"],
        "selection_seed": 7, "selection_samples": 512,
        "evaluation_seed": 100, "samples": samples,
        "parameters": asdict(parameters),
        "access_minutes": 0, "egress_minutes": 0,
        "candidate_routes": [asdict(route) for route in result.candidates],
        "evaluations": evaluations,
        "google_manual_reference": [
            {"services": "151 -> 61", "displayed_minutes": 50},
            {"services": "151 -> walk -> 174/970", "displayed_minutes": 54},
            {"services": "151 -> walk -> 157/174", "displayed_minutes": 58,
             "displayed_walk_minutes": 3, "displayed_first_bus_time": "16:16"},
            {"services": "95 -> 970", "displayed_minutes": 67},
        ],
        "limitations": [
            "Google fields manually transcribed from user screenshot, not training data.",
            "Date from user; screenshot lacks endpoint and calendar fields.",
            "Later 16:30 options excluded from the 16:00 comparison.",
            "Displayed slash-separated services remain ambiguous alternatives.",
            "Not all area services or transfer locations included.",
            "No cross-stop walks; only same-stop transfers with a 3-minute buffer.",
            "Ride minutes use 20 km/h distance conversion; delay bounds estimated.",
            "ETA headways are extrapolated to 16:00, not an observed 16:00 schedule.",
            "A mean over random waits is not a prediction of a specific scheduled bus.",
        ],
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: value["summary"] for name, value in evaluations.items()}, indent=2))
    return document


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "run"])
    parser.add_argument("--network", default=str(NETWORK))
    parser.add_argument("--output", default="results/information_technology_signature_20260928.json")
    args = parser.parse_args()
    if args.action == "build":
        build_network()
    else:
        run_case(args.network, args.output)


if __name__ == "__main__":
    main()

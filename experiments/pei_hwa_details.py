"""Exact-transfer comparison of manually supplied itinerary details, offline only."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from data.real.build_subset import RAW, load_rows, select_pattern
from experiments.pei_hwa_case import ROOT, build_offline, evaluate_case, file_hash
from sg_transit.io import load_network
from sg_transit.models import Leg, Route, validate_route
from sg_transit.routing import RoutingParameters
from sg_transit.simulation import evaluate

OBSERVATIONS = ROOT / "data/validation/google_pei_hwa_20261004_1600_details.json"
OUTPUT = ROOT / "results/pei_hwa_20261004_details"


def components(row):
    board1, arrive1, board2, arrive2 = row["time_offsets_minutes_from_query"]
    walk, egress = row["transfer_walk_minutes"], row["egress_walk_minutes"]
    if not 0 <= board1 <= arrive1 <= board2 <= arrive2 or walk < 0 or egress < 0:
        raise ValueError("Invalid itinerary time order")
    if walk > board2 - arrive1 or arrive2 + egress != row["total_minutes"]:
        raise ValueError("Itinerary components disagree with total")
    return {
        "initial_wait": board1,
        "ride": arrive1 - board1 + arrive2 - board2,
        "transfer_interval": board2 - arrive1,
        "transfer_wait_after_walk": board2 - arrive1 - walk,
        "walk": walk + egress,
        "total": row["total_minutes"],
    }


def build_extended(path):
    document = build_offline(path)
    pattern = select_pattern(load_rows(RAW / "BusRoutes.csv"), "95", "1", "16189", "11261")
    service = next(s for s in document["services"] if s["id"] == "95-D1")
    distances = [float(row["Distance"]) for row in pattern]
    service.update(
        stops=[row["BusStopCode"] for row in pattern],
        source_stop_sequences=[int(row["StopSequence"]) for row in pattern],
        ride_minutes=[max(0.5, round((b - a) * 3, 4)) for a, b in zip(distances, distances[1:])],
    )
    document["query_departures"] = ["2026-10-04T16:00:00+08:00"]
    document["provenance"]["extension_note"] = (
        "95-D1 extended one stop from 11401 to 11261 using the same frozen raw BusRoutes.csv. "
        "Timing assumptions unchanged; no Google times used to fit parameters."
    )
    Path(path).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return load_network(path)


def exact_route(network, first, second, transfer):
    legs = []
    for service_id, start, end in ((first, "16189", transfer), (second, transfer, "42171")):
        service = network.services[service_id]
        legs.append(Leg(service_id, start, end, service.ride_time(start, end),
                        service.headway_minutes / 2, 3.0 if legs else 0.0))
    route = Route("16189", "42171", legs)
    validate_route(route, network)
    return route


def run(output=OUTPUT, samples=10000, pressure=True):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    network_path = output / "network.json"
    network, source = build_extended(network_path)
    observations = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
    exact = {}
    for name, first, second, transfer in (
        ("151_61", "151-D2", "61-D2", "42141"),
        ("95_970", "95-D1", "970-D2", "11261"),
    ):
        route = exact_route(network, first, second, transfer)
        trial = evaluate(route, network, samples=samples, seed=100, departure_time=960,
                         parameters=RoutingParameters())
        exact[name] = {"route": asdict(route), "summary": asdict(trial.summary),
                       "ride_minutes_without_delay": route.ride_minutes}
    model, _ = evaluate_case(network_path, samples=samples, pressure=pressure)
    report = {
        "query_departure": observations["query_departure"],
        "observations_sha256": file_hash(OBSERVATIONS), "network_sha256": file_hash(network_path),
        "live_api_used": False, "model": model, "exact_transfer_routes": exact,
        "google_components": {row["id"]: components(row) for row in observations["routes"]},
        "endpoint_note": "Final stop 42171 inferred from exact stop name and existing static network; ID not printed in user details.",
        "timing_note": "Modeled waits and speeds remain stationary assumptions, not the October 4 timetable.",
    }
    (output / "experiment.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# Detailed Reference: 2026-10-04 16:00 SGT", "",
        "Latest user transcription supersedes the overview for this comparison only. Original records are unchanged.",
        "First total (48 minutes) is derived from 16:00 to 16:48; other totals are in the supplied headers.",
        "Final stop 42171 is inferred from the name Signature Pk Condo, not an ID printed in the details.", "",
        "## Google Planned Time Components", "",
        "| Services | Initial wait | Riding | Transfer interval | Walk within interval | Final walk | Total |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in observations["routes"]:
        c = components(row)
        lines.append(f"| {' -> '.join(row['services'])} | {c['initial_wait']} | {c['ride']} | "
                     f"{c['transfer_interval']} | {row['transfer_walk_minutes']} | {row['egress_walk_minutes']} | {c['total']} |")
    lines.extend(["", "Transfer interval INCLUDES the transfer walk; do not add that walk twice.",
                  "Walking estimates are approximate; residual waiting is inferred, not separately measured.",
                  "No walking leg is present for 151/61 or 95/970 in the latest text; this revises the earlier overview.",
                  "These are planned times, not observed journeys.", "", "## Exact Transfer Route Simulation", "",
                  f"{samples} samples, seed 100; unchanged headway 15 min, speed 20 km/h and delay bound 3 min.",
                  "95 is extended to 11261 from the frozen static CSV, not from Google's route timings.", "",
                  "| Route / transfer stop | Google total | Model mean | Model P95 | Google riding | Model riding, no delay |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for name, transfer in (("151_61", "42141"), ("95_970", "11261")):
        v, c = exact[name], report["google_components"][name]
        lines.append(f"| {name} / {transfer} | {c['total']} | {v['summary']['mean_minutes']:.2f} | "
                     f"{v['summary']['p95_minutes']:.2f} | {c['ride']} | {v['ride_minutes_without_delay']:.2f} |")
    lines.extend(["", "Exact transfer geometry is now modeled, but no dated timetable is fitted.",
                  "The first Google wait of 16 minutes exceeds the model's assumed Uniform(0,15) initial wait.",
                  "A difference against Google here measures model/schedule disagreement, not an algorithm win.", "",
                  "## Same-Model Algorithm Comparison", "",
                  "| Strategy | Mean | P95 |", "| --- | ---: | ---: |"])
    for label in ("shortest_expected", "full_adaptive", "bounded_adaptive"):
        s = model["evaluations"][label]["summary"]
        lines.append(f"| {label} | {s['mean_minutes']:.2f} | {s['p95_minutes']:.2f} |")
    lines.extend(["", "## Still Outside This Bus-Only Experiment", "",
                  "151 -> walk -> 174: transfer walk between Opp King Albert Pk Stn and King Albert Pk (42061).",
                  "96 -> 173: alights at Bef Jln Jurong Kechil, then walks about 400 m / 5 min to the destination place.",
                  "Neither walking itinerary is silently replaced by a different bus-only route or assigned an invented duration.",
                  "This comparison does not require any new API request. No Google screenshot or bulk route content is saved.", "",
                  "Reproduce: `python -m experiments.pei_hwa_details`.", "",
                  "This project is an independent research project and is not affiliated with,",
                  "endorsed by, or sponsored by the Land Transport Authority of Singapore,",
                  "Google, or Citymapper."])
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--samples", type=int, default=10000)
    args = parser.parse_args()
    run(args.output, args.samples)
    print(f"Report: {args.output / 'report.md'}")

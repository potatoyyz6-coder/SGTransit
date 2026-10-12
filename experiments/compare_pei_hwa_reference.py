"""Side-by-side manual observations, never a matched-time superiority test."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = ROOT / "data/validation/google_pei_hwa_20261004_1600.json"
MODEL = ROOT / "results/pei_hwa_20261001/experiment.json"
OUTPUT = ROOT / "results/pei_hwa_20261004_1600"


def compare(observations, model, network_path):
    network_path = Path(network_path)
    if not network_path.is_absolute():
        network_path = ROOT / network_path
    departure = datetime.fromisoformat(observations["query_departure"])
    if departure.utcoffset() != timedelta(hours=8):
        raise ValueError("Use an explicit Singapore departure time")
    if (observations["origin_stop_id"], observations["intended_destination_stop_id"]) != (
        model["origin"], model["destination"]
    ):
        raise ValueError("Intended endpoints do not match the model")
    if hashlib.sha256(Path(network_path).read_bytes()).hexdigest() != model["base"]["network_sha256"]:
        raise ValueError("Network snapshot hash mismatch")
    pairs = {("151", "61"): "reference_151_61", ("95", "970"): "reference_95_970"}
    rows = []
    for observed in observations["routes"]:
        pair = tuple(observed["services"])
        model_key = pairs.get(pair)
        entry = model["base"]["evaluations"].get(model_key) if model_key else None
        if observed["interchange_walk_visible"]:
            entry = None
            status = "Interchange walking edge not modeled"
        elif entry is None:
            status = "Service pair not represented in the current model"
        else:
            status = "Service-pair reference only; transfer/alighting stops and walking not matched"
        first_board = observed.get("first_boarding_sgt")
        initial_wait = None
        if first_board:
            board = datetime.fromisoformat(first_board)
            if board.utcoffset() != timedelta(hours=8) or board < departure:
                raise ValueError("Invalid first boarding timestamp")
            initial_wait = (board - departure).total_seconds() / 60
        rows.append({
            "services": list(pair), "google_displayed_minutes": observed["displayed_total_minutes"],
            "google_displayed_walk_minutes": observed["displayed_walk_minutes"],
            "query_to_first_board_minutes": initial_wait,
            "model_mean_minutes": entry["summary"]["mean_minutes"] if entry else None,
            "model_p95_minutes": entry["summary"]["p95_minutes"] if entry else None,
            "model_route": entry["route"] if entry else None,
            "status": status, "matched_comparison": False,
        })
    return {
        "query_departure": observations["query_departure"],
        "model_experiment": model["experiment"], "model_generated_at": model["generated_at"],
        "network_sha256": model["base"]["network_sha256"],
        "model_reused_without_rerun": True,
        "model_semantics": "Stationary assumed timing; not an October 4 timetable or Sunday prediction",
        "model_date_specific": False, "live_api_used": False,
        "comparisons": rows,
        "adaptive_reference": {key: model["base"]["evaluations"][key]["summary"]
                               for key in ("full_adaptive", "bounded_adaptive")},
        "limitations": [
            "All four Google options show final walking; the model ends at bus stop 42171.",
            "The destination is not visible in the crop. Same service numbers do not establish identical routes.",
            "No subtraction of walking or initial waiting from totals: components and endpoints are unverified.",
            "No Google-minus-model speedup is computed. Google observations do not change any model parameter.",
            "The October 1 experiment remains unchanged; only the external query is dated October 4.",
        ],
    }


def run(observations_path=OBSERVATIONS, model_path=MODEL, output=OUTPUT):
    observations = json.loads(Path(observations_path).read_text(encoding="utf-8"))
    model = json.loads(Path(model_path).read_text(encoding="utf-8"))
    report = compare(observations, model, model["network_path"])
    report["observations_sha256"] = hashlib.sha256(Path(observations_path).read_bytes()).hexdigest()
    report["model_report_sha256"] = hashlib.sha256(Path(model_path).read_bytes()).hexdigest()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# Google Reference: 2026-10-04 16:00 SGT", "",
        "Information Technology (16189) to intended Signature Pk Condo (42171).",
        "Manual user observations only; no screenshot saved or API accessed.", "",
        "The full date comes from the user. The crop shows Sunday, not the calendar date or destination.",
        "Model values reuse the October 1 stationary experiment; no new Sunday simulation or timetable is implied.", "",
        "| Services | Google displayed min | Model mean min | Model P95 min | Status |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in report["comparisons"]:
        number = lambda value: "N/A" if value is None else f"{value:.2f}"
        lines.append(f"| {' -> '.join(row['services'])} | {row['google_displayed_minutes']} | "
                     f"{number(row['model_mean_minutes'])} | {number(row['model_p95_minutes'])} | {row['status']} |")
    lines.extend(["", "## Scope Differences", "",
                  "151 -> 61 shows boarding at 16:16 after a 16:00 query, a 16-minute pre-boarding interval,",
                  "and 5 minutes walking with unknown allocation. Do not label 53 minutes as in-vehicle time",
                  "or assume 53 minus 5 matches the model. The model includes random initial waiting.", ""])
    lines.extend(f"- {note}" for note in report["limitations"])
    lines.extend(["", "## Next Evidence", "",
                  "For 151 -> 61, request the transfer stop, final alighting stop, and walking-leg endpoints/durations.",
                  "For 151 -> walk -> 174, a pedestrian connection must be identified before representing the itinerary.",
                  "96 -> 173 needs a separately verified network extension; no runtime is invented for it.", "",
                  "Reproduce: `python -m experiments.compare_pei_hwa_reference`.", "",
                  "This project is an independent research project and is not affiliated with,",
                  "endorsed by, or sponsored by the Land Transport Authority of Singapore,",
                  "Google, or Citymapper."])
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, default=OBSERVATIONS)
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.observations, args.model, args.output)
    print(f"Reference saved: {args.output / 'report.md'}")

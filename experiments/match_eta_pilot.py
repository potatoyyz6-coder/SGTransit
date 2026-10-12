"""Build auditable, provisional vehicle associations from the October 4 pilot."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import timedelta, timezone
import hashlib
from itertools import combinations
import json
from pathlib import Path

from data.real.build_subset import load_rows, select_pattern
from sg_transit.eta_matching import MatchParameters, build_associations, serialize, instant, follow_temporal

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    ("151", "2", ["16189", "12061", "12071", "42141", "42059"]),
    ("61", "2", ["12061", "12071", "42141", "42071", "42171"]),
    ("52", "2", ["12061", "42071"]),
    ("184", "1", ["12061", "42071"]),
    ("75", "2", ["12061", "42071"]),
    ("174", "2", ["42061", "42071", "42171"]),
    ("157", "1", ["42071", "42171"]),
    ("985", "2", ["42071", "42171"]),
    ("95", "1", ["16189", "11261"]),
    ("970", "2", ["11261", "42171"]),
]


def directed_pairs(path):
    rows = load_rows(path)
    pairs = []
    for service, direction, stops in PATTERNS:
        for upstream, downstream in combinations(stops, 2):
            select_pattern(rows, service, direction, upstream, downstream)
            pairs.append((service, upstream, downstream))
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/pei_hwa_20261004_1430")
    args = parser.parse_args()
    raw_paths = [ROOT / f"data/recorded/raw/eta_pilot_20261004_1430{suffix}.jsonl"
                 for suffix in ("", "_walk")]
    snapshots, sources = [], []
    for path in raw_paths:
        raw = path.read_bytes()
        sources.append({"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(raw).hexdigest()})
        for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
            row = json.loads(line)
            if row["type"] == "observation":
                snapshots.append((f"{path.name}:{number}", row))
    topology = ROOT / "data/real/raw/BusRoutes.csv"
    pairs = directed_pairs(topology)
    parameters = MatchParameters()
    result = build_associations(snapshots, pairs, parameters)
    counts = Counter()
    for edge in result["accepted"]:
        a, b = result["entries"][edge["source"]], result["entries"][edge["target"]]
        counts[(edge["kind"], a.service, a.stop, b.stop)] += 1
    examples = []
    cutoff = max(instant(r["received_at"]) for _, r in snapshots)
    for edge in result["accepted"]:
        a, b = result["entries"][edge["source"]], result["entries"][edge["target"]]
        if (edge["kind"] == "cross_stop" and a.stop == "16189" and b.stop in ("12071", "11261")
                and instant("2026-10-04T14:30:00+08:00") <= a.received
                <= instant("2026-10-04T15:20:00+08:00")):
            trace = follow_temporal(result, b.id, cutoff)
            last = result["entries"][trace["entry_ids"][-1]]
            examples.append({"service": a.service, "available_at": edge["available_at"],
                             "source_entry": a.id, "target_entry": b.id,
                             "origin_eta": a.eta.isoformat(), "transfer_eta": b.eta.isoformat(),
                             "transfer_stop": b.stop, "distance_m": edge["position_distance_m"],
                             "temporal_trace": trace, "last_received": last.received.isoformat(),
                             "last_transfer_eta": last.eta.isoformat()})
    cleaned = ROOT / "data/recorded/cleaned/eta_pilot_20261004_1430_associations.json"
    params = ROOT / "data/recorded/parameters/eta_pilot_20261004_1430_matching.json"
    for path in (cleaned, params):
        path.parent.mkdir(parents=True, exist_ok=True)
    provenance = {"sources": sources, "topology_sha256": hashlib.sha256(topology.read_bytes()).hexdigest(),
                  "directed_pairs": pairs, "parameters": asdict(parameters),
                  "identity_quality": "inferred_not_verified", "parameters_fitted": False}
    cleaned.write_text(json.dumps({"provenance": provenance, **serialize(result)}, indent=2) + "\n", encoding="utf-8")
    params.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    summary = {"sources": sources, "parameters": asdict(parameters),
               "accepted_association_count": len(result["accepted"]),
               "ambiguous_candidate_count": len(result["ambiguous_candidates"]),
               "rejected_entries": result["rejected_entries"],
               "counts": [{"kind": k[0], "service": k[1], "from": k[2], "to": k[3], "count": n}
                          for k, n in sorted(counts.items())],
               "origin_transfer_examples": examples}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "matching.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = ["# Provisional ETA-entry associations", "",
             "This project is an independent research project and is not affiliated with,",
             "endorsed by, or sponsored by the Land Transport Authority of Singapore,",
             "Google, or Citymapper.", "", "## Method", "",
             "Associations use only monitored entries with finite, nonzero positions and matching",
             "service, endpoint and visit fields. These are NOT guaranteed vehicle identities.",
             "Cross-stop links require direction verified in the frozen static topology,",
             "response skew <=5 seconds, position separation <=30m, and ordered ETAs.",
             "Temporal links require consecutive usable snapshots <=90 seconds apart,",
             "ETA drift <=120 seconds, and displacement <=70km/h plus 30m slack.",
             "These fixed gates are heuristic, not measured confidence or fitted parameters.",
             "Only isolated candidate edges are retained; ambiguous components are not assigned.",
             "A temporal chain breaks on missing/unmonitored/error evidence. Slots are not IDs.",
             "Events process in receive order; every edge has an available_at timestamp.",
             "A replay may not use an edge before that timestamp. Do not collapse all edges",
             "into definitive identity components: compounded errors and later ambiguity remain.", "",
             "## Counts", "",
             f"Accepted provisional edges: {len(result['accepted'])}.",
             f"Ambiguous candidate edges retained separately: {len(result['ambiguous_candidates'])}.",
             f"Rejected entries: {json.dumps(result['rejected_entries'])}.", "",
             "Counts are observation associations, not independent buses, journeys, or accuracy rates.", "",
             "## Origin-to-transfer examples", "",
             "All times Singapore. Each row is a same-time spatial association, not an observed ride.",
             "| Service | Evidence available | Origin ETA | Transfer stop | Transfer ETA | Position gap (m) |",
             "| --- | --- | --- | --- | --- | ---: |"]
    sgt = timezone(timedelta(hours=8))
    for example in examples:
        clock = lambda key: instant(example[key]).astimezone(sgt).strftime("%H:%M:%S")
        lines.append(f"| {example['service']} | {clock('available_at')} | {clock('origin_eta')} | "
                     f"{example['transfer_stop']} | {clock('transfer_eta')} | {example['distance_m']:.1f} |")
    lines += ["", "## Continuity of transfer forecasts", "",
              "Trace endpoints use later observations and belong to retrospective diagnostics,",
              "NOT information available at initial boarding. Multiple anchors may belong to the",
              "same inferred chain; row counts are not independent trials. No last ETA is treated",
              "as an actual arrival event, and a disappearing entry is not proof of alighting.", "",
              "| Service | Anchor evidence time | Trace entries | Last response | Last transfer ETA | End status |",
              "| --- | --- | ---: | --- | --- | --- |"]
    for example in examples:
        clock = lambda key: instant(example[key]).astimezone(sgt).strftime("%H:%M:%S")
        lines.append(f"| {example['service']} | {clock('available_at')} | "
                     f"{len(example['temporal_trace']['entry_ids'])} | {clock('last_received')} | "
                     f"{clock('last_transfer_eta')} | {example['temporal_trace']['status']} |")
    lines += ["", "## Remaining work", "",
              "Use these provisional links in a chronological replay with explicit unknown outcomes.",
              "An expired ETA, disappearing entry or matched position does not establish boarding,",
              "alighting, actual arrival or missed connection. Probability calibration still needs",
              "independent outcome evidence. No actual-trip time or speedup is reported here.", "",
              "Reproduce: `python -m experiments.match_eta_pilot` from the repository root.",
              "Detailed entry-level evidence and parameters remain in git-ignored data/recorded",
              "directories; summary results contain hashes and trace references.", ""]
    (args.output / "matching.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("counts", "origin_transfer_examples")}, indent=2))
    print(f"Origin-transfer evidence rows: {len(examples)}")


if __name__ == "__main__":
    main()

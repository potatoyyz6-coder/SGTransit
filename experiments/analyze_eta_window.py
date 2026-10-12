"""Analyze a saved scheduled ETA window without any API calls."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from data.real.build_subset import load_rows, select_pattern
from experiments.audit_eta_pilot import coverage
from experiments.match_eta_pilot import ROOT, PATTERNS, directed_pairs
from experiments.replay_eta_pilot import case_paths, projected_network
from sg_transit.eta_diagnostics import distribution, revision_diagnostics, snapshot_at, waiting_probe
from sg_transit.eta_matching import MatchParameters, build_associations, instant
from sg_transit.eta_policy import SuffixReplaySelector, expand_paths
from sg_transit.eta_replay import ReplayLimits, Ride, Tape, replay
from sg_transit.corridors import CorridorParameters, DestinationIndex, discover_candidates
from sg_transit.routing import RoutingParameters, enumerate_routes, route_key


DISCLAIMER = ("This project is an independent research project and is not affiliated with,\n"
              "endorsed by, or sponsored by the Land Transport Authority of Singapore,\n"
              "Google, or Citymapper.")


def source(path):
    return {"path": path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def replay_groups(rows, stops):
    base = case_paths()
    groups = {k: v for k, v in base.items() if k.startswith("fixed_") and
              all(isinstance(a, Ride) and a.start in stops and a.end in stops
                  for p in v for a in p)}
    # Include the same fixed hub route in the shared candidate pool. Differences
    # versus the Blk 116 reference are not effects of the decision rule alone.
    groups["fixed_151_61_blk109"] = [[Ride("151", "16189", "12061"), Ride("61", "12061", "42171")]]
    pool = base["first_eligible_hub_strategy"] + groups["fixed_151_61"]
    directions = {s: d for s, d, _ in PATTERNS}
    for path in pool:
        for a in path:
            if a.start not in stops or a.end not in stops:
                raise ValueError("Candidate contains an unrecorded decision stop")
            select_pattern(rows, a.service, directions[a.service], a.start, a.end)
    network = projected_network(rows, pool)
    expanded, routes = expand_paths(pool, network)
    # Expose exactly the same intermediate stops for fixed and flexible policies.
    groups = {k: expand_paths(v, network)[0] for k, v in groups.items()}
    groups["first_eligible"] = expanded
    groups["stationary_suffix"] = expanded
    return groups, network, routes


def validate_outcome(result, tape):
    if result["actual_outcome"] != "unknown":
        raise AssertionError("ETA replay cannot establish actual outcomes")
    if result["status"] == "modeled_complete":
        total = sum(result[k] for k in ("prefix_wait_minutes", "prefix_ride_minutes", "prefix_walk_minutes"))
        if abs(total - result["duration_minutes"]) > 1e-7:
            raise AssertionError("Journey time accounting mismatch")
    elif result["duration_minutes"] is not None or result["long_transfer_wait"] is not None:
        raise AssertionError("Unknown journey was assigned a score")
    for event in result["events"]:
        if event["kind"] in ("modeled_board", "stay_onboard"):
            for key in ("source_entry", "target_entry"):
                if tape.entries[event[key]].received > instant(event["at"]):
                    raise AssertionError("Future evidence used at boarding")


def reverse_search_audit(network):
    """Search-only comparison on the frozen projected network, not ETA quality."""
    parameters = RoutingParameters(max_transfers=2, max_candidates=10000)
    corridors = CorridorParameters()
    stats = {}
    full = enumerate_routes(network, "16189", "42171", parameters, stats=stats)
    index = DestinationIndex(network, "42171")
    bounded = discover_candidates(index, "16189", parameters, corridors)
    all_keys, kept = set(map(route_key, full)), set(map(route_key, bounded.routes))
    if not kept <= all_keys:
        raise AssertionError("Bounded search produced paths outside the full comparator")
    return {"kind": "static_projected_topology_search_only", "parameters": asdict(parameters),
            "corridor_parameters": asdict(corridors), "full_routes": len(full),
            "bounded_routes": len(bounded.routes), "full_expansions": stats["expansions"],
            "bounded_expansions": bounded.expansions, "candidate_recall": len(kept) / len(all_keys) if all_keys else None,
            "missed_routes": [asdict(r) for r in full if route_key(r) not in kept],
            "truncated": bounded.truncated, "truncation_reasons": bounded.truncation_reasons,
            "selected_hubs": [hub.stop for hub in bounded.selected_hubs],
            "both_searches_use_reverse_ride_bounds": True,
            "changes_replay_candidates": False,
            "note": "Expansion counts exclude preprocessing and are not latency. Missing route descriptions are not necessarily missing shared-graph recombinations. No full-trip quality benefit established."}


def run(config_path, output):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    raw_path = ROOT / config["raw_output"]
    records = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    snapshots = [(f"{raw_path.name}:{i}", r) for i, r in enumerate(records, 1)
                 if r["type"] == "observation"]
    completion = [r for r in records if r["type"] == "completion"]
    if not completion or completion[-1]["requests"] != len(snapshots) or completion[-1]["successful_requests"] != sum(r["status"] == "ok" for _, r in snapshots):
        raise ValueError("Missing or inconsistent completion record")
    departures = [instant(t) for t in config["departures"]]
    topology = ROOT / "data/real/raw/BusRoutes.csv"
    stops = set(config["stops"])
    pairs = [p for p in directed_pairs(topology) if p[1] in stops and p[2] in stops]
    parameters = MatchParameters()
    associations = build_associations(snapshots, pairs, parameters)
    tape = Tape(snapshots, associations)
    groups, network, routes = replay_groups(load_rows(topology), stops)
    runs, flat = [], []
    for departure in departures:
        for buffer in (60, 180, 300):
            for shift in (-60, 0, 60):
                limits = ReplayLimits(transfer_seconds=buffer, alight_shift_seconds=shift)
                selector = SuffixReplaySelector(network, routes, RoutingParameters(transfer_walk_minutes=buffer / 60))
                for name, paths in groups.items():
                    result = replay(tape, paths, departure, limits=limits,
                                    selector=selector if name == "stationary_suffix" else None)
                    validate_outcome(result, tape)
                    item = {"departure": departure.isoformat(), "buffer_seconds": buffer,
                            "alight_shift_seconds": shift, "strategy": name, "result": result}
                    runs.append(item)
                    flat.append({**{k: v for k, v in item.items() if k != "result"},
                                 **{k: result[k] for k in ("status", "duration_minutes", "prefix_wait_minutes",
                                     "transfer_count", "max_transfer_wait_minutes", "long_transfer_wait")}})
    probe_rows = []
    for sid, row in snapshots:
        if row["bus_stop_code"] != "12061":
            continue
        decision = instant(row["received_at"])
        for flag in (True, False):
            for incoming in (None, "151"):
                fixed = waiting_probe([(sid, row)], "12061", decision, ["61"], monitored=flag, incoming_service=incoming)
                multi = waiting_probe([(sid, row)], "12061", decision, ["61", "52", "75", "184"], monitored=flag, incoming_service=incoming)
                probe_rows.append({"fixed": fixed, "multi": multi})
    probe_summary = []
    for flag in (True, False):
        for incoming in (None, "151"):
            subset = [p for p in probe_rows if p["fixed"]["monitored"] == flag and p["fixed"]["incoming_service"] == incoming]
            paired = [p for p in subset if all(p[k]["predicted_wait_minutes"] is not None for k in ("fixed", "multi"))]
            probe_summary.append({"monitored": flag, "incoming_service": incoming, "snapshot_count": len(subset),
                "paired_count": len(paired),
                "fixed_statuses": dict(Counter(p["fixed"]["status"] for p in subset)),
                "multi_statuses": dict(Counter(p["multi"]["status"] for p in subset)),
                "fixed_wait_minutes": distribution([p["fixed"]["predicted_wait_minutes"] for p in paired]),
                "multi_wait_minutes": distribution([p["multi"]["predicted_wait_minutes"] for p in paired]),
                "fixed_wait_over_10_count": sum(p["fixed"]["predicted_wait_minutes"] > 10 for p in paired),
                "multi_wait_over_10_count": sum(p["multi"]["predicted_wait_minutes"] > 10 for p in paired)})
    checks = [{"departure": d.isoformat(), "stop": s,
               **{k: v for k, v in snapshot_at(snapshots, s, d).items() if k != "record"}}
              for d in departures for s in config["stops"]]
    revisions = revision_diagnostics(associations)
    provenance = {"sources": [source(config_path), source(raw_path), source(topology)],
                  "collection": {k: records[0][k] for k in ("source", "endpoint", "started_at", "deadline", "processing")},
                  "matching_parameters": asdict(parameters), "directed_pairs": pairs,
                  "probabilities_calibrated": False, "new_api_requests": 0,
                  "google_data_used": False, "actual_arrivals_available": False}
    report = {"kind": "offline_ETA_forecast_diagnostics_and_conditional_replay", **provenance,
              "completion": completion[-1], "coverage": coverage(records), "query_checks": checks,
              "matching": {"accepted_counts": dict(Counter(e["kind"] for e in associations["accepted"])),
                           "ambiguous_counts": dict(Counter(e["kind"] for e in associations["ambiguous_candidates"])),
                           "rejected_entries": associations["rejected_entries"]},
              "revision_summary": {k: v for k, v in revisions.items() if k != "evidence"},
              "probe_summary": probe_summary,
              "path_definitions": {k: [[asdict(a) for a in p] for p in ps] for k, ps in groups.items()},
              "stationary_model": {"headway_minutes": 15, "delay_max_minutes": 3,
                                   "ride_kmh": 20, "minimum_segment_minutes": .5,
                                   "transfer_penalty": 5, "samples": 64, "seed": 29,
                                   "fitted_to_capture": False},
              "reverse_search_audit": reverse_search_audit(network),
              "runs": runs}
    output.mkdir(parents=True, exist_ok=True)
    stem = raw_path.stem
    for subdir, suffix, content in (("cleaned", "diagnostics", {"revisions": revisions["evidence"], "probes": probe_rows}),
                                    ("parameters", "analysis", provenance)):
        path = ROOT / "data/recorded" / subdir / f"{stem}_{suffix}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    (output / "analysis.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (output / "replay.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    (output / "analysis.md").write_text(render(report, config_path), encoding="utf-8")
    print(json.dumps({"replays": len(runs), "statuses": dict(Counter(r["result"]["status"] for r in runs)),
                      "matching": report["matching"], "probes": probe_summary}, indent=2))
    return report


def render(report, config_path):
    def fmt(value):
        return "unknown" if value is None else f"{value:.2f}"
    lines = ["# Recorded ETA window analysis", "", DISCLAIMER, "",
        "## Scope", "", "Offline analysis only; zero new API requests. Times use Singapore UTC+08:00.",
        "Four virtual demands are not four observed passenger trips or independent samples.",
        "No Google comparison or actual catch/long-wait probability is possible from this recording alone.", "",
        "## Coverage", "", "| Stop | Responses | Errors | Max gap (s) | Monitored entries | Unmonitored entries |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in report["coverage"]:
        counts = r["monitored_flag_entry_counts"]
        lines.append(f"| {r['stop']} | {r['successful_requests']} | {r['failed_requests']} | {fmt(r['max_gap_seconds'])} | {counts.get('True', 0)} | {counts.get('False', 0)} |")
    lines += ["", f"Fresh departure/stop snapshots: {sum(c['status'] == 'available' for c in report['query_checks'])}/{len(report['query_checks'])}.",
        "Fresh snapshots do not guarantee continuous monitored vehicle evidence.", "",
        "## Conditional replay", "", "Three-minute transfer buffer; zero alighting ETA shift.",
        "Fixed routes and both flexible policies expose the same recorded intermediate stops.",
        "Fixed routes are declared in advance, not chosen from their realized outcomes.",
        "The flexible pool contains all three fixed paths plus the Blk 109 -> Pei Hwa branches.",
        "No walking alternative is replayed: its connecting stops were not collected.",
        "The 96 -> 173 route is also outside this capture. No results are imputed for either.", "",
        "| Departure | Strategy | Status | Modeled total (min) | Prefix wait (min) |",
        "| --- | --- | --- | ---: | ---: |"]
    for run in report["runs"]:
        if run["buffer_seconds"] == 180 and run["alight_shift_seconds"] == 0:
            r = run["result"]
            lines.append(f"| {run['departure'][11:16]} | {run['strategy']} | {r['status']} | {fmt(r['duration_minutes'])} | {fmt(r['prefix_wait_minutes'])} |")
    lines += ["", "Unknown is not a failed transfer, slow trip, or successful completion.",
        "Prefix waiting is a partial accounted lower bound, not a complete journey score.",
        "Never rank completed-only results against censored alternatives.",
        "Full traces and all 1/3/5-minute-buffer x -60/0/+60-second-shift scenarios are in analysis.json and replay.csv.",
        "The nine scenarios per demand are correlated sensitivity checks, not probability samples.", "",
        "## Blk 109 forecast opportunities", "",
        "At each of 120 response times compare 61 alone against 61/52/75/184, with a three-minute buffer.",
        "A station probe assumes availability now; a 151 probe uses that snapshot's earliest future 151 ETA.",
        "The latter is NOT matched to the bus boarded at the origin. Only same-flag predictions are paired.",
        "Wait includes the transfer buffer. Paired rows require both sets to have a future eligible prediction.",
        "Unmonitored and monitored forecasts are deliberately not pooled; missing predictions remain unknown.", "",
        "| Monitored | Probe | Paired / all snapshots | 61 mean forecast wait | Multi mean forecast wait | 61 >10m count | Multi >10m count |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in report["probe_summary"]:
        lines.append(f"| {r['monitored']} | {r['incoming_service'] or 'station now'} | {r['paired_count']}/{r['snapshot_count']} | {fmt(r['fixed_wait_minutes']['mean'])} | {fmt(r['multi_wait_minutes']['mean'])} | {r['fixed_wait_over_10_count']} | {r['multi_wait_over_10_count']} |")
    lines += ["", "These are overlapping forecast snapshots, not independent waits or long-wait probabilities.",
        "Taking the minimum over a superset cannot increase this local forecast wait by construction.",
        "This does not establish a faster full trip: alternative services may require another transfer.", "",
        "## Forecast revisions", "",
        "Only unique monitored temporal associations passing fixed gates are used.",
        "Positive means a later absolute ETA, not countdown time elapsed and not measured lateness.",
        "The matcher rejects revisions over 120 seconds and ambiguous/missing positions.",
        "Thus these conditional quantiles are selection-truncated and MUST NOT calibrate ETA errors.", "",
        "| Stop | Service | Matched updates | Median absolute revision (s) | P95 absolute revision (s) | Later >30s | Earlier >30s |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in report["revision_summary"]["groups"]:
        if r["service"] in ("151", "61", "52", "75", "184", "95", "970"):
            d = r["absolute_seconds"]
            lines.append(f"| {r['stop']} | {r['service']} | {d['count']} | {fmt(d['p50'])} | {fmt(d['p95'])} | {r['later_over_30_seconds']} | {r['earlier_over_30_seconds']} |")
    search = report["reverse_search_audit"]
    lines += ["", "## Reverse-search check", "",
        "Both existing full enumeration and hub-oriented candidate discovery already use reverse directed ride-time bounds.",
        "This check compares those existing searches, not a new fluid algorithm. Maximum two transfers on the projected network.",
        f"Full enumeration: {search['full_routes']} routes / {search['full_expansions']} expansions.",
        f"Hub-oriented search: {search['bounded_routes']} routes / {search['bounded_expansions']} expansions; selected hubs: {search['selected_hubs']}.",
        f"Candidate recall: {search['candidate_recall']:.3f}; missing route descriptions: {len(search['missed_routes'])}.",
        f"Truncated: {search['truncated']}; reasons: {search['truncation_reasons']}.",
        "Search counts exclude indexing overhead and do not prove a wall-clock speedup.",
        "Candidate recall is not executable shared-graph recall; shared branches may recombine into omitted descriptions.",
        "No quality gain is claimed and this audit does not change the declared ETA-replay candidate pool.",
        "Raw bus count is not an adequate downstream value: remaining riding, transfer waits, direction,",
        "vehicle continuation and correlated arrivals all matter. The current ride lower bound has no waiting-risk model.",
        "Cache reusable downstream structure, retain bypasses and measure omissions before more aggressive hub pruning.",
        "", "## Assumptions and next decision", "",
        "ETA-as-event replay remains conditional on provisional identity, freshness <=90s and five-second onboard observation grace.",
        "Same-bus continuation has no extra boarding, transfer or waiting. Ambiguity remains unknown.",
        "Only evidence received by the virtual decision time can enter a decision; later updates only advance replay chronologically.",
        "The stationary suffix policy uses existing mean-plus-transfer scoring, H=15min, distance/20kmh (>=0.5min per original segment),",
        "delay_max=3min, 64 draws/seed29 and a five-minute transfer penalty. These assumptions are NOT fitted to today's data.",
        "Limits of 5 transfers/45-minute gap/120-minute trip are model constraints, not verified fare law.",
        "Reverse downstream propagation can reuse shared route structure, but cannot fix missing vehicle identity or ETA error.",
        "Do not loosen identity gates or substitute unmonitored forecasts merely to manufacture complete trips.",
        "Priority before a catch-probability claim: independently observed arrival evidence or a separately validated error model.",
        "No additional collection window is authorized or started by this analysis.", "",
        "## Reproduce", "", f"`python -m experiments.analyze_eta_window --config {config_path.relative_to(ROOT).as_posix()}`", "",
        "Requires the locally retained, git-ignored recording and frozen BusRoutes.csv. Source hashes and parameters are in analysis.json.",
        "Detailed revision/probe evidence is in data/recorded/cleaned; analysis parameters in data/recorded/parameters.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "experiments/eta_window_20261007.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/eta_20261007_1000")
    args = parser.parse_args()
    run(args.config.resolve(), args.output.resolve())

"""Conditional, causal route replay of saved ETAs; never a ground-truth score."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from data.real.build_subset import load_rows, select_pattern
from experiments.match_eta_pilot import ROOT, PATTERNS, directed_pairs
from sg_transit.eta_matching import MatchParameters, build_associations, instant
from sg_transit.eta_replay import ReplayLimits, Ride, Tape, Walk, replay
from sg_transit.eta_policy import SuffixReplaySelector, expand_paths
from sg_transit.models import Stop, TransitNetwork, TransitService
from sg_transit.routing import RoutingParameters


def case_paths():
    fixed151 = [Ride("151", "16189", "12071"), Ride("61", "12071", "42171")]
    fixed95 = [Ride("95", "16189", "11261"), Ride("970", "11261", "42171")]
    flexible = [[Ride("151", "16189", "12061"), Ride("61", "12061", "42171")]]
    for service in ("52", "75", "184"):
        for last in ("61", "157", "174", "985"):
            flexible.append([Ride("151", "16189", "12061"), Ride(service, "12061", "42071"),
                             Ride(last, "42071", "42171")])
    flexible.append(fixed95)
    return {
        "fixed_151_61": [fixed151],
        "fixed_95_970": [fixed95],
        "fixed_151_walk_174": [[Ride("151", "16189", "42059"), Walk("42059", "42061", 5),
                                 Ride("174", "42061", "42171")]],
        "first_eligible_hub_strategy": flexible,
    }


def projected_network(rows, paths):
    """Keep decision stops; preserve distance-based stationary timing assumptions."""
    by_service = {}
    for path in paths:
        for action in path:
            by_service.setdefault(action.service, set()).update((action.start, action.end))
    directions = {s: d for s, d, _ in PATTERNS}
    services = []
    for service, stops in sorted(by_service.items()):
        pattern = sorted((r for r in rows if r["ServiceNo"] == service
                          and r["Direction"] == directions[service]), key=lambda r: int(r["StopSequence"]))
        ordered = [r["BusStopCode"] for r in pattern if r["BusStopCode"] in stops]
        rides = []
        for a, b in zip(ordered, ordered[1:]):
            segment = select_pattern(rows, service, directions[service], a, b)
            distance = [float(r["Distance"]) for r in segment]
            rides.append(sum(max(0.5, (v - u) * 3) for u, v in zip(distance, distance[1:])))
        services.append(TransitService(service, tuple(ordered), tuple(rides), 15, 3))
    return TransitNetwork([Stop(s, s) for s in sorted(set.union(*by_service.values()))], services)


def run(output, *, long_wait_minutes=10, transfer_penalty=5):
    sources, snapshots = [], []
    for suffix in ("", "_walk"):
        path = ROOT / f"data/recorded/raw/eta_pilot_20261004_1430{suffix}.jsonl"
        raw = path.read_bytes()
        sources.append({"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(raw).hexdigest()})
        for number, line in enumerate(raw.decode().splitlines(), 1):
            row = json.loads(line)
            if row["type"] == "observation":
                snapshots.append((f"{path.name}:{number}", row))
    topology = ROOT / "data/real/raw/BusRoutes.csv"
    rows, paths = load_rows(topology), case_paths()
    policy_network = projected_network(rows, paths["first_eligible_hub_strategy"])
    expanded, policy_routes = expand_paths(paths["first_eligible_hub_strategy"], policy_network)
    directions = {s: d for s, d, _ in PATTERNS}
    for group in paths.values():
        for path in group:
            for action in path:
                if isinstance(action, Ride):
                    select_pattern(rows, action.service, directions[action.service], action.start, action.end)
    matching = MatchParameters()
    associations = build_associations(snapshots, directed_pairs(topology), matching)
    tape = Tape(snapshots, associations)
    departure = instant("2026-10-04T14:30:00+08:00")
    scenarios = {}
    for buffer in (60, 180, 300):
        for shift in (-60, 0, 60):
            key = f"buffer_{buffer}_shift_{shift}"
            limits = ReplayLimits(transfer_seconds=buffer, alight_shift_seconds=shift,
                                  long_wait_seconds=long_wait_minutes * 60)
            scenarios[key] = {"limits": asdict(limits), "strategies": {
                name: replay(tape, group, departure, limits=limits) for name, group in paths.items()}}
            parameters = RoutingParameters(transfer_walk_minutes=buffer / 60, transfer_penalty=transfer_penalty)
            selector = SuffixReplaySelector(policy_network, policy_routes, parameters)
            scenarios[key]["strategies"]["first_eligible_shared_stops"] = replay(tape, expanded, departure, limits=limits)
            scenarios[key]["strategies"]["stationary_suffix_policy"] = replay(tape, expanded, departure,
                                                                                 limits=limits, selector=selector)
    report = {"kind": "conditional_ETA_as_event_replay_not_actual_journeys", "sources": sources,
              "topology_sha256": hashlib.sha256(topology.read_bytes()).hexdigest(),
              "departure": departure.isoformat(), "matching_parameters": asdict(matching),
              "path_definitions": {k: [[asdict(a) for a in p] for p in v] for k, v in paths.items()},
              "shared_stop_paths": [[asdict(a) for a in p] for p in expanded],
              "suffix_network_services": [asdict(s) for s in policy_network.services.values()],
              "transfer_penalty": transfer_penalty,
              "suffix_value_samples": 64, "suffix_value_seed": 29,
              "suffix_scoring_note": "Existing SharedSuffixPolicy.update; stationary expected remaining time plus configured transfer penalty, not calibrated P90/P95 optimization. H=15min, ride=max(0.5min, distance/20kmh) per original segment, delay_max=3min.",
              "scenarios": scenarios,
              "probabilities_calibrated": False, "google_ride_or_wait_times_used": False,
              "manual_reference_walk_used_as_scenario_input": True,
              "walking_note": "Five-minute reference walk is an explicit scenario input, not inferred pedestrian accessibility or a fitted routing edge."}
    output.mkdir(parents=True, exist_ok=True)
    (output / "replay.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Conditional ETA route replay", "",
             "This project is an independent research project and is not affiliated with,",
             "endorsed by, or sponsored by the Land Transport Authority of Singapore,",
             "Google, or Citymapper.", "", "## What this evaluates", "",
             "One virtual departure at 2026-10-04 14:30 Singapore time. Fixed service sequences",
             "and a first-eligible hub policy see the same received observations. This is not",
             "a replay of a real passenger, a calibrated reliability score, or a Google speed test.",
             "The hub policy admits 151 -> Blk 109 -> 61 directly, or 52/75/184 to Pei Hwa",
             "followed by 61/157/174/985. It also admits 95 -> 970 via Holland Village.",
             "It selects the first currently eligible matched bus, not the best hindsight outcome.",
             "The existing SharedSuffixPolicy.update is also run on the same recorded-stop",
             "network as first_eligible_shared_stops. The original first_eligible_hub_strategy",
             "uses longer ride legs; use the shared-stops pair to isolate the decision rule.",
             "Suffix values use fixed 15-minute headways, distance/20kmh segment times (at least",
             f"0.5 minutes each), delay_max=3 minutes and a {transfer_penalty}-minute transfer penalty. They are",
             "not fitted to this capture or Google. Only current-stop departures enter decisions.",
             "The existing local score is expected remaining time plus transfer penalties,",
             "NOT a calibrated P90/P95 or catch-probability objective. Current executable arcs",
             "are restricted to retained path prefixes; the downstream value model is unchanged.", "",
             "## Explicit event assumptions", "",
             "- A future boarding ETA is revised while new observations arrive before boarding.",
             "- A ride advances on the tracked destination ETA. This ETA-as-event assumption",
             "  is a model substitute, not evidence of actual arrival or successful boarding.",
             "- Only provisional monitored-position associations are used; gaps, ambiguities,",
             "  stale evidence (>90 seconds), and the end of the capture produce unknown outcomes.",
             "- Local boarding forecasts without cross-stop matches cannot be silently skipped",
             "  in favor of a later matched bus. A pending boarding forecast that moves behind",
             "  the next polling time is unknown, not an observed missed bus or extra headway.",
             "- Same-vehicle continuation has no new boarding, waiting time, or transfer penalty.",
             "  It preserves a previous cross-stop association while both endpoints retain",
             "  unique, fresh temporal chains. It does not require a new spatial match from",
             "  scratch at every intermediate stop; ambiguous chains remain unknown.",
             "  A bounded five-second observation grace accommodates sequential stop requests;",
             "  this modeled onboard time is counted as riding, not as station waiting. It does",
             "  not establish actual dwell time. Longer missing continuation evidence is unknown.",
             "- Walking is a five-minute scenario input for the manually referenced connector,",
             "  not a validated pedestrian route; it is counted once. The transfer buffer is",
             "  added after the walk. Initial and transfer waiting are kept separate from walking.",
             "- The limits are modeling constraints (5 transfers, 45-minute gaps, 2-hour trip),",
             "  not a verified implementation of current Singapore fare law.",
             "- No independent Monte Carlo samples are created from repeated ETA updates.",
             "  Sensitivity scenarios are not independent journeys and do not yield probabilities.", "",
             "## Base scenario: three-minute transfer buffer, no ETA shift", "",
             "| Strategy | Status | Modeled total (min) | Prefix wait (min) | Max transfer wait (min) | Transfers |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    base = scenarios["buffer_180_shift_0"]["strategies"]
    for name, value in base.items():
        duration = f"{value['duration_minutes']:.2f}" if value["duration_minutes"] is not None else "unknown"
        max_wait = f"{value['max_transfer_wait_minutes']:.2f}" if value["max_transfer_wait_minutes"] is not None else "unknown"
        lines.append(f"| {name} | {value['status']} | {duration} | {value['prefix_wait_minutes']:.2f} | {max_wait} | {value['transfer_count']} |")
    lines += ["", "Prefix waits for incomplete trips are lower bounds, not full-journey scores.",
              "Do not rank completed-only rows against censored rows or impute missing time.", "",
              "An early implementation silently skipped unresolved boarding forecasts and",
              "produced an inflated 65.27-minute fixed 151 -> 61 result. That result is invalid",
              "and superseded: the corrected outcome is unknown at the boarding interval.", "",
              f"Configured long-wait threshold: strictly greater than {long_wait_minutes} minutes.",
              "This is a per-replay event flag, not a probability. Unknown trip flags stay null.",
              "The suffix policy uses 151 -> 61 at Blk 109, whereas the fixed external-reference",
              "variant transfers at Blk 116. Do not attribute their difference solely to scoring.", "",
              "## Sensitivity", "",
              "Buffers: 1, 3, 5 minutes. Alighting-event shifts: -60, 0, +60 seconds.",
              "The shift tests an assumption; it is not an empirically fitted error distribution.", "",
              "| Scenario | Strategy | Status | Modeled total (min) |",
              "| --- | --- | --- | ---: |"]
    for name, scenario in scenarios.items():
        for strategy, value in scenario["strategies"].items():
            duration = f"{value['duration_minutes']:.2f}" if value["duration_minutes"] is not None else "unknown"
            lines.append(f"| {name} | {strategy} | {value['status']} | {duration} |")
    lines += ["", "## External reference", "",
              "The manually reported Google alternatives were 44/52/63/68 minutes from the",
              "common 14:30 clock. Their observed actual outcomes are unknown. First bus selection",
              "here follows observed ETA updates, not Google's specified departure, so differences",
              "are not algorithm speedups. Google times are not used to generate ride events.", "",
              "## Reproduction", "", "`python -m experiments.replay_eta_pilot`", "",
              "Source hashes, scenario parameters, route definitions, trace entry references and",
              "decision timestamps are in replay.json. No new API calls are made.", ""]
    (output / "replay.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({name: {k: v for k, v in value.items() if k not in ("events", "decisions")} for name, value in base.items()}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/pei_hwa_20261004_1430")
    parser.add_argument("--long-wait-minutes", type=float, default=10)
    parser.add_argument("--transfer-penalty", type=float, default=5)
    args = parser.parse_args()
    run(args.output, long_wait_minutes=args.long_wait_minutes, transfer_penalty=args.transfer_penalty)

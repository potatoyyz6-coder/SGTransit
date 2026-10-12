"""Frozen local bus topology, reproducible OD sampling and preference comparison."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import random
from time import perf_counter

import networkx as nx
import numpy as np

from data.real.build_subset import RAW, SEGMENTS as EARLIER_SEGMENTS, load_rows, select_pattern
from experiments.fair_benchmark import safe
from experiments.pei_hwa_case import SEGMENTS
from sg_transit.adaptive import SharedSuffixPolicy
from sg_transit.benchmark import WorldModel, Worlds, audit_candidate_closure, execute, paired_difference
from sg_transit.models import Leg, Route, Stop, TransitNetwork, TransitService, validate_route
from sg_transit.preferences import DistributionalPolicy, Preference, select_fixed_preferences
from sg_transit.routing import RoutingParameters, SearchBudgetExceeded, enumerate_routes, route_key

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results/local_routes_20261007"
HOME = ("16189", "42171")
HUBS = frozenset({"16189", "12061", "12071", "42141", "42071", "42171", "11401", "11261",
                  "16009", "16089", "17161", "28009"})


def build_network():
    source = json.loads((ROOT / "data/real/sources.json").read_text(encoding="utf-8"))
    for name, digest in source["raw_sha256"].items():
        if hashlib.sha256((RAW / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen topology hash mismatch: {name}")
    rows = load_rows(RAW / "BusRoutes.csv")
    stops = {r["BusStopCode"]: r for r in load_rows(RAW / "BusStops.csv")}
    segments = [(s, d, a, "11261" if s == "95" else b) for s, d, a, b in SEGMENTS]
    segments.append(("75", "2", "12061", "42071"))
    segments.extend((s, d, a, b) for s, d, a, b, _ in EARLIER_SEGMENTS)
    services = []
    for sid, direction, start, end in segments:
        pattern = select_pattern(rows, sid, direction, start, end)
        distances = [float(r["Distance"]) for r in pattern]
        if any(b < a for a, b in zip(distances, distances[1:])):
            raise ValueError("Nonmonotonic source distance")
        services.append(TransitService(f"{sid}-D{direction}", tuple(r["BusStopCode"] for r in pattern),
                        tuple(max(.5, round((b-a)*3, 4)) for a, b in zip(distances, distances[1:])), 15, 3))
    used = sorted({s for service in services for s in service.stops})
    network = TransitNetwork([Stop(s, stops[s]["Description"], float(stops[s]["Longitude"]),
                                   float(stops[s]["Latitude"])) for s in used], services)
    return network, source


def project(network, origin, destination):
    """Only explicit hubs and query endpoints allow alighting/boarding decisions."""
    keep = HUBS | {origin, destination}
    services = []
    for s in network.services.values():
        retained = tuple(stop for stop in s.stops if stop in keep)
        if len(retained) >= 2:
            services.append(TransitService(s.id, retained,
                            tuple(s.ride_time(a, b) for a, b in zip(retained, retained[1:])),
                            s.headway_minutes, s.delay_max_minutes))
    return TransitNetwork([s for k, s in network.stops.items() if k in keep], services)


def sample_queries(network, seed=20261007):
    pools = {0: [], 1: [], 2: []}
    for origin in sorted(network.stops):
        graph = nx.DiGraph()
        graph.add_nodes_from(network.stops)
        for start in sorted((HUBS | {origin}) & network.stops.keys()):
            graph.add_edges_from((start, end) for end, _, _ in network.neighbors(start))
        for destination, boardings in sorted(nx.single_source_shortest_path_length(graph, origin).items()):
            if destination == origin or (origin, destination) == HOME:
                continue
            transfers = boardings - 1
            if transfers in pools:
                pools[transfers].append((origin, destination))
    rng = random.Random(seed)
    queries = [{"id": "home", "origin": HOME[0], "destination": HOME[1], "stratum": "specified"}]
    for transfers, count in ((0, 7), (1, 7), (2, 6)):
        if len(pools[transfers]) < count:
            raise ValueError(f"Insufficient OD pairs in stratum {transfers}: {len(pools[transfers])}")
        for origin, destination in rng.sample(pools[transfers], count):
            queries.append({"id": f"random_{len(queries):02d}", "origin": origin,
                            "destination": destination, "stratum": transfers})
    return {"sampling_seed": seed, "pool_sizes": {str(k): len(v) for k, v in pools.items()}, "queries": queries}


def named_route(route, full):
    return " | ".join(f"{leg.service_id}: {full.stops[leg.board_stop].name} ({leg.board_stop}) -> "
                      f"{full.stops[leg.alight_stop].name} ({leg.alight_stop})" for leg in route.legs)


class ExamplePolicy(DistributionalPolicy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = []

    def update(self, *args, **kwargs):
        decision = super().update(*args, **kwargs)
        if decision:
            self.actions.append(decision.arc)
        return decision


def example(policy, worlds, full):
    one = Worlds({k: v[:1] for k, v in worlds.phases.items()},
                 {k: v[:1] for k, v in worlds.delays.items()}, 1, worlds.seed)
    trial = execute(policy, one)
    legs = []
    for arc in policy.actions:
        if legs and legs[-1].service_id == arc.service_id:
            prev = legs[-1]
            legs[-1] = Leg(arc.service_id, prev.board_stop, arc.end, prev.ride_minutes + arc.ride_minutes)
        else:
            legs.append(Leg(arc.service_id, arc.start, arc.end, arc.ride_minutes))
    complete = bool(np.isfinite(trial.durations[0]))
    route = Route(policy.origin, policy.destination if complete else (legs[-1].alight_stop if legs else policy.origin), legs)
    validate_route(route, full)
    return {"world_index": 0, "complete": complete, "route": asdict(route),
            "text": named_route(route, full), "minutes": float(trial.durations[0]),
            "note": "One reproducible example, not the whole adaptive strategy"}


def run_query(full, query, *, variant="base", samples=1000, training_samples=256,
              rollout_samples=64, output=OUTPUT):
    if any(not isinstance(n, int) or n < 1 for n in (samples, training_samples, rollout_samples)):
        raise ValueError("Sample counts must be positive integers")
    start = perf_counter()
    network = project(full, query["origin"], query["destination"])
    p = RoutingParameters(max_transfers=2, max_candidates=500, max_expansions=30000)
    if variant == "headway20":
        network = TransitNetwork(network.stops.values(), [replace(s, headway_minutes=20) for s in network.services.values()])
    elif variant == "delay8":
        network = TransitNetwork(network.stops.values(), [replace(s, delay_max_minutes=8) for s in network.services.values()])
    elif variant == "buffer5":
        p = replace(p, transfer_walk_minutes=5)
    elif variant not in {"base", "synchronized"}:
        raise ValueError("Unknown sensitivity variant")
    model = WorldModel(phase_groups={k: "shared" for k in network.services}) if variant == "synchronized" else WorldModel()
    result = {"query": query, "variant": variant, "parameters": asdict(p), "samples": samples,
              "training_samples": training_samples, "rollout_samples": rollout_samples,
              "training_seed": 7001, "test_seed": 9001, "rollout_seed": 2309,
              "world_model": asdict(model), "status": "started", "stage": "search",
              "candidate_search_complete": False, "search": {}, "evaluations": {}}
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    try:
        routes = enumerate_routes(network, query["origin"], query["destination"], p, stats=result["search"])
        result.update(candidate_search_complete=True, stage="candidate_validation")
        if not routes:
            raise ValueError("No legal route within declared constraints")
        # Projected loops through hidden intermediate stops must never pass unnoticed.
        for route in routes:
            validate_route(route, full)
        shared = SharedSuffixPolicy(network, routes, p)
        result["candidate_audit"] = audit_candidate_closure(shared, routes, max_expansions=30000)
        result["search_ms"] = (perf_counter() - start) * 1000
        result["candidates"] = [{"route": asdict(r), "text": named_route(r, full)} for r in routes]
        result["stage"] = "training_selection"
        prefs = {k: Preference(k) for k in ("fast", "cool", "reliable")}
        train = Worlds.generate(network, training_samples, 7001, model)
        selected, rows = select_fixed_preferences(routes, network, p, train, prefs)
        test = Worlds.generate(network, samples, 9001, model)
        result["training_scores"] = rows
        result["test_world_sha256"] = test.fingerprint()
        result["selected_fixed"] = {k: {"route": asdict(r), "text": named_route(r, full)} for k, r in selected.items()}
        result["stage"] = "heldout_evaluation"
        trials, times, cache = {}, {}, {}
        for label, route in selected.items():
            tick = perf_counter()
            key = route_key(route)
            if key not in cache:
                cache[key] = execute(SharedSuffixPolicy(network, [route], p), test, controller="first")
            trials[f"fixed_{label}"] = cache[key]
            times[f"fixed_{label}"] = (perf_counter() - tick)*1000
        examples = {}
        for label, pref in prefs.items():
            tick = perf_counter()
            policy = ExamplePolicy(network, routes, p, preference=pref, rollout_samples=rollout_samples,
                                   max_suffix_paths=500, max_suffix_states=10000)
            examples[label] = example(policy, test, full)
            # Avoid retaining per-decision traces for the full Monte Carlo run.
            policy = DistributionalPolicy(network, routes, p, preference=pref, rollout_samples=rollout_samples,
                                         max_suffix_paths=500, max_suffix_states=10000)
            trials[f"dynamic_{label}"] = execute(policy, test)
            times[f"dynamic_{label}"] = (perf_counter()-tick)*1000
        for label, controller in (("first_eligible", "first"), ("legacy_scored", "scored")):
            tick = perf_counter()
            trials[label] = execute(shared, test, controller=controller)
            times[label] = (perf_counter()-tick)*1000
        result.update(status="completed", stage="complete", dynamic_examples=examples,
                      evaluations={k: {"summary": t.summary(), "boardings": t.branches,
                                       "evaluation_ms": times[k]} for k, t in trials.items()},
                      paired={f"dynamic_{k}_minus_fixed_{k}": paired_difference(trials[f"dynamic_{k}"], trials[f"fixed_{k}"],
                                                                                 bootstrap_samples=100) for k in prefs})
        np.savez_compressed(out / f"{query['id']}_{variant}.npz", **{
            f"{k}__{metric}": getattr(t, metric) for k,t in trials.items()
            for metric in ("durations", "waits", "buffers", "rides", "transfers", "max_transfer_wait")})
    except (SearchBudgetExceeded, ValueError) as exc:
        result.update(status="budget_exceeded" if isinstance(exc, SearchBudgetExceeded) else "invalid_case",
                      error=str(exc))
    result["total_seconds"] = perf_counter() - start
    (out / f"{query['id']}_{variant}.json").write_text(json.dumps(safe(result), indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return safe(result)


def write_report(results, manifest, full, output):
    out = Path(output)
    lines = ["# Local Stop-Pair Experiment", "", "Historical real bus topology; all timing is assumed, not observed or live.",
             "No API or Google data used. Twenty stratified random OD pairs plus the specified home trip.",
             "Seven pairs require zero transfers, seven one, six two, within the declared local transfer model.",
             "Sampling seed: " + str(manifest["sampling_seed"]) + ". Manifest is saved before evaluating any pair.", "",
             "## Scope", "", "Transfer decisions are allowed only at: " + ", ".join(sorted(HUBS)) + ".",
             "Other stops remain eligible endpoints. Intermediate riding time is summed, not removed.",
             "Complete search means only within this restricted model, at most two transfers, 120 minutes,",
             "45-minute transfer gap; not complete area or Singapore routing. Direction and expanded original-stop",
             "loop validity are checked for every candidate. Graph recombination must not give dynamic extra routes.",
             "Search caps: 500 routes, 30,000 expansions. Budget/error cases remain listed; no replacement sampling.",
             "Timing: 20km/h distance conversion, at least 0.5min per original segment; headway15, delay U(0,3), buffer3.",
             "Home sensitivities change headway, delay, buffer or phase dependence one at a time.",
             "All are stationary assumptions, not forecasts for a calendar departure. Static provenance is in manifest.json.",
             "Default 1,000 held-out worlds / 256 training worlds per query, 64 separate rollout draws.",
             "Each mode selects a fixed route on training data; dynamic modes use the same candidate graph and test worlds.",
             "Fast=min mean; cool=mean+2*wait+3*transfers; reliable=projected P95. Completion takes priority.",
             "Independent stationary rollouts do not learn phase correlations; no global-P95 optimality claim.", "",
             "## Results", "", "Minutes; LWP = model probability of a transfer wait >10min. Wait excludes transfer buffer.",
             "| Query | Variant | Strategy | Mean | P95 | Wait | LWP | Completion |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    table = []
    fmt = lambda x: "unknown/infinite" if x is None else f"{x:.2f}"
    for r in results:
        q = r["query"]
        if r["status"] != "completed":
            lines.append(f"| {q['id']} | {r['variant']} | {r['status']}: {r.get('error','')} | - | - | - | - | - |")
        for k, e in r["evaluations"].items():
            s = e["summary"]
            table.append({"query":q["id"], "origin":q["origin"], "destination":q["destination"],
                          "variant":r["variant"], "strategy":k, **s})
            lines.append(f"| {q['id']} | {r['variant']} | {k} | " + " | ".join(fmt(s[m]) for m in
                         ("mean_minutes","p95_minutes","mean_recorded_wait_minutes","long_transfer_wait_probability","completion_probability")) + " |")
    lines += ["", "## Route Details and Search", ""]
    for r in results:
        q = r["query"]
        lines += [f"### {q['id']} / {r['variant']}", "",
                  f"{full.stops[q['origin']].name} ({q['origin']}) -> {full.stops[q['destination']].name} ({q['destination']})",
                  f"Status: {r['status']}; search: {r['search']}; total experiment seconds: {r['total_seconds']:.2f}.", ""]
        for k, route in r.get("selected_fixed", {}).items():
            lines.append(f"- Fixed {k}: {route['text']}")
        for k, route in r.get("dynamic_examples", {}).items():
            lines.append(f"- Dynamic {k}, test world 0 only (complete={route['complete']}): {route['text']}")
        lines.append("")
    lines += ["## Interpretation", "", "Every sampled pair is retained, including equal, worse and uncomputed outcomes.",
              "A world-0 route is an illustration, not a fixed prescription for the adaptive strategy.",
              "Riding through Pei Hwa on 61 does not add a transfer, wait or second boarding delay.",
              "Incomplete trips retain infinite durations (JSON null); wait/count metrics then describe prefixes.",
              "JSON includes all candidates, selected fixed routes, actual dynamic examples, source-backed names,",
              "paired Monte Carlo intervals and per-strategy evaluation time. Timings are batch timings, not production latency.",
              "No walking links, vehicle capacity, actual timetables or calibrated catch probabilities are modeled.",
              "This small preselected corridor and stratified sample cannot represent all Singapore trips.", "",
              "Reproduce: `python -m experiments.local_routes` (no credentials required).", "",
              "This project is an independent research project and is not affiliated with, endorsed by, or sponsored",
              "by the Land Transport Authority of Singapore, Google, or Citymapper."]
    (out / "report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    if table:
        with (out / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(table[0])); writer.writeheader(); writer.writerows(table)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--training-samples", type=int, default=256)
    parser.add_argument("--rollout-samples", type=int, default=64)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    full, source = build_network()
    manifest = sample_queries(full)
    manifest.update(provenance=source, transfer_stops=sorted(HUBS),
                    network={"stops":[asdict(s) for s in full.stops.values()],
                             "services":[asdict(s) for s in full.services.values()]}, configuration=vars(args) | {"output":str(args.output)})
    files = [Path(__file__), ROOT / "experiments/pei_hwa_case.py", ROOT / "data/real/build_subset.py",
             *[ROOT / "src/sg_transit" / (name + ".py") for name in
               ("models", "routing", "simulation", "adaptive", "benchmark", "preferences")]]
    manifest["source_sha256"] = {p.resolve().relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    results = []
    for query in manifest["queries"]:
        result = run_query(full, query, **vars(args))
        results.append(result)
        print(query["id"], result["status"], result["search"], round(result["total_seconds"],2), flush=True)
    for variant in ("headway20", "delay8", "buffer5", "synchronized"):
        result = run_query(full, manifest["queries"][0], variant=variant, **vars(args))
        results.append(result)
        print("home",variant,result["status"],round(result["total_seconds"],2),flush=True)
    write_report(results, manifest, full, args.output)
    print(args.output / "report.md")


if __name__ == "__main__":
    main()

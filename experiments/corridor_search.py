"""Small-network audit of bounded candidate search and shared suffix decisions."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import json
import math
from pathlib import Path
from time import perf_counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sg_transit.adaptive import SharedSuffixPolicy, evaluate_adaptive, select_fixed_reference
from sg_transit.corridors import CorridorParameters, DestinationIndex, discover_candidates
from sg_transit.models import Stop, TransitNetwork, TransitService
from sg_transit.routing import RoutingParameters, _baseline, enumerate_routes, route_key
from sg_transit.simulation import evaluate

SCENARIOS = ("shared_corridor", "onboard_continuation", "candidate_loss")
RESULTS = Path(__file__).resolve().parents[1] / "results/corridor_search"


def scenario(name):
    if name == "shared_corridor":
        services = [
            *[TransitService(f"F{i}", ("O", f"A{i}", "H"), (3, 3), 8 + i * 2, 2)
              for i in range(4)],
            *[TransitService(f"T{i}", ("H", "X", "D"), (4, 4), 16 + i * 2, 2)
              for i in range(4)],
            TransitService("ordinary", ("O", "Z", "D"), (16, 16), 8),
            TransitService("reverse", ("D", "Q", "H"), (1, 1), 2),
        ]
        corridors = CorridorParameters()
    elif name == "onboard_continuation":
        services = [
            TransitService("through", ("O", "H", "X", "D"), (6, 4, 4), 12, 2),
            TransitService("feeder", ("O", "A", "B", "H"), (2, 2, 2), 8, 2),
            *[TransitService(f"T{i}", ("H", "X", "D"), (4, 4), 18 + i * 2, 2)
              for i in range(3)],
            TransitService("ordinary", ("O", "C", "E", "F", "D"), (8, 8, 8, 8), 10),
        ]
        corridors = CorridorParameters()
    elif name == "candidate_loss":
        services = [
            TransitService("risky", ("O", "R1", "R2", "D"), (0.3, 0.3, 0.4), 2, 40),
            TransitService("stable", ("O", "S1", "S2", "S3", "D"), (5.5, 5.5, 5.5, 5.5), 4),
            *[TransitService(f"slow{i}", ("O", f"Z{i}", "D"), (20, 20), 10) for i in range(3)],
        ]
        # Deliberately aggressive: demonstrate that a quality loss is observable.
        corridors = CorridorParameters(max_hubs=0, ordinary_candidates=1)
    else:
        raise ValueError(f"Unknown scenario: {name}")
    stops = sorted({stop for service in services for stop in service.stops})
    return TransitNetwork([Stop(stop, stop) for stop in stops], services), corridors


def _safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    return value


def _fixed_summary(trial):
    summary = asdict(trial.summary)
    summary["completion_probability"] = 1.0
    summary["stopped_probability"] = 0.0
    return summary


def run_scenario(name, *, samples=10000, selection_samples=512,
                 seed=100, selection_seed=7, output=RESULTS):
    if seed == selection_seed:
        raise ValueError("Selection and held-out seeds must differ")
    if samples < 1 or selection_samples < 1:
        raise ValueError("Sample counts must be positive")
    network, corridors = scenario(name)
    p = RoutingParameters(max_transfers=2, max_candidates=10000, max_expansions=100000)
    exact_stats = {}
    started = perf_counter()
    exact = enumerate_routes(network, "O", "D", p, stats=exact_stats)
    exact_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    index = DestinationIndex(network, "D")
    index_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    bounded = discover_candidates(index, "O", p, corridors)
    bounded_ms = (perf_counter() - started) * 1000
    if not bounded.routes:
        raise ValueError("Bounded search found no route in the audit case")
    fixed_routes = {
        "shortest_expected": _baseline(exact, network, "time"),
        "minimum_transfers": _baseline(exact, network, "transfers"),
        "minimum_ride": _baseline(exact, network, "ride"),
        "full_fixed_reliable": select_fixed_reference(
            exact, network, p, samples=selection_samples, seed=selection_seed),
        "bounded_fixed_reliable": select_fixed_reference(
            bounded.routes, network, p, samples=selection_samples, seed=selection_seed),
    }
    evaluations = {}
    pressure = {}
    raw = []
    for label, route in fixed_routes.items():
        trial = evaluate(route, network, samples, seed, parameters=p)
        evaluations[label] = {
            "summary": _fixed_summary(trial), "route": asdict(route),
            "branch_counts": trial.branch_counts,
        }
        pressure[label] = _fixed_summary(evaluate(
            route, network, samples, seed, parameters=p, phase_correlation=1))
        raw.extend({"strategy": label, "sample": i, "duration": float(duration)}
                   for i, duration in enumerate(trial.durations))
    for label, routes in (("full_adaptive", exact), ("bounded_adaptive", bounded.routes)):
        started = perf_counter()
        policy = SharedSuffixPolicy(network, routes, p)
        policy.value(policy.initial_state().structure)
        compile_ms = (perf_counter() - started) * 1000
        started = perf_counter()
        trial = evaluate_adaptive(policy, samples, seed)
        simulation_ms = (perf_counter() - started) * 1000
        evaluations[label] = {
            "summary": trial.summary, "branch_counts": trial.branch_counts,
            "shared_nodes": len(policy.nodes),
            "shared_arcs": sum(len(node.options) for node in policy.nodes.values()),
            "value_states": policy.value_state_count,
            "value_cache_hits": policy.value_cache_hits,
            "local_updates": policy.local_updates,
            "compile_ms": compile_ms, "simulation_ms": simulation_ms,
            "unshared_route_segment_count": sum(
                network.services[leg.service_id].stops.index(leg.alight_stop)
                - network.services[leg.service_id].stops.index(leg.board_stop)
                for route in routes for leg in route.legs),
        }
        pressure[label] = evaluate_adaptive(policy, samples, seed, phase_correlation=1).summary
        raw.extend({"strategy": label, "sample": i, "duration": float(duration)}
                   for i, duration in enumerate(trial.durations))
    exact_keys, bounded_keys = set(map(route_key, exact)), set(map(route_key, bounded.routes))
    a = evaluations["bounded_adaptive"]["summary"]
    b = evaluations["full_adaptive"]["summary"]
    document = {
        "scenario": name, "data_kind": "synthetic", "origin": "O", "destination": "D",
        "samples": samples, "seed": seed,
        "selection_samples": selection_samples, "selection_seed": selection_seed,
        "stationary_value_seed": 29, "stationary_value_samples": 64,
        "parameters": asdict(p), "corridor_parameters": asdict(corridors),
        "network": {"stops": [asdict(s) for s in network.stops.values()],
                    "services": [asdict(s) for s in network.services.values()]},
        "search": {
            "exact_candidates": len(exact), "bounded_candidates": len(bounded.routes),
            "exact_expansions": exact_stats["expansions"],
            "bounded_expansions": bounded.expansions,
            "exact_search_ms": exact_ms, "index_build_ms": index_ms,
            "bounded_query_ms": bounded_ms, "bounded_cold_ms": index_ms + bounded_ms,
            "candidate_recall": len(exact_keys & bounded_keys) / len(exact_keys),
            "missed_route_count": len(exact_keys - bounded_keys),
            "missed_selected_full_fixed": route_key(fixed_routes["full_fixed_reliable"]) not in bounded_keys,
            "truncated": bounded.truncated, "truncation_reasons": bounded.truncation_reasons,
            "hubs": [asdict(hub) for hub in bounded.selected_hubs],
            "ordinary_route_count": len(bounded.ordinary_route_keys),
            "bypass_route_count": len(bounded.bypass_route_keys),
            "bounded_routes": [asdict(route) for route in bounded.routes],
        },
        "evaluations": evaluations, "fully_correlated_pressure": pressure,
        "bounded_minus_full_adaptive": {
            key: a[key] - b[key] for key in ("mean_minutes", "p95_minutes", "failure_probability")
        },
        "limitations": [
            "Synthetic stop-to-stop bus network; not Singapore travel-time predictions.",
            "Exact means complete legal route enumeration within this small network and bounds.",
            "Full adaptive is the same heuristic on full candidates, not an optimal stochastic policy.",
            "Independent uniform future waits approximate downstream value; no future realized data.",
            "Shared topology may recombine routes; candidate recall is not executable-path recall.",
            "Realized delay is charged once per boarding; remaining onboard does not repay it.",
            "Local observations are perfect next-departure times at the current stop in this simulator.",
            "Budgets may omit better routes; candidate_loss intentionally demonstrates this risk.",
            "Known infeasible actions are rejected; future random delays can still end a trip.",
            "Uncompleted durations are infinite internally, null in JSON; completion is reported.",
            "Single-run wall-clock timings are diagnostic, not production speed benchmarks.",
            "No Google route content, passenger data, or live APIs used.",
        ],
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    document = _safe(document)
    (output / f"{name}.json").write_text(json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (output / f"{name}.samples.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["strategy", "sample", "duration"])
        writer.writeheader()
        writer.writerows(raw)
    return document


def write_report(documents, output):
    output = Path(output)
    number = lambda value, decimals=2: "uncompleted" if value is None else f"{value:.{decimals}f}"
    lines = [
        "# Destination Corridor Search Audit", "",
        "Independent synthetic research, stop to stop; not a Singapore ETA claim.",
        "Reproduce: `python -m experiments.corridor_search`.", "",
        "Selection seed 7; held-out seed 100; future-value quadrature seed 29.",
        "Full search enumerates all legal routes within the stated small-network bounds.",
        "Both adaptive variants use the same local decision rule; neither is a globally optimal policy.", "",
        "## Search and Candidate Loss", "",
        "| Case | Full / bounded routes | Full / bounded expansions | Recall | Missed selected reliable route |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for doc in documents:
        s = doc["search"]
        lines.append(f"| {doc['scenario']} | {s['exact_candidates']} / {s['bounded_candidates']} | "
                     f"{s['exact_expansions']} / {s['bounded_expansions']} | {s['candidate_recall']:.3f} | "
                     f"{s['missed_selected_full_fixed']} |")
    lines.extend(["", "Recall counts enumerated route descriptions, not all recombinations in the shared graph.",
                  "Ordinary and hub-bypassing candidates are reserved before hub proposals.",
                  "Bypassing routes are searched separately; budgets or no such route may prevent retention.",
                  "", "## Held-Out Journey Results", "",
                  "| Case | Strategy | Mean | P90 | P95 | Missed | Completed |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
    for doc in documents:
        for label, result in doc["evaluations"].items():
            s = result["summary"]
            lines.append(f"| {doc['scenario']} | {label} | {number(s['mean_minutes'])} | "
                         f"{number(s['p90_minutes'])} | {number(s['p95_minutes'])} | "
                         f"{number(s['failure_probability'], 3)} | {number(s['completion_probability'], 3)} |")
    lines.extend(["", "## Computation and Shared Structure", "",
                  "| Case | Full search ms | Index ms | Bounded query ms | Full / bounded value states |",
                  "| --- | ---: | ---: | ---: | ---: |"])
    for doc in documents:
        s, e = doc["search"], doc["evaluations"]
        lines.append(f"| {doc['scenario']} | {s['exact_search_ms']:.2f} | {s['index_build_ms']:.2f} | "
                     f"{s['bounded_query_ms']:.2f} | {e['full_adaptive']['value_states']} / "
                     f"{e['bounded_adaptive']['value_states']} |")
    lines.extend(["", "These timings are single local runs; fewer expansions do not guarantee lower total latency.",
                  "JSON includes compilation/simulation time, shared node/arc counts, unshared segment counts,",
                  "local update counts, cache hits, truncation reasons and a fully correlated phase stress test.",
                  "", "## Interpretation", "",
                  "The deliberately narrow candidate_loss configuration can omit the more reliable fixed route.",
                  "It is retained as a negative result, not tuned away.",
                  "The dynamic objective is estimated remaining time plus a transfer penalty; P95 is measured,",
                  "not globally optimized. More alternatives can change both mean and tail behavior.",
                  "", "Future-state values include history but use stationary waits. Actual local arrival clocks",
                  "and observed departures are evaluated anew; no per-trip future delay is exposed to decisions.",
                  "Continuation on the same bus adds neither a wait nor a boarding delay nor a transfer.",
                  "", "No city-wide performance, fare compliance, or live navigation claim is made.",
                  "", "This project is an independent research project and is not affiliated with,",
                  "endorsed by, or sponsored by the Land Transport Authority of Singapore,",
                  "Google, or Citymapper."])
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    figure, axes = plt.subplots(1, len(documents), figsize=(16, 4.8), squeeze=False)
    labels = ("shortest_expected", "full_fixed_reliable", "full_adaptive", "bounded_adaptive")
    for axis, doc in zip(axes[0], documents):
        for i, metric in enumerate(("mean_minutes", "p95_minutes")):
            axis.bar([x + i * 0.35 for x in range(len(labels))],
                     [(doc["evaluations"][label]["summary"][metric]
                       if doc["evaluations"][label]["summary"][metric] is not None else math.nan)
                      for label in labels],
                     width=0.35, label=metric)
        axis.set_xticks([x + 0.175 for x in range(len(labels))],
                       ["Fast fixed", "Reliable fixed", "Full", "Bounded"], rotation=15)
        axis.set_title(doc["scenario"])
        axis.set_ylabel("Minutes")
    figure.legend(*axes[0][0].get_legend_handles_labels(), loc="upper center", ncol=2)
    figure.tight_layout(rect=(0, 0, 1, 0.91))
    figure.savefig(output / "comparison.png", dpi=140)
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=10000)
    parser.add_argument("--selection-samples", type=int, default=512)
    parser.add_argument("--output", type=Path, default=RESULTS)
    args = parser.parse_args()
    documents = [
        run_scenario(name, samples=args.samples, selection_samples=args.selection_samples, output=args.output)
        for name in SCENARIOS
    ]
    write_report(documents, args.output)
    for doc in documents:
        s = doc["search"]
        e = doc["evaluations"]
        print(f"{doc['scenario']}: expansions {s['exact_expansions']} -> {s['bounded_expansions']}; "
              f"adaptive P95 {e['full_adaptive']['summary']['p95_minutes']:.2f} -> "
              f"{e['bounded_adaptive']['summary']['p95_minutes']:.2f}")
    print(f"Report: {args.output / 'report.md'}")


if __name__ == "__main__":
    main()

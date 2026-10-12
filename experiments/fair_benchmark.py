"""Offline matched-candidate benchmark with positive and negative controls."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys
import sys

import numpy as np

from sg_transit.adaptive import SharedSuffixPolicy
from sg_transit.benchmark import WorldModel, Worlds, audit_candidate_closure, execute, paired_difference, select_fixed
from sg_transit.models import Stop, TransitNetwork, TransitService
from sg_transit.routing import RoutingParameters, enumerate_routes, route_key

SCENARIOS = ("independent_alternatives", "synchronized_alternatives", "independent_delay", "common_delay",
             "tight_connection", "detour_transfers", "mean_tail_conflict", "single_service")
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "results/fair_benchmark"


def scenario(name):
    model = WorldModel()
    p = RoutingParameters(max_transfers=3, max_candidates=1000)
    if name in {"independent_alternatives", "synchronized_alternatives", "independent_delay", "common_delay"}:
        services = [TransitService("feeder", ("O", "H"), (6,), 8, 2),
                    *[TransitService(f"tail{i}", ("H", "D"), (8,), 20, 2) for i in range(4)]]
        if name == "synchronized_alternatives":
            model = WorldModel(phase_groups={f"tail{i}": "tails" for i in range(4)},
                               delay_groups={f"tail{i}": "tails" for i in range(4)})
        if name in {"independent_delay", "common_delay"}:
            services = [TransitService(s.id, s.stops, s.ride_minutes, s.headway_minutes, 8) for s in services]
            model = WorldModel(phase_groups={f"tail{i}": "tails" for i in range(4)},
                               delay_groups={s.id: "common_shock" for s in services} if name == "common_delay" else {})
    elif name == "tight_connection":
        services = [TransitService("feeder", ("O", "H"), (8,), 15, 6),
                    TransitService("connection", ("H", "D"), (8,), 15),
                    TransitService("backup", ("H", "D"), (12,), 10),
                    TransitService("direct", ("O", "D"), (32,), 6)]
        # Nominal feeder arrival + 3-minute buffer + 1-minute slack.
        model = WorldModel(phase_groups={"feeder": "pulse", "connection": "pulse"},
                           phase_offsets={"connection": 12})
    elif name == "detour_transfers":
        services = [TransitService("through", ("O", "H", "D"), (4, 8), 12),
                    TransitService("feeder", ("O", "H"), (3,), 4),
                    TransitService("detour", ("H", "J"), (8,), 4),
                    TransitService("last", ("J", "D"), (8,), 6)]
    elif name == "mean_tail_conflict":
        services = [TransitService("risky", ("O", "D"), (1,), 2, 40),
                    TransitService("stable", ("O", "D"), (24,), 4)]
    elif name == "single_service":
        services = [TransitService("only", ("O", "H", "D"), (6, 8), 15, 3)]
    else:
        raise ValueError(f"Unknown scenario: {name}")
    stops = sorted({stop for s in services for stop in s.stops})
    return TransitNetwork([Stop(s, s) for s in stops], services), p, model


def safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    return value


def run_case(name, *, samples=10000, training_samples=2000, training_seed=7001,
             test_seed=9001, bootstrap_samples=300, output=DEFAULT_OUTPUT):
    if training_seed == test_seed or training_seed == 29 or test_seed == 29:
        raise ValueError("Training, testing and stationary-value seeds must differ")
    network, p, model = scenario(name)
    routes = enumerate_routes(network, "O", "D", p)
    shared = SharedSuffixPolicy(network, routes, p)
    audit = audit_candidate_closure(shared, routes)
    train = Worlds.generate(network, training_samples, training_seed, model)
    selected, training_scores = select_fixed(routes, network, p, train)
    test = Worlds.generate(network, samples, test_seed, model)
    trials = {label: execute(SharedSuffixPolicy(network, [route], p), test, controller="first")
              for label, route in selected.items()}
    trials["first_eligible"] = execute(shared, test, controller="first")
    trials["suffix_scored"] = execute(shared, test, controller="scored")
    candidate_payload = [asdict(r) for r in routes]
    document = {
        "scenario": name, "data_kind": "synthetic", "origin": "O", "destination": "D",
        "departure_minutes": 0, "samples": samples, "training_samples": training_samples,
        "training_seed": training_seed, "test_seed": test_seed,
        "value_seed": 29, "value_samples": 64,
        "runtime": {"python": sys.version.split()[0], "numpy": np.__version__},
        "source_sha256": {str(path.relative_to(Path(__file__).resolve().parents[1])).replace("\\", "/"):
                          hashlib.sha256(path.read_bytes()).hexdigest() for path in
                          [Path(__file__).resolve(), *[Path(__file__).resolve().parents[1] / "src/sg_transit" / filename
                           for filename in ("benchmark.py", "adaptive.py", "models.py", "routing.py", "simulation.py")]]},
        "runtime": {"python": sys.version.split()[0], "numpy": np.__version__},
        "source_sha256": {str(path.relative_to(Path(__file__).resolve().parents[1])).replace("\\", "/"):
                          hashlib.sha256(path.read_bytes()).hexdigest() for path in
                          [Path(__file__).resolve(), *[Path(__file__).resolve().parents[1] / "src/sg_transit" / filename
                           for filename in ("benchmark.py", "adaptive.py", "models.py", "routing.py", "simulation.py")]]},
        "training_world_sha256": train.fingerprint(), "test_world_sha256": test.fingerprint(),
        "candidate_sha256": hashlib.sha256(json.dumps(candidate_payload, sort_keys=True).encode()).hexdigest(),
        "parameters": asdict(p), "world_model": asdict(model),
        "network": {"stops": [asdict(s) for s in network.stops.values()],
                    "services": [asdict(s) for s in network.services.values()]},
        "candidate_audit": audit, "candidates": candidate_payload,
        "fixed_selection": {label: route_key(r) for label, r in selected.items()},
        "training_scores": training_scores,
        "evaluations": {label: {"summary": t.summary(), "boardings": t.branches} for label, t in trials.items()},
        "paired_differences": {
            f"{a}_minus_{b}": paired_difference(trials[a], trials[b], bootstrap_samples=bootstrap_samples)
            for a, b in (("suffix_scored", "fixed_mean"), ("suffix_scored", "fixed_p95"),
                         ("suffix_scored", "first_eligible"), ("first_eligible", "fixed_mean"))},
        "uncertainty": {"mean": "paired normal 95% Monte Carlo interval",
                        "p95": "paired percentile bootstrap 95% interval",
                        "bootstrap_samples": bootstrap_samples, "bootstrap_seed": 811,
                        "scope": "Conditional on the selected policy and synthetic world model; no calibration claim"},
    }
    if name == "tight_connection":
        diagnostic = next(r for r in routes if r.services == ("feeder", "connection"))
        document["prespecified_tight_connection_diagnostic"] = {
            "route": route_key(diagnostic),
            "summary": execute(SharedSuffixPolicy(network, [diagnostic], p), test, controller="first").summary(),
            "purpose": "Explain the tight-connection mechanism, not choose a route after seeing test results",
        }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    document = safe(document)
    (output / f"{name}.json").write_text(json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    arrays = {f"{label}__{metric}": getattr(trial, metric) for label, trial in trials.items()
              for metric in ("durations", "waits", "buffers", "rides", "max_transfer_wait", "transfers", "missed")}
    np.savez_compressed(output / f"{name}.samples.npz", **arrays)
    return document


def write_report(documents, output):
    output = Path(output)
    lines = ["# Fair Synthetic Policy Benchmark", "",
             "This is an offline controlled experiment, not a forecast for Singapore or a Google comparison.", "",
             "## Protocol", "",
             "- Same network, departure time, complete candidate set and immutable held-out worlds per case.",
             "- Graph recombination is audited: every executable complete path must be in the fixed candidate set.",
             "- One executor for fixed, first-eligible and scored policies; identical constraints and cost accounting.",
             "- fixed_mean: select minimum training mean + 5 minutes per transfer, then freeze the route.",
             "- fixed_p95: separately select minimum training P95 (mean breaks ties), then freeze the route.",
             "- first_eligible: earliest feasible local departure; remain onboard on equal-time ties.",
             "- suffix_scored: existing SharedSuffixPolicy, stationary remaining mean + transfer penalty.",
             "- No test-world route selection, retrospective best route, future realized delay, or remote API.",
             "- Quantiles use the nearest-rank empirical definition; a trip that cannot finish has infinite duration.",
             "- Infinite metrics become null in JSON, with completion and conditional completed means retained.", "",
             "## Held-Out Results", "",
             "| Case | Strategy | Mean | P90 | P95 | Station wait | P(transfer wait >10m) | Transfers | Completed |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    rows = []
    fmt = lambda x: "unknown/infinite" if x is None else f"{x:.2f}"
    for doc in documents:
        for label, evaluation in doc["evaluations"].items():
            s = evaluation["summary"]
            rows.append({"scenario": doc["scenario"], "strategy": label, **s})
            keys = ("mean_minutes", "p90_minutes", "p95_minutes", "mean_recorded_wait_minutes",
                    "long_transfer_wait_probability", "mean_recorded_transfers", "completion_probability")
            lines.append(f"| {doc['scenario']} | {label} | " + " | ".join(fmt(s[k]) for k in keys) + " |")
    lines += ["", "Station wait excludes the transfer buffer; both are recorded separately in the sample files.",
              "For incomplete trips, wait/transfer counts are observed prefixes and long-wait risk is bounded, not imputed.",
              "", "## Paired Comparisons", "",
              "Differences are scored minus comparator; negative means lower modeled journey time.",
              "Intervals measure Monte Carlo sampling uncertainty only and are not adjusted for multiple comparisons.", "",
              "| Case | Comparator | Mean delta [95% interval] | P95 delta [95% interval] |",
              "| --- | --- | --- | --- |"]
    for doc in documents:
        for comparator in ("fixed_mean", "fixed_p95", "first_eligible"):
            d = doc["paired_differences"][f"suffix_scored_minus_{comparator}"]
            cells = []
            for metric in ("mean", "p95"):
                ci = d[f"{metric}_ci95"]
                cells.append(fmt(d[f"{metric}_delta"]) + (f" [{fmt(ci[0])}, {fmt(ci[1])}]" if ci else " [unavailable]"))
            lines.append(f"| {doc['scenario']} | {comparator} | " + " | ".join(cells) + " |")
    lines += ["", "![Mean and P95 comparison](comparison.png)", "", "## Diagnostic", ""]
    for doc in documents:
        diagnostic = doc.get("prespecified_tight_connection_diagnostic")
        if diagnostic:
            s = diagnostic["summary"]
            lines += [f"Pre-specified feeder-to-connection fixed path: nominal miss rate "
                      f"{s['nominal_connection_miss_probability']:.3f}, mean {fmt(s['mean_minutes'])}, "
                      f"P95 {fmt(s['p95_minutes'])} minutes.",
                      "With delay Uniform(0,6) and one minute of slack, its analytic miss probability is 5/6.",
                      "This diagnostic is not a retrospectively selected comparator; the main fixed baselines may",
                      "select the direct route during training, which is a legitimate response to connection risk.", ""]
    lines += ["", "![Mean and P95 comparison](comparison.png)", "", "## Diagnostic", ""]
    for doc in documents:
        diagnostic = doc.get("prespecified_tight_connection_diagnostic")
        if diagnostic:
            s = diagnostic["summary"]
            lines += [f"Pre-specified feeder-to-connection fixed path: nominal miss rate "
                      f"{s['nominal_connection_miss_probability']:.3f}, mean {fmt(s['mean_minutes'])}, "
                      f"P95 {fmt(s['p95_minutes'])} minutes.",
                      "With delay Uniform(0,6) and one minute of slack, its analytic miss probability is 5/6.",
                      "This diagnostic is not a retrospectively selected comparator; the main fixed baselines may",
                      "select the direct route during training, which is a legitimate response to connection risk.", ""]
    lines += ["", "## Controls and Limitations", "",
              "Independent and synchronized alternatives use identical topology and marginal time distributions.",
              "Synchronized tails share phases and delays: four service labels need not provide four independent chances.",
              "independent_delay and common_delay both have synchronized tail phases and eight-minute delay bounds.",
              "Only delay dependence changes: independent shocks versus one common shock across services. Neither",
              "is a physical congestion/bunching model, and this pair is separate from the low-delay phase controls.",
              "tight_connection has one minute of nominal transfer slack after the three-minute buffer; feeder delay",
              "can miss that bus. Its miss diagnostic compares actual readiness with a no-delay nominal clock along",
              "the selected path; it is not a measured catch probability or evidence against a published timetable.",
              "detour_transfers tests the cost of taking an early bus that creates extra riding or transfers.",
              "mean_tail_conflict is deliberately adverse to mean optimization: a faster-mean route has a heavy tail.",
              "single_service is a no-choice control; all controllers must agree sample by sample.",
              "No scenario is removed because adaptive performance is equal or worse.", "",
              "Local next departures are perfect observations; downstream waits in the value function remain stationary",
              "and independent even in correlated test worlds. No learned adaptation to these correlations is claimed.",
              "Periodic schedules have random initial phases. Delay is charged once on boarding and retained while",
              "onboard, not at every stop. This is a passenger-level cost model, not a consistent multi-bus fleet model.",
              "No walking access, road network, actual fares, live ETA errors, capacity limits or passenger observations.",
              "The existing scorer does not directly optimize P95 or outdoor comfort. The P95-selected fixed control",
              "prevents lower mean time being mislabeled as universal tail-risk superiority.", "",
              "## Reproduction", "", "```powershell", "python -m experiments.fair_benchmark", "```", "",
              "Install the project first: `python -m pip install -e \".[dev]\"`. No credentials are required.",
              "Default: 2,000 training worlds, 10,000 held-out worlds per case; training seed 7001, test seed 9001,",
              "stationary-value seed 29 (64 draws), paired-bootstrap seed 811 (300 resamples).",
              "JSON contains actual counts/seeds/configurations, all training scores, selected routes, graph audit,",
              "candidate/world hashes, and every comparison. NPZ files contain paired sample arrays; summary.csv",
              "is a compact table. Each NPZ index refers to the same world across strategies within its case.", "",
              "This project is an independent research project and is not affiliated with,",
              "endorsed by, or sponsored by the Land Transport Authority of Singapore, Google, or Citymapper."]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (output / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_plot(documents, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = ("fixed_mean", "fixed_p95", "first_eligible", "suffix_scored")
    colors = ("#497d98", "#54815b", "#b27742", "#a35165")
    figure, axes = plt.subplots(math.ceil(len(documents) / 2), 2,
                                figsize=(13, 3.2 * math.ceil(len(documents) / 2)), squeeze=False)
    for axis, doc in zip(axes.flat, documents):
        for i, (label, color) in enumerate(zip(labels, colors)):
            s = doc["evaluations"][label]["summary"]
            axis.bar(i, s["mean_minutes"] if s["mean_minutes"] is not None else np.nan,
                     width=.6, color=color)
            axis.scatter(i, s["p95_minutes"] if s["p95_minutes"] is not None else np.nan,
                         color="black", marker="_", s=260, zorder=3)
        axis.set_xticks(range(4), ("Fixed mean", "Fixed P95", "First bus", "Scored"))
        axis.set_title(doc["scenario"].replace("_", " "))
        axis.set_ylabel("Journey minutes")
        axis.set_ylim(bottom=0)
        axis.grid(axis="y", alpha=.2)
        axis.set_axisbelow(True)
    for axis in list(axes.flat)[len(documents):]:
        axis.set_visible(False)
    figure.suptitle("Synthetic held-out comparison: bars = mean, black marks = P95", fontsize=14)
    figure.tight_layout(rect=(0, 0, 1, .97))
    figure.savefig(Path(output) / "comparison.png", dpi=140)
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=10000)
    parser.add_argument("--training-samples", type=int, default=2000)
    parser.add_argument("--training-seed", type=int, default=7001)
    parser.add_argument("--test-seed", type=int, default=9001)
    parser.add_argument("--bootstrap-samples", type=int, default=300)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    docs = []
    for name in SCENARIOS:
        doc = run_case(name, samples=args.samples, training_samples=args.training_samples,
                       training_seed=args.training_seed, test_seed=args.test_seed,
                       bootstrap_samples=args.bootstrap_samples, output=args.output)
        docs.append(doc)
        s = doc["evaluations"]["suffix_scored"]["summary"]
        print(f"{name}: mean={s['mean_minutes']}, P95={s['p95_minutes']}", flush=True)
    write_report(docs, args.output)
    write_plot(docs, args.output)
    print(f"Report: {args.output / 'report.md'}")


if __name__ == "__main__":
    main()

"""Offline preference experiments on the eight regressions plus a comfort control."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np

from experiments.fair_benchmark import SCENARIOS as REGRESSIONS, safe, scenario as regression_scenario
from sg_transit.adaptive import SharedSuffixPolicy
from sg_transit.benchmark import WorldModel, Worlds, audit_candidate_closure, execute, paired_difference
from sg_transit.models import Stop, TransitNetwork, TransitService
from sg_transit.preferences import DistributionalPolicy, Preference, select_fixed_preferences
from sg_transit.routing import RoutingParameters, enumerate_routes, route_key

SCENARIOS = (*REGRESSIONS, "wait_ride_tradeoff")
OUTPUT = Path(__file__).resolve().parents[1] / "results/preference_benchmark"


def scenario(name):
    if name != "wait_ride_tradeoff":
        return regression_scenario(name)
    net = TransitNetwork([Stop("O", "O"), Stop("D", "D")], [
        TransitService("short_infrequent", ("O", "D"), (5,), 20),
        TransitService("long_frequent", ("O", "D"), (18,), 4),
    ])
    return net, RoutingParameters(max_transfers=3, max_candidates=1000), WorldModel()


def run_case(name, *, samples=10000, training_samples=2000, training_seed=7001,
             test_seed=9001, rollout_samples=256, rollout_seed=2309,
             extra_wait_weight=2.0, transfer_penalty=3.0, bootstrap_samples=300,
             output=OUTPUT):
    if len({training_seed, test_seed, rollout_seed, 29}) != 4:
        raise ValueError("Training, test, rollout and legacy value seeds must be distinct")
    preferences = {label: Preference(label, extra_wait_weight=extra_wait_weight,
                                    transfer_penalty=transfer_penalty) for label in ("fast", "cool", "reliable")}
    net, p, model = scenario(name)
    routes = enumerate_routes(net, "O", "D", p)
    shared = SharedSuffixPolicy(net, routes, p)
    audit = audit_candidate_closure(shared, routes)
    training = Worlds.generate(net, training_samples, training_seed, model)
    selected, rows = select_fixed_preferences(routes, net, p, training, preferences)
    # Hold-out data are created only after the fixed decisions have been frozen.
    testing = Worlds.generate(net, samples, test_seed, model)
    trials, fixed_cache = {}, {}
    for label, route in selected.items():
        key = route_key(route)
        if key not in fixed_cache:
            fixed_cache[key] = execute(SharedSuffixPolicy(net, [route], p), testing, controller="first")
        trials[f"fixed_{label}"] = fixed_cache[key]
    for label, preference in preferences.items():
        policy = DistributionalPolicy(net, routes, p, preference=preference,
                                      rollout_samples=rollout_samples, rollout_seed=rollout_seed)
        trials[f"dynamic_{label}"] = execute(policy, testing)
    trials["first_eligible"] = execute(shared, testing, controller="first")
    trials["legacy_scored"] = execute(shared, testing)
    pairs = [(f"dynamic_{mode}", f"fixed_{mode}") for mode in preferences]
    pairs += [("dynamic_cool", "dynamic_fast"), ("dynamic_reliable", "dynamic_fast"),
              ("dynamic_reliable", "legacy_scored"), ("dynamic_fast", "first_eligible")]
    root = Path(__file__).resolve().parents[1]
    source_files = [Path(__file__).resolve(), root / "experiments/fair_benchmark.py",
                    *[root / "src/sg_transit" / f"{module}.py" for module in
                      ("preferences", "benchmark", "adaptive", "models", "routing", "simulation")]]
    doc = {
        "scenario": name, "data_kind": "synthetic", "samples": samples,
        "training_samples": training_samples, "training_seed": training_seed, "test_seed": test_seed,
        "rollout_samples": rollout_samples, "rollout_seed": rollout_seed,
        "training_world_sha256": training.fingerprint(), "test_world_sha256": testing.fingerprint(),
        "source_sha256": {str(f.relative_to(root)).replace("\\", "/"): hashlib.sha256(f.read_bytes()).hexdigest() for f in source_files},
        "network": {"stops": [asdict(s) for s in net.stops.values()],
                    "services": [asdict(s) for s in net.services.values()]},
        "parameters": asdict(p), "world_model": asdict(model),
        "preferences": {label: asdict(pref) for label, pref in preferences.items()},
        "candidate_audit": audit, "candidates": [asdict(r) for r in routes],
        "training_scores": rows, "selected_fixed": {label: route_key(r) for label, r in selected.items()},
        "evaluations": {label: {"summary": t.summary(), "boardings": t.branches} for label, t in trials.items()},
        "paired": {f"{a}_minus_{b}": paired_difference(trials[a], trials[b], bootstrap_samples=bootstrap_samples)
                   for a, b in pairs},
        "comfort_tradeoff": {
            "dynamic_cool_minus_fast_total": float((trials["dynamic_cool"].durations - trials["dynamic_fast"].durations).mean())
            if all(np.isfinite(trials[x].durations).all() for x in ("dynamic_cool", "dynamic_fast")) else None,
            "dynamic_cool_minus_fast_wait": float((trials["dynamic_cool"].waits - trials["dynamic_fast"].waits).mean()),
            "dynamic_cool_minus_fast_transfers": float((trials["dynamic_cool"].transfers - trials["dynamic_fast"].transfers).mean()),
        },
        "protocol": {"bootstrap_samples": bootstrap_samples, "bootstrap_seed": 811,
                     "future_model": "independent stationary uniform waits and boarding delays; stratified midpoint draws",
                     "dynamic_policy": "fixed suffix scored before realization; only first arc executed; replan at next stop",
                     "completion": "minimize modeled noncompletion first; infinite durations are not dropped",
                     "fairness": "same executable candidates, local observations, held-out worlds, constraints and executor",
                     "limit": "not a globally optimal dynamic P95 policy; correlations are not inferred from local observations"},
    }
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    doc = safe(doc)
    (out / f"{name}.json").write_text(json.dumps(doc, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    np.savez_compressed(out / f"{name}.samples.npz", **{
        f"{label}__{metric}": getattr(t, metric) for label, t in trials.items()
        for metric in ("durations", "waits", "buffers", "rides", "transfers", "max_transfer_wait", "missed")})
    return doc


def write_report(documents, output):
    out = Path(output)
    fmt = lambda value: "unknown/infinite" if value is None else f"{value:.2f}"
    lines = ["# Preference-Aware Routing Experiment", "",
             "Synthetic, offline, stop-to-stop research. No LTA or Google calls or real journey predictions.", "",
             "## Decision Rules", "",
             "All modes first minimize estimated noncompletion probability, then their objective:",
             "- fast: mean remaining duration.",
             "- cool: mean duration + extra_wait_weight * mean station wait + transfer_penalty * transfers.",
             "  Defaults are 2 and 3: waiting already in duration has a total weight of 3. These are declared",
             "  scenario preferences, not empirically learned comfort values. JSON stores the actual settings.",
             "- reliable: nearest-rank P95 duration; mean and transfers break ties.", "",
             "Fixed routes are selected on training outcomes and frozen before testing. Dynamic modes score",
             "each complete legal fixed suffix using model distributions, choose one before realization, execute",
             "only its first arc, then replan. There is no per-draw selection of the best future route.",
             "Future waits/delays use independent stationary stratified uniform draws, separate from test data.",
             "Only local next departures are observed. Remaining onboard incurs no extra wait, delay or transfer.",
             "This is bounded distributional lookahead, not a globally optimal or time-consistent P95 policy.", "",
             "## Held-Out Results", "",
             "| Case | Strategy | Mean | P95 | Station wait | P(transfer wait >10m) | Transfers | Completion |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    rows = []
    for doc in documents:
        for label, e in doc["evaluations"].items():
            s = e["summary"]
            rows.append({"scenario": doc["scenario"], "strategy": label, **s})
            keys = ("mean_minutes", "p95_minutes", "mean_recorded_wait_minutes", "long_transfer_wait_probability",
                    "mean_recorded_transfers", "completion_probability")
            lines.append(f"| {doc['scenario']} | {label} | " + " | ".join(fmt(s[k]) for k in keys) + " |")
    lines += ["", "## Comfort Tradeoffs", "",
              "Dynamic cool minus dynamic fast. Negative means lower; extra travel time is not hidden.", "",
              "| Case | Total time delta | Station wait delta | Transfer delta |", "| --- | ---: | ---: | ---: |"]
    for doc in documents:
        lines.append(f"| {doc['scenario']} | " + " | ".join(fmt(v) for v in doc["comfort_tradeoff"].values()) + " |")
    lines += ["", "## Paired Uncertainty", "",
              "Differences are within-world comparisons. Approximate 95% mean intervals and paired bootstrap",
              "P95 intervals measure Monte Carlo uncertainty conditional on the synthetic model and trained choice.",
              "They do not include model error, policy selection uncertainty or multiple-comparison correction.", "",
              "| Case | Difference | Mean [95% interval] | P95 [95% interval] |", "| --- | --- | --- | --- |"]
    for doc in documents:
        for label, pair in doc["paired"].items():
            cells = []
            for metric in ("mean", "p95"):
                ci = pair[f"{metric}_ci95"]
                cells.append(fmt(pair[f"{metric}_delta"]) + (f" [{fmt(ci[0])}, {fmt(ci[1])}]" if ci else " [unavailable]"))
            lines.append(f"| {doc['scenario']} | {label} | " + " | ".join(cells) + " |")
    lines += ["", "![Selected preference tradeoffs](preferences.png)",
              "", "The figure highlights three diagnostic cases; all nine cases and eight strategy labels are",
              "retained above, including ties and regressions.", "",
              "## Observed Boundaries", ""]
    indexed = {doc["scenario"]: doc for doc in documents}
    if "tight_connection" in indexed:
        case = indexed["tight_connection"]["evaluations"]
        lines += ["In tight_connection, reliable P95 is " + fmt(case["dynamic_reliable"]["summary"]["p95_minutes"])
                  + " minutes versus legacy_scored " + fmt(case["legacy_scored"]["summary"]["p95_minutes"]) + ".",
                  "Reliable targets its projected suffix distribution; it does not guarantee beating the old",
                  "heuristic once the future model is misspecified and choices are replanned.", ""]
    if "detour_transfers" in indexed:
        case = indexed["detour_transfers"]["comfort_tradeoff"]
        lines += ["In detour_transfers, cool minus fast changes mean time by " + fmt(case["dynamic_cool_minus_fast_total"])
                  + ", mean wait by " + fmt(case["dynamic_cool_minus_fast_wait"])
                  + ", and mean transfers by " + fmt(case["dynamic_cool_minus_fast_transfers"]) + ".",
                  "Lower waiting can come with extra transfers despite their configured penalty. Transfer buffers",
                  "are not counted as station waiting; this is not a validated outdoor heat-exposure model.", ""]
    lines += ["", "## Limits and Reproduction", "",
              "All eight prior regression cases are retained, plus a declared wait-versus-ride control.",
              "Correlation and tight-connection cases deliberately violate the dynamic stationary independent",
              "future model; training-fixed selection sees those scenarios, dynamic rollouts do not learn them.",
              "This information/model difference is explicit: the comparison does not isolate preference weights",
              "from model approximation. Compare the three new dynamic modes to isolate their preference effects.",
              "legacy_scored uses its existing stationary mean + 5-per-transfer heuristic, not the new fast rule.",
              "More branches are useful only when their times and downstream costs are useful. Negative outcomes",
              "remain in these tables. No preference promises universal improvements on every metric.", "",
              "Wait excludes the separately recorded transfer buffer. Incomplete journeys keep infinite duration",
              "(JSON null); recorded waits/counts are prefixes and long-wait risk is bounded, not filled as success.",
              "No walking access, capacity limits, live ETA errors, actual fares or actual catch probabilities.",
              "The cool objective penalizes expected wait, not directly P(wait >10m); that probability is reported.",
              "The reliable mode optimizes a conditional suffix percentile; replanning can change the final mixture",
              "and need not reduce the overall journey P95. Limits and no-choice cases are retained.", "",
              "```powershell", "python -m experiments.preference_benchmark", "```", "",
              "Default: 2,000 training worlds (seed 7001), 10,000 held-out worlds (9001), 256 rollout draws (2309).",
              "Legacy value seed 29; bootstrap seed 811, 300 resamples. Actual settings and source hashes are in JSON.",
              "Each NPZ sample index is the same test world across all strategy labels. No credentials required.", "",
              "This project is an independent research project and is not affiliated with, endorsed by, or sponsored",
              "by the Land Transport Authority of Singapore, Google, or Citymapper."]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (out / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_plot(documents, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = ("mean_tail_conflict", "wait_ride_tradeoff", "tight_connection")
    docs = {doc["scenario"]: doc for doc in documents}
    selected = [name for name in names if name in docs]
    if not selected:
        return
    figure, axes = plt.subplots(len(selected), 3, figsize=(13, 3.4 * len(selected)), squeeze=False)
    labels = ("dynamic_fast", "dynamic_cool", "dynamic_reliable", "legacy_scored")
    colors = ("#437c96", "#579260", "#a35476", "#898989")
    metrics = (("mean_minutes", "Mean trip"), ("p95_minutes", "P95 trip"),
               ("mean_recorded_wait_minutes", "Mean station wait"))
    for row, name in enumerate(selected):
        for col, (metric, title) in enumerate(metrics):
            axis = axes[row, col]
            values = [docs[name]["evaluations"][label]["summary"][metric] for label in labels]
            bars = axis.bar(range(4), [x if x is not None else np.nan for x in values], color=colors)
            axis.bar_label(bars, fmt="%.1f", padding=3, fontsize=9)
            axis.set_xticks(range(4), ("Fast", "Cool", "Reliable", "Legacy"))
            axis.set_title(name.replace("_", " ") + "\n" + title)
            axis.set_ylabel("Minutes")
            axis.set_ylim(0, max((x for x in values if x is not None), default=1) * 1.2 + .2)
            axis.grid(axis="y", alpha=.2)
            axis.set_axisbelow(True)
    figure.suptitle("Synthetic preferences: benefits and costs on held-out worlds", fontsize=14)
    figure.tight_layout(rect=(0, 0, 1, .96))
    figure.savefig(Path(output) / "preferences.png", dpi=140)
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in (("samples", 10000), ("training-samples", 2000), ("training-seed", 7001),
                          ("test-seed", 9001), ("rollout-samples", 256), ("rollout-seed", 2309),
                          ("bootstrap-samples", 300)):
        parser.add_argument(f"--{name}", type=int, default=default)
    parser.add_argument("--extra-wait-weight", type=float, default=2.0)
    parser.add_argument("--transfer-penalty", type=float, default=3.0)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    docs = []
    for name in SCENARIOS:
        doc = run_case(name, **vars(args))
        docs.append(doc)
        print(name, {k: round(v["summary"]["mean_minutes"], 2) for k, v in doc["evaluations"].items()}, flush=True)
    write_report(docs, args.output)
    write_plot(docs, args.output)
    print(f"Report: {args.output / 'report.md'}")


if __name__ == "__main__":
    main()

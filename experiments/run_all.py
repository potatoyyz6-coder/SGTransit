from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

from examples.demo import build_demo_network
from sg_transit.models import Route, Stop, Strategy, TransitNetwork, TransitService, compile_policy
from sg_transit.routing import RoutingParameters, plan
from sg_transit.simulation import SimulationResult, evaluate

SAMPLES = 10_000
SELECTION_SAMPLES = 512
RESULTS = Path(__file__).resolve().parents[1] / "results"
SCENARIOS = ("single_critical_transfer", "alternative_services", "transfer_tradeoff")


def scenario_network(name: str) -> tuple[TransitNetwork, str, str]:
    """Build a small synthetic network with an interpretable failure mode."""
    if name == "single_critical_transfer":
        return build_demo_network(), "S1", "S8"
    if name == "alternative_services":
        stops = [Stop(f"A{i}", f"Alternative Stop {i}", i, 0) for i in range(1, 7)]
        services = [
            TransitService("FAST-1", ("A1", "A2", "A3"), (7, 7), 24),
            TransitService("LOCAL-1", ("A1", "A2", "A4"), (9, 8), 10),
            TransitService("CONNECT-1", ("A3", "A5", "A6"), (6, 6), 8),
            TransitService("CONNECT-2", ("A4", "A5", "A6"), (8, 8), 12),
        ]
        return TransitNetwork(stops, services), "A1", "A6"
    if name == "transfer_tradeoff":
        stops = [Stop(f"T{i}", f"Tradeoff Stop {i}", i, 0) for i in range(1, 8)]
        services = [
            TransitService("DIRECT-RISK", ("T1", "T7"), (10,), 2, 45),
            TransitService("STABLE-A", ("T1", "T4"), (12,), 8),
            TransitService("STABLE-B", ("T4", "T7"), (12,), 8),
            TransitService("BACKUP-A", ("T1", "T3"), (13,), 9),
            TransitService("BACKUP-B", ("T3", "T7"), (13,), 9),
        ]
        return TransitNetwork(stops, services), "T1", "T7"
    raise ValueError(f"Unknown scenario: {name}")


def _json_number(value):
    return value.item() if isinstance(value, (np.integer, np.floating)) else value


def _route_payload(route: Route) -> dict:
    return {
        "origin": route.origin,
        "destination": route.destination,
        "walk_minutes": route.walk_minutes,
        "services": list(route.services),
        "transfers": route.transfers,
        "ride_minutes": route.ride_minutes,
        "legs": [asdict(leg) for leg in route.legs],
    }


def _strategy_payload(strategy: Strategy) -> dict:
    return {
        "name": strategy.name,
        "route_count": len(strategy.routes),
        "routes": [_route_payload(route) for route in strategy.routes],
    }


def _policy_payload(strategy: Strategy) -> dict:
    def visit(node):
        return [
            {
                "service": leg.service_id,
                "board": leg.board_stop,
                "alight": leg.alight_stop,
                "ride_minutes": leg.ride_minutes,
                "transfer_minutes": leg.transfer_minutes,
                "then": visit(child),
            }
            for leg, child in node.options
        ]

    return {
        "strategy": strategy.name,
        "rule": "board the first arriving accepted service at the current stop",
        "options": visit(compile_policy(strategy)),
    }


def _as_strategy(name: str, value: Route | Strategy) -> Strategy:
    return value if isinstance(value, Strategy) else Strategy(name, (value,))


def _summary_payload(result: SimulationResult) -> dict:
    return {key: _json_number(value) for key, value in asdict(result.summary).items()}


def _metric_summary(result: SimulationResult) -> dict:
    summary = _summary_payload(result)
    return {
        "samples": summary["samples"],
        "mean_minutes": summary["mean_minutes"],
        "median_minutes": summary["median_minutes"],
        "p90_minutes": summary["p90_minutes"],
        "p95_minutes": summary["p95_minutes"],
        "mean_wait_minutes": summary["mean_wait_minutes"],
        "failure_probability": summary["failure_probability"],
        "invalid_transfer_probability": summary["invalid_transfer_probability"],
        "over_two_hours_probability": summary["over_two_hours_probability"],
        "over_trip_limit_probability": summary["over_trip_limit_probability"],
        "fare_invalid_probability": summary["fare_invalid_probability"],
        "transfers": summary["transfers"],
        "max_minutes": summary["max_minutes"],
    }


def paired_bootstrap_ci(
    left: np.ndarray | Iterable[float],
    right: np.ndarray | Iterable[float],
    statistic: Callable[[np.ndarray], float],
    *,
    seed: int,
    resamples: int = 1_000,
) -> dict:
    """Return a paired estimate and percentile 95% confidence interval."""
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    if left.ndim != 1 or right.ndim != 1 or left.size != right.size or not left.size:
        raise ValueError("Paired bootstrap inputs must be non-empty and equal length")
    if resamples < 1:
        raise ValueError("resamples must be positive")
    rng = np.random.default_rng(seed)
    differences = np.empty(resamples, dtype=float)
    for index in range(resamples):
        sample = rng.integers(0, left.size, left.size)
        differences[index] = statistic(left[sample]) - statistic(right[sample])
    return {
        "estimate": float(statistic(left) - statistic(right)),
        "ci95": [
            float(np.quantile(differences, 0.025)),
            float(np.quantile(differences, 0.975)),
        ],
        "resamples": resamples,
        "difference_definition": "left minus right",
    }


def _strategy_rows(evaluations, scenario: str, origin: str, destination: str) -> list[dict]:
    rows = []
    for name, (strategy, result) in evaluations.items():
        rows.append(
            {
                "scenario": scenario,
                "strategy": name,
                "route_count": len(strategy.routes),
                "services": " | ".join(" -> ".join(route.services) for route in strategy.routes),
                "origin": origin,
                "destination": destination,
                **_metric_summary(result),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _raw_rows(evaluations, scenario: str, parameters: RoutingParameters) -> list[dict]:
    rows = []
    for name, (_, result) in evaluations.items():
        for sample in range(result.durations.size):
            duration = float(result.durations[sample])
            transfers = int(result.transfer_counts[sample])
            rows.append(
                {
                    "scenario": scenario,
                    "strategy": name,
                    "sample": sample,
                    "duration_minutes": duration,
                    "waiting_minutes": float(result.waits[sample]),
                    "missed_transfer": bool(result.missed[sample]),
                    "invalid_transfer": bool(result.invalid[sample]),
                    "over_trip_limit": bool(duration > parameters.max_trip_minutes),
                    "transfer_count": transfers,
                    "fare_invalid_approximation": bool(
                        duration > parameters.max_trip_minutes or transfers > parameters.max_transfers
                    ),
                }
            )
    return rows


def _bar_plot(rows: list[dict], metric: str, title: str, ylabel: str, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(9, 4.8))
    axis.bar([row["strategy"] for row in rows], [row[metric] for row in rows], color="#2f6f8f")
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.tick_params(axis="x", labelrotation=25)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)


def _plot_quantiles(rows: list[dict], scenario: str, path: Path) -> None:
    labels = [row["strategy"] for row in rows]
    x = np.arange(len(labels))
    width = 0.25
    figure, axis = plt.subplots(figsize=(10, 5))
    axis.bar(x - width, [row["mean_minutes"] for row in rows], width, label="Mean")
    axis.bar(x, [row["p90_minutes"] for row in rows], width, label="P90")
    axis.bar(x + width, [row["p95_minutes"] for row in rows], width, label="P95")
    axis.set_xticks(x, labels, rotation=25, ha="right")
    axis.set_ylabel("Minutes")
    axis.set_title(f"{scenario}: journey-time quantiles")
    axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)


def _plot_waiting(evaluations, scenario: str, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(9, 5))
    for name, (_, result) in evaluations.items():
        axis.hist(result.waits, bins=35, alpha=0.35, density=True, label=name)
    axis.set_title(f"{scenario}: total waiting-time distribution")
    axis.set_xlabel("Waiting minutes")
    axis.set_ylabel("Density")
    axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)


def _plot_failure_rates(rows: list[dict], scenario: str, path: Path) -> None:
    labels = [row["strategy"] for row in rows]
    x = np.arange(len(labels))
    width = 0.2
    figure, axis = plt.subplots(figsize=(11, 5))
    metrics = (
        ("failure_probability", "Missed transfer"),
        ("invalid_transfer_probability", "Invalid transfer"),
        ("over_trip_limit_probability", "Over trip limit"),
        ("fare_invalid_probability", "Fare invalid"),
    )
    for offset, (metric, label) in enumerate(metrics):
        axis.bar(
            x + (offset - 1.5) * width,
            [row[metric] for row in rows],
            width,
            label=label,
        )
    axis.set_xticks(x, labels, rotation=25, ha="right")
    axis.set_ylabel("Probability")
    axis.set_ylim(0, 1)
    axis.set_title(f"{scenario}: failure and constraint rates")
    axis.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)


def _plot_network(network: TransitNetwork, origin: str, destination: str, scenario: str, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(10, 5))
    for service in network.services.values():
        axis.plot(
            [network.stops[stop].x for stop in service.stops],
            [network.stops[stop].y for stop in service.stops],
            marker="o",
            alpha=0.55,
            label=service.id,
        )
    for stop in network.stops.values():
        color = "#d1495b" if stop.id == origin else "#00798c" if stop.id == destination else "#555555"
        axis.scatter(stop.x, stop.y, s=45, color=color, zorder=3)
        axis.annotate(stop.id, (stop.x, stop.y), xytext=(4, 4), textcoords="offset points", fontsize=8)
    axis.set_title(f"{scenario}: synthetic service network")
    axis.set_xlabel("Synthetic x")
    axis.set_ylabel("Synthetic y")
    axis.legend(fontsize=8, ncol=2)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)


def _plot_policy(strategy: Strategy, scenario: str, path: Path) -> None:
    graph = nx.DiGraph()
    counter = 0

    def visit(node, parent=None, label="origin"):
        nonlocal counter
        node_id = f"n{counter}"
        counter += 1
        graph.add_node(node_id, label=label)
        if parent is not None:
            graph.add_edge(parent, node_id)
        for leg, child in node.options:
            visit(child, node_id, f"{leg.service_id}\n{leg.board_stop}->{leg.alight_stop}")

    visit(compile_policy(strategy))
    figure, axis = plt.subplots(figsize=(11, 5))
    nx.draw_networkx(
        graph,
        nx.spring_layout(graph, seed=19),
        ax=axis,
        labels=nx.get_node_attributes(graph, "label"),
        node_color="#d9edf7",
        node_size=2_500,
        font_size=8,
        arrows=True,
    )
    axis.set_title(f"{scenario}: executable reliability policy ({strategy.name})")
    axis.axis("off")
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)


def _plot_pressure(normal_rows: list[dict], pressure_rows: list[dict], scenario: str, path: Path) -> None:
    normal = {row["strategy"]: row for row in normal_rows}
    pressure = {row["strategy"]: row for row in pressure_rows}
    labels = list(normal)
    x = np.arange(len(labels))
    width = 0.2
    figure, axis = plt.subplots(figsize=(11, 5))
    for offset, metric in enumerate(("mean_minutes", "p95_minutes")):
        axis.bar(
            x + (offset * 2 - 1.5) * width,
            [normal[name][metric] for name in labels],
            width,
            label=f"Independent {metric.replace('_minutes', '')}",
        )
        axis.bar(
            x + (offset * 2 - 0.5) * width,
            [pressure[name][metric] for name in labels],
            width,
            label=f"Shared {metric.replace('_minutes', '')}",
        )
    axis.set_xticks(x, labels, rotation=25, ha="right")
    axis.set_ylabel("Minutes")
    axis.set_title(f"{scenario}: phase_correlation=1 pressure comparison")
    axis.legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)


def _observed_conflicts(rows: list[dict]) -> list[dict]:
    conflicts = []
    for left in rows:
        for right in rows:
            if left["strategy"] == right["strategy"]:
                continue
            if left["mean_minutes"] < right["mean_minutes"] and left["p95_minutes"] > right["p95_minutes"]:
                conflicts.append(
                    {
                        "faster_on_mean": left["strategy"],
                        "slower_on_mean": right["strategy"],
                        "faster_mean_minutes": left["mean_minutes"],
                        "faster_p95_minutes": left["p95_minutes"],
                        "slower_mean_minutes": right["mean_minutes"],
                        "slower_p95_minutes": right["p95_minutes"],
                    }
                )
    return conflicts


def _write_scenario_report(path: Path, document: dict, rows: list[dict]) -> None:
    name = document["scenario"]
    recommended = document["recommended_strategy"]
    lines = [
        f"# {name}",
        "",
        "Generated from held-out Monte Carlo samples.",
        "",
        f"- Origin: `{document['origin']}`",
        f"- Destination: `{document['destination']}`",
        f"- Held-out samples per strategy: `{document['samples']}`",
        f"- Selection seed: `{document['selection_seed']}`",
        f"- Held-out evaluation seed: `{document['evaluation_seed']}`",
        f"- Recommended strategy: `{recommended}`",
        f"- Recommended route count: `{document['strategies'][recommended]['route_count']}`",
        "",
        "## Results",
        "",
        "| Strategy | Routes | Mean | P90 | P95 | Mean wait | Missed | Invalid | Fare invalid |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {strategy} | {route_count} | {mean_minutes:.2f} | {p90_minutes:.2f} | "
            "{p95_minutes:.2f} | {mean_wait_minutes:.2f} | {failure_probability:.3f} | "
            "{invalid_transfer_probability:.3f} | {fare_invalid_probability:.3f} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The experiment does not force a reliability win. Mean/tail conflicts are "
            "reported only when observed in the held-out measurements.",
            "",
            f"- Executable multi-branch policy: `{document['multi_branch_policy']}`.",
            f"- Observed mean/tail conflicts: `{len(document['observed_mean_tail_conflicts'])}`.",
            f"- Reliability-policy P95 change under shared phase: "
            f"`{document['pressure_comparison']['p95_delta_vs_independent']:.2f}` minutes.",
            "",
            "## Artifacts",
            "",
            f"- `{name}.summary.json`",
            f"- `{name}.samples.csv`",
            f"- `{name}.phase_correlation_1.csv`",
            f"- `{name}.duration_quantiles.png`",
            f"- `{name}.waiting_distribution.png`",
            f"- `{name}.failure_rates.png`",
            f"- `{name}.network.png`",
            f"- `{name}.policy.png`",
            f"- `{name}.phase_correlation_1.png`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_aggregate_report(results_dir: Path, documents: list[dict]) -> None:
    lines = [
        "# SG-Transit Reliability Experiments",
        "",
        "Generated by `python -m experiments.run_all` using `plan()` for strategy "
        "selection and `evaluate()` for held-out simulation.",
        "",
        "Selection samples are separate from the 10,000 held-out samples. Results "
        "compare synthetic baselines and do not claim to beat Google Maps.",
        "",
        "## Scenarios",
        "",
        "| Scenario | Recommended | Routes | Mean | P95 | Mean/tail conflicts |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for document in documents:
        recommended = document["recommended_strategy"]
        summary = document["strategies"][recommended]["summary"]
        lines.append(
            f"| {document['scenario']} | {recommended} | "
            f"{document['strategies'][recommended]['route_count']} | "
            f"{summary['mean_minutes']:.2f} | {summary['p95_minutes']:.2f} | "
            f"{len(document['observed_mean_tail_conflicts'])} |"
        )
    lines.extend(
        [
            "",
            "A conflict means one evaluated strategy has a lower mean but a higher "
            "P95 than another. A zero count is a valid result; no threshold or "
            "hand-picked outcome is used.",
            "",
            "Each scenario also includes a phase_correlation=1 pressure comparison "
            "to test whether a multi-service advantage depends on independent timing.",
        ]
    )
    (results_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_scenario(
    name: str,
    seed: int = 100,
    *,
    selection_seed: int = 7,
    samples: int = SAMPLES,
    selection_samples: int = SELECTION_SAMPLES,
    results_dir: Path | str = RESULTS,
    bootstrap_resamples: int = 1_000,
) -> dict:
    """Run one scenario with independent selection and held-out evaluation seeds."""
    if seed == selection_seed:
        raise ValueError("selection_seed and evaluation seed must be different")
    if samples < 1 or selection_samples < 1:
        raise ValueError("samples and selection_samples must be positive")

    network, origin, destination = scenario_network(name)
    parameters = RoutingParameters()
    decision = plan(
        network,
        origin,
        destination,
        parameters,
        samples=selection_samples,
        seed=selection_seed,
        departure_time=0.0,
    )
    if decision.recommended_strategy is None:
        raise ValueError(f"No route found for scenario {name}")

    strategies = {
        label: _as_strategy(label, route)
        for label, route in decision.baselines.items()
        if route is not None
    }
    strategies["reliability_policy"] = decision.recommended_strategy
    evaluations = {
        label: (
            strategy,
            evaluate(
                strategy,
                network,
                samples=samples,
                seed=seed,
                departure_time=0.0,
                parameters=parameters,
                phase_correlation=0.0,
            ),
        )
        for label, strategy in strategies.items()
    }
    pressure_evaluations = {
        label: (
            strategy,
            evaluate(
                strategy,
                network,
                samples=samples,
                seed=seed,
                departure_time=0.0,
                parameters=parameters,
                phase_correlation=1.0,
            ),
        )
        for label, strategy in strategies.items()
    }

    rows = _strategy_rows(evaluations, name, origin, destination)
    pressure_rows = _strategy_rows(pressure_evaluations, name, origin, destination)
    baseline_name = "shortest_expected_time" if "shortest_expected_time" in evaluations else next(iter(evaluations))
    baseline_result = evaluations[baseline_name][1]
    paired = {}
    for index, (label, (_, result)) in enumerate(evaluations.items()):
        paired[label] = {
            "mean_minutes": paired_bootstrap_ci(
                result.durations,
                baseline_result.durations,
                np.mean,
                seed=seed + 10_001 + index,
                resamples=bootstrap_resamples,
            ),
            "p95_minutes": paired_bootstrap_ci(
                result.durations,
                baseline_result.durations,
                lambda values: float(np.quantile(values, 0.95)),
                seed=seed + 20_001 + index,
                resamples=bootstrap_resamples,
            ),
            "baseline": baseline_name,
        }

    pressure_summary = {
        label: _metric_summary(result) for label, (_, result) in pressure_evaluations.items()
    }
    pressure_policy = pressure_summary["reliability_policy"]
    normal_policy = evaluations["reliability_policy"][1].summary
    document = {
        "schema_version": 2,
        "scenario": name,
        "origin": origin,
        "destination": destination,
        "selection_seed": selection_seed,
        "evaluation_seed": seed,
        "selection_samples": selection_samples,
        "samples": samples,
        "parameters": asdict(parameters),
        "candidate_count": len(decision.candidates),
        "candidate_routes": [_route_payload(route) for route in decision.candidates],
        "recommended_strategy": "reliability_policy",
        "recommended_strategy_name": decision.recommended_strategy.name,
        "strategies": {
            label: {
                **_strategy_payload(strategy),
                "policy": _policy_payload(strategy),
                "summary": _metric_summary(result),
                "branch_counts": {key: int(value) for key, value in result.branch_counts.items()},
            }
            for label, (strategy, result) in evaluations.items()
        },
        "paired_bootstrap_vs_baseline": paired,
        "pressure_comparison": {
            "phase_correlation": 1.0,
            "p95_delta_vs_independent": float(pressure_policy["p95_minutes"] - normal_policy.p95_minutes),
            "strategies": pressure_summary,
        },
        "multi_branch_policy": len(decision.recommended_strategy.routes) > 1,
        "observed_mean_tail_conflicts": _observed_conflicts(rows),
        "assumptions": [
            "Synthetic network and stationary headway model.",
            "Selection samples are not reused as held-out samples.",
            "phase_correlation=1 is a stress comparison, not a timetable claim.",
            "Fare-invalid values are diagnostics, not a real Singapore fare calculation.",
        ],
    }

    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / f"{name}.summary.json").write_text(
        json.dumps(document, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    _write_csv(results_dir / f"{name}.samples.csv", _raw_rows(evaluations, name, parameters))
    _write_csv(
        results_dir / f"{name}.phase_correlation_1.csv",
        _raw_rows(pressure_evaluations, name, parameters),
    )
    _bar_plot(rows, "mean_minutes", f"{name}: mean journey time", "Minutes", results_dir / f"{name}_mean.png")
    _bar_plot(rows, "p90_minutes", f"{name}: P90 journey time", "Minutes", results_dir / f"{name}_p90.png")
    _bar_plot(rows, "p95_minutes", f"{name}: P95 journey time", "Minutes", results_dir / f"{name}_p95.png")
    _plot_quantiles(rows, name, results_dir / f"{name}.duration_quantiles.png")
    _plot_waiting(evaluations, name, results_dir / f"{name}.waiting_distribution.png")
    _plot_failure_rates(rows, name, results_dir / f"{name}.failure_rates.png")
    _plot_network(network, origin, destination, name, results_dir / f"{name}.network.png")
    _plot_policy(decision.recommended_strategy, name, results_dir / f"{name}.policy.png")
    _plot_pressure(rows, pressure_rows, name, results_dir / f"{name}.phase_correlation_1.png")
    _write_scenario_report(results_dir / f"{name}.report.md", document, rows)
    return document


def main(
    *,
    results_dir: Path | str = RESULTS,
    samples: int = SAMPLES,
    selection_samples: int = SELECTION_SAMPLES,
    bootstrap_resamples: int = 1_000,
) -> list[dict]:
    results_dir = Path(results_dir)
    documents = [
        run_scenario(
            name,
            seed=100 + index,
            selection_seed=7 + index,
            samples=samples,
            selection_samples=selection_samples,
            results_dir=results_dir,
            bootstrap_resamples=bootstrap_resamples,
        )
        for index, name in enumerate(SCENARIOS)
    ]
    summary_rows = []
    for document in documents:
        for label, strategy in document["strategies"].items():
            summary_rows.append(
                {
                    "scenario": document["scenario"],
                    "strategy": label,
                    "route_count": strategy["route_count"],
                    **strategy["summary"],
                }
            )
    _write_csv(results_dir / "all_scenarios.csv", summary_rows)
    _write_aggregate_report(results_dir, documents)
    (results_dir / "manifest.json").write_text(
        json.dumps(
            {
                "scenarios": list(SCENARIOS),
                "samples_per_strategy": samples,
                "selection_samples": selection_samples,
                "selection_seeds": [7 + index for index in range(len(SCENARIOS))],
                "evaluation_seeds": [100 + index for index in range(len(SCENARIOS))],
                "matplotlib_backend": matplotlib.get_backend(),
                "summary_files": [f"{name}.summary.json" for name in SCENARIOS],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Generated {len(documents)} scenario reports in {results_dir}")
    return documents


if __name__ == "__main__":
    main()

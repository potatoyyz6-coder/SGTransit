import csv
import json

import numpy as np
import pytest

from experiments.run_all import (
    SCENARIOS,
    main,
    paired_bootstrap_ci,
    run_scenario,
)


def test_paired_bootstrap_is_reproducible_and_has_ci():
    left = np.arange(40, dtype=float)
    right = left + 2
    first = paired_bootstrap_ci(left, right, np.mean, seed=11, resamples=80)
    second = paired_bootstrap_ci(left, right, np.mean, seed=11, resamples=80)

    assert first == second
    assert first["estimate"] == pytest.approx(-2)
    assert len(first["ci95"]) == 2


def test_run_scenario_writes_held_out_artifacts_and_multibranch_policy(tmp_path):
    document = run_scenario(
        "alternative_services",
        seed=101,
        selection_seed=7,
        samples=64,
        selection_samples=32,
        results_dir=tmp_path,
        bootstrap_resamples=40,
    )

    assert document["selection_seed"] != document["evaluation_seed"]
    assert document["samples"] == 64
    assert document["multi_branch_policy"] is True
    assert len(document["paired_bootstrap_vs_baseline"]) >= 1
    assert document["pressure_comparison"]["phase_correlation"] == 1.0

    summary_path = tmp_path / "alternative_services.summary.json"
    assert summary_path.exists()
    assert json.loads(summary_path.read_text(encoding="utf-8"))["samples"] == 64

    with (tmp_path / "alternative_services.samples.csv").open(
        newline="", encoding="utf-8"
    ) as file:
        rows = list(csv.DictReader(file))
    expected_rows = 64 * len(document["strategies"])
    assert len(rows) == expected_rows
    assert {row["strategy"] for row in rows} == set(document["strategies"])

    with (tmp_path / "alternative_services.phase_correlation_1.csv").open(
        newline="", encoding="utf-8"
    ) as file:
        pressure_rows = list(csv.DictReader(file))
    assert len(pressure_rows) == expected_rows

    for suffix in (
        "_mean.png",
        "_p90.png",
        "_p95.png",
        ".duration_quantiles.png",
        ".waiting_distribution.png",
        ".failure_rates.png",
        ".network.png",
        ".policy.png",
        ".phase_correlation_1.png",
        ".report.md",
    ):
        assert (tmp_path / f"alternative_services{suffix}").exists()


def test_main_runs_all_scenarios_without_reusing_selection_seed(tmp_path):
    documents = main(
        results_dir=tmp_path,
        samples=24,
        selection_samples=16,
        bootstrap_resamples=20,
    )

    assert [document["scenario"] for document in documents] == list(SCENARIOS)
    assert all(
        document["selection_seed"] != document["evaluation_seed"]
        for document in documents
    )
    assert (tmp_path / "all_scenarios.csv").exists()
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "manifest.json").exists()


def test_selection_and_evaluation_seeds_must_differ(tmp_path):
    with pytest.raises(ValueError, match="must be different"):
        run_scenario(
            "single_critical_transfer",
            seed=7,
            selection_seed=7,
            samples=8,
            selection_samples=8,
            results_dir=tmp_path,
            bootstrap_resamples=5,
        )

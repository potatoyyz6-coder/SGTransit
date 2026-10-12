import json

import pytest

from experiments.corridor_search import run_scenario, write_report


def test_candidate_loss_is_measured_not_hidden(tmp_path):
    document = run_scenario("candidate_loss", samples=100, selection_samples=64, output=tmp_path)
    search = document["search"]
    assert search["missed_selected_full_fixed"]
    assert search["candidate_recall"] < 1
    assert search["bounded_expansions"] < search["exact_expansions"]
    assert search["truncated"]
    assert search["ordinary_route_count"] == 1
    assert document["evaluations"]["bounded_fixed_reliable"]["summary"]["p95_minutes"] > (
        document["evaluations"]["full_fixed_reliable"]["summary"]["p95_minutes"])
    saved = json.loads((tmp_path / "candidate_loss.json").read_text())
    assert saved == document
    write_report([document], tmp_path)
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "comparison.png").stat().st_size > 1000


def test_shared_search_saves_expansions_and_records_full_comparator(tmp_path):
    document = run_scenario("shared_corridor", samples=100, selection_samples=64, output=tmp_path)
    search = document["search"]
    assert search["bounded_expansions"] < search["exact_expansions"]
    result = document["evaluations"]["bounded_adaptive"]
    assert result["shared_arcs"] < result["unshared_route_segment_count"]
    assert result["local_updates"] > 100
    assert result["value_cache_hits"] > 0
    assert result["summary"]["completion_probability"] == 1
    assert "full_adaptive" in document["fully_correlated_pressure"]


def test_selection_and_evaluation_seed_separation(tmp_path):
    with pytest.raises(ValueError, match="seeds"):
        run_scenario("shared_corridor", seed=7, selection_seed=7, output=tmp_path)


def test_report_preserves_uncompleted_metrics(tmp_path):
    document = run_scenario("candidate_loss", samples=20, selection_samples=20, output=tmp_path)
    summary = document["evaluations"]["bounded_adaptive"]["summary"]
    summary.update(mean_minutes=None, p90_minutes=None, p95_minutes=None,
                   completion_probability=0.8, stopped_probability=0.2)
    write_report([document], tmp_path)
    text = (tmp_path / "report.md").read_text()
    assert "uncompleted" in text
    assert "0.800" in text

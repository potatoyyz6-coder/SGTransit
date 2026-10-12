from copy import deepcopy
import json
from pathlib import Path

import pytest

from experiments.compare_pei_hwa_reference import MODEL, OBSERVATIONS, compare, run


def inputs():
    return (json.loads(OBSERVATIONS.read_text(encoding="utf-8")),
            json.loads(MODEL.read_text(encoding="utf-8")))


def test_reference_keeps_walking_waiting_and_unmatched_routes_separate():
    observed, model = inputs()
    report = compare(observed, model, model["network_path"])
    assert report["query_departure"] == "2026-10-04T16:00:00+08:00"
    assert [row["google_displayed_minutes"] for row in report["comparisons"]] == [53, 57, 67, 67]
    first, walk, other, absent = report["comparisons"]
    assert first["query_to_first_board_minutes"] == 16
    assert first["google_displayed_walk_minutes"] == 5
    assert first["model_mean_minutes"] is not None
    assert other["model_mean_minutes"] is not None
    assert walk["model_mean_minutes"] is None
    assert absent["model_mean_minutes"] is None
    assert not any(row["matched_comparison"] for row in report["comparisons"])
    assert report["model_reused_without_rerun"] and not report["model_date_specific"]


def test_reference_rejects_network_endpoint_and_time_mismatches():
    observed, model = inputs()
    bad = deepcopy(model)
    bad["base"]["network_sha256"] = "wrong"
    with pytest.raises(ValueError, match="hash"):
        compare(observed, bad, model["network_path"])
    bad = deepcopy(observed)
    bad["origin_stop_id"] = "other"
    with pytest.raises(ValueError, match="endpoints"):
        compare(bad, model, model["network_path"])
    bad = deepcopy(observed)
    bad["query_departure"] = "2026-10-04T16:00:00"
    with pytest.raises(ValueError, match="Singapore"):
        compare(bad, model, model["network_path"])


def test_report_does_not_modify_inputs_or_access_live_data(tmp_path, monkeypatch):
    import socket
    import sg_transit.lta as lta
    def forbidden(*args, **kwargs):
        raise AssertionError("External access is not allowed")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(lta, "provider_from_environment", forbidden)
    before = [path.read_bytes() for path in (OBSERVATIONS, MODEL)]
    run(output=tmp_path)
    assert before == [path.read_bytes() for path in (OBSERVATIONS, MODEL)]
    assert "no new Sunday" in (tmp_path / "report.md").read_text()

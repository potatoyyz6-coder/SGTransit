import csv
import json
import socket

import pytest

from experiments.pei_hwa_case import (
    DEPARTURES, ORIGIN, DESTINATION, build_offline, run_offline, write_google_template,
)
from sg_transit.io import load_network
from sg_transit.models import Leg, Route, validate_route


def test_offline_expansion_directions_and_five_onward_options(tmp_path):
    path = tmp_path / "network.json"
    build_offline(path)
    network, document = load_network(path)
    assert len(network.stops) == 47
    assert len(network.services) == 10
    assert network.services["151-D2"].can_ride(ORIGIN, "42141")
    assert "42071" not in network.services["154-D1"].stops
    for service in ("52-D2", "61-D2", "184-D1"):
        assert network.services[service].can_ride("12061", "42071")
        assert not network.services[service].can_ride("42071", "12061")
    for service in ("61-D2", "157-D1", "174-D2", "970-D2", "985-D2"):
        assert network.services[service].can_ride("42071", DESTINATION)
    assert document["timing_parameters"]["live_api_used"] is False
    assert document["timing_parameters"]["time_of_day_profiles"] is False


def test_users_multitransfer_paths_are_legal(tmp_path):
    path = tmp_path / "network.json"
    build_offline(path)
    network, _ = load_network(path)
    for transfer in ("52-D2", "61-D2", "184-D1"):
        specs = (("151-D2", ORIGIN, "12061"), (transfer, "12061", "42071"),
                 ("985-D2", "42071", DESTINATION))
        legs = [Leg(service, start, end, network.services[service].ride_time(start, end), 7.5,
                    0 if index == 0 else 3) for index, (service, start, end) in enumerate(specs)]
        validate_route(Route(ORIGIN, DESTINATION, legs), network)
    specs = (("151-D2", ORIGIN, "12061"), ("154-D1", "12061", "42141"),
             ("52-D2", "42141", "42071"), ("985-D2", "42071", DESTINATION))
    validate_route(Route(ORIGIN, DESTINATION, [
        Leg(service, start, end, network.services[service].ride_time(start, end))
        for service, start, end in specs]), network)


def test_six_future_queries_and_no_overwrite_of_manual_google_entries(tmp_path):
    assert DEPARTURES == tuple(f"2026-10-01T{hour:02d}:00:00+08:00" for hour in (10, 12, 14, 16, 18, 20))
    path = tmp_path / "google.csv"
    write_google_template(path, "hash")
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 6
    assert all(not row["displayed_total_minutes"] for row in rows)
    assert all(row["network_sha256"] == "hash" for row in rows)
    path.write_text("user observations")
    write_google_template(path, "changed")
    assert path.read_text() == "user observations"


def test_offline_runner_does_not_use_network_or_credentials(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline experiment attempted a live API/credential operation")
    import sg_transit.lta as lta
    monkeypatch.setattr(lta, "provider_from_environment", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    result = run_offline(
        tmp_path / "results", tmp_path / "network.json", samples=20,
        sensitivity=False, pressure=False, bootstrap_repetitions=5)
    assert not result["recorded_eta_used"]
    assert not result["live_api_used"]
    assert not result["google_observations_used"]
    assert len(result["slots"]) == 6
    assert result["slots"][0]["metrics"] == result["slots"][-1]["metrics"]
    assert result["base"]["search"]["full_candidates"] > result["base"]["search"]["bounded_candidates"]
    assert result["base"]["search"]["full_transfer_count_histogram"][5] > 0
    assert len(result["base"]["search"]["pei_hwa_direct_services"]) == 5
    saved = json.loads((tmp_path / "results/experiment.json").read_text())
    assert saved["base"]["network_sha256"] == result["base"]["network_sha256"]
    assert (tmp_path / "results/comparison.png").stat().st_size > 1000
    text = (tmp_path / "results/report.md").read_text()
    assert "NOT six measured" in text
    assert "2026-09-28 screenshots" in text


def test_offline_parameters_validate(tmp_path):
    with pytest.raises(ValueError):
        build_offline(tmp_path / "network.json", speed_kmh=0)

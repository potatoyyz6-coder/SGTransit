import json

import pytest

from sg_transit.lta import (
    DATAMALL_API_KEY_ENV,
    LEGACY_API_KEY_ENV,
    LTAApiError,
    LTABusArrivalProvider,
    collect_bus_arrival_series,
    collect_bus_arrivals,
    parse_bus_arrival_response,
    provider_from_environment,
)
from sg_transit.lta_calibration import apply_headways_to_network, estimate_headways


PAYLOAD = {
    "Services": [
        {
            "ServiceNo": "151",
            "NextBus": {
                "OriginCode": "16181",
                "DestinationCode": "28009",
                "EstimatedArrival": "2026-09-28T16:05:00+08:00",
                "Monitored": True,
                "Latitude": "1.2965",
                "Longitude": "103.7725",
                "VisitNumber": "1",
                "Load": "SEA",
                "Feature": "WAB",
            },
            "NextBus2": {
                "OriginCode": "16181",
                "DestinationCode": "28009",
                "EstimatedArrival": "",
                "Monitored": False,
                "Latitude": "",
                "Longitude": "",
                "VisitNumber": "1",
                "Load": "SEA",
                "Feature": "",
            },
            "NextBus3": {},
        }
    ]
}


def test_parse_bus_arrival_response_normalizes_next_buses():
    arrivals = parse_bus_arrival_response(PAYLOAD)
    assert len(arrivals) == 2
    assert arrivals[0].service_no == "151"
    assert arrivals[0].latitude == pytest.approx(1.2965)
    assert arrivals[1].estimated_arrival == ""
    assert arrivals[1].latitude is None


def test_provider_builds_authenticated_request_and_parses_json():
    calls = []

    def transport(url, headers, timeout):
        calls.append((url, headers, timeout))
        return json.dumps(PAYLOAD).encode()

    provider = LTABusArrivalProvider("test-key", transport=transport, timeout=3)
    arrivals = provider.fetch("16181", "151")

    assert len(arrivals) == 2
    assert "BusStopCode=16181" in calls[0][0]
    assert "ServiceNo=151" in calls[0][0]
    assert calls[0][1]["AccountKey"] == "test-key"
    assert calls[0][2] == 3


def test_collector_writes_a_reproducible_snapshot(tmp_path):
    provider = LTABusArrivalProvider(
        "test-key",
        transport=lambda url, headers, timeout: json.dumps(PAYLOAD).encode(),
    )
    output = tmp_path / "lta" / "arrivals.json"
    snapshot = collect_bus_arrivals(
        provider,
        ["16181", "28009"],
        output_path=output,
        collected_at="2026-09-28T08:00:00+00:00",
    )

    assert output.exists()
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved == snapshot
    assert [item["bus_stop_code"] for item in snapshot["bus_stops"]] == ["16181", "28009"]


def test_provider_rejects_invalid_response():
    provider = LTABusArrivalProvider(
        "test-key",
        transport=lambda url, headers, timeout: b'{"Services": null}',
    )
    with pytest.raises(LTAApiError):
        provider.fetch("16181")


def test_headway_calibration_clusters_repeated_eta_observations():
    def snapshot(*times):
        return {
            "schema_version": 1,
            "bus_stops": [
                {
                    "bus_stop_code": "16181",
                    "arrivals": [
                        {"service_no": "151", "estimated_arrival": time}
                        for time in times
                    ],
                }
            ],
        }

    series = {
        "schema_version": 2,
        "samples": 3,
        "snapshots": [
            snapshot("2026-09-28T16:05:00+08:00", "2026-09-28T16:17:00+08:00"),
            snapshot("2026-09-28T16:06:00+08:00", "2026-09-28T16:18:00+08:00"),
            snapshot("2026-09-28T16:04:30+08:00", "2026-09-28T16:16:30+08:00"),
        ],
    }

    report = estimate_headways(series)

    assert report["estimates"][0]["service_no"] == "151"
    assert report["estimates"][0]["median_headway_minutes"] == pytest.approx(12)


def test_calibration_preserves_eta_collection_window():
    series = {
        "schema_version": 2,
        "provider": "https://example.org/v3/BusArrival",
        "snapshots": [
            {
                "collected_at": "2026-09-28T10:00:00+08:00",
                "bus_stops": [],
            },
            {
                "collected_at": "2026-09-28T10:01:00+08:00",
                "bus_stops": [],
            },
        ],
    }

    report = estimate_headways(series)

    assert report["source_endpoint"] == series["provider"]
    assert report["collected_from"] == series["snapshots"][0]["collected_at"]
    assert report["collected_to"] == series["snapshots"][1]["collected_at"]


def test_collector_can_record_repeated_snapshots_without_waiting(tmp_path):
    provider = LTABusArrivalProvider(
        "test-key",
        transport=lambda url, headers, timeout: json.dumps(PAYLOAD).encode(),
    )
    output = tmp_path / "lta" / "series.json"
    series = collect_bus_arrival_series(
        provider,
        ["16181"],
        samples=2,
        interval_seconds=0,
        output_path=output,
        collected_at_fn=lambda: "2026-09-28T08:00:00+00:00",
    )

    assert series["schema_version"] == 2
    assert series["samples"] == 2
    assert len(series["snapshots"]) == 2
    assert json.loads(output.read_text(encoding="utf-8")) == series


def test_provider_from_environment_uses_datamall_api_access_key(monkeypatch):
    monkeypatch.setenv(DATAMALL_API_KEY_ENV, "datamall-key")
    monkeypatch.setenv(LEGACY_API_KEY_ENV, "sdk-key")

    provider = provider_from_environment()

    assert provider.account_key == "datamall-key"


def test_provider_from_environment_rejects_sdk_key_only(monkeypatch):
    monkeypatch.delenv(DATAMALL_API_KEY_ENV, raising=False)
    monkeypatch.setenv(LEGACY_API_KEY_ENV, "sdk-key")

    with pytest.raises(ValueError, match="DataMall API Access Key"):
        provider_from_environment()


def test_apply_headways_updates_only_matching_service_and_preserves_source():
    network = {
        "provenance": {"timing_note": "source estimates"},
        "services": [
            {
                "id": "105-D1",
                "source_service": "105",
                "stops": ["A", "B"],
                "headway_minutes": 12.0,
                "timing_quality": "estimated",
            },
            {
                "id": "183-D1",
                "source_service": "183",
                "stops": ["A", "B"],
                "headway_minutes": 10.0,
                "timing_quality": "estimated",
            },
        ],
    }
    calibration = {
        "source_schema_version": 2,
        "input_samples": 3,
        "estimates": [
            {
                "bus_stop_code": "A",
                "service_no": "105",
                "headway_observation_count": 2,
                "median_headway_minutes": 8.0,
            }
        ],
    }

    derived = apply_headways_to_network(network, calibration)

    assert network["services"][0]["headway_minutes"] == 12.0
    assert derived["services"][0]["headway_minutes"] == 8.0
    assert derived["services"][0]["timing_quality"] == "calibrated_from_lta_bus_arrival_snapshots"
    assert derived["services"][1]["headway_minutes"] == 10.0
    assert derived["provenance"]["headway_calibration"]["applied_service_ids"] == ["105-D1"]


def test_apply_headways_prefers_boarding_side_over_return_terminal():
    network = {
        "services": [
            {
                "id": "105-D1",
                "source_service": "105",
                "stops": ["17161", "28009"],
                "headway_minutes": 12.0,
            }
        ]
    }
    calibration = {
        "source_schema_version": 2,
        "input_samples": 12,
        "estimates": [
            {
                "bus_stop_code": "28009",
                "service_no": "105",
                "headway_observation_count": 3,
                "median_headway_minutes": 20.0,
            },
            {
                "bus_stop_code": "17161",
                "service_no": "105",
                "headway_observation_count": 3,
                "median_headway_minutes": 8.0,
            },
        ],
    }

    derived = apply_headways_to_network(network, calibration, min_observations=2)

    service = derived["services"][0]
    assert service["headway_minutes"] == 8.0
    assert service["headway_calibration"]["matched_observations"][0]["bus_stop_code"] == "17161"

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
import math
from pathlib import Path
from statistics import median
from typing import Mapping


def _parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid ISO timestamp: {value!r}") from exc


def _cluster_times(times: list[datetime], tolerance_minutes: float) -> list[datetime]:
    clusters: list[list[datetime]] = []
    for value in sorted(times):
        if not clusters or (value - clusters[-1][-1]).total_seconds() / 60 > tolerance_minutes:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    return [
        datetime.fromtimestamp(
            sum(value.timestamp() for value in cluster) / len(cluster),
            tz=cluster[0].tzinfo,
        )
        for cluster in clusters
    ]


def estimate_headways(
    series: Mapping[str, object],
    *,
    tolerance_minutes: float = 2.0,
    min_headway_minutes: float = 3.0,
) -> dict[str, object]:
    """Estimate service headways from repeated ETA snapshots."""
    if series.get("schema_version") != 2 or not isinstance(series.get("snapshots"), list):
        raise ValueError("Expected a schema_version 2 LTA snapshot series")
    if tolerance_minutes < 0 or min_headway_minutes <= 0:
        raise ValueError("Invalid headway calibration parameters")

    snapshots = series["snapshots"]
    collected_at = [
        str(snapshot.get("collected_at"))
        for snapshot in snapshots
        if isinstance(snapshot, Mapping) and snapshot.get("collected_at")
    ]
    events: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    for snapshot in snapshots:
        if not isinstance(snapshot, Mapping):
            raise ValueError("Snapshot must be an object")
        for stop in snapshot.get("bus_stops", []):
            if not isinstance(stop, Mapping):
                raise ValueError("Bus stop entry must be an object")
            stop_code = str(stop.get("bus_stop_code", "")).strip()
            for arrival in stop.get("arrivals", []):
                if not isinstance(arrival, Mapping):
                    raise ValueError("Arrival entry must be an object")
                estimated = str(arrival.get("estimated_arrival", "")).strip()
                service_no = str(arrival.get("service_no", "")).strip()
                if stop_code and service_no and estimated:
                    events[(stop_code, service_no)].append(_parse_time(estimated))

    estimates = []
    for (stop_code, service_no), times in sorted(events.items()):
        clustered = _cluster_times(times, tolerance_minutes)
        gaps = [
            (right - left).total_seconds() / 60
            for left, right in zip(clustered, clustered[1:])
        ]
        gaps = [gap for gap in gaps if math.isfinite(gap) and gap >= min_headway_minutes]
        if gaps:
            estimates.append(
                {
                    "bus_stop_code": stop_code,
                    "service_no": service_no,
                    "arrival_event_count": len(clustered),
                    "headway_observation_count": len(gaps),
                    "median_headway_minutes": float(median(gaps)),
                    "min_headway_minutes": float(min(gaps)),
                    "max_headway_minutes": float(max(gaps)),
                }
            )

    return {
        "schema_version": 1,
        "source_schema_version": series.get("schema_version"),
        "input_samples": series.get("samples", len(series["snapshots"])),
        "source_endpoint": series.get("provider"),
        "collected_from": min(collected_at) if collected_at else None,
        "collected_to": max(collected_at) if collected_at else None,
        "tolerance_minutes": float(tolerance_minutes),
        "min_headway_minutes": float(min_headway_minutes),
        "estimates": estimates,
        "note": "Estimates are derived from repeated ETA snapshots; they are not official schedules.",
    }


def calibrate_headways_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    tolerance_minutes: float = 2.0,
    min_headway_minutes: float = 3.0,
) -> dict[str, object]:
    series = json.loads(Path(input_path).read_text(encoding="utf-8"))
    report = estimate_headways(
        series,
        tolerance_minutes=tolerance_minutes,
        min_headway_minutes=min_headway_minutes,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def apply_headways_to_network(
    network: Mapping[str, object],
    calibration: Mapping[str, object],
    *,
    min_observations: int = 1,
) -> dict[str, object]:
    """Return a derived network with matching LTA headway estimates applied.

    The source network is not modified. A service is updated only when an
    estimate has the same source service number and was observed at a stop
    served by that service. Prefer the earliest observed stop in the modeled
    direction, so measurements at a return terminal are not mixed into the
    boarding-side estimate. The result remains a mixed-data network when some
    services have no live estimate.
    """
    if min_observations < 1:
        raise ValueError("min_observations must be positive")
    services = network.get("services")
    estimates = calibration.get("estimates")
    if not isinstance(services, list) or not isinstance(estimates, list):
        raise ValueError("Network and calibration must contain list fields")

    derived = json.loads(json.dumps(network))
    estimate_by_service: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for estimate in estimates:
        if not isinstance(estimate, Mapping):
            raise ValueError("Calibration estimate must be an object")
        service_no = str(estimate.get("service_no", "")).strip()
        value = estimate.get("median_headway_minutes")
        observations = estimate.get("headway_observation_count", 0)
        if not service_no or not isinstance(value, (int, float)) or not math.isfinite(value):
            continue
        if not isinstance(observations, int) or observations < min_observations:
            continue
        estimate_by_service[service_no].append(estimate)

    applied = []
    for service in derived["services"]:
        if not isinstance(service, dict):
            raise ValueError("Network service must be an object")
        source_service = str(service.get("source_service", service.get("id", ""))).strip()
        estimates_by_stop = {
            str(estimate.get("bus_stop_code", "")).strip(): estimate
            for estimate in estimate_by_service.get(source_service, [])
        }
        matches = [
            estimates_by_stop[str(stop)]
            for stop in service.get("stops", [])
            if str(stop) in estimates_by_stop
        ][:1]
        if not matches:
            continue
        headway = float(median(float(item["median_headway_minutes"]) for item in matches))
        service["headway_minutes"] = headway
        service["timing_quality"] = "calibrated_from_lta_bus_arrival_snapshots"
        service["headway_calibration"] = {
            "service_no": source_service,
            "matched_observations": [
                {
                    "bus_stop_code": item.get("bus_stop_code"),
                    "headway_observation_count": item.get("headway_observation_count"),
                    "median_headway_minutes": item.get("median_headway_minutes"),
                }
                for item in matches
            ],
        }
        applied.append(service.get("id", source_service))

    provenance = derived.setdefault("provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("Network provenance must be an object")
    provenance["headway_calibration"] = {
        "source_endpoint": calibration.get("source_endpoint"),
        "collected_from": calibration.get("collected_from"),
        "collected_to": calibration.get("collected_to"),
        "source_schema_version": calibration.get("source_schema_version"),
        "input_samples": calibration.get("input_samples"),
        "min_observations": min_observations,
        "applied_service_ids": applied,
        "note": "Only matched services were updated; unmatched services retain their source estimates.",
    }
    return derived


def apply_headways_file(
    network_path: str | Path,
    calibration_path: str | Path,
    output_path: str | Path,
    *,
    min_observations: int = 1,
) -> dict[str, object]:
    network = json.loads(Path(network_path).read_text(encoding="utf-8-sig"))
    calibration = json.loads(Path(calibration_path).read_text(encoding="utf-8"))
    derived = apply_headways_to_network(
        network,
        calibration,
        min_observations=min_observations,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(derived, indent=2) + "\n", encoding="utf-8")
    return derived

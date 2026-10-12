from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
OUTPUT = ROOT / "network.json"
SOURCES = ROOT / "sources.json"

COMMIT = "5b9ed168436b4efe260feef997e66aa39932996e"
REPO_URL = "https://github.com/Vorld/singapore-gtfs"
RAW_BASE = f"https://raw.githubusercontent.com/Vorld/singapore-gtfs/{COMMIT}/data/raw/datamall-bus"

# The endpoints are real stops. The selected service patterns are real ordered
# patterns; timing fields are deliberately estimated for this first experiment.
SEGMENTS = (
    ("151", "1", "16181", "16009", 15.0),
    ("10", "2", "16009", "16089", 10.0),
    ("183", "1", "16089", "28009", 10.0),
    ("201", "1", "16009", "17161", 10.0),
    ("105", "1", "17161", "28009", 12.0),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def select_pattern(
    rows: list[dict[str, str]], service_id: str, direction: str, start: str, end: str
) -> list[dict[str, str]]:
    pattern = [
        row
        for row in rows
        if row["ServiceNo"] == service_id and row["Direction"] == direction
    ]
    pattern.sort(key=lambda row: int(row["StopSequence"]))
    codes = [row["BusStopCode"] for row in pattern]
    try:
        start_index = codes.index(start)
        end_index = next(index for index, code in enumerate(codes) if index > start_index and code == end)
    except (StopIteration, ValueError) as exc:
        raise ValueError(f"Missing {service_id}/{direction} segment {start}->{end}") from exc
    if start_index >= end_index:
        raise ValueError(f"Segment is not forward in {service_id}/{direction}: {start}->{end}")
    return pattern[start_index : end_index + 1]


def estimated_ride_minutes(pattern: list[dict[str, str]]) -> list[float]:
    # DataMall's Distance column is cumulative route distance in km. A fixed
    # 20 km/h conversion is only a transparent first-stage estimate.
    distances = [float(row["Distance"]) for row in pattern]
    return [max(0.5, round((right - left) * 3.0, 2)) for left, right in zip(distances, distances[1:])]


def main() -> None:
    stop_rows = load_rows(RAW / "BusStops.csv")
    route_rows = load_rows(RAW / "BusRoutes.csv")
    stops_by_id = {row["BusStopCode"]: row for row in stop_rows}
    services = []
    used_stop_ids: set[str] = set()
    for service_id, direction, start, end, headway in SEGMENTS:
        pattern = select_pattern(route_rows, service_id, direction, start, end)
        stop_ids = [row["BusStopCode"] for row in pattern]
        used_stop_ids.update(stop_ids)
        services.append(
            {
                "id": f"{service_id}-D{direction}",
                "source_service": service_id,
                "direction": direction,
                "stops": stop_ids,
                "ride_minutes": estimated_ride_minutes(pattern),
                "headway_minutes": headway,
                "delay_max_minutes": 3.0,
                "timing_quality": "estimated_from_distance_and_assumed_headway",
            }
        )

    missing = sorted(stop_id for stop_id in used_stop_ids if stop_id not in stops_by_id)
    if missing:
        raise ValueError(f"Missing selected stop metadata: {missing}")
    stops = [
        {
            "id": stop_id,
            "name": f"{stops_by_id[stop_id]['Description']} ({stops_by_id[stop_id]['RoadName']})",
            "x": float(stops_by_id[stop_id]["Longitude"]),
            "y": float(stops_by_id[stop_id]["Latitude"]),
        }
        for stop_id in sorted(used_stop_ids)
    ]
    provenance = {
        "source_url": REPO_URL,
        "raw_urls": {
            "BusStops.csv": f"{RAW_BASE}/BusStops.csv",
            "BusRoutes.csv": f"{RAW_BASE}/BusRoutes.csv",
        },
        "commit": COMMIT,
        "license": "Singapore Open Data Licence v1.0 (LTA data); MIT (mirror code only)",
        "license_url": "https://datamall.lta.gov.sg/content/datamall/en/SingaporeOpenDataLicence.html",
        "upstream_accessed_at": "2026-07-06",
        "accessed_at": "2026-09-27",
        "raw_sha256": {
            "BusStops.csv": sha256(RAW / "BusStops.csv"),
            "BusRoutes.csv": sha256(RAW / "BusRoutes.csv"),
        },
        "scope": "Selected ordered service-pattern segments around NUS Ctrl Lib and Jurong East Int.",
        "timing_note": "Stop coordinates and ordered service patterns are sourced; ride times, headways and delay bounds are modeling estimates.",
    }
    document = {
        "schema_version": 1,
        "provenance": provenance,
        "stops": stops,
        "services": services,
        "validation_endpoints": {
            "origin": "16181",
            "origin_label": "Ctrl Lib, Kent Ridge Cres",
            "destination": "28009",
            "destination_label": "Jurong East Int, Jurong Gateway Rd",
        },
    }
    OUTPUT.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    SOURCES.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(stops)} stops and {len(services)} services")


if __name__ == "__main__":
    main()

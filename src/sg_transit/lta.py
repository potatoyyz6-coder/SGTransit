from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BUS_ARRIVAL_ENDPOINT = (
    "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival"
)
DATAMALL_API_KEY_ENV = "LTA_DATAMALL_API_KEY"
LEGACY_API_KEY_ENV = "LTA_ACCOUNT_KEY"


class LTAApiError(RuntimeError):
    """Raised when the LTA Bus Arrival response is unavailable or invalid."""


@dataclass(frozen=True)
class BusArrival:
    service_no: str
    origin_code: str
    destination_code: str
    estimated_arrival: str
    monitored: bool | None
    latitude: float | None
    longitude: float | None
    visit_number: str
    load: str
    feature: str
    arrival_slot: str = ""


Transport = Callable[[str, Mapping[str, str], float], bytes]


def _urlopen_transport(url: str, headers: Mapping[str, str], timeout: float) -> bytes:
    request = Request(url, headers=dict(headers), method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except OSError as exc:
        raise LTAApiError(f"LTA request failed: {exc}") from exc


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise LTAApiError(f"Invalid numeric arrival field: {value!r}") from exc


def _optional_bool(value: object) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    normalized = _text(value).strip().casefold()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise LTAApiError(f"Invalid monitored arrival field: {value!r}")


def _parse_arrival(service_no: object, payload: Mapping[str, object], slot: str = "") -> BusArrival:
    return BusArrival(
        service_no=_text(service_no),
        origin_code=_text(payload.get("OriginCode")),
        destination_code=_text(payload.get("DestinationCode")),
        estimated_arrival=_text(payload.get("EstimatedArrival")),
        monitored=_optional_bool(payload.get("Monitored")),
        latitude=_optional_float(payload.get("Latitude")),
        longitude=_optional_float(payload.get("Longitude")),
        visit_number=_text(payload.get("VisitNumber")),
        load=_text(payload.get("Load")),
        feature=_text(payload.get("Feature")),
        arrival_slot=slot,
    )


def parse_bus_arrival_response(document: Mapping[str, object]) -> list[BusArrival]:
    """Normalize an LTA BusArrival v3 response into flat arrival records."""
    services = document.get("Services")
    if not isinstance(services, list):
        raise LTAApiError("LTA response does not contain a Services list")

    arrivals: list[BusArrival] = []
    for service in services:
        if not isinstance(service, Mapping):
            raise LTAApiError("LTA service entry is not an object")
        service_no = service.get("ServiceNo")
        for key in ("NextBus", "NextBus2", "NextBus3"):
            payload = service.get(key)
            if payload in (None, {}):
                continue
            if not isinstance(payload, Mapping):
                raise LTAApiError(f"LTA field {key} is not an object")
            arrivals.append(_parse_arrival(service_no, payload, key))
    return arrivals


class LTABusArrivalProvider:
    """Small dependency-injectable client for LTA DataMall BusArrival v3."""

    def __init__(
        self,
        account_key: str,
        *,
        endpoint: str = DEFAULT_BUS_ARRIVAL_ENDPOINT,
        transport: Transport = _urlopen_transport,
        timeout: float = 10.0,
    ) -> None:
        if not account_key.strip():
            raise ValueError("An LTA AccountKey is required")
        if not endpoint.startswith("https://"):
            raise ValueError("LTA endpoint must use HTTPS")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.account_key = account_key
        self.endpoint = endpoint
        self.transport = transport
        self.timeout = timeout

    def fetch(self, bus_stop_code: str, service_no: str | None = None) -> list[BusArrival]:
        code = str(bus_stop_code).strip()
        if not code:
            raise ValueError("bus_stop_code must not be empty")
        query = {"BusStopCode": code}
        if service_no is not None and str(service_no).strip():
            query["ServiceNo"] = str(service_no).strip()
        url = f"{self.endpoint}?{urlencode(query)}"
        headers = {"AccountKey": self.account_key, "Accept": "application/json"}
        try:
            raw = self.transport(url, headers, self.timeout)
            document = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except LTAApiError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise LTAApiError(f"Invalid LTA response: {exc}") from exc
        if not isinstance(document, Mapping):
            raise LTAApiError("LTA response is not a JSON object")
        return parse_bus_arrival_response(document)


def collect_bus_arrivals(
    provider: LTABusArrivalProvider,
    bus_stop_codes: list[str] | tuple[str, ...],
    *,
    output_path: str | Path | None = None,
    collected_at: str | None = None,
) -> dict[str, object]:
    """Collect one snapshot for each stop and optionally persist it as JSON."""
    codes = [str(code).strip() for code in bus_stop_codes if str(code).strip()]
    if not codes:
        raise ValueError("At least one bus stop code is required")
    timestamp = collected_at or datetime.now(timezone.utc).isoformat()
    snapshot = {
        "schema_version": 1,
        "provider": "lta_datamall_bus_arrival_v3",
        "collected_at": timestamp,
        "endpoint": provider.endpoint,
        "bus_stops": [
            {
                "bus_stop_code": code,
                "arrivals": [asdict(arrival) for arrival in provider.fetch(code)],
            }
            for code in codes
        ],
    }
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return snapshot


def collect_bus_arrival_series(
    provider: LTABusArrivalProvider,
    bus_stop_codes: list[str] | tuple[str, ...],
    *,
    samples: int,
    interval_seconds: float,
    output_path: str | Path | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    collected_at_fn: Callable[[], str] | None = None,
) -> dict[str, object]:
    """Record repeated live snapshots for later headway calibration.

    A single ETA response cannot reconstruct a historical headway distribution.
    Keeping the raw sequence makes that later calibration possible without
    pretending that one live response is historical ground truth.
    """
    if not isinstance(samples, int) or samples < 1:
        raise ValueError("samples must be a positive integer")
    if not isinstance(interval_seconds, (int, float)) or interval_seconds < 0:
        raise ValueError("interval_seconds must be nonnegative")
    snapshots = []
    for index in range(samples):
        snapshots.append(
            collect_bus_arrivals(
                provider,
                bus_stop_codes,
                collected_at=collected_at_fn() if collected_at_fn else None,
            )
        )
        if index + 1 < samples and interval_seconds:
            sleep_fn(float(interval_seconds))
    document = {
        "schema_version": 2,
        "provider": provider.endpoint,
        "samples": samples,
        "interval_seconds": float(interval_seconds),
        "snapshots": snapshots,
    }
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return document


def provider_from_environment(
    *,
    endpoint: str = DEFAULT_BUS_ARRIVAL_ENDPOINT,
    timeout: float = 10.0,
) -> LTABusArrivalProvider:
    api_key = os.getenv(DATAMALL_API_KEY_ENV, "")
    if not api_key:
        if os.getenv(LEGACY_API_KEY_ENV, ""):
            raise ValueError(
                f"Set {DATAMALL_API_KEY_ENV} to the DataMall API Access Key "
                "from the first LTA email. The Extended OBU SDK Account Key "
                f"({LEGACY_API_KEY_ENV}) cannot authenticate DataMall APIs."
            )
        raise ValueError(
            f"Set {DATAMALL_API_KEY_ENV} before using the live LTA collector"
        )
    return LTABusArrivalProvider(api_key, endpoint=endpoint, timeout=timeout)

"""Bounded, paced official static-data snapshots; never persist request headers."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlencode

from .lta import LTAApiError, _urlopen_transport

BASE = "https://datamall2.mytransport.sg/ltaodataservice/"


def collect_static(account_key, dataset, output, *, transport=_urlopen_transport,
                   sleep_fn=time.sleep, interval=1.0, max_pages=100):
    if dataset not in {"BusRoutes", "BusStops"}:
        raise ValueError("Unsupported static dataset")
    if not account_key.strip() or interval < 1 or max_pages < 1:
        raise ValueError("Key and positive bounded collection parameters required")
    output = Path(output)
    if output.exists():
        raise ValueError("Refusing to overwrite an existing raw snapshot")
    endpoint = BASE + dataset
    headers = {"AccountKey": account_key, "Accept": "application/json"}
    started = datetime.now(timezone.utc).isoformat()
    rows, pages, fingerprints = [], [], set()
    for page in range(max_pages):
        if page:
            sleep_fn(interval)
        raw = transport(endpoint + "?" + urlencode({"$skip": page * 500}), headers, 20.0)
        try:
            document = json.loads(raw)
            values = document["value"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LTAApiError("Invalid static-data response") from exc
        if not isinstance(values, list) or len(values) > 500 or any(not isinstance(row, dict) for row in values):
            raise LTAApiError("Invalid static-data page")
        fingerprint = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
        if values and fingerprint in fingerprints:
            raise LTAApiError("Repeated page: pagination did not advance")
        fingerprints.add(fingerprint)
        pages.append({"skip": page * 500, "rows": len(values), "sha256": fingerprint,
                      "received_at": datetime.now(timezone.utc).isoformat()})
        rows.extend(values)
        if len(values) < 500:
            break
    else:
        raise LTAApiError("Static snapshot exceeded its page budget; no partial snapshot written")
    result = {
        "schema_version": 1, "data_kind": "official_lta_static_snapshot",
        "endpoint": endpoint, "collected_from": started,
        "collected_to": datetime.now(timezone.utc).isoformat(),
        "pagination": pages, "value": rows,
        "note": "Collection timestamp is not a guarantee of service validity on any future date.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result

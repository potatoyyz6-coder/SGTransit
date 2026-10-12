from __future__ import annotations

import json
from pathlib import Path

from .models import Stop, TransitNetwork, TransitService


def load_network(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    network = TransitNetwork(
        [Stop(str(s["id"]), s["name"], float(s.get("x", 0)), float(s.get("y", 0))) for s in data["stops"]],
        [TransitService(str(s["id"]), tuple(str(x) for x in s["stops"]), tuple(float(x) for x in s["ride_minutes"]), float(s["headway_minutes"]), float(s.get("delay_max_minutes", 0))) for s in data["services"]],
    )
    return network, data


def resolve_stop(network, name):
    if name in network.stops:
        return name
    candidates = [s.id for s in network.stops.values() if s.name.casefold() == name.casefold()]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError(f"No exact stop named {name!r}; use the stops command and select an ID")
    raise ValueError(f"Ambiguous stop name {name!r}; choose ID from {candidates}")

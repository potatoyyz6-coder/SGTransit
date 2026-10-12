"""Conservative causal associations of ETA entries, never authoritative bus IDs.

Only isolated candidate edges are accepted. Matching thresholds are explicit
heuristics, not fitted error distributions or calibrated confidence scores.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import math

import networkx as nx


def instant(value):
    value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        raise ValueError("Timezone offset required")
    return value


@dataclass(frozen=True)
class MatchParameters:
    cross_skew_seconds: float = 5.0
    cross_distance_m: float = 30.0
    temporal_gap_seconds: float = 90.0
    eta_drift_seconds: float = 120.0
    max_speed_kmh: float = 70.0
    position_slack_m: float = 30.0
    max_ride_seconds: float = 5400.0

    def __post_init__(self):
        if any(not math.isfinite(v) or v <= 0 for v in asdict(self).values()):
            raise ValueError("Matching thresholds must be finite and positive")


@dataclass(frozen=True)
class Entry:
    id: str
    stop: str
    service: str
    origin: str
    destination: str
    visit: str
    received: datetime
    eta: datetime
    latitude: float
    longitude: float
    slot: str

    @property
    def direction_key(self):
        return self.service, self.origin, self.destination, self.visit


def parse_entries(record, source_id):
    """Return usable monitored positions and rejection counts; no silent fallback."""
    received = instant(record["received_at"])
    entries, rejected = [], {}
    for index, arrival in enumerate(record.get("arrivals", [])):
        reason = None
        if arrival.get("monitored") is not True:
            reason = "not_monitored"
        try:
            lat, lon = float(arrival["latitude"]), float(arrival["longitude"])
            if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90
                    and -180 <= lon <= 180 and (lat != 0 or lon != 0)):
                reason = reason or "invalid_position"
        except (ValueError, TypeError, KeyError):
            reason = reason or "invalid_position"
            lat = lon = 0.0
        try:
            eta = instant(arrival["estimated_arrival"])
        except (ValueError, TypeError, KeyError):
            reason = reason or "invalid_eta"
            eta = received
        fields = [str(arrival.get(key) or "") for key in
                  ("service_no", "origin_code", "destination_code", "visit_number")]
        if not all(fields):
            reason = reason or "missing_direction_or_visit"
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        entries.append(Entry(f"{source_id}:{index}", record["bus_stop_code"], *fields,
                             received, eta, lat, lon, arrival.get("arrival_slot", "")))
    return entries, rejected


def distance_m(a, b):
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(b.longitude - a.longitude)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


def candidate(a, b, kind, parameters):
    if a.direction_key != b.direction_key:
        return None
    separation = distance_m(a, b)
    delta = (b.received - a.received).total_seconds()
    eta_delta = (b.eta - a.eta).total_seconds()
    if kind == "cross_stop":
        if (a.stop == b.stop or abs(delta) > parameters.cross_skew_seconds
                or separation > parameters.cross_distance_m
                or not 0 <= eta_delta <= parameters.max_ride_seconds):
            return None
    elif kind == "temporal":
        if (a.stop != b.stop or not 0 < delta <= parameters.temporal_gap_seconds
                or abs(eta_delta) > parameters.eta_drift_seconds
                or separation > parameters.max_speed_kmh / 3.6 * delta + parameters.position_slack_m):
            return None
    else:
        raise ValueError("Unknown association kind")
    return {"source": a.id, "target": b.id, "kind": kind,
            "available_at": max(a.received, b.received).isoformat(),
            "position_distance_m": separation, "snapshot_delta_seconds": delta,
            "eta_delta_seconds": eta_delta,
            "evidence": "unique_under_heuristic_gates_not_verified_identity"}


def associate(left, right, kind, parameters=MatchParameters()):
    graph = nx.Graph()
    for a in left:
        for b in right:
            edge = candidate(a, b, kind, parameters)
            if edge:
                graph.add_edge((0, a.id), (1, b.id), evidence=edge)
    accepted, ambiguous = [], []
    for component in nx.connected_components(graph):
        edges = [attr["evidence"] for _, _, attr in graph.subgraph(component).edges(data=True)]
        if len(component) == 2 and len(edges) == 1:
            accepted.extend(edges)
        else:
            ambiguous.extend(edges)
    return {"accepted": accepted, "ambiguous_candidates": ambiguous}


def build_associations(snapshots, directed_pairs, parameters=MatchParameters(), *, cutoff=None):
    """Process responses in receive order. Errors invalidate that stop's snapshot.

    directed_pairs contains statically verified (service, upstream, downstream).
    No links are retroactively reassigned on seeing a future response.
    """
    rows = sorted(snapshots, key=lambda item: (instant(item[1]["received_at"]), item[0]))
    latest, entries, accepted, ambiguous = {}, {}, {}, {}
    rejected = {}
    for source_id, record in rows:
        if cutoff is not None and instant(record["received_at"]) > cutoff:
            continue
        stop = record["bus_stop_code"]
        if record["status"] != "ok":
            latest.pop(stop, None)
            continue
        current, reasons = parse_entries(record, source_id)
        entries.update({entry.id: entry for entry in current})
        for reason, count in reasons.items():
            rejected[reason] = rejected.get(reason, 0) + count
        batches = []
        if stop in latest:
            batches.append(associate(latest[stop], current, "temporal", parameters))
        latest[stop] = current
        for service, upstream, downstream in directed_pairs:
            if stop not in (upstream, downstream) or upstream not in latest or downstream not in latest:
                continue
            batches.append(associate([e for e in latest[upstream] if e.service == service],
                                     [e for e in latest[downstream] if e.service == service],
                                     "cross_stop", parameters))
        for batch in batches:
            for row in batch["accepted"]:
                accepted[(row["kind"], row["source"], row["target"])] = row
            for row in batch["ambiguous_candidates"]:
                ambiguous[(row["kind"], row["source"], row["target"])] = row
    return {"entries": entries, "accepted": list(accepted.values()),
            "ambiguous_candidates": list(ambiguous.values()), "rejected_entries": rejected}


def serialize(result):
    return {**result, "entries": {
        key: {**asdict(entry), "received": entry.received.isoformat(), "eta": entry.eta.isoformat()}
        for key, entry in result["entries"].items()}}


def follow_temporal(result, anchor_id, cutoff):
    """Follow only directed temporal evidence available by cutoff, not slot rank.

    A terminal prediction is not an arrival event. Do not backdate its receipt
    to its ETA, even if that ETA is already in the past.
    """
    entries = result["entries"]
    anchor = entries[anchor_id]
    if anchor.received > cutoff:
        return {"status": "anchor_not_available", "entry_ids": []}
    successors, uncertain = {}, set()
    for edge in result["accepted"]:
        if edge["kind"] == "temporal" and instant(edge["available_at"]) <= cutoff:
            successors.setdefault(edge["source"], []).append(edge["target"])
    for edge in result["ambiguous_candidates"]:
        if edge["kind"] == "temporal" and instant(edge["available_at"]) <= cutoff:
            uncertain.add(edge["source"])
    trace, current = [anchor_id], anchor_id
    while True:
        choices = successors.get(current, [])
        if current in uncertain or len(choices) > 1:
            return {"status": "ambiguous", "entry_ids": trace}
        if not choices:
            return {"status": "no_successor_in_prefix", "entry_ids": trace}
        target = choices[0]
        if target in trace or entries[target].received <= entries[current].received:
            raise ValueError("Non-forward temporal evidence")
        trace.append(target)
        current = target

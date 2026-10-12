"""Offline forecast diagnostics; no arrival truth or calibrated probabilities."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
import math

from .eta_matching import instant


def snapshot_at(snapshots, stop, decision, freshness=90):
    eligible = [(instant(r["received_at"]), source, r) for source, r in snapshots
                if r["bus_stop_code"] == stop and instant(r["received_at"]) <= decision]
    if not eligible:
        return {"status": "missing", "source": None, "record": None}
    received, source, record = max(eligible, key=lambda item: (item[0], item[1]))
    age = (decision - received).total_seconds()
    status = "error" if record["status"] != "ok" else "stale" if age > freshness else "available"
    return {"status": status, "source": source, "age_seconds": age,
            "record": record if status == "available" else None}


def distribution(values):
    """Descriptive nearest-rank quantiles, not independent-sample estimates."""
    values = sorted(values)
    if not values:
        return {"count": 0, "mean": None, "p50": None, "p95": None, "min": None, "max": None}
    return {"count": len(values), "mean": sum(values) / len(values),
            "p50": values[math.ceil(len(values) * .5) - 1],
            "p95": values[math.ceil(len(values) * .95) - 1],
            "min": values[0], "max": values[-1]}


def revision_diagnostics(associations):
    groups, evidence = defaultdict(list), []
    for edge in associations["accepted"]:
        if edge["kind"] != "temporal":
            continue
        a, b = (associations["entries"][edge[k]] for k in ("source", "target"))
        delta = (b.eta - a.eta).total_seconds()
        groups[(a.stop, a.service)].append(delta)
        evidence.append({"stop": a.stop, "service": a.service, "source": a.id, "target": b.id,
                         "available_at": edge["available_at"], "revision_seconds": delta})
    return {"kind": "monitored_unique_temporal_links_only_not_forecast_error",
            "selection_warning": "Matching gates truncate revisions and exclude ambiguous/missing chains; not an error distribution.",
            "groups": [{"stop": s, "service": v, "signed_seconds": distribution(ds),
                        "absolute_seconds": distribution([abs(d) for d in ds]),
                        "later_over_30_seconds": sum(d > 30 for d in ds),
                        "earlier_over_30_seconds": sum(d < -30 for d in ds)}
                       for (s, v), ds in sorted(groups.items())], "evidence": evidence}


def waiting_probe(snapshots, stop, decision, services, *, monitored, buffer_seconds=180,
                  incoming_service=None):
    """Fixed-time probe or connection forecast within one response.

    An incoming-service probe uses the earliest future incoming ETA in this
    snapshot, not a vehicle matched to a passenger or an origin boarding.
    Missing future slots never imply a missed bus or an infinite wait.
    """
    if not math.isfinite(buffer_seconds) or buffer_seconds < 0:
        raise ValueError("Nonnegative finite buffer required")
    snap = snapshot_at(snapshots, stop, decision)
    result = {k: v for k, v in snap.items() if k != "record"}
    result.update(stop=stop, decision=decision.isoformat(), services=list(services),
                  monitored=monitored, buffer_seconds=buffer_seconds,
                  incoming_service=incoming_service, predicted_wait_minutes=None)
    if snap["record"] is None:
        return result
    arrivals = []
    for i, a in enumerate(snap["record"].get("arrivals", [])):
        if a.get("monitored") is not monitored:
            continue
        try:
            eta = instant(a["estimated_arrival"])
        except (KeyError, TypeError, ValueError):
            continue
        if eta >= decision:
            arrivals.append((eta, a["service_no"], i))
    available = decision
    if incoming_service is not None:
        incoming = [a for a in arrivals if a[1] == incoming_service]
        if not incoming:
            return {**result, "status": "no_incoming_prediction"}
        first = min(incoming)
        available = first[0]
        result["incoming_entry"] = f"{snap['source']}:{first[2]}"
        result["incoming_eta"] = available.isoformat()
    ready = available + timedelta(seconds=buffer_seconds)
    usable = [a for a in arrivals if a[1] in services and a[0] >= ready]
    result["ready_at"] = ready.isoformat()
    if not usable:
        return {**result, "status": "no_eligible_prediction"}
    eta, service, index = min(usable)
    return {**result, "status": "forecast_only", "selected_service": service,
            "selected_entry": f"{snap['source']}:{index}", "selected_eta": eta.isoformat(),
            "predicted_wait_minutes": (eta - available).total_seconds() / 60,
            "slack_after_buffer_minutes": (eta - ready).total_seconds() / 60}

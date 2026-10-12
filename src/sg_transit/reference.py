"""Static reference estimates and historical operating-window checks."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
import math

from .models import validate_route
from .routing import expected_time


def clock_minutes(value):
    text = str(value).replace(":", "")
    if len(text) != 4 or not text.isdigit():
        raise ValueError("Expected HHMM or HH:MM")
    hours, minutes = int(text[:2]), int(text[2:])
    if hours > 47 or minutes > 59:
        raise ValueError("Invalid service-day clock")
    return hours * 60 + minutes


def window_status(row, minute, day="weekday"):
    """Minute is relative to the start of the reference service day, not modulo 24h."""
    if day not in {"weekday", "saturday", "sunday"}:
        raise ValueError("Unknown day type")
    if not math.isfinite(minute) or minute < 0:
        raise ValueError("Invalid reference minute")
    prefix = {"weekday": "WD", "saturday": "SAT", "sunday": "SUN"}[day]
    first, last = row.get(prefix + "_FirstBus"), row.get(prefix + "_LastBus")
    if first == last == "-":
        return "not_operating"
    try:
        start, end = clock_minutes(first), clock_minutes(last)
    except ValueError:
        return "unknown"
    if end < start:
        end += 1440
    return "within_historical_window" if start <= minute <= end else "outside_historical_window"


def estimate(route, network, windows, parameters, *, departure=600, day="weekday", limited=()):
    validate_route(route, network)
    cursor, legs, reasons = departure, [], []
    for leg in route.legs:
        service = network.services[leg.service_id]
        board = cursor + leg.transfer_minutes + leg.wait_minutes
        delay = service.delay_max_minutes / 2
        status = window_status(windows.get(leg.service_id, {}).get(leg.board_stop, {}), board, day)
        if status != "within_historical_window":
            reasons.append(status)
        if leg.service_id in limited:
            reasons.append("limited_service_not_default")
        if legs and leg.transfer_minutes + leg.wait_minutes > parameters.max_transfer_gap:
            reasons.append("estimated_transfer_gap_exceeded")
        cursor = board + delay + leg.ride_minutes
        legs.append({**asdict(leg), "board_minute": board, "alight_minute": cursor,
                     "mean_boarding_delay_minutes": delay, "operating_status": status})
    duration = expected_time(route, network)
    if duration > parameters.max_trip_minutes:
        reasons.append("estimated_trip_limit_exceeded")
    if route.transfers > parameters.max_transfers:
        reasons.append("transfer_count_exceeded")
    if abs(cursor - departure - duration) > 1e-7:
        raise ValueError("Reference time accounting mismatch")
    return {"route": asdict(route), "services": list(route.services), "legs": legs,
            "estimated_total_minutes": duration, "ride_minutes": route.ride_minutes,
            "wait_minutes": route.scheduled_wait_minutes,
            "buffer_minutes": sum(l.transfer_minutes for l in route.legs),
            "delay_minutes": sum(l["mean_boarding_delay_minutes"] for l in legs),
            "transfers": route.transfers, "recommendable": not reasons,
            "exclusion_reasons": sorted(set(reasons)), "timing_source": "stationary_model_not_live"}


def shortlist(records, limit=8):
    """Select service families without deleting any underlying stop variants."""
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("Positive display limit required")
    families = defaultdict(list)
    for row in records:
        if row["recommendable"]:
            families[tuple(row["services"])].append(row)
    order = lambda r: (r["estimated_total_minutes"], r["transfers"], r["id"])
    representatives = [min(rows, key=order) for rows in families.values()]
    selections = []
    for label, key, amount in (
        ("estimated_fast", order, 4),
        ("few_transfers", lambda r: (r["transfers"], *order(r)), 2),
        ("less_wait", lambda r: (r["wait_minutes"], *order(r)), 2),
    ):
        selections.extend((r, label) for r in sorted(representatives, key=key)[:amount])
    selections.extend((r, "time_order_fill") for r in sorted(representatives, key=order))
    selected = {}
    for row, label in selections:
        key = tuple(row["services"])
        if key in selected:
            if label != "time_order_fill" and label not in selected[key]["selection_reasons"]:
                selected[key]["selection_reasons"].append(label)
        elif len(selected) < limit:
            selected[key] = {"representative_id": row["id"], "services": list(key),
                             "selection_reasons": [label],
                             "variant_ids": [v["id"] for v in sorted(families[key], key=order)]}
    return list(selected.values())

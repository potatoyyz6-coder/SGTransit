"""Conditional ETA-as-event replay, NOT observed passenger travel times.

Predicted arrivals drive virtual events only while their provisional vehicle
association stays continuous and fresh. Unknown outcomes are never imputed.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from .eta_matching import instant


@dataclass(frozen=True)
class Ride:
    service: str
    start: str
    end: str


@dataclass(frozen=True)
class Walk:
    start: str
    end: str
    minutes: float

    def __post_init__(self):
        if not math.isfinite(self.minutes) or self.minutes <= 0:
            raise ValueError("Walking time must be finite and positive")


@dataclass(frozen=True)
class ReplayLimits:
    freshness_seconds: float = 90
    transfer_seconds: float = 180
    max_transfer_seconds: float = 2700
    max_trip_seconds: float = 7200
    max_transfers: int = 5
    alight_shift_seconds: float = 0
    continuation_grace_seconds: float = 5
    long_wait_seconds: float = 600

    def __post_init__(self):
        if any(not math.isfinite(v) or v <= 0 for v in (
                self.freshness_seconds, self.max_transfer_seconds, self.max_trip_seconds)):
            raise ValueError("Time limits must be finite and positive")
        if not math.isfinite(self.transfer_seconds) or self.transfer_seconds < 0:
            raise ValueError("Transfer buffer must be finite and nonnegative")
        if not math.isfinite(self.alight_shift_seconds):
            raise ValueError("Alighting sensitivity shift must be finite")
        if not math.isfinite(self.continuation_grace_seconds) or self.continuation_grace_seconds < 0:
            raise ValueError("Continuation observation grace must be finite and nonnegative")
        if not math.isfinite(self.long_wait_seconds) or self.long_wait_seconds < 0:
            raise ValueError("Long-wait threshold must be finite and nonnegative")
        if not isinstance(self.max_transfers, int) or self.max_transfers < 0:
            raise ValueError("Transfer bound must be a nonnegative integer")


class Tape:
    def __init__(self, snapshots, associations):
        self.entries = associations["entries"]
        self.by_stop, self.cross, self.temporal, self.ambiguous = {}, {}, {}, {}
        self.records = dict(snapshots)
        self.temporal_parents, self.bridges = {}, {}
        for source_id, record in snapshots:
            self.by_stop.setdefault(record["bus_stop_code"], []).append(
                (instant(record["received_at"]), source_id, record["status"]))
        for stop, rows in self.by_stop.items():
            rows.sort()
        self.times = {stop: [row[0] for row in rows] for stop, rows in self.by_stop.items()}
        self.end = max(t for times in self.times.values() for t in times)
        for edge in associations["accepted"]:
            if edge["kind"] == "cross_stop":
                a, b = self.entries[edge["source"]], self.entries[edge["target"]]
                self.cross.setdefault((a.service, a.stop, b.stop), []).append(edge)
            else:
                self.temporal.setdefault(edge["source"], []).append(edge)
                self.temporal_parents.setdefault(edge["target"], []).append(edge)
        for edge in associations["ambiguous_candidates"]:
            if edge["kind"] == "temporal":
                self.ambiguous.setdefault(edge["source"], []).append(edge)

    def latest(self, stop, now):
        index = bisect_right(self.times.get(stop, []), now) - 1
        return self.by_stop[stop][index] if index >= 0 else None

    def next_update(self, stops, now):
        future = []
        for stop in stops:
            times = self.times.get(stop, [])
            index = bisect_right(times, now)
            if index < len(times):
                future.append(times[index])
        return min(future) if future else None

    def current(self, entry, now, freshness):
        row = self.latest(entry.stop, now)
        return (row is not None and row[2] == "ok" and row[1] == entry.id.rsplit(":", 1)[0]
                and 0 <= (now - entry.received).total_seconds() <= freshness)

    def options(self, action, now, ready, limits, onboard_entry=None):
        result = []
        if onboard_entry is not None:
            a = self.entries[onboard_entry]
            if not self.current(a, now, limits.freshness_seconds):
                return []
            ancestors, current = {onboard_entry}, onboard_entry
            while True:
                parents = [e for e in self.temporal_parents.get(current, [])
                           if instant(e["available_at"]) <= now]
                if len(parents) != 1:
                    break
                current = parents[0]["source"]
                if current in ancestors:
                    raise ValueError("Cyclic temporal lineage")
                ancestors.add(current)
            found = set()
            for edge in self.cross.get((action.service, action.start, action.end), []):
                if edge["source"] not in ancestors or instant(edge["available_at"]) > now:
                    continue
                linked, error = self.advance_entry(edge["target"], now)
                if error or linked in found:
                    continue
                b = self.entries[linked]
                if self.current(b, now, limits.freshness_seconds) and now >= ready and b.eta >= now:
                    found.add(linked)
                    self.bridges[(a.id, b.id)] = {"cross_source": edge["source"],
                        "cross_target": edge["target"], "cross_available_at": edge["available_at"],
                        "source_current": a.id, "target_current": b.id,
                        "available_at": now.isoformat(), "kind": "continuous_temporal_bridge"}
                    result.append((now, a, b))
            # Distinct surviving destination identities are uncertain, not choices
            # of a new bus while supposedly remaining on the same vehicle.
            return result if len(result) == 1 else []
        for edge in self.cross.get((action.service, action.start, action.end), []):
            if instant(edge["available_at"]) > now:
                continue
            a, b = self.entries[edge["source"]], self.entries[edge["target"]]
            if not all(self.current(e, now, limits.freshness_seconds) for e in (a, b)):
                continue
            if onboard_entry is not None and a.id != onboard_entry:
                continue
            board = now if onboard_entry is not None else a.eta
            if board < ready or b.eta < board:
                continue
            result.append((board, a, b))
        return result

    def local_departures(self, action, now, ready, limits):
        row = self.latest(action.start, now)
        if row is None or row[2] != "ok" or (now - row[0]).total_seconds() > limits.freshness_seconds:
            return []
        results = []
        for index, arrival in enumerate(self.records[row[1]].get("arrivals", [])):
            if arrival.get("service_no") != action.service:
                continue
            try:
                eta = instant(arrival["estimated_arrival"])
            except (ValueError, TypeError, KeyError):
                continue
            if eta >= ready:
                results.append((eta, f"{row[1]}:{index}"))
        return results

    def advance_entry(self, entry_id, now):
        current = entry_id
        seen = {current}
        while True:
            ambiguous = [e for e in self.ambiguous.get(current, []) if instant(e["available_at"]) <= now]
            following = [e for e in self.temporal.get(current, []) if instant(e["available_at"]) <= now]
            if ambiguous or len(following) > 1:
                return None, "ambiguous_identity"
            if not following:
                return current, None
            current = following[0]["target"]
            if current in seen:
                raise ValueError("Cyclic temporal evidence")
            seen.add(current)

    def ride(self, entry_id, board, deadline, limits):
        now, current, trace = board, entry_id, []
        while now <= deadline:
            current, reason = self.advance_entry(current, now)
            if reason:
                return None, current, trace, reason
            entry = self.entries[current]
            if not trace or trace[-1] != current:
                trace.append(current)
            if not self.current(entry, now, limits.freshness_seconds):
                return None, current, trace, "missing_or_stale_vehicle"
            due = max(now, entry.eta + timedelta(seconds=limits.alight_shift_seconds))
            change = self.next_update([entry.stop], now)
            expiry = entry.received + timedelta(seconds=limits.freshness_seconds)
            if due <= min(deadline, self.end, expiry) and (change is None or due < change):
                return due, current, trace, None
            if change is None or change > min(deadline, self.end, expiry):
                return None, current, trace, "censored_or_stale_vehicle"
            now = change
        return None, current, trace, "trip_limit"


def replay(tape, paths, departure, *, limits=ReplayLimits(), selector=None):
    """First-eligible strategy over explicit directed paths, with live ETA updates.

    Static topology is validated by the caller. Ties use action labels, never
    downstream realized outcomes. The engine only simulates one departure.
    """
    if not paths or any(not path for path in paths):
        raise ValueError("At least one nonempty path is required")
    endpoints = {(path[0].start, path[-1].end) for path in paths}
    if len(endpoints) != 1:
        raise ValueError("Paths must have common endpoints")
    for path in paths:
        if any(a.end != b.start for a, b in zip(path, path[1:])):
            raise ValueError("Disconnected path")
    origin, destination = endpoints.pop()
    now, stop, remaining = departure, origin, [tuple(path) for path in paths]
    deadline = departure + timedelta(seconds=limits.max_trip_seconds)
    onboard, anchor, alighted = None, None, None
    used, visited, events, waits = set(), {origin}, [], []
    decisions = []
    walk_seconds = ride_seconds = 0.0

    def finish(status):
        complete = status == "modeled_complete"
        transfer_waits = [e["transfer_wait_seconds"] for e in events
                          if e["kind"] == "modeled_board" and e["transfer_wait_seconds"] > 0]
        return {"status": status, "actual_outcome": "unknown",
                "event_model": "ETA_as_event_with_provisional_association",
                "departure": departure.isoformat(), "arrival": now.isoformat() if complete else None,
                "duration_minutes": (now - departure).total_seconds() / 60 if complete else None,
                "prefix_wait_minutes": sum(waits) / 60, "prefix_walk_minutes": walk_seconds / 60,
                "prefix_ride_minutes": ride_seconds / 60, "transfer_count": max(0, len(used) - 1),
                "max_transfer_wait_minutes": max(transfer_waits, default=0) / 60 if complete else None,
                "long_wait_threshold_minutes": limits.long_wait_seconds / 60,
                "long_transfer_wait": any(w > limits.long_wait_seconds for w in transfer_waits) if complete else None,
                "long_transfer_wait_over_10min": any(e.get("transfer_wait_seconds", 0) > 600 for e in events)
                if complete else None, "events": events, "decisions": decisions}

    for _ in range(10000):
        if stop == destination:
            return finish("modeled_complete")
        actions = list(dict.fromkeys(path[0] for path in remaining))
        walking = [a for a in actions if isinstance(a, Walk)]
        if walking:
            if len(actions) != 1:
                raise ValueError("Walking choices must be explicit, not mixed with boarding choices")
            action = walking[0]
            if action.end in visited:
                return finish("cycle_rejected")
            end = now + timedelta(minutes=action.minutes)
            if end > min(deadline, tape.end):
                return finish("walk_censored_or_trip_limit")
            events.append({"kind": "modeled_walk", "start": stop, "end": action.end,
                           "started_at": now.isoformat(), "ended_at": end.isoformat()})
            walk_seconds += action.minutes * 60
            now, stop, onboard, anchor = end, action.end, None, None
            visited.add(stop)
            remaining = [path[1:] for path in remaining]
            continue
        wait_start = now
        if onboard is not None and not any(a.service == onboard for a in actions):
            onboard, anchor = None, None
        chosen = None
        pending = None
        while now <= min(deadline, tape.end):
            if pending is not None:
                # A forecast moving behind the next poll leaves boarding uncertain;
                # it is not permission to silently skip to a later bus.
                tracked, reason = tape.advance_entry(pending, now)
                if reason:
                    return finish("boarding_identity_ambiguous")
                if tracked == pending and not tape.current(tape.entries[tracked], now, limits.freshness_seconds):
                    return finish("boarding_identity_lost")
                if tape.entries[tracked].eta < now:
                    return finish("boarding_between_polls_unknown")
                pending = tracked
            candidates = []
            for action in actions:
                if action.end in visited:
                    continue
                continuing = onboard == action.service
                if not continuing and (action.service in used or len(used) >= limits.max_transfers + 1):
                    continue
                ready = now if continuing else max(now, wait_start + timedelta(
                    seconds=limits.transfer_seconds if used else 0))
                current_anchor = None
                if continuing:
                    current_anchor, error = tape.advance_entry(anchor, now)
                    if error:
                        return finish(error)
                matched = tape.options(action, now, ready, limits, current_anchor)
                for board, a, b in matched:
                    if used and not continuing and alighted is not None and (
                            board - alighted).total_seconds() > limits.max_transfer_seconds:
                        continue
                    candidates.append((board, action.service, action.end, action, a, b, continuing))
                if not continuing:
                    matched_ids = {a.id for _, a, _ in matched}
                    for board, entry_id in tape.local_departures(action, now, ready, limits):
                        if entry_id not in matched_ids:
                            if used and alighted is not None and (board - alighted).total_seconds() > limits.max_transfer_seconds:
                                continue
                            candidates.append((board, action.service, action.end, action, None, None, False))
            if onboard and any(a.service == onboard for a in actions) and not any(c[6] for c in candidates):
                change = tape.next_update({s for a in actions for s in (a.start, a.end)}, now)
                grace_end = wait_start + timedelta(seconds=limits.continuation_grace_seconds)
                if change is not None and change <= min(grace_end, deadline, tape.end):
                    now = change
                    continue
                return finish("onboard_continuation_unknown")
            if candidates:
                if selector is None:
                    chosen = min(candidates, key=lambda x: (*x[:3], x[4] is not None))
                else:
                    chosen, detail = selector.choose(candidates, stop=stop, now=now,
                        departure=departure, onboard=onboard, used=frozenset(used),
                        visited=frozenset(visited), alighted=alighted, limits=limits)
                    decisions.append(detail)
                    if chosen is None:
                        return finish("policy_no_feasible_action")
                relevant = {s for a in actions for s in (a.start, a.end)}
                change = tape.next_update(relevant, now)
                board = chosen[0]
                # New observations may revise or invalidate a not-yet-boarded vehicle.
                if change is not None and change <= board:
                    if not chosen[6]:
                        # Once waiting for another service, do not keep resetting
                        # the buffer as though still onboard at each ETA update.
                        onboard, anchor = None, None
                    pending = chosen[4].id if chosen[4] is not None else None
                    now = change
                    chosen = None
                    continue
                if board > min(deadline, tape.end):
                    return finish("boarding_censored_or_trip_limit")
                break
            if onboard and any(a.service == onboard for a in actions):
                return finish("onboard_continuation_unknown")
            if used and alighted is not None and (now - alighted).total_seconds() >= limits.max_transfer_seconds:
                return finish("transfer_window_exceeded")
            change = tape.next_update({s for a in actions for s in (a.start, a.end)}, now)
            if change is None:
                return finish("no_further_observations")
            now = change
        if chosen is None:
            return finish("observation_or_trip_limit")
        board, _, _, action, source, target, continuing = chosen
        if source is None or target is None:
            events.append({"kind": "unmatched_boarding_opportunity", "service": action.service,
                           "stop": stop, "predicted_at": board.isoformat(), "decision_at": now.isoformat()})
            return finish("earlier_boarding_without_cross_stop_evidence")
        if not all(tape.current(e, board, limits.freshness_seconds) for e in (source, target)):
            return finish("boarding_evidence_stale")
        if not continuing:
            waiting = (board - wait_start).total_seconds()
            waits.append(waiting)
            events.append({"kind": "modeled_board", "service": action.service, "stop": stop,
                           "at": board.isoformat(), "evidence_received_at": max(source.received, target.received).isoformat(),
                           "source_entry": source.id, "target_entry": target.id,
                           "wait_seconds": waiting, "transfer_wait_seconds": waiting if used else 0})
            used.add(action.service)
        else:
            ride_seconds += (board - wait_start).total_seconds()
            events.append({"kind": "stay_onboard", "service": action.service, "stop": stop,
                           "at": board.isoformat(), "source_entry": source.id, "target_entry": target.id,
                           "observation_hold_seconds": (board - wait_start).total_seconds(),
                           "association_bridge": tape.bridges.get((source.id, target.id))})
        arrival, final_anchor, trace, error = tape.ride(target.id, board, deadline, limits)
        if error:
            events.append({"kind": "unknown_ride", "service": action.service, "reason": error,
                           "trace_entry_ids": trace})
            return finish(error)
        ride_seconds += (arrival - board).total_seconds()
        events.append({"kind": "modeled_arrival", "service": action.service, "stop": action.end,
                       "at": arrival.isoformat(), "trace_entry_ids": trace})
        now, stop, onboard, anchor, alighted = arrival, action.end, action.service, final_anchor, arrival
        visited.add(stop)
        remaining = [path[1:] for path in remaining if path[0] == action]
    return finish("event_budget_exceeded")

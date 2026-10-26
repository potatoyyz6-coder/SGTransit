"""Import declared directed patterns without erasing source stop events.

The current routing model cannot represent repeated visits. Such patterns stay
in the event inventory with a coverage gap, never split into fictitious buses.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math

from .models import Stop, TransitNetwork, TransitService
from .station_catalog import CatalogStop


@dataclass(frozen=True)
class StopEvent:
    service: str
    direction: str
    sequence: int
    stop: str
    visit: int
    distance_km: float
    window: tuple[tuple[str, str], ...]


@dataclass
class DirectedImport:
    network: TransitNetwork
    windows: dict
    events: dict[str, tuple[StopEvent, ...]]
    source_patterns: dict
    gaps: list[dict]


def import_patterns(stop_rows, route_rows, requested, *, speed_kmh=20, headway=15, delay_max=3):
    for value, positive in ((speed_kmh, True), (headway, True), (delay_max, False)):
        if isinstance(value, bool) or not math.isfinite(value) or value < 0 or positive and value == 0:
            raise ValueError('Invalid timing assumption')
    requested = list(requested)
    if not requested or len(set(requested)) != len(requested):
        raise ValueError('Choose unique service/direction patterns')
    if any(len(p) != 2 or not all(isinstance(x, str) and x for x in p) for p in requested):
        raise ValueError('Use (service, direction) string pairs')
    stops = {}
    for row in stop_rows:
        record = CatalogStop(row['BusStopCode'], row['Description'], float(row['Longitude']), float(row['Latitude']))
        if record.id in stops:
            raise ValueError('Duplicate source stop ID')
        stops[record.id] = Stop(record.id, record.name, record.longitude, record.latitude)
    grouped = defaultdict(list)
    for row in route_rows:
        pair = (row['ServiceNo'], row['Direction'])
        if pair in requested:
            grouped[pair].append(dict(row))
    services, windows, events, patterns, gaps = [], {}, {}, {}, []
    for number, direction in sorted(requested):
        key = f'{number}-D{direction}'
        rows = sorted(grouped[(number, direction)], key=lambda r: int(r['StopSequence']))
        if not rows:
            gaps.append(dict(service=key, reason='pattern_missing', event_count=0))
            events[key] = ()
            continue
        sequence = [int(r['StopSequence']) for r in rows]
        if len(set(sequence)) != len(sequence) or sequence[0] < 1:
            raise ValueError(f'Ambiguous stop sequence: {key}')
        distances = [float(r['Distance']) for r in rows]
        if any(not math.isfinite(d) or d < 0 for d in distances) or any(b < a for a, b in zip(distances, distances[1:])):
            raise ValueError(f'Invalid cumulative distance: {key}')
        visits, items = defaultdict(int), []
        for row, seq, distance in zip(rows, sequence, distances):
            stop = row['BusStopCode']
            if stop not in stops:
                raise ValueError(f'Unknown source stop: {stop}')
            visits[stop] += 1
            items.append(StopEvent(number, direction, seq, stop, visits[stop], distance,
                         tuple(sorted((k, v) for k, v in row.items() if k.endswith(('_FirstBus','_LastBus'))))))
        events[key] = tuple(items)
        patterns[key] = dict(service_no=number, direction=direction, ordered_source_rows=rows)
        reason = ('missing_intermediate_sequence' if any(b != a+1 for a, b in zip(sequence, sequence[1:]))
                  else 'repeated_stop_events_not_supported' if max(visits.values()) > 1
                  else 'too_few_events' if len(rows) < 2 else None)
        if reason:
            gaps.append(dict(service=key, reason=reason, event_count=len(items)))
            continue
        services.append(TransitService(key, tuple(e.stop for e in items),
                        tuple(max(.5, (b-a)*60/speed_kmh) for a,b in zip(distances, distances[1:])),
                        headway, delay_max))
        windows[key] = {event.stop: dict(event.window) for event in items}
    used = {stop for service in services for stop in service.stops}
    return DirectedImport(TransitNetwork([stops[s] for s in sorted(used)], services), windows,
                          events, patterns, gaps)

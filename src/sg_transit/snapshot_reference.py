"""Departure-time references from frozen forecasts, never retrospective trip truth."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta, timezone
import math

from .eta_diagnostics import snapshot_at
from .eta_matching import instant
from .models import Route, validate_route
from .reference import estimate

SGT = timezone(timedelta(hours=8))


def pattern_bindings(patterns, source_rows):
    """Bind a directed fragment to full-route endpoints and stop visit ordinal."""
    result = {}
    for key, pattern in patterns.items():
        full = sorted((r for r in source_rows if r['ServiceNo'] == pattern['service_no']
                       and r['Direction'] == pattern['direction']), key=lambda r: int(r['StopSequence']))
        if not full or len({r['StopSequence'] for r in full}) != len(full):
            raise ValueError('Ambiguous full service pattern')
        visits, by_sequence = {}, {}
        for row in full:
            stop = row['BusStopCode']
            visits[stop] = visits.get(stop, 0) + 1
            by_sequence[row['StopSequence']] = (stop, str(visits[stop]))
        result[key] = {}
        for row in pattern['ordered_source_rows']:
            stop, visit = by_sequence[row['StopSequence']]
            if stop != row['BusStopCode']:
                raise ValueError('Fragment and full pattern disagree')
            result[key][stop] = dict(service_no=pattern['service_no'],
                origin_code=full[0]['BusStopCode'], destination_code=full[-1]['BusStopCode'], visit_number=visit)
    return result


class FrozenForecasts:
    def __init__(self, snapshots, decision, bindings, *, freshness=90):
        if decision.tzinfo is None or not math.isfinite(freshness) or freshness < 0:
            raise ValueError('Aware decision time and nonnegative freshness required')
        self.decision, self.bindings = decision.astimezone(SGT), bindings
        self.midnight = self.decision.replace(hour=0, minute=0, second=0, microsecond=0)
        self.departure = self.minute(self.decision)
        self.day = ('saturday' if self.decision.weekday() == 5 else
                    'sunday' if self.decision.weekday() == 6 else 'weekday')
        self.snapshots = {stop: snapshot_at(snapshots, stop, decision, freshness)
                          for stop in {r['bus_stop_code'] for _, r in snapshots}}

    def minute(self, value):
        return (value - self.midnight).total_seconds() / 60

    def timestamp(self, minute):
        return (self.midnight + timedelta(minutes=minute)).isoformat()

    def boarding(self, service_id, stop, ready, mean_wait):
        """Freshness is assessed at query time, not a simulated future stop visit."""
        if not math.isfinite(ready) or ready < self.departure or not math.isfinite(mean_wait) or mean_wait < 0:
            raise ValueError('Invalid readiness or mean wait')
        snap = self.snapshots.get(stop, {'status': 'missing', 'record': None, 'source': None})
        base = dict(timing_source='modeled_wait', snapshot_status=snap['status'],
                    snapshot_source=snap['source'], snapshot_age_seconds=snap.get('age_seconds'),
                    ready_at=self.timestamp(ready), selected_entry=None, monitored=None,
                    forecast_at=None, forecast_horizon_at=None)
        fallback = snap['status']
        binding = self.bindings.get(service_id, {}).get(stop)
        if snap['record'] is not None and binding:
            matching, usable_service_entries = [], 0
            for index, arrival in enumerate(snap['record'].get('arrivals', [])):
                if arrival.get('service_no') != binding['service_no']:
                    continue
                usable_service_entries += 1
                if any(arrival.get(k) != v for k, v in binding.items()):
                    continue
                try:
                    eta = instant(arrival['estimated_arrival'])
                except (KeyError, TypeError, ValueError):
                    continue
                matching.append((self.minute(eta), index, arrival))
            future = [item for item in matching if item[0] >= self.departure]
            base['forecast_horizon_at'] = self.timestamp(max(x[0] for x in future)) if future else None
            eligible = [item for item in future if item[0] >= ready]
            if eligible:
                minute, index, arrival = min(eligible, key=lambda item: (item[0], item[1]))
                return {**base, 'timing_source': 'snapshot_eta', 'fallback_reason': None,
                        'board_minute': minute, 'wait_minutes': minute-ready,
                        'selected_entry': f"{snap['source']}:{index}", 'monitored': arrival.get('monitored'),
                        'forecast_at': self.timestamp(minute)}
            fallback = ('beyond_forecast_horizon' if future else 'no_future_matching_prediction'
                        if matching else 'unusable_or_pattern_mismatch' if usable_service_entries else 'service_missing')
        elif snap['record'] is not None:
            fallback = 'unverified_pattern_binding'
        return {**base, 'fallback_reason': fallback, 'board_minute': ready+mean_wait,
                'wait_minutes': mean_wait}


def snapshot_estimate(route, network, windows, parameters, forecasts, *, limited=()):
    validate_route(route, network)
    if route.walk_minutes:
        raise ValueError('This same-stop reference does not support access walking')
    cursor, legs, evidence = forecasts.departure, [], []
    for leg in route.legs:
        service = network.services[leg.service_id]
        choice = forecasts.boarding(service.id, leg.board_stop, cursor+leg.transfer_minutes,
                                    service.headway_minutes/2)
        legs.append(replace(leg, wait_minutes=choice['wait_minutes']))
        evidence.append(choice)
        cursor = choice['board_minute'] + service.delay_max_minutes/2 + leg.ride_minutes
    conditioned = Route(route.origin, route.destination, legs)
    result = estimate(conditioned, network, windows, parameters, departure=forecasts.departure,
                      day=forecasts.day, limited=limited)
    for leg, item in zip(result['legs'], evidence):
        leg.update(item, board_at=forecasts.timestamp(leg['board_minute']),
                   alight_at=forecasts.timestamp(leg['alight_minute']))
    baseline = estimate(route, network, windows, parameters, departure=forecasts.departure,
                        day=forecasts.day, limited=limited)
    count = sum(e['timing_source'] == 'snapshot_eta' for e in evidence)
    result.update(timing_source='historical_snapshot_conditioned_model',
                  snapshot_boardings=count, modeled_boardings=len(legs)-count,
                  unmonitored_snapshot_boardings=sum(e['timing_source'] == 'snapshot_eta' and e['monitored'] is not True for e in evidence),
                  model_only_total_minutes=baseline['estimated_total_minutes'],
                  difference_from_model_minutes=result['estimated_total_minutes']-baseline['estimated_total_minutes'],
                  estimated_arrival_at=forecasts.timestamp(cursor),
                  availability='unknown_where_modeled' if count < len(legs) else 'forecast_only_not_confirmed')
    return result


def projected_choices(records, network, reference_ids):
    """Compare all eligible candidates sharing the same travelled adjacent arcs.

    A route's long leg expands only for structural matching. Its time estimate
    remains one boarding, so staying on the bus does not incur another wait.
    """
    lookup, histories = {r['id']: r for r in records}, {}
    for row in records:
        if not row['recommendable']:
            continue
        arcs = []
        for index, leg in enumerate(row['legs']):
            stops = network.services[leg['service_id']].stops
            a, b = stops.index(leg['board_stop']), stops.index(leg['alight_stop'])
            arcs.extend((leg['service_id'], x, y, index) for x, y in zip(stops[a:b], stops[a+1:b+1]))
        history = []
        for service, start, end, index in arcs:
            if history:
                histories.setdefault(tuple(history), []).append((row['id'], service, index))
            history.append((service, start, end))
    result = []
    for identifier in dict.fromkeys(reference_ids):
        row, history = lookup[identifier], []
        for leg in row['legs']:
            service = network.services[leg['service_id']]
            a, b = service.stops.index(leg['board_stop']), service.stops.index(leg['alight_stop'])
            for start, end in zip(service.stops[a:b], service.stops[a+1:b+1]):
                history.append((service.id, start, end))
                options = {}
                for other_id, next_service, index in histories.get(tuple(history), []):
                    other = lookup[other_id]
                    current = options.get(next_service)
                    if current is None or (other['estimated_total_minutes'], other_id) < (current['total_minutes'], current['candidate_id']):
                        continuing = next_service == service.id
                        next_leg = other['legs'][index]
                        options[next_service] = dict(service=next_service, continuing=continuing,
                            candidate_id=other_id, total_minutes=other['estimated_total_minutes'],
                            new_transfer=not continuing,
                            wait_including_buffer_minutes=0 if continuing else next_leg['wait_minutes']+next_leg['transfer_minutes'],
                            new_boarding_delay_minutes=0 if continuing else next_leg['mean_boarding_delay_minutes'],
                            timing_source='same_vehicle_continuation' if continuing else next_leg['timing_source'])
                if len(options) > 1:
                    result.append(dict(reference_id=identifier, stop=end, onboard=service.id,
                        alternatives=sorted(options.values(), key=lambda o: (o['total_minutes'], o['service']))))
    return result

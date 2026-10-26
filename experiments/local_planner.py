"""In-memory, personal-use adapter around the existing research route models."""
from __future__ import annotations

from collections import Counter, OrderedDict
from copy import copy
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import secrets
import time

from data.real.build_subset import RAW, load_rows, select_pattern
from experiments.blk18_cde_case import ROOT, Settings, build_network, LIMITED
from experiments.blk18_snapshot_reference import INPUT, load_snapshot
from experiments.pei_hwa_case import SEGMENTS as HOME_SEGMENTS
from sg_transit.lta import DATAMALL_API_KEY_ENV, provider_from_environment
from sg_transit.corridors import CorridorParameters, DestinationIndex, discover_candidates
from sg_transit.models import Leg, Route, Stop, TransitNetwork, TransitService
from sg_transit.reference import shortlist, window_status
from sg_transit.routing import SearchBudgetExceeded, enumerate_routes, route_key
from sg_transit.snapshot_reference import SGT, FrozenForecasts, pattern_bindings, snapshot_estimate

CASES = {
    'school': {'label': 'Blk 18 → CDE', 'origin': '42161', 'destination': '16159'},
    'home': {'label': 'Information Technology → Signature Pk', 'origin': '16189', 'destination': '42171'},
}


class UserError(Exception):
    def __init__(self, message, status=400, code='invalid_request'):
        super().__init__(message)
        self.status = status
        self.code = code


@lru_cache(maxsize=2)
def network_data(case):
    """Load declared topology independently of query endpoints and preferences."""
    if case not in CASES:
        raise UserError('案例或换乘缓冲无效。')
    settings = Settings()
    network, windows, patterns, source = build_network(settings)
    full = load_rows(RAW / 'BusRoutes.csv')
    if case == 'home':
        stops = {r['BusStopCode']: r for r in load_rows(RAW / 'BusStops.csv')}
        services, windows, patterns = [], {}, {}
        for number, direction, start, end in HOME_SEGMENTS:
            rows = select_pattern(full, number, direction, start, end)
            key = f'{number}-D{direction}'
            distances = [float(r['Distance']) for r in rows]
            if any(b < a for a, b in zip(distances, distances[1:])):
                raise ValueError('Invalid source distances')
            services.append(TransitService(key, tuple(r['BusStopCode'] for r in rows),
                tuple(max(.5, (b-a)*3) for a, b in zip(distances, distances[1:])), 15, 3))
            windows[key] = {r['BusStopCode']: {k: v for k, v in r.items() if k.endswith(('_FirstBus', '_LastBus'))} for r in rows}
            patterns[key] = dict(service_no=number, direction=direction, ordered_source_rows=rows)
        codes = sorted({s for v in services for s in v.stops})
        network = TransitNetwork([Stop(s, stops[s]['Description'], float(stops[s]['Longitude']),
                                       float(stops[s]['Latitude'])) for s in codes], services)
        source = {**source, 'scope': 'Ten directed Information Technology / Pei Hwa / Signature Pk fragments; not all services or cross-stop walking'}
    payload = dict(stops=[asdict(s) for s in network.stops.values()],
                   services=[asdict(s) for s in network.services.values()], windows=windows,
                   source=source)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return network, windows, pattern_bindings(patterns, full), {**source, 'network_sha256': digest}


@lru_cache(maxsize=8)
def case_data(case, buffer):
    if case not in CASES or buffer not in (1, 2, 3, 4, 5):
        raise UserError('案例或换乘缓冲无效。')
    network, windows, bindings, source = network_data(case)
    parameters = Settings(transfer_buffer=buffer).routing()
    stats = {}
    if case == 'home':
        search = discover_candidates(DestinationIndex(network, CASES[case]['destination']),
            CASES[case]['origin'], parameters,
            CorridorParameters(max_hubs=6, ordinary_candidates=30, prefixes_per_hub=8, bypass_candidates=4))
        routes = sorted(search.routes, key=route_key)
        stats = dict(candidates=len(routes), expansions=search.expansions,
                     complete=False, method='bounded_corridor', reasons=search.truncation_reasons)
    else:
        routes = enumerate_routes(network, CASES[case]['origin'], CASES[case]['destination'], parameters, stats=stats)
        stats.update(complete=True, method='enumeration_within_declared_bounds')
    return network, windows, bindings, source, parameters, routes, stats


def expanded(route, network):
    arcs = []
    for leg in route.legs:
        service = network.services[leg.service_id]
        a, b = service.stops.index(leg.board_stop), service.stops.index(leg.alight_stop)
        arcs.extend((service.id, x, y) for x, y in zip(service.stops[a:b], service.stops[a+1:b+1]))
    return arcs


def suffix_route(arcs, origin, destination, network, buffer):
    groups = []
    for service, start, end in arcs:
        if groups and groups[-1][0] == service:
            groups[-1][2] = end
        else:
            groups.append([service, start, end])
    return Route(origin, destination, [Leg(s, a, b, network.services[s].ride_time(a, b),
                network.services[s].headway_minutes/2, buffer) for s, a, b in groups])


def remaining_estimate(route, data, forecasts, used, onboard, started, alighted):
    network, windows, _, _, p, _, _ = data
    cursor, legs, reasons = forecasts.departure, [], []
    new_boardings = 0
    for i, leg in enumerate(route.legs):
        service = network.services[leg.service_id]
        continuing = i == 0 and leg.service_id == onboard
        if continuing:
            choice = dict(board_minute=cursor, wait_minutes=0, timing_source='same_vehicle_continuation',
                          monitored=None, fallback_reason=None, ready_at=forecasts.timestamp(cursor))
            buffer, delay, status = 0, 0, 'already_onboard_user_input'
        else:
            buffer = max(0, alighted + p.transfer_walk_minutes - cursor) if i == 0 else p.transfer_walk_minutes
            choice = forecasts.boarding(service.id, leg.board_stop, cursor+buffer, service.headway_minutes/2)
            delay = service.delay_max_minutes/2
            status = window_status(windows.get(service.id, {}).get(leg.board_stop, {}), choice['board_minute'], forecasts.day)
            if status != 'within_historical_window':
                reasons.append(status)
            gap_start = alighted if i == 0 else cursor
            if choice['board_minute'] - gap_start > p.max_transfer_gap:
                reasons.append('estimated_transfer_gap_exceeded')
            new_boardings += 1
        if service.id in LIMITED:
            reasons.append('limited_service_not_default')
        cursor = choice['board_minute'] + delay + leg.ride_minutes
        legs.append({**asdict(leg), **choice, 'transfer_minutes': buffer,
            'mean_boarding_delay_minutes': delay, 'operating_status': status,
            'board_at': forecasts.timestamp(choice['board_minute']), 'alight_at': forecasts.timestamp(cursor),
            'alight_minute': cursor})
    prior_transfers = max(0, len(used)-1)
    if prior_transfers + new_boardings > p.max_transfers:
        reasons.append('transfer_count_exceeded')
    duration = cursor - forecasts.departure
    if (forecasts.decision-started).total_seconds()/60 + duration > p.max_trip_minutes:
        reasons.append('estimated_trip_limit_exceeded')
    return dict(route=asdict(route), services=list(route.services), legs=legs, transfers=new_boardings,
        trip_transfers=prior_transfers+new_boardings, estimated_total_minutes=duration,
        ride_minutes=route.ride_minutes, wait_minutes=sum(l['wait_minutes'] for l in legs),
        buffer_minutes=sum(l['transfer_minutes'] for l in legs),
        delay_minutes=sum(l['mean_boarding_delay_minutes'] for l in legs),
        estimated_arrival_at=forecasts.timestamp(cursor), recommendable=not reasons,
        exclusion_reasons=sorted(set(reasons)), snapshot_boardings=sum(l['timing_source']=='snapshot_eta' for l in legs),
        modeled_boardings=sum(l['timing_source']=='modeled_wait' for l in legs))


class LocalPlanner:
    def __init__(self, *, now=lambda: datetime.now(SGT), provider_factory=None,
                 raw_dir=ROOT/'data/recorded/raw/local_ui', saved_snapshot=INPUT,
                 clock=time.monotonic):
        self.now, self.clock = now, clock
        self.provider_factory = provider_factory or (lambda: provider_from_environment(timeout=6))
        self.raw_dir, self.saved_snapshot = Path(raw_dir), Path(saved_snapshot)
        self.plans = OrderedDict()
        self.last_collection = -float('inf')
        from experiments.station_planner import StationPlanner
        self.stations = StationPlanner(self)

    def config(self):
        cases = []
        for key, item in CASES.items():
            net, _, _, _ = network_data(key)
            cases.append({**item, 'id': key, 'stop_count': len(net.stops),
                'origin_name': net.stops[item['origin']].name,
                'destination_name': net.stops[item['destination']].name})
        return dict(cases=cases, station_planning=self.stations.config(),
                    key_present=bool(os.getenv(DATAMALL_API_KEY_ENV, '').strip()),
                    saved_available=self.saved_snapshot.is_file(), max_requests=64, cooldown_seconds=60)

    def collect(self, data, consent):
        if consent is not True:
            raise UserError('本次 ETA 查询需要确认。')
        if self.clock()-self.last_collection < 60:
            raise UserError('距离上次采集不足 60 秒，请稍后再试。', 429)
        try:
            provider = self.provider_factory()
        except Exception:
            raise UserError('后端未配置可用的 LTA_DATAMALL_API_KEY；可先使用离线估算。', 503) from None
        network, _, _, provenance, _, _, _ = data
        stops = sorted(network.stops)
        if len(stops) > 64:
            raise UserError('站点数超过单轮请求上限。')
        self.last_collection = self.clock()
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        path = self.raw_dir / f'eta_{self.now().strftime("%Y%m%d_%H%M%S")}_{secrets.token_hex(4)}.jsonl'
        observations, error, requests = [], None, 0
        with path.open('x', encoding='utf-8') as file:
            def emit(row):
                file.write(json.dumps(row, allow_nan=False)+'\n')
                file.flush()
            emit(dict(type='metadata', source='LTA DataMall BusArrival v3', endpoint=provider.endpoint,
                started_at=self.now().isoformat(), topology_provenance=provenance,
                data_kind='ETA_predictions_not_actual_arrivals', max_requests=len(stops), rounds=1,
                processing='Manual single batch; no retries, passenger identifiers or journey selections'))
            for index, stop in enumerate(stops, 2):
                if self.clock()-self.last_collection >= 90:
                    error = '采集达到 90 秒上限，未采集部分使用模型估计。'
                    break
                row = dict(type='observation', bus_stop_code=stop, requested_at=self.now().isoformat())
                requests += 1
                try:
                    arrivals = [asdict(a) for a in provider.fetch(stop)]
                    row.update(status='ok', arrivals=arrivals)
                except Exception:
                    row.update(status='error', error_type='LTA_request_failed')
                    error = 'LTA 请求失败，已停止本轮采集；缺失部分使用模型估计。'
                row['received_at'] = self.now().isoformat()
                emit(row)
                observations.append((str(index), row))
                if error:
                    break
            emit(dict(type='completion', status='partial' if error else 'completed_single_round',
                      requests=requests, ended_at=self.now().isoformat()))
        return observations, self.now(), dict(requests=requests, warning=error,
            source='manual_current_snapshot', raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            captured_at=self.now().isoformat())

    def plan(self, body):
        if 'origins' in body or 'destinations' in body or body.get('query_type') == 'stations':
            return self.stations.plan(body)
        case, mode, buffer = body.get('case', 'school'), body.get('mode', 'model'), body.get('buffer', 3)
        if mode not in ('model', 'saved', 'live'):
            raise UserError('未知数据模式。')
        if not isinstance(buffer, int) or isinstance(buffer, bool):
            raise UserError('换乘缓冲必须为整数分钟。')
        data = case_data(case, buffer)
        network, windows, bindings, provenance, parameters, routes, stats = data
        decision, observations, info = self.now(), [], dict(requests=0, source='model')
        if mode == 'saved':
            if case != 'school' or not self.saved_snapshot.is_file():
                raise UserError('该案例没有可用的已保存快照。')
            observations, decision, info = load_snapshot(self.saved_snapshot)
            info = {**info, 'requests': 0, 'source': 'saved_snapshot'}
        elif mode == 'live':
            observations, decision, info = self.collect(data, body.get('consent'))
        f = FrozenForecasts(observations, decision, bindings)
        rows = []
        for i, route in enumerate(routes):
            row = snapshot_estimate(route, network, windows, parameters, f, limited=LIMITED)
            row['id'] = f'R{i+1:05d}'
            rows.append(row)
        identifier = secrets.token_urlsafe(12)
        state = dict(case=case, mode=mode, buffer=buffer, data=data, rows=rows,
                     forecasts=f, info=info, alighted={}, created=self.clock())
        self.plans[identifier] = state
        while len(self.plans) > 3:
            self.plans.popitem(last=False)
        families = shortlist(rows)
        index = {r['id']: r for r in rows}
        output = dict(plan_id=identifier, case=case, mode=mode, decision_at=f.decision.isoformat(),
            computed_at=self.now().isoformat(), info=info, candidate_count=len(rows),
            eligible_count=sum(r['recommendable'] for r in rows), search=stats,
            exclusions=dict(Counter(reason for r in rows for reason in r['exclusion_reasons'])),
            families=[dict(row=self.public_row(index[item['representative_id']], network),
                variants=[dict(id=rid, total=index[rid]['estimated_total_minutes'],
                    transfers=[network.stops[l['alight_stop']].name for l in index[rid]['legs'][:-1]]) for rid in item['variant_ids']]) for item in families],
            parameters=asdict(parameters), topology=provenance)
        return output

    def state(self, identifier):
        state = self.plans.get(identifier)
        if state is None or self.clock()-state['created'] > 3*3600:
            raise UserError('查询已过期，请重新查询路线。', 410)
        return state

    def public_row(self, row, network):
        result = {k: row[k] for k in ('id', 'services', 'estimated_total_minutes', 'ride_minutes', 'wait_minutes',
            'buffer_minutes', 'delay_minutes', 'transfers', 'estimated_arrival_at', 'snapshot_boardings', 'modeled_boardings')}
        result['legs'] = [{**l, 'board_name': network.stops[l['board_stop']].name,
                         'alight_name': network.stops[l['alight_stop']].name} for l in row['legs']]
        route = Route(row['route']['origin'], row['route']['destination'], [Leg(**l) for l in row['route']['legs']])
        points = []
        for i, (service, _, stop) in enumerate(expanded(route, network), 1):
            points.append(dict(index=i, stop=stop, name=network.stops[stop].name, service=service))
        result['points'] = points
        result.update(origin=route.origin, destination=route.destination,
                      origin_name=network.stops[route.origin].name,
                      destination_name=network.stops[route.destination].name)
        for key in ('access_minutes', 'egress_minutes', 'reference_total_minutes',
                    'ready_at', 'operating_status', 'reference_arrival_at', 'timing_basis'):
            if key in row:
                result[key] = row[key]
        return result

    def detail(self, body):
        state = self.state(body.get('plan_id'))
        row = next((r for r in state['rows'] if r['id']==body.get('route_id')), None)
        if row is None or not row['recommendable']:
            raise UserError('路线不存在或不在默认参考池。')
        return self.public_row(row, state['data'][0])

    def combinations(self, body):
        from sg_transit.route_combinations import CombinationIndex

        identifier = body.get('plan_id')
        if not isinstance(identifier, str):
            raise UserError('查询标识无效。')
        state = self.state(identifier)
        network, _, _, _, _, routes, stats = state['data']
        if 'combination_index' not in state:
            state['combination_index'] = CombinationIndex(network,
                [(row['id'], route) for row, route in zip(state['rows'], routes)
                 if row['recommendable']])
        origin, destination = body.get('origin'), body.get('destination')
        if any(x is not None and not isinstance(x, str) for x in (origin, destination)):
            raise UserError('请选择实际起终点。')
        try:
            view = state['combination_index'].view(origin, destination,
                **{key: body[key] for key in ('selection', 'choice_page', 'route_page',
                   'graph_page', 'expand', 'stop_page', 'inspect') if key in body})
        except ValueError as exc:
            raise UserError(str(exc), code='invalid_combination') from None
        rows = {r['id']: r for r in state['rows']}
        view['routes'] = [self.public_row(rows[rid], network) for rid in view['routes']]
        view.update(plan_id=identifier, search=stats,
            excluded_count=sum(not r['recommendable'] for r in state['rows']),
            exclusions=dict(Counter(reason for r in state['rows'] for reason in r['exclusion_reasons'])))
        return view

    def onward(self, body):
        state = self.state(body.get('plan_id'))
        route_id, point = body.get('route_id'), body.get('point')
        if not isinstance(point, int) or isinstance(point, bool) or not isinstance(body.get('onboard'), bool):
            raise UserError('请选择当前位置与乘车状态。')
        data = state['data']
        network, _, bindings, _, p, routes, _ = data
        indices = {row['id']: i for i, row in enumerate(state['rows'])}
        if route_id not in indices or not state['rows'][indices[route_id]]['recommendable']:
            raise UserError('未知路线。')
        base = routes[indices[route_id]]
        selected_row = state['rows'][indices[route_id]]
        is_custom = state.get('query_type') == 'stations'
        base_forecast = (FrozenForecasts([], datetime.fromisoformat(selected_row['ready_at']), bindings)
                         if is_custom else state['forecasts'])
        arcs = expanded(base, network)
        if not 1 <= point <= len(arcs):
            raise UserError('当前位置不在选定路线中。')
        history = arcs[:point]
        current_service, _, stop = history[-1]
        used = {s for s, _, _ in history}
        onboard = current_service if body['onboard'] else None
        at = base_forecast.decision
        # Saved snapshots are explored at the selected route's model arrival,
        # never presented as current positions or refreshed against today's clock.
        if state['mode'] == 'saved' or is_custom:
            if body.get('live'):
                raise UserError('历史案例或自选站点离线推演不能刷新为当前 ETA。')
            row = state['rows'][indices[route_id]]
            leg = next(l for l in row['legs'] if l['service_id'] == current_service)
            at = datetime.fromisoformat(leg['board_at']) + timedelta(minutes=
                leg['mean_boarding_delay_minutes'] + network.services[current_service].ride_time(leg['board_stop'], stop))
        else:
            at = self.now()
        if at < base_forecast.decision:
            raise UserError('当前时间早于原查询时间，请重新查询。')
        if (at-base_forecast.decision).total_seconds() > p.max_trip_minutes*60:
            raise UserError('行程已超过 120 分钟模型上限，请重新发起查询。')
        key = (base.origin, base.destination, tuple(history))
        if onboard is None:
            alighted = state['alighted'].setdefault(key, at)
        else:
            alighted = at
        info = dict(requests=0, source='model')
        if body.get('live') is True:
            observations, at, info = self.collect(data, body.get('consent'))
            f = FrozenForecasts(observations, at, bindings)
        elif state['mode'] == 'saved':
            f = state['forecasts']
            info = dict(requests=0, source='saved_projection')
        else:
            f = FrozenForecasts([], at, bindings)
            if is_custom:
                info['source'] = 'model_projection'
        # Retain the original knowledge cutoff for saved projections, while the
        # passenger readiness advances to the manually selected future stop.
        cursor = f.minute(at)
        options, seen = [], set()
        for i, route in enumerate(routes):
            if (route.origin, route.destination) != (base.origin, base.destination):
                continue
            path = expanded(route, network)
            if path[:point] != history:
                continue
            tail = path[point:]
            if tail and tail[0][0] in used and tail[0][0] != onboard:
                continue
            suffix = suffix_route(tail, stop, base.destination, network, p.transfer_walk_minutes)
            if route_key(suffix) in seen:
                continue
            seen.add(route_key(suffix))
            # A shifted view changes the route start, not forecast receipt gates.
            view = copy(f)
            view.decision, view.departure = at, cursor
            row = remaining_estimate(suffix, data, view, used, onboard,
                                     base_forecast.decision, f.minute(alighted))
            if is_custom:
                self.stations.retain_unknown(row)
            row['id'] = state['rows'][i]['id']
            options.append(row)
        eligible = [r for r in options if r['recommendable']]
        families = shortlist(eligible)
        rows = {r['id']: r for r in eligible}
        return dict(at=at.isoformat(), info=info, stop=stop, name=network.stops[stop].name,
            onboard=onboard, candidate_count=len(options), eligible_count=len(eligible),
            exclusions=dict(Counter(x for r in options for x in r['exclusion_reasons'])),
            routes=[{**self.public_row(rows[x['representative_id']], network),
                     'can_adopt': state['rows'][indices[x['representative_id']]]['recommendable']}
                    for x in families])

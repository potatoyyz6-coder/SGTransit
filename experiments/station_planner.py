"""Offline multi-endpoint adapter. No providers, address lookup or walking edges."""
from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib
import json
import math
import secrets

from data.real.build_subset import RAW, load_rows
from experiments.blk18_cde_case import LIMITED, ROOT, Settings
from sg_transit.corridors import CorridorParameters, DestinationIndex, discover_candidates
from sg_transit.routing import SearchBudgetExceeded, enumerate_routes
from sg_transit.snapshot_reference import FrozenForecasts, SGT, snapshot_estimate
from sg_transit.station_catalog import CatalogStop, StationCatalog


@lru_cache(maxsize=1)
def local_catalog():
    source = json.loads((ROOT/'data/real/sources.json').read_text(encoding='utf-8'))
    path = RAW/'BusStops.csv'
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != source['raw_sha256']['BusStops.csv']:
        raise ValueError('Catalog source hash mismatch')
    return StationCatalog(CatalogStop(r['BusStopCode'], r['Description'],
                          float(r['Longitude']), float(r['Latitude'])) for r in load_rows(path)), digest


def endpoint_families(rows, limit=16):
    """Keep endpoint identity; guarantee one displayed family per eligible pair."""
    groups = defaultdict(list)
    for row in rows:
        if row['recommendable']:
            key = (row['route']['origin'], row['route']['destination'], tuple(row['services']))
            groups[key].append(row)
    order = lambda r: (r['estimated_total_minutes'], r['transfers'], r['id'])
    representatives = sorted((min(group, key=order) for group in groups.values()), key=order)
    chosen, pairs = [], set()
    for row in representatives:
        pair = (row['route']['origin'], row['route']['destination'])
        if pair not in pairs:
            chosen.append(row)
            pairs.add(pair)
    for candidates in (representatives[:4], sorted(representatives, key=lambda r: (r['transfers'], *order(r)))[:2],
                       sorted(representatives, key=lambda r: (r['wait_minutes'], *order(r)))[:2], representatives):
        for row in candidates:
            if len(chosen) < limit and row not in chosen:
                chosen.append(row)
    result = []
    for row in sorted(chosen, key=order):
        group = groups[(row['route']['origin'], row['route']['destination'], tuple(row['services']))]
        result.append(dict(representative_id=row['id'], variant_ids=[r['id'] for r in sorted(group, key=order)]))
    return result


class StationPlanner:
    MAX_PAIRS = 9
    MAX_CANDIDATES = 20000
    MAX_EXPANSIONS = 200000

    def __init__(self, owner):
        self.owner = owner
        self.cache = OrderedDict()

    @staticmethod
    def fail(message, code='invalid_request'):
        from experiments.local_planner import UserError
        raise UserError(message, code=code)

    def config(self):
        from experiments.local_planner import CASES
        from experiments.station_networks import EXTRA_NETWORKS
        catalog, digest = local_catalog()
        networks = []
        for key, spec in {**CASES, **EXTRA_NETWORKS}.items():
            bundle = self.bundle(key)
            first = next(iter(bundle[0].services.values()))
            networks.append(dict(id=key, label=spec['label'], stop_count=len(bundle[0].stops),
                default_origin=spec.get('origin', first.stops[0]),
                default_destination=spec.get('destination', first.stops[-1]),
                network_sha256=bundle[3]['network_sha256'], coverage_gaps=bundle[3].get('coverage_gaps', [])))
        return dict(default_radius_m=400, max_radius_m=2000, max_per_end=3, max_pairs=self.MAX_PAIRS,
                    max_candidates=self.MAX_CANDIDATES, max_expansions=self.MAX_EXPANSIONS,
                    catalog_count=len(catalog.stops), catalog_sha256=digest,
                    now_sgt=self.owner.now().astimezone(SGT).isoformat(), offline_only=True, networks=networks)

    def bundle(self, name):
        from experiments.local_planner import CASES, network_data
        from experiments.station_networks import EXTRA_NETWORKS, imported_bundle
        if not isinstance(name, str) or name not in {*CASES, *EXTRA_NETWORKS}:
            self.fail('Unknown declared network.', 'unknown_network')
        return imported_bundle(name) if name in EXTRA_NETWORKS else network_data(name)

    def stop_record(self, stop, network):
        services = [s for s in network.services.values() if stop.id in s.stops]
        return dict(id=stop.id, name=stop.name, longitude=stop.longitude, latitude=stop.latitude,
                    covered=stop.id in network.stops,
                    coverage='declared_fragments_only' if stop.id in network.stops else 'outside_network',
                    services=[dict(id=s.id, to=network.stops[s.stops[-1]].name,
                                   can_board=stop.id != s.stops[-1], can_alight=stop.id != s.stops[0])
                              for s in services])

    def stops(self, body):
        network = self.bundle(body.get('network', 'school'))[0]
        query = body.get('text', '')
        if not isinstance(query, str) or len(query) > 100:
            self.fail('Stop search must contain at most 100 characters.')
        catalog, digest = local_catalog()
        records, count = catalog.search(query, limit=len(catalog.stops))
        records.sort(key=lambda s: (s.id.casefold() != query.strip().casefold(), s.id not in network.stops,
                                    s.name.casefold(), s.id))
        records = records[:25]
        return dict(stops=[self.stop_record(s, network) for s in records], total=count,
                    omitted=count-len(records), catalog_sha256=digest)

    def nearby(self, body):
        network = self.bundle(body.get('network', 'school'))[0]
        catalog, digest = local_catalog()
        center = body.get('center')
        if not isinstance(center, str) or center not in catalog.stops:
            self.fail('Unknown center stop ID.', 'unknown_stop')
        radius = body.get('radius_m', 400)
        if not isinstance(radius, (int, float)) or isinstance(radius, bool):
            self.fail('Radius must be numeric.')
        try:
            records, defaults = catalog.nearby(center, radius, body.get('max_selected', 3))
        except ValueError as exc:
            self.fail(str(exc))
        defaults = [center] + [s.id for s, _ in records if s.id != center and s.id in network.stops]
        defaults = defaults[:body.get('max_selected', 3)]
        return dict(center=center, radius_m=radius, catalog_sha256=digest,
                    distance_kind='straight_line_not_verified_walk', total=len(records),
                    selection_rule='center_then_nearest_covered_stops_user_confirmation_required',
                    unsupported_count=sum(s.id not in network.stops for s, _ in records),
                    not_auto_selected=len(records)-len(defaults), selected=defaults,
                    stops=[{**self.stop_record(s, network), 'distance_m': d, 'center': s.id == center}
                           for s, d in records])

    def endpoints(self, value, time_field, network):
        if not isinstance(value, list) or not 1 <= len(value) <= 3:
            self.fail('Confirm between one and three stops at each end.')
        catalog, _ = local_catalog()
        result = []
        for item in value:
            if not isinstance(item, dict):
                self.fail('Each endpoint needs a stop ID.')
            stop, minutes = item.get('stop'), item.get(time_field)
            if not isinstance(stop, str) or stop not in catalog.stops:
                self.fail('Unknown stop ID.', 'unknown_stop')
            if stop not in network.stops:
                self.fail(f'Stop {stop} is in the directory but outside this declared network.', 'outside_network')
            if minutes is not None and (isinstance(minutes, bool) or not isinstance(minutes, (int, float))
                                        or not math.isfinite(minutes) or not 0 <= minutes <= 120):
                self.fail('Access/egress minutes must be blank or between 0 and 120.')
            result.append(dict(stop=stop, **{time_field: minutes}))
        if len({x['stop'] for x in result}) != len(result):
            self.fail('Duplicate endpoint IDs are not allowed.')
        return sorted(result, key=lambda x: x['stop'])

    @staticmethod
    def retain_unknown(row):
        # Only this model-reference path retains unknown windows. Historical
        # replay and existing snapshot evidence gates are deliberately unchanged.
        unknown = 'unknown' in row['exclusion_reasons']
        row['exclusion_reasons'] = [r for r in row['exclusion_reasons'] if r != 'unknown']
        row['recommendable'] = not row['exclusion_reasons']
        row['operating_status'] = ('unknown' if unknown else 'outside_or_limited' if row['exclusion_reasons']
                                   else 'within_historical_windows_not_current_guarantee')

    def search(self, bundle, origin, destination, parameters):
        method = 'bounded_corridor' if len(bundle[0].stops) > 30 else 'enumeration'
        key = (bundle[3]['network_sha256'], origin, destination, parameters, method)
        if key in self.cache:
            self.cache.move_to_end(key)
            routes, stats = self.cache[key]
            return routes, {**stats, 'cache_hit': True}
        stats = dict(method=method)
        try:
            if method == 'bounded_corridor':
                index = DestinationIndex(bundle[0], destination)
                search = discover_candidates(index, origin, parameters, CorridorParameters(
                    max_hubs=6, ordinary_candidates=30, prefixes_per_hub=8, bypass_candidates=4))
                routes = search.routes
                complete = origin == destination or origin not in index.lower
                stats.update(expansions=search.expansions, candidates=len(routes), complete=complete,
                             reasons=search.truncation_reasons,
                             status=('complete' if routes else 'unreachable_within_bounds') if complete
                             else 'bounded_candidates' if routes else 'bounded_no_candidate')
            else:
                routes = enumerate_routes(bundle[0], origin, destination, parameters, stats=stats)
                stats.update(status='complete' if routes else 'unreachable_within_bounds', complete=True)
        except SearchBudgetExceeded:
            routes = []
            stats.update(status='budget_exceeded', complete=False)
        self.cache[key] = (routes, dict(stats))
        while len(self.cache) > 24 or sum(len(v[0]) for v in self.cache.values()) > self.MAX_CANDIDATES:
            self.cache.popitem(last=False)
        return routes, {**stats, 'cache_hit': False}

    def plan(self, body):
        if body.get('mode', 'model') != 'model' or body.get('consent') is True:
            self.fail('Custom station comparisons are offline only.', 'offline_only')
        name = body.get('network', 'school')
        bundle = self.bundle(name)
        network, windows, bindings, provenance = bundle
        origins = self.endpoints(body.get('origins'), 'access_minutes', network)
        destinations = self.endpoints(body.get('destinations'), 'egress_minutes', network)
        buffer = body.get('buffer', 3)
        if isinstance(buffer, bool) or not isinstance(buffer, int) or buffer not in range(1, 6):
            self.fail('Transfer buffer must be an integer from 1 to 5.')
        value = body.get('departure_time')
        try:
            if value is None:
                departure = self.owner.now().astimezone(SGT)
            else:
                if not isinstance(value, str) or not 16 <= len(value) <= 40:
                    raise ValueError()
                departure = datetime.fromisoformat(value)
                departure = (departure.replace(tzinfo=SGT) if departure.tzinfo is None
                             else departure.astimezone(SGT))
                if not 2000 <= departure.year <= 2100:
                    raise ValueError()
        except (ValueError, TypeError, OverflowError):
            self.fail('Use a valid Singapore departure date and time.', 'invalid_departure')
        parameters = Settings(transfer_buffer=buffer).routing()
        rows, routes, pairs = [], [], []
        expansions, candidates = 0, 0
        for origin in origins:
            ready = departure + timedelta(minutes=origin['access_minutes'] or 0)
            forecast = FrozenForecasts([], ready, bindings)
            for destination in destinations:
                left_candidates, left_expansions = self.MAX_CANDIDATES-candidates, self.MAX_EXPANSIONS-expansions
                if min(left_candidates, left_expansions) < 1:
                    found, stats = [], dict(status='budget_not_searched', complete=False, expansions=0, candidates=0)
                else:
                    bounded = replace(parameters, max_candidates=min(parameters.max_candidates, left_candidates),
                                      max_expansions=min(parameters.max_expansions, left_expansions))
                    found, stats = self.search(bundle, origin['stop'], destination['stop'], bounded)
                expansions += stats['expansions']
                candidates += stats['candidates']
                pair_rows = []
                for route in found:
                    row = snapshot_estimate(route, network, windows, parameters, forecast, limited=LIMITED)
                    self.retain_unknown(row)
                    access, egress = origin['access_minutes'], destination['egress_minutes']
                    total = None if access is None or egress is None else access+row['estimated_total_minutes']+egress
                    row.update(id=f'R{len(rows)+1:05d}', access_minutes=access, egress_minutes=egress,
                               reference_total_minutes=total, ready_at=ready.isoformat(),
                               reference_arrival_at=None if total is None else (departure+timedelta(minutes=total)).isoformat(),
                               timing_basis='bus_from_selected_stop_readiness' if access is None else 'manual_access_shifted_readiness')
                    rows.append(row)
                    pair_rows.append(row)
                    routes.append(route)
                eligible = sum(r['recommendable'] for r in pair_rows)
                pairs.append(dict(origin=origin['stop'], destination=destination['stop'], **stats,
                                  eligible_count=eligible, returned_candidates=len(found),
                                  operating_unknown_count=sum(r['operating_status']=='unknown' for r in pair_rows),
                                  exclusions=dict(Counter(x for r in pair_rows for x in r['exclusion_reasons']))))
        query = dict(network=name, origins=origins, destinations=destinations,
                     departure_time=departure.isoformat(), parameters=asdict(parameters),
                     network_sha256=provenance['network_sha256'], max_candidates=self.MAX_CANDIDATES,
                     max_expansions=self.MAX_EXPANSIONS)
        query_hash = hashlib.sha256(json.dumps(query, sort_keys=True, allow_nan=False).encode()).hexdigest()
        identifier = secrets.token_urlsafe(12)
        stats = dict(complete=all(p['complete'] for p in pairs), method='budgeted_endpoint_enumeration',
                     candidates=candidates, expansions=expansions, pairs=pairs)
        info = dict(requests=0, source='model', warning=None)
        self.owner.plans[identifier] = dict(query_type='stations', case=name, mode='model', buffer=buffer,
            data=(*bundle, parameters, routes, stats), rows=rows, forecasts=FrozenForecasts([], departure, bindings),
            info=info, alighted={}, created=self.owner.clock(), query=query, query_sha256=query_hash)
        while len(self.owner.plans) > 3:
            self.owner.plans.popitem(last=False)
        lookup = {r['id']: r for r in rows}
        families = endpoint_families(rows)
        return dict(plan_id=identifier, case=name, query_type='stations', mode='model', query=query,
            query_sha256=query_hash, decision_at=departure.isoformat(), computed_at=self.owner.now().isoformat(),
            info=info, candidate_count=len(rows), eligible_count=sum(r['recommendable'] for r in rows),
            operating_unknown_count=sum(r['operating_status']=='unknown' for r in rows), search=stats,
            exclusions=dict(Counter(x for r in rows for x in r['exclusion_reasons'])),
            families=[dict(row=self.owner.public_row(lookup[f['representative_id']], network),
                           variants=[dict(id=rid, total=lookup[rid]['estimated_total_minutes'],
                                          transfers=[network.stops[l['alight_stop']].name for l in lookup[rid]['legs'][:-1]])
                                     for rid in f['variant_ids']]) for f in families],
            parameters=asdict(parameters), topology=provenance)

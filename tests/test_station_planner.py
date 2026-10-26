from dataclasses import replace
from datetime import datetime
import math

import pytest

from experiments.local_planner import LocalPlanner, UserError, network_data
from experiments import station_planner as module
from sg_transit.models import Stop, TransitNetwork, TransitService, validate_route
from sg_transit.routing import RoutingParameters
from sg_transit.snapshot_reference import SGT
from sg_transit.station_catalog import CatalogStop, StationCatalog, distance_m


def test_catalog_radius_boundary_opposite_names_and_center_cap():
    a = CatalogStop('A', 'Same name', 103.8, 1.3)
    b = CatalogStop('B', 'Same name', 103.801, 1.3)
    c = CatalogStop('C', 'Third', 103.8, 1.3)
    catalog = StationCatalog([b, a, c])
    radius = distance_m(a, b)
    found, selected = catalog.nearby('A', radius, cap=1)
    assert [s.id for s, _ in found] == ['A', 'C', 'B']
    assert selected == ['A']
    assert {s.id for s, _ in catalog.nearby('A', radius-.001)[0]} == {'A', 'C'}
    assert len(catalog.search('same')[0]) == 2
    assert catalog.search('B')[0][0].id == 'B'
    assert catalog.search('not found') == ([], 0)
    assert StationCatalog([a]).nearby('A', 0)[1] == ['A']
    with pytest.raises(ValueError):
        StationCatalog([a, a])


@pytest.mark.parametrize('lon,lat', [(math.nan, 1), (104, math.inf), (181, 1), (100, -91), (True, 1)])
def test_invalid_coordinates(lon, lat):
    with pytest.raises(ValueError):
        CatalogStop('A', 'A', lon, lat)


@pytest.fixture
def planner():
    def forbidden():
        raise AssertionError('No API calls allowed')
    return LocalPlanner(now=lambda: datetime(2026, 10, 24, 23, 0, tzinfo=SGT), provider_factory=forbidden)


def request(origins=('28109',), destinations=('16159',), **kwargs):
    return dict(query_type='stations', network='school', mode='model',
                origins=[dict(stop=s) for s in origins], destinations=[dict(stop=s) for s in destinations],
                departure_time='2026-10-26T10:00', **kwargs)


def test_directory_nearby_explicit_coverage_and_selection(planner):
    result = planner.stations.nearby(dict(center='42161', network='school'))
    assert result['stops'][0]['id'] == '42161'
    assert result['selected'][0] == '42161' and len(result['selected']) <= 3
    assert result['unsupported_count'] > 0 and result['not_auto_selected'] > 0
    opposite = next(s for s in result['stops'] if s['id'] == '42169')
    assert not opposite['covered'] and opposite['coverage'] == 'outside_network'
    assert all(s['id'] not in result['selected'] for s in result['stops'] if not s['covered'])
    assert result['distance_kind'] == 'straight_line_not_verified_walk'
    assert planner.stations.stops(dict(text='Coll of Design', network='school'))['total'] >= 1
    assert planner.stations.stops(dict(text='42161', network='school'))['stops'][0]['services']
    unsupported = planner.stations.nearby(dict(center='42169', network='school', radius_m=0))
    assert unsupported['selected'] == ['42169'] and not unsupported['stops'][0]['covered']


@pytest.mark.parametrize('changes,code', [
    ({'origins': [{'stop': 'no-such-stop'}]}, 'unknown_stop'),
    ({'origins': [{'stop': '42169'}]}, 'outside_network'),
    ({'origins': []}, 'invalid_request'),
    ({'origins': [{'stop':'42161'}]*4}, 'invalid_request'),
    ({'origins': [{'stop':'42161'}]*2}, 'invalid_request'),
    ({'origins': [{'stop':'42161','access_minutes':float('nan')}]}, 'invalid_request'),
    ({'origins': [{'stop':'42161','access_minutes':False}]}, 'invalid_request'),
    ({'departure_time': 'yesterday'}, 'invalid_departure'),
    ({'departure_time': '9999-12-31T23:59'}, 'invalid_departure'),
    ({'mode': 'live', 'consent': True}, 'offline_only'),
    ({'buffer': True}, 'invalid_request'),
])
def test_invalid_requests_are_structured(planner, changes, code):
    with pytest.raises(UserError) as exc:
        planner.plan({**request(), **changes})
    assert exc.value.code == code


def test_new_pairs_route_costs_repeatability_and_no_api(planner):
    body = request(origins=('28109', '28019'), destinations=('17159', '16159'))
    first = planner.plan(body)
    assert first['info']['requests'] == 0 and len(first['search']['pairs']) == 4
    assert first['search']['complete'] and all(p['returned_candidates'] for p in first['search']['pairs'])
    shown = {(f['row']['origin'], f['row']['destination']) for f in first['families']}
    assert shown == {(a['stop'], b['stop']) for a in body['origins'] for b in body['destinations']}
    state = planner.state(first['plan_id'])
    for row, route in zip(state['rows'], state['data'][5]):
        validate_route(route, state['data'][0])
        assert row['reference_total_minutes'] is None
        assert row['access_minutes'] is None and row['egress_minutes'] is None
        assert row['estimated_total_minutes'] == pytest.approx(sum(row[k] for k in
               ('ride_minutes', 'wait_minutes', 'buffer_minutes', 'delay_minutes')))
    second = planner.plan(body)
    assert first['query_sha256'] == second['query_sha256']
    assert first['families'] == second['families']
    assert all(p['cache_hit'] for p in second['search']['pairs'])
    another = planner.plan({**body, 'departure_time':'2026-10-26T12:00'})
    assert another['query_sha256'] != first['query_sha256']


def test_same_stop_and_wrong_direction_are_not_unknown(planner):
    same = planner.plan(request(origins=('16159',)))
    assert same['candidate_count'] == 1
    row = same['families'][0]['row']
    assert row['estimated_total_minutes'] == 0 and not row['points'] and not row['legs']
    reverse = planner.plan(request(origins=('16159',), destinations=('42161',)))
    assert reverse['candidate_count'] == 0 and reverse['search']['complete']
    assert reverse['search']['pairs'][0]['status'] == 'unreachable_within_bounds'


def test_larger_existing_network_keeps_bounded_useful_candidates(planner):
    result = planner.plan({**request(origins=('16189',), destinations=('42171',)), 'network':'home'})
    assert result['eligible_count'] > 0 and not result['search']['complete']
    assert result['search']['pairs'][0]['method'] == 'bounded_corridor'
    assert result['search']['pairs'][0]['status'] == 'bounded_candidates'
    assert any(f['row']['services']==['151-D2','61-D2'] for f in result['families'])


def test_budget_failure_is_not_unreachable_and_cache_keys_include_budgets(planner):
    s = planner.stations
    bundle = network_data('school')
    p = RoutingParameters(max_candidates=1, max_expansions=20)
    routes, stats = s.search(bundle, '42161', '16159', p)
    assert not routes and stats['status'] == 'budget_exceeded' and not stats['complete']
    routes, stats = s.search(bundle, '42161', '16159', replace(p, max_candidates=10000, max_expansions=100000))
    assert routes and stats['complete'] and not stats['cache_hit']
    changed = (*bundle[:3], {**bundle[3], 'network_sha256':'changed-for-test'})
    assert not s.search(changed, '42161', '16159', p)[1]['cache_hit']
    s.MAX_EXPANSIONS = 1
    result = planner.plan(request(origins=('42161','28109')))
    assert not result['search']['complete']
    assert [p['status'] for p in result['search']['pairs']] == ['budget_exceeded', 'budget_not_searched']


@pytest.fixture
def toy(planner, monkeypatch):
    catalog = StationCatalog([CatalogStop(s, s, 103.8+i*.001, 1.3) for i, s in enumerate('ABCD')])
    net = TransitNetwork([Stop(s, s) for s in 'ABCD'], [TransitService('T-D1', ('A','B','C'), (2,3), 10, 0)])
    windows = {'T-D1': {s: {'WD_FirstBus':'0600', 'WD_LastBus':'1005'} for s in 'ABC'}}
    bundle = (net, windows, {}, {'network_sha256':'synthetic-test'})
    monkeypatch.setattr(module, 'local_catalog', lambda: (catalog, 'synthetic-test'))
    monkeypatch.setattr(planner.stations, 'bundle', lambda name: bundle)
    return planner, bundle


def test_access_changes_readiness_before_windows_egress_unknown_separate(toy):
    planner, _ = toy
    body = request(origins=('A',), destinations=('C',))
    default = planner.plan(body)['families'][0]['row']
    assert default['ready_at'] == '2026-10-26T10:00:00+08:00'
    assert default['reference_total_minutes'] is None
    explicit = planner.plan({**body, 'origins':[{'stop':'A','access_minutes':0}],
                             'destinations':[{'stop':'C','egress_minutes':4}]})['families'][0]['row']
    assert explicit['reference_total_minutes'] == explicit['estimated_total_minutes']+4
    late = planner.plan({**body, 'origins':[{'stop':'A','access_minutes':1}]})
    assert late['candidate_count'] == 1 and late['eligible_count'] == 0
    assert late['exclusions']['outside_historical_window'] == 1
    state = planner.state(late['plan_id'])
    assert state['rows'][0]['legs'][0]['board_at'] == '2026-10-26T10:06:00+08:00'


def test_unknown_operating_keeps_topology_only_in_reference(toy):
    planner, bundle = toy
    bundle[1].clear()
    result = planner.plan(request(origins=('A',), destinations=('C',)))
    assert result['candidate_count'] == result['eligible_count'] == result['operating_unknown_count'] == 1
    row = result['families'][0]['row']
    assert row['operating_status'] == 'unknown'
    assert row['legs'][0]['operating_status'] == 'unknown'


def test_nearby_bus_time_can_improve_without_door_to_door_claim(toy):
    planner, _ = toy
    result = planner.plan(request(origins=('A','B'), destinations=('C',)))
    pairs = {f['row']['origin']:f['row'] for f in result['families']}
    assert pairs['B']['estimated_total_minutes'] < pairs['A']['estimated_total_minutes']
    assert pairs['B']['reference_total_minutes'] is None
    assert pairs['A']['services'] == pairs['B']['services']
    assert len(pairs) == 2  # Service-only grouping would lose an endpoint.


def test_nine_pairs_include_unreachable_and_nearby_can_have_no_benefit(toy, monkeypatch):
    planner, bundle = toy
    net = TransitNetwork(bundle[0].stops.values(), [
        TransitService('A-D1', ('A','C'), (10,), 10, 0),
        TransitService('B-D1', ('B','C'), (10,), 10, 0),
        TransitService('D-D1', ('D','C'), (15,), 10, 0)])
    monkeypatch.setattr(planner.stations, 'bundle', lambda name: (net,{}, {}, {'network_sha256':'nine-pair-fixture'}))
    result = planner.plan(request(origins=('A','B','D'), destinations=('A','B','C')))
    assert len(result['search']['pairs']) == 9
    assert all(p['complete'] for p in result['search']['pairs'])
    assert any(p['status']=='unreachable_within_bounds' for p in result['search']['pairs'])
    rows = {f['row']['origin']: f['row'] for f in result['families'] if f['row']['destination']=='C'}
    assert rows['A']['estimated_total_minutes'] == rows['B']['estimated_total_minutes']
    assert rows['D']['estimated_total_minutes'] > rows['A']['estimated_total_minutes']


def test_custom_onward_uses_projected_departure_and_keeps_endpoints(planner):
    result = planner.plan(request(origins=('28109','28019'), destinations=('17159','16159')))
    state = planner.state(result['plan_id'])
    row = next(r for r in state['rows'] if r['recommendable'] and r['route']['origin']=='28109'
               and r['route']['destination']=='16159' and r['services']==['173-D1','183-D1'])
    detail = planner.detail(dict(plan_id=result['plan_id'], route_id=row['id']))
    point = next(p['index'] for p in detail['points'] if p['stop']=='28019')
    body = dict(plan_id=result['plan_id'], route_id=row['id'], point=point, onboard=True)
    onward = planner.onward(body)
    assert onward['at'].startswith('2026-10-26') and onward['info']['source']=='model_projection'
    assert onward['routes'] and all(r['destination']=='16159' for r in onward['routes'])
    continuation = next(r for r in onward['routes'] if r['services'][0]=='173-D1')
    leg = continuation['legs'][0]
    assert leg['wait_minutes'] == leg['transfer_minutes'] == leg['mean_boarding_delay_minutes'] == 0
    waiting = planner.onward({**body, 'onboard':False})
    assert all('173-D1' not in r['services'] for r in waiting['routes'])
    for r in onward['routes']:
        if r['can_adopt']:
            adopted = planner.detail(dict(plan_id=result['plan_id'], route_id=r['id']))
            assert (adopted['origin'], adopted['destination']) == ('28109','16159')
    with pytest.raises(UserError):
        planner.onward({**body, 'live':True, 'consent':True})

from copy import deepcopy
from datetime import timedelta
import json
import socket
import urllib.request

import pytest

from experiments.blk18_cde_case import Settings
from experiments.blk18_snapshot_reference import load_snapshot, run
from sg_transit.eta_matching import instant
from sg_transit.models import Leg, Route, Stop, TransitNetwork, TransitService
from sg_transit.routing import RoutingParameters
from sg_transit.snapshot_reference import FrozenForecasts, pattern_bindings, projected_choices, snapshot_estimate

T = instant('2026-10-08T11:20:00+08:00')


def arrival(service='A', minutes=5, monitored=True, **changes):
    return dict(service_no=service, origin_code='o', destination_code='z', visit_number='1',
                estimated_arrival=(T+timedelta(minutes=minutes)).isoformat(), monitored=monitored, **changes)


def record(stop='o', arrivals=None, received=T, status='ok'):
    return dict(type='observation', bus_stop_code=stop, requested_at=(received-timedelta(seconds=1)).isoformat(),
                received_at=received.isoformat(), status=status, arrivals=arrivals or [])


def bindings():
    return {s: {stop: dict(service_no=s, origin_code='o', destination_code='z', visit_number='1')
                for stop in ('o', 'x')} for s in ('A', 'B', 'C')}


def forecasts(rows, decision=T):
    return FrozenForecasts([(str(i), r) for i, r in enumerate(rows)], decision, bindings())


@pytest.fixture
def tiny():
    net = TransitNetwork([Stop(s, s) for s in ('o', 'x', 'z')], [
        TransitService('A', ('o', 'x', 'z'), (5, 8), 15, 3),
        TransitService('B', ('x', 'z'), (5,), 15, 3),
        TransitService('C', ('x', 'z'), (6,), 15, 3)])
    windows = {s: {stop: {'WD_FirstBus': '0500', 'WD_LastBus': '2359'} for stop in net.services[s].stops}
               for s in net.services}
    route = Route('o', 'z', [Leg('A', 'o', 'x', 5, 7.5), Leg('B', 'x', 'z', 5, 7.5, 3)])
    return net, windows, route


def test_waiting_readiness_selects_later_slot_and_preserves_monitoring(tiny):
    net, windows, route = tiny
    f = forecasts([record(arrivals=[arrival()]), record('x', [arrival('B', 13), arrival('B', 15, False)])])
    result = snapshot_estimate(route, net, windows, RoutingParameters(), f)
    # 5 wait + 1.5 delay + 5 ride + 3 buffer => ready at +14.5.
    assert result['legs'][1]['wait_minutes'] == pytest.approx(.5)
    assert result['legs'][1]['monitored'] is False
    assert result['legs'][1]['forecast_at'] == (T+timedelta(minutes=15)).isoformat()
    assert result['estimated_total_minutes'] == pytest.approx(21.5)
    assert result['model_only_total_minutes'] == pytest.approx(31)
    assert result['snapshot_boardings'] == 2 and result['modeled_boardings'] == 0
    assert result['unmonitored_snapshot_boardings'] == 1
    assert sum(result[k] for k in ('ride_minutes', 'wait_minutes', 'buffer_minutes', 'delay_minutes')) == pytest.approx(21.5)
    assert route.legs[1].wait_minutes == 7.5


def test_no_future_response_leak_and_latest_error_not_backfilled():
    rows = [record(arrivals=[arrival()]), record(arrivals=[arrival(minutes=1)], received=T+timedelta(seconds=1))]
    f = forecasts(rows)
    assert f.boarding('A', 'o', f.departure, 7.5)['wait_minutes'] == 5
    rows.append(record(received=T, status='error'))
    f = forecasts(rows)
    assert f.boarding('A', 'o', f.departure, 7.5)['fallback_reason'] == 'error'


@pytest.mark.parametrize('mode,reason', [('missing', 'missing'), ('stale', 'stale'),
    ('empty', 'service_missing'), ('past', 'no_future_matching_prediction'), ('horizon', 'beyond_forecast_horizon'),
    ('wrong_direction', 'unusable_or_pattern_mismatch'), ('bad_eta', 'unusable_or_pattern_mismatch'),
    ('wrong_visit', 'unusable_or_pattern_mismatch')])
def test_explicit_model_fallbacks(mode, reason):
    a = arrival()
    if mode == 'past':
        a = arrival(minutes=-1)
    if mode == 'wrong_direction':
        a['destination_code'] = 'wrong'
    if mode == 'wrong_visit':
        a['visit_number'] = '2'
    if mode == 'bad_eta':
        a['estimated_arrival'] = 'bad'
    rows = [] if mode == 'missing' else [record(arrivals=[] if mode == 'empty' else [a],
        received=T-timedelta(seconds=91) if mode == 'stale' else T)]
    f = forecasts(rows)
    r = f.boarding('A', 'o', f.departure+(10 if mode == 'horizon' else 0), 7.5)
    assert r['timing_source'] == 'modeled_wait' and r['fallback_reason'] == reason
    assert r['wait_minutes'] == 7.5 and r['selected_entry'] is None and r['forecast_at'] is None


def test_future_ready_does_not_make_departure_snapshot_stale():
    f = forecasts([record(arrivals=[arrival(minutes=40)])])
    r = f.boarding('A', 'o', f.departure+30, 7.5)
    assert r['timing_source'] == 'snapshot_eta' and r['wait_minutes'] == 10
    f = forecasts([record(arrivals=[arrival(minutes=40)])], T+timedelta(seconds=91))
    assert f.boarding('A', 'o', f.departure, 7.5)['fallback_reason'] == 'stale'


def test_pattern_binding_full_endpoints_loop_visits():
    rows = [dict(ServiceNo='41', Direction='1', StopSequence=str(i), BusStopCode=s)
            for i, s in enumerate(('o', 'x', 'z', 'x', 'o'), 1)]
    pattern = {'41-D1': dict(service_no='41', direction='1', ordered_source_rows=rows[3:])}
    b = pattern_bindings(pattern, rows)
    assert b['41-D1']['x'] == dict(service_no='41', origin_code='o', destination_code='o', visit_number='2')
    with pytest.raises(ValueError, match='Ambiguous'):
        pattern_bindings(pattern, rows+[rows[0]])


def test_limits_windows_and_missing_eta_retain_topology(tiny):
    net, windows, route = tiny
    f = forecasts([])
    p = RoutingParameters(max_trip_minutes=20, max_transfer_gap=5, max_transfers=0)
    windows = deepcopy(windows)
    windows['B']['x'] = {}
    r = snapshot_estimate(route, net, windows, p, f, limited=('A',))
    assert not r['recommendable'] and len(r['legs']) == 2
    assert set(r['exclusion_reasons']) == {'estimated_trip_limit_exceeded', 'estimated_transfer_gap_exceeded',
        'transfer_count_exceeded', 'unknown', 'limited_service_not_default'}
    assert r['availability'] == 'unknown_where_modeled'
    windows['B']['x'] = {'WD_FirstBus': '0500', 'WD_LastBus': '1125'}
    r = snapshot_estimate(route, net, windows, RoutingParameters(), f)
    assert 'outside_historical_window' in r['exclusion_reasons']


def test_same_vehicle_and_all_candidates_participate(tiny):
    net, windows, route = tiny
    routes = [Route('o', 'z', [Leg('A', 'o', 'z', 13, 7.5)]), route,
              Route('o', 'z', [route.legs[0], Leg('C', 'x', 'z', 6, 7.5, 3)])]
    f = forecasts([record(arrivals=[arrival()])])
    rows = [dict(snapshot_estimate(r, net, windows, RoutingParameters(), f), id=str(i)) for i, r in enumerate(routes)]
    choices = projected_choices(rows, net, ['0'])
    assert len(choices) == 1
    assert {o['service'] for o in choices[0]['alternatives']} == {'A', 'B', 'C'}
    stay = next(o for o in choices[0]['alternatives'] if o['continuing'])
    assert stay['new_transfer'] is False
    assert stay['wait_including_buffer_minutes'] == stay['new_boarding_delay_minutes'] == 0
    assert rows[0]['estimated_total_minutes'] == 19.5 and rows[0]['snapshot_boardings'] == 1


def test_snapshot_load_cutoff_and_invalid_timestamps(tmp_path):
    path = tmp_path/'fixture.jsonl'
    rows = [record(), record('x', received=T+timedelta(seconds=2))]
    path.write_text('\n'.join(map(json.dumps, rows)))
    _, decision, source = load_snapshot(path)
    assert decision == T+timedelta(seconds=2) and source['observation_count'] == 2
    assert source['new_api_calls'] == 0 and len(source['raw_sha256']) == 64
    rows[0]['requested_at'] = (T+timedelta(seconds=5)).isoformat()
    path.write_text('\n'.join(map(json.dumps, rows)))
    with pytest.raises(ValueError, match='before request'):
        load_snapshot(path)


def test_end_to_end_offline_reproducible_and_explicit_search_states(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('No network allowed')
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    source = tmp_path/'synthetic.jsonl'
    source.write_text(json.dumps(record('42161'))+'\n')
    settings = Settings(max_transfers=2)
    a = run(tmp_path/'a', source, settings)
    b = run(tmp_path/'b', source, settings)
    assert a == b and a['status'] == 'completed' and a['recommendable_count'] > 0
    for filename in ('reference.json', 'report.md'):
        assert (tmp_path/'a'/filename).read_bytes() == (tmp_path/'b'/filename).read_bytes()
    assert len(a['shortlist']) == 8
    assert any('106-D1' in r['services'] and r['recommendable'] for r in a['candidates'])
    assert all(not r['recommendable'] for r in a['candidates'] if '106A-D1' in r['services'])
    assert a['projected_choices']
    for row in a['candidates']:
        assert row['snapshot_boardings'] == 0
        assert row['estimated_total_minutes'] == pytest.approx(row['model_only_total_minutes'])
    same = run(tmp_path/'same', source, settings, destination='42161')
    assert same['candidates'][0]['estimated_total_minutes'] == 0
    none = run(tmp_path/'none', source, settings, origin='16159', destination='42161')
    assert none['status'] == 'no_route_in_declared_network'
    cap = run(tmp_path/'cap', source, Settings(max_candidates=1))
    assert cap['status'] == 'search_budget_exceeded' and not cap['candidate_search_complete']
    assert not cap['candidates'] and not cap['preferences']

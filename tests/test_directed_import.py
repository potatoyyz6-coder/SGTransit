from dataclasses import asdict

import pytest

from data.real.build_subset import RAW, load_rows
from experiments.local_planner import LocalPlanner
from experiments.station_networks import imported_bundle
from sg_transit.directed_import import import_patterns
from sg_transit.models import validate_route


def stops():
    return [dict(BusStopCode=s, Description=s, Longitude='103.8', Latitude='1.3') for s in 'ABCD']


def pattern(codes, service='7', direction='1'):
    return [dict(ServiceNo=service, Direction=direction, StopSequence=str(i+1), BusStopCode=s,
                 Distance=str(i*.5), WD_FirstBus='0600', WD_LastBus='2300') for i,s in enumerate(codes)]


def test_import_events_preserves_order_direction_and_onboard_identity():
    rows = pattern('ABCD') + pattern('DCBA', direction='2')
    imported = import_patterns(stops(), list(reversed(rows)), [('7','1'),('7','2')])
    assert imported.network.services['7-D1'].stops == tuple('ABCD')
    assert imported.network.services['7-D2'].stops == tuple('DCBA')
    assert imported.network.services['7-D1'].ride_time('A','D') == 4.5
    assert [e.sequence for e in imported.events['7-D1']] == [1,2,3,4]
    assert all(e.visit == 1 for e in imported.events['7-D1'])
    assert imported.windows['7-D1']['B']['WD_LastBus'] == '2300'
    assert not imported.gaps


def test_loop_is_not_deduplicated_or_split_into_new_boardings():
    imported = import_patterns(stops(), pattern('ABAC'), [('7','1')])
    assert [e.stop for e in imported.events['7-D1']] == list('ABAC')
    assert [e.visit for e in imported.events['7-D1']] == [1,1,2,1]
    assert not imported.network.services
    assert imported.gaps == [dict(service='7-D1',reason='repeated_stop_events_not_supported',event_count=4)]
    assert len(imported.source_patterns['7-D1']['ordered_source_rows']) == 4


def test_missing_pattern_or_intermediate_event_is_a_coverage_gap():
    rows = pattern('ABCD')
    result = import_patterns(stops(), [rows[0],rows[2],rows[3]], [('7','1'),('8','1')])
    assert not result.network.services
    assert {g['reason'] for g in result.gaps} == {'pattern_missing','missing_intermediate_sequence'}
    assert [e.sequence for e in result.events['7-D1']] == [1,3,4]


@pytest.mark.parametrize('field,value', [('StopSequence','1'),('Distance','-1'),('Distance','nan'),('BusStopCode','NO')])
def test_bad_source_is_not_silently_repaired(field, value):
    rows = pattern('ABC')
    rows[1][field] = value
    with pytest.raises(ValueError):
        import_patterns(stops(), rows, [('7','1')])


def test_expanded_network_all_original_events_and_provenance():
    bundle = imported_bundle('service97')
    network, windows, _, source = bundle
    full = load_rows(RAW/'BusRoutes.csv')
    assert len(network.stops) == 102 and len(network.services) == 2
    assert source['stop_event_count'] == 103 and not source['coverage_gaps']
    for direction in ('1','2'):
        rows = sorted([r for r in full if r['ServiceNo']=='97' and r['Direction']==direction],
                      key=lambda r:int(r['StopSequence']))
        key = f'97-D{direction}'
        assert network.services[key].stops == tuple(r['BusStopCode'] for r in rows)
        assert len(windows[key]) == len(rows)
    assert len(source['event_inventory_sha256']) == len(source['network_sha256']) == 64
    assert source['api_calls'] == 0


def test_new_corridor_multiple_pairs_without_hardcoded_answers():
    planner = LocalPlanner(provider_factory=lambda: pytest.fail('API forbidden'))
    network = imported_bundle('service97')[0]
    for service in network.services.values():
        for start, end in ((0,12),(8,23),(19,35)):
            origin, destination = service.stops[start], service.stops[end]
            result = planner.plan(dict(query_type='stations',network='service97',
                origins=[dict(stop=origin)], destinations=[dict(stop=destination)],
                departure_time='2026-10-26T10:00'))
            assert result['eligible_count'] > 0 and result['info']['requests'] == 0
            state = planner.state(result['plan_id'])
            assert any(route.services == (service.id,) for route in state['data'][5])
            for route in state['data'][5]:
                validate_route(route, network)
                assert (route.origin, route.destination) == (origin,destination)
                assert route.transfers <= 5
            direct = next(r for r in state['rows'] if r['services']==[service.id])
            assert direct['transfers']==0 and direct['wait_minutes']==7.5 and direct['delay_minutes']==1.5
            assert direct['ride_minutes'] == pytest.approx(service.ride_time(origin,destination))

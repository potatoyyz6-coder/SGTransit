from dataclasses import asdict
from datetime import datetime
import json

import pytest

from experiments.local_planner import LocalPlanner, UserError
from sg_transit.models import Leg, Route, Stop, TransitNetwork, TransitService
from sg_transit.route_combinations import CombinationIndex
from sg_transit.snapshot_reference import SGT


def fixture():
    net = TransitNetwork([Stop(s, s) for s in 'ABCDEFXY'], [
        TransitService('1-D1', ('A', 'B', 'C', 'D', 'E'), (1, 1, 1, 1), 15),
        TransitService('2-D1', ('B', 'X', 'D'), (1, 1), 15),
        TransitService('3-D1', ('D', 'F', 'E'), (1, 1), 15),
        TransitService('1-D2', ('E', 'D', 'C', 'B', 'A'), (1, 1, 1, 1), 15),
        TransitService('4-D1', ('D', 'E'), (1,), 15),
    ])
    def route(*legs):
        return Route(legs[0][1], legs[-1][2], [Leg(s, a, b, net.services[s].ride_time(a, b)) for s, a, b in legs])
    entries = [
        ('r1', route(('1-D1', 'A', 'E'))),
        ('r2', route(('1-D1', 'A', 'B'), ('2-D1', 'B', 'D'), ('4-D1', 'D', 'E'))),
        ('r3', route(('1-D1', 'A', 'D'), ('3-D1', 'D', 'E'))),
    ]
    return net, entries, route


def test_prefix_direction_branch_selection_and_no_stitching():
    net, entries, route = fixture()
    index = CombinationIndex(net, entries)
    view = index.view('A', 'E')
    assert view['frontier']['id'] == 'B'
    assert view['compatible_count'] == 3
    choices = [b for b in view['nodes'] if b['kind'] == 'choice']
    stay, transfer = sorted(choices, key=lambda b: b['service'])
    assert stay['action'] == 'continue' and transfer['action'] == 'transfer'
    branch = index.view('A', 'E', selection=[transfer['branch']])
    assert branch['routes'] == ['r2'] and branch['terminal']
    with pytest.raises(ValueError, match='incompatible'):
        index.view('A', 'E', selection=[transfer['branch'], stay['branch']])
    assert all('3-D1' != b['service'] for b in branch['nodes'])
    reverse = route(('1-D2', 'E', 'A'))
    index = CombinationIndex(net, entries+[('reverse', reverse)])
    assert index.view('E', 'A')['routes'] == ['reverse']
    with pytest.raises(ValueError):
        index.view('E', 'A', selection=[transfer['branch']])


def test_rejoin_distinguishes_arrival_vehicle_and_preserves_originals():
    net, _, route = fixture()
    entries = [('stay', route(('2-D1', 'B', 'D'), ('1-D1', 'D', 'E'))),
               ('ride', route(('1-D1', 'B', 'E')))]
    before = [asdict(r) for _, r in entries]
    index = CombinationIndex(net, entries)
    merged = next(n for n in index.view()['nodes'] if n['kind'] == 'rejoin')
    assert merged['service'] == '1-D1'
    assert merged['entry_states'] == dict(continue_count=1, transfer_count=1, board_count=0)
    assert before == [asdict(r) for _, r in entries]
    inspected = index.view(inspect=dict(segment=merged['id'], service='1-D1'))
    assert set(inspected['routes']) == {'stay', 'ride'} and inspected['reference_count'] == 2
    with pytest.raises(ValueError, match='not in'):
        index.view(inspect=dict(segment=merged['id'], service='3-D1'))


def test_single_empty_and_same_stop():
    net, entries, _ = fixture()
    assert CombinationIndex(net, []).view()['compatible_count'] == 0
    same = CombinationIndex(net, [('same', Route('A', 'A', []))]).view()
    assert same['terminal'] and same['nodes'] == [] and same['routes'] == ['same']
    one = CombinationIndex(net, entries[:1]).view()
    assert one['terminal'] and one['nodes'][0]['stop_count'] == 5
    expanded = CombinationIndex(net, entries[:1]).view(expand=0)
    assert [s['id'] for s in expanded['expanded']['stops']] == list('ABCDE')


@pytest.mark.parametrize('args', [dict(selection=[True]), dict(selection='x'), dict(choice_page=-1),
    dict(route_page=True), dict(route_page=100), dict(expand=100), dict(stop_page=-1)])
def test_invalid_controls(args):
    net, entries, _ = fixture()
    with pytest.raises(ValueError):
        CombinationIndex(net, entries).view(**args)


def test_no_cycle_or_reboarding_imported():
    net, _, route = fixture()
    invalid = route(('1-D1', 'A', 'B'), ('2-D1', 'B', 'D'), ('1-D1', 'D', 'E'))
    with pytest.raises(ValueError, match='Repeated'):
        CombinationIndex(net, [('bad', invalid)])
    cycle = route(('1-D1', 'A', 'E'), ('1-D2', 'E', 'A'))
    with pytest.raises(ValueError, match='revisits'):
        CombinationIndex(net, [('bad', cycle)])


def test_pagination_keeps_every_route_and_stop():
    codes = [str(i) for i in range(100)]
    services = [TransitService(f'{i}-D1', tuple(codes), (1,)*99, 15) for i in range(12)]
    net = TransitNetwork([Stop(s, s) for s in codes], services)
    entries = [(str(i), Route('0', '99', [Leg(s.id, '0', '99', 99)])) for i, s in enumerate(services)]
    index = CombinationIndex(net, entries)
    first = index.view()
    assert first['choice_count'] == 12 and first['hidden_choices'] == 4
    assert len(first['nodes']) == 1 and len(first['nodes'][0]['options']) == 8
    assert len(index.view(choice_page=1)['nodes'][0]['options']) == 4
    assert index.view(choice_page=1)['hidden_choices'] == 8
    assert set(first['routes']+index.view(route_page=1)['routes']) == {rid for rid, _ in entries}
    stops = []
    for page in range(5):
        v = index.view(expand=0, stop_page=page)
        assert v['displayed_nodes'] <= 60
        stops += [s['id'] for s in v['expanded']['stops']]
    assert stops == codes


@pytest.mark.parametrize('case', ['school', 'home'])
def test_real_cases_all_candidates_unchanged_offline(case):
    def forbidden():
        pytest.fail('No API allowed')
    planner = LocalPlanner(now=lambda: datetime(2026, 10, 23, 10, tzinfo=SGT), provider_factory=forbidden)
    plan = planner.plan(dict(case=case, mode='model'))
    state = planner.state(plan['plan_id'])
    before = json.dumps(state['rows'], sort_keys=True)
    view = planner.combinations(dict(plan_id=plan['plan_id']))
    assert view['compatible_count'] == plan['eligible_count']
    index = state['combination_index']
    assert set(index.route_ids) == {r['id'] for r in state['rows'] if r['recommendable']}
    assert before == json.dumps(state['rows'], sort_keys=True)
    assert view == planner.combinations(dict(plan_id=plan['plan_id']))
    for row in view['routes']:
        assert row == planner.detail(dict(plan_id=plan['plan_id'], route_id=row['id']))
    assert view['displayed_nodes'] <= 60
    if case == 'home':
        assert any(any(a[2] == '12061' for a in path) for path in index.paths.values())
        assert any(n.get('alternatives') for n in view['nodes'] if n['kind'] == 'rejoin')
        block = next(n for n in view['nodes'] if n['kind'] == 'rejoin')
        option = block['alternatives'][0]
        filtered = planner.combinations(dict(plan_id=plan['plan_id'], inspect=dict(
            segment=block['id'], service=option['service'])))
        assert filtered['reference_count'] == option['count']
        assert all(any(l['service_id'] == option['service'] for l in r['legs']) for r in filtered['routes'])


def test_custom_od_scope_and_expiry():
    planner = LocalPlanner(now=lambda: datetime(2026, 10, 23, 10, tzinfo=SGT))
    plan = planner.plan(dict(query_type='stations', network='school', mode='model',
        origins=[dict(stop='42161'), dict(stop='28109')], destinations=[dict(stop='16159')],
        departure_time='2026-10-23T10:00'))
    view = planner.combinations(dict(plan_id=plan['plan_id'], origin='28109', destination='16159'))
    assert len(view['groups']) == 2
    assert all(row['origin'] == '28109' and row['access_minutes'] is None for row in view['routes'])
    with pytest.raises(UserError):
        planner.combinations(dict(plan_id=plan['plan_id'], origin='x', destination='16159'))
    planner.clock = lambda: float('inf')
    with pytest.raises(UserError, match='过期'):
        planner.combinations(dict(plan_id=plan['plan_id']))


def test_large_shared_corridor_pages_expand_without_moving_boundaries():
    stops = tuple(str(i) for i in range(100))
    net = TransitNetwork([Stop(s, s) for s in ('O',)+stops], [
        TransitService('X-D1', ('O', '0'), (.5,), 15),
        TransitService('Y-D1', ('O', '0'), (.5,), 15),
        TransitService('C-D1', stops, (.5,)*99, 15),
        TransitService('D-D1', stops, (.5,)*99, 15),
    ])
    entries = [(f'{first}-{i}', Route('O', '99', [Leg(first, 'O', '0', .5),
        Leg('C-D1', '0', str(i), i*.5), Leg('D-D1', str(i), '99', (99-i)*.5)]))
        for first in ('X-D1', 'Y-D1') for i in range(1, 99)]
    index = CombinationIndex(net, entries)
    first = index.view()
    assert first['graph_pages'] > 1 and first['hidden_nodes'] > 0
    seen = []
    for page in range(first['graph_pages']):
        view = index.view(graph_page=page)
        ids = [n['id'] for n in view['nodes']]
        seen.extend(ids)
        expanded = index.view(graph_page=page, expand=ids[-1])
        assert [n['id'] for n in expanded['nodes']] == ids
        assert expanded['displayed_nodes'] <= 60
        assert expanded['expanded']['segment'] == ids[-1]
        assert expanded['compatible_count'] == len(entries)
    assert seen == list(range(len(seen)))
    assert set(index.route_ids) == {rid for rid, _ in entries}

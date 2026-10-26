from dataclasses import asdict
from itertools import product
import math
import random

import pytest

from experiments.fragment_index import CachedLegIndex, FragmentIndex
from sg_transit.models import Stop, TransitNetwork, TransitService, validate_route
from sg_transit.routing import RoutingParameters, SearchBudgetExceeded, enumerate_routes, route_key


def network(services):
    stops = sorted({stop for service in services for stop in service.stops})
    return TransitNetwork([Stop(stop, stop) for stop in stops], services)


def equivalent(actual, expected, net, parameters):
    assert [route_key(r) for r in actual] == [route_key(r) for r in expected]
    for route, reference in zip(actual, expected):
        validate_route(route, net)
        assert route.transfers <= parameters.max_transfers
        assert len(route.services) == len(set(route.services))
        assert route.total_minutes == pytest.approx(reference.total_minutes)
        assert route.ride_minutes == pytest.approx(reference.ride_minutes)
        assert route.scheduled_wait_minutes == pytest.approx(reference.scheduled_wait_minutes)
        assert [leg.transfer_minutes for leg in route.legs] == [leg.transfer_minutes for leg in reference.legs]


@pytest.mark.parametrize('index_type', [CachedLegIndex, FragmentIndex])
def test_continuing_at_transfer_limit_and_time_boundary(index_type):
    net = network([TransitService('through', ('A', 'B', 'C', 'D'), (.1, .2, .3), 15, 3)])
    index = index_type(net)
    p = RoutingParameters(max_transfers=0, max_trip_minutes=sum((.1, .2, .3)))
    routes = index.query('A', 'D', p)
    equivalent(routes, enumerate_routes(net, 'A', 'D', p), net, p)
    assert len(routes) == 1 and len(routes[0].legs) == 1
    assert routes[0].scheduled_wait_minutes == 7.5
    assert routes[0].transfers == 0
    assert index.query('A', 'D', RoutingParameters(max_trip_minutes=.59)) == []
    assert index.query('A', 'D', RoutingParameters(
        max_trip_minutes=math.nextafter(sum((.1, .2, .3)), -math.inf))) == []


def test_fragment_storage_retains_shared_services_and_only_adjacent_edges():
    net = network([TransitService('X', ('A', 'B', 'C', 'D'), (1, 2, 3), 10),
                   TransitService('Y', ('A', 'B', 'C'), (2, 3), 12)])
    fragments, legs = FragmentIndex(net), CachedLegIndex(net)
    assert fragments.connection_count == 5
    assert legs.connection_count == 9
    routes = fragments.query('A', 'D')
    assert any(r.services == ('X',) for r in routes)
    assert any(r.services == ('Y', 'X') for r in routes)


@pytest.mark.parametrize('index_type', [CachedLegIndex, FragmentIndex])
def test_transfer_constraints_and_no_reboarding_or_cycles(index_type):
    net = network([TransitService('X', ('A', 'B', 'C', 'D'), (2, 2, 2), 12),
                   TransitService('Y', ('B', 'C'), (1,), 10),
                   TransitService('reverse', ('C', 'A'), (1,), 10)])
    p = RoutingParameters(max_transfers=1)
    routes = index_type(net).query('A', 'D', p)
    equivalent(routes, enumerate_routes(net, 'A', 'D', p), net, p)
    assert all(r.services != ('X', 'Y', 'X') for r in routes)
    assert index_type(net).query('D', 'A', p) == []
    assert len(index_type(net).query('B', 'B', p)) == 1
    with pytest.raises(ValueError, match='Unknown endpoint'):
        index_type(net).query('missing', 'A', p)


def test_detour_is_not_pruned_by_geographic_heading():
    net = TransitNetwork([Stop('A', 'A', 0, 0), Stop('B', 'B', -10, 0), Stop('D', 'D', 1, 0)],
                         [TransitService('detour', ('A', 'B', 'D'), (1, 1), 10)])
    assert FragmentIndex(net).query('A', 'D')[0].services == ('detour',)


@pytest.mark.parametrize('index_type', [CachedLegIndex, FragmentIndex])
def test_five_transfer_limit_and_full_minimum_duration(index_type):
    net = network([TransitService(str(i), (str(i), str(i+1)), (10,), 15) for i in range(7)])
    index = index_type(net)
    assert index.query('0', '7') == []
    assert index.query('0', '7', RoutingParameters(max_transfers=6, max_trip_minutes=87)) == []
    routes = index.query('0', '7', RoutingParameters(max_transfers=6, max_trip_minutes=88))
    assert len(routes) == 1 and routes[0].transfers == 6
    assert routes[0].ride_minutes == 70


@pytest.mark.parametrize('index_type', [CachedLegIndex, FragmentIndex])
def test_budgets_are_explicit_not_empty_routes(index_type):
    net = network([TransitService('X', ('A', 'B', 'C'), (1, 1), 10),
                   TransitService('Y', ('A', 'C'), (3,), 10)])
    index = index_type(net)
    with pytest.raises(SearchBudgetExceeded, match='Expansion'):
        index.query('A', 'C', RoutingParameters(max_expansions=1))
    with pytest.raises(SearchBudgetExceeded, match='Candidate'):
        index.query('A', 'C', RoutingParameters(max_candidates=1))


@pytest.mark.parametrize('index_type', [CachedLegIndex, FragmentIndex])
def test_snapshot_reuse_does_not_rebuild_neighbors_or_read_changed_input(index_type, monkeypatch):
    net = network([TransitService('X', ('A', 'B', 'C'), (1, 1), 10)])
    index = index_type(net)
    before = [asdict(r) for r in index.query('A', 'C')]
    old_hash = index.snapshot_hash
    net.services['X'] = TransitService('X', ('A', 'B', 'C'), (10, 10), 30)
    assert index_type(net).snapshot_hash != old_hash
    monkeypatch.setattr(TransitNetwork, 'neighbors', lambda *_: pytest.fail('Query rebuilt neighbors'))
    assert [asdict(r) for r in index.query('A', 'C')] == before


@pytest.mark.parametrize('seed', range(5))
def test_all_pairs_match_on_small_seeded_directed_networks(seed):
    rng = random.Random(seed)
    stops = list('ABCDEF')
    services = []
    for i in range(5):
        route = tuple(rng.sample(stops, rng.randint(2, 5)))
        services.append(TransitService(str(i), route, tuple(rng.uniform(.5, 4) for _ in route[1:]), 10 + i))
    net = network(services)
    p = RoutingParameters(max_transfers=3, max_candidates=10000, max_expansions=100000)
    indexes = [CachedLegIndex(net), FragmentIndex(net)]
    for start, end in product(net.stops, repeat=2):
        reference = enumerate_routes(net, start, end, p)
        for index in indexes:
            equivalent(index.query(start, end, p), reference, net, p)


def test_repeated_stop_pattern_stays_unsupported_not_silently_split():
    with pytest.raises(ValueError, match='circular'):
        TransitService('loop', ('A', 'B', 'A'), (1, 1), 10)

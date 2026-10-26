import json

import pytest

from experiments.fragment_benchmark import load_case, query_pairs, run
from experiments.fragment_index import FragmentIndex
from sg_transit.routing import RoutingParameters


def test_offline_report_preserves_inputs_and_reproduces_candidates(tmp_path):
    results = [run(tmp_path / str(i), cases=('onboard_continuation',), repeats=1,
                   random_queries=2, make_plot=False) for i in range(2)]
    for result in results:
        assert result['api_calls'] == 0
        assert result['mismatches'] == result['inconclusive'] == 0
        assert len(result['cases'][0]['records']) == 9
        builds = result['cases'][0]['builds']
        assert builds['fragments']['connections'] < builds['cached_legs']['connections']
        assert builds['fragments']['retained_python_bytes'] > 0
    a, b = (r['cases'][0] for r in results)
    assert a['network_sha256'] == b['network_sha256'] and a['queries'] == b['queries']
    assert [(r['candidate_sha256'], r['candidate_count']) for r in a['records']] == [
        (r['candidate_sha256'], r['candidate_count']) for r in b['records']]
    saved = json.loads((tmp_path / '0/experiment.json').read_text())
    assert saved['parameters']['max_transfers'] == 5
    assert (tmp_path / '0/queries.csv').is_file()
    report = (tmp_path / '0/report.md').read_text()
    assert 'not process RSS' in report and 'not observed travel-time' in report


def test_mismatch_cannot_be_reported_as_success(tmp_path, monkeypatch):
    monkeypatch.setattr(FragmentIndex, 'query', lambda *args, **kwargs: [])
    result = run(tmp_path, cases=('onboard_continuation',), repeats=1, random_queries=0, make_plot=False)
    assert result['mismatches'] == 1
    assert result['cases'][0]['records'][2]['matches_reference'] is False


def test_budget_exhaustion_is_inconclusive_not_no_route(tmp_path):
    result = run(tmp_path, cases=('onboard_continuation',), repeats=1, random_queries=0,
                 make_plot=False, parameters=RoutingParameters(max_candidates=1))
    assert result['inconclusive'] == 3 and result['mismatches'] == 0
    for record in result['cases'][0]['records']:
        assert record['status'] == 'budget_exceeded'
        assert record['candidate_count'] is None
        assert record['matches_reference'] is None


def test_workload_seed_and_invalid_parameters(tmp_path):
    net, primary, _ = load_case('shared_corridor')
    first = query_pairs(net, primary, 5, 29)
    assert first == query_pairs(net, primary, 5, 29)
    assert first != query_pairs(net, primary, 5, 30)
    assert first[0] == primary and len(set(first)) == 6
    for kwargs in ({'repeats': 0}, {'random_queries': -1}, {'cases': ()}, {'cases': ('unknown',)}):
        with pytest.raises(ValueError):
            run(tmp_path, make_plot=False, **kwargs)

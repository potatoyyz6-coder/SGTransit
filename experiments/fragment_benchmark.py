"""Offline three-arm experiment: rebuilt routing, cached legs, adjacent fragments."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import gc
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import random
import statistics
from time import perf_counter
import tracemalloc

from experiments.blk18_cde_case import Settings, build_network, DISCLAIMER
from experiments.corridor_search import scenario
from experiments.fragment_index import CachedLegIndex, FragmentIndex, network_hash, network_record
from sg_transit.models import validate_route
from sg_transit.routing import RoutingParameters, SearchBudgetExceeded, enumerate_routes, expected_time, route_key

OUTPUT = Path(__file__).resolve().parents[1] / 'results/fragment_benchmark'
CASES = ('shared_corridor', 'onboard_continuation', 'candidate_loss', 'blk18_cde')
METHODS = ('rebuild', 'cached_legs', 'fragments')


def load_case(name):
    if name == 'blk18_cde':
        net, _, _, provenance = build_network(Settings())
        return net, ('42161', '16159'), provenance
    net, _ = scenario(name)
    return net, ('O', 'D'), {'data_kind': 'synthetic', 'source': 'experiments.corridor_search.scenario'}


def query_pairs(network, primary, count, seed):
    candidates = [(a, b) for a in sorted(network.stops) for b in sorted(network.stops)
                  if a != b and (a, b) != primary]
    rng = random.Random(seed)
    rng.shuffle(candidates)
    return [primary, *candidates[:count]]


def timed(function):
    started = perf_counter()
    result = function()
    return (perf_counter() - started) * 1000, result


def allocations(function):
    if tracemalloc.is_tracing():
        raise RuntimeError('Run allocation measurement outside another tracemalloc session')
    gc.collect()
    tracemalloc.start()
    try:
        result = function()
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, current, peak


def invoke(function):
    stats = {}
    try:
        routes = function(stats)
        return {'status': 'complete', 'routes': routes, 'stats': stats}
    except SearchBudgetExceeded as exc:
        return {'status': 'budget_exceeded', 'routes': None, 'stats': stats, 'reason': str(exc)}


def route_metrics(route, network):
    return (route.ride_minutes, route.scheduled_wait_minutes, route.total_minutes,
            expected_time(route, network), route.transfers,
            sum(leg.transfer_minutes for leg in route.legs))


def describe(outcome, network, parameters):
    result = {key: value for key, value in outcome.items() if key != 'routes'}
    if outcome['status'] != 'complete':
        return {**result, 'candidate_count': None, 'candidate_sha256': None}
    routes = outcome['routes']
    for route in routes:
        validate_route(route, network)
        minimum = 0.0
        for leg in route.legs:
            minimum = minimum + leg.transfer_minutes + leg.ride_minutes
        if minimum > parameters.max_trip_minutes or route.transfers > parameters.max_transfers:
            raise AssertionError('Candidate violates the declared minimum-time/transfer bound')
    keys = [route_key(route) for route in routes]
    if len(keys) != len(set(keys)):
        raise AssertionError('Duplicate route emitted')
    return {**result, 'candidate_count': len(routes), 'candidate_sha256':
            hashlib.sha256(json.dumps(keys, separators=(',', ':')).encode()).hexdigest()}


def compare(reference, actual, network):
    if reference['status'] != 'complete' or actual['status'] != 'complete':
        return None
    left, right = reference['routes'], actual['routes']
    if [route_key(r) for r in left] != [route_key(r) for r in right]:
        return False
    return all(all(math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)
                   for a, b in zip(route_metrics(x, network), route_metrics(y, network)))
               for x, y in zip(left, right))


def run_case(name, *, repeats, random_queries, seed, parameters):
    network, primary, provenance = load_case(name)
    indexes, builds = {}, {'rebuild': {'median_ms': 0.0, 'samples_ms': [],
                                    'retained_python_bytes': 0, 'peak_python_bytes': 0}}
    for method, cls in (('cached_legs', CachedLegIndex), ('fragments', FragmentIndex)):
        samples = []
        for _ in range(repeats):
            elapsed, index = timed(lambda: cls(network))
            samples.append(elapsed)
        del index
        index, retained, peak = allocations(lambda: cls(network))
        indexes[method] = index
        builds[method] = {'median_ms': statistics.median(samples), 'samples_ms': samples,
                          'retained_python_bytes': retained, 'peak_python_bytes': peak,
                          'connections': index.connection_count}
    pairs = query_pairs(network, primary, random_queries, seed)
    records = []
    order_rng = random.Random(seed)
    for origin, destination in pairs:
        functions = {'rebuild': lambda stats: enumerate_routes(network, origin, destination, parameters, stats=stats)}
        functions.update({method: (lambda stats, index=index: index.query(origin, destination, parameters, stats=stats))
                          for method, index in indexes.items()})
        # Correctness and allocation passes are outside the timed measurements.
        baseline = invoke(functions['rebuild'])
        reference = describe(baseline, network, parameters)
        metadata = {}
        for method, function in functions.items():
            outcome, retained, peak = allocations(lambda: invoke(function))
            metadata[method] = {**describe(outcome, network, parameters),
                                'matches_reference': compare(baseline, outcome, network),
                                'query_peak_python_bytes': peak,
                                'query_retained_python_bytes': retained}
            del outcome
        del baseline
        timings = {method: [] for method in METHODS}
        for _ in range(repeats):
            order = list(METHODS)
            order_rng.shuffle(order)
            for method in order:
                elapsed, outcome = timed(lambda: invoke(functions[method]))
                check = describe(outcome, network, parameters)
                if (check['status'], check['candidate_sha256']) != (
                        metadata[method]['status'], metadata[method]['candidate_sha256']):
                    raise AssertionError('Non-reproducible route result')
                timings[method].append(elapsed)
                del outcome
        for method in METHODS:
            records.append({'case': name, 'origin': origin, 'destination': destination,
                            'method': method, **metadata[method], 'samples_ms': timings[method],
                            'median_query_ms': statistics.median(timings[method]),
                            'reference_candidate_count': reference['candidate_count']})
    return {'name': name, 'provenance': provenance, 'network_sha256': network_hash(network),
            'network': network_record(network), 'queries': pairs, 'builds': builds, 'records': records}


def write_report(experiment, output):
    lines = ['# Adjacent-fragment index experiment', '',
             'Offline topology/model comparison, not observed travel-time improvement.', '',
             '## Method', '',
             '- `rebuild`: unchanged production enumerate_routes, including graph reconstruction each query.',
             '- `cached_legs`: reuse all downstream ride connections and their graph; a caching control.',
             '- `fragments`: reuse only adjacent, service-labeled connections; merge same-service continuation.',
             '- Both experimental arms share a traversal implementation; cached_legs also caches traversed stops.',
             '- No completed routes, destination bounds, ETA, or live vehicle identities are cached.',
             '- Every query recomputes the reverse optimistic ride-time bound. No geographic-heading pruning.',
             '- Indexes freeze input records; changed topology/timing requires rebuilding the index.',
             '- Same transfer, minimum-time and count budgets; expansion units differ between representations.',
             '- Compare full route keys AND ride/wait/buffer/expected costs, not merely the fastest route.',
             '- Numerical pruning tolerance never relaxes the completed-route minimum-time limit.', '',
             '## Measurement', '',
             f"- {experiment['repeats']} repeats; seeded shuffled method order; correctness/allocation passes warm the process first.",
             '- Build samples include snapshot hashing and graph preparation, but exclude file loading/imports.',
             '- Warm query samples exclude build, correctness validation, plotting and tracemalloc overhead.',
             '- Allocation figures are separately measured Python tracemalloc bytes, not process RSS/native memory.',
             '- Query allocation excludes the retained index and input network, but includes output routes.',
             '- Workload time is the SUM of per-query medians, not a timed end-to-end batch.',
             '- First-workload estimate = median build + sum of query medians; not application startup latency.',
             '- Seeded OD workload includes unreachable pairs; this is not representative passenger demand.', '',
             '## Results', '',
             '| Network | Method | Connections | Build ms | Workload ms | First workload ms | Match / total | Max query Python KiB | Index Python KiB |',
             '| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |']
    failures, gaps = 0, 0
    for case in experiment['cases']:
        for method in METHODS:
            rows = [r for r in case['records'] if r['method'] == method]
            build = case['builds'][method]
            warm = sum(r['median_query_ms'] for r in rows)
            matched = sum(r['matches_reference'] is True for r in rows)
            failures += sum(r['matches_reference'] is False for r in rows)
            gaps += sum(r['matches_reference'] is None for r in rows)
            lines.append(f"| {case['name']} | {method} | {build.get('connections', 'rebuilt')} | "
                         f"{build['median_ms']:.3f} | {warm:.3f} | {build['median_ms'] + warm:.3f} | "
                         f"{matched}/{len(rows)} | {max(r['query_peak_python_bytes'] for r in rows)/1024:.1f} | "
                         f"{build['retained_python_bytes']/1024:.1f} |")
    lines += ['', f'Candidate/cost mismatches: **{failures}**. Inconclusive method/query comparisons: **{gaps}**.', '',
              'A budget-exceeded query is inconclusive, not unreachable or an empty successful result.', '',
              '## Interpretation and limits', '',
              'Compare fragments against BOTH controls. Beating rebuild alone does not establish that',
              'fragment search is better than ordinary caching. Reuse shifts work into index creation',
              'and consumes retained memory; adjacent expansion can visit more intermediate states.',
              'Repeated-query gains do not imply a faster first query or faster actual bus journeys.', '',
              'Small millisecond differences are descriptive measurements, not statistical evidence',
              'of a speed advantage. Five repeats on these small networks do not establish scaling.', '',
              'The local case preserves all declared direction fragments, including limited 106A,',
              'solely to compare topology enumeration. Operating windows, fare continuity, live arrivals',
              'and catch probabilities are not evaluated. Minimum-time bounds omit random waiting.',
              'One-pattern repeated stops remain unsupported by the existing model; cycles across',
              'services and reboarding are rejected. This is not an all-island or timetable solver.', '',
              'Timing and allocation results depend on Python, hardware, GC and tracing behavior.',
              'The workload, network hashes, candidate hashes and route counts are reproducible;',
              'milliseconds and allocation byte counts are not guaranteed identical across runs.', '',
              '## Reproduce', '', '```sh', 'python -m experiments.fragment_benchmark', '```', '',
              'Default parameters: 5 repeats, seed 29, 5 seeded additional OD pairs per case.',
              'See experiment.json for exact inputs, per-query budgets, build samples, hashes and provenance;',
              'queries.csv contains per-method/query results. JSON/CSV are generated locally and Git-ignored.', '',
              DISCLAIMER]
    (output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return failures, gaps


def plot(experiment, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names = [case['name'] for case in experiment['cases']]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2))
    fig.subplots_adjust(left=.08, right=.99, bottom=.18, top=.82, wspace=.30)
    colors = ('#56646c', '#176b50', '#ae4561')
    for i, (method, color) in enumerate(zip(METHODS, colors)):
        warm = [sum(r['median_query_ms'] for r in case['records'] if r['method'] == method)
                for case in experiment['cases']]
        first = [x + case['builds'][method]['median_ms'] for x, case in zip(warm, experiment['cases'])]
        for ax, values in zip(axes, (warm, first)):
            ax.bar([j + (i-1)*.25 for j in range(len(names))], values, .25, label=method, color=color)
    for ax, title in zip(axes, ('Warm workload: sum of query medians', 'First workload estimate: build + queries')):
        ax.set_title(title, fontsize=11)
        ax.set_yscale('log')
        ax.set_ylabel('Milliseconds (log scale; lower is better)')
        ax.set_xticks(range(len(names)), [n.replace('_', '\n') for n in names], fontsize=9)
        ax.legend(fontsize=8)
    fig.suptitle('Offline routing computation only; not bus journey duration', fontsize=12, y=.97)
    fig.savefig(output / 'comparison.png', dpi=160)
    plt.close(fig)


def run(output=OUTPUT, *, repeats=5, random_queries=5, seed=29, cases=CASES,
        parameters=None, make_plot=True):
    if repeats < 1 or random_queries < 0 or not cases or any(c not in CASES for c in cases):
        raise ValueError('Use positive repeats, nonnegative query count and known cases')
    p = parameters or RoutingParameters(max_candidates=10000, max_expansions=100000)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    source_files = ('experiments/fragment_index.py', 'experiments/fragment_benchmark.py',
                    'src/sg_transit/routing.py', 'src/sg_transit/models.py')
    experiment = {'schema_version': 1, 'repeats': repeats, 'random_queries': random_queries,
                  'seed': seed, 'parameters': asdict(p), 'api_calls': 0,
                  'source_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                    for name in source_files},
                  'environment': {'python': platform.python_version(), 'system': platform.system(),
                                  'machine': platform.machine(), 'networkx': version('networkx')}, 'cases': []}
    for name in cases:
        experiment['cases'].append(run_case(name, repeats=repeats, random_queries=random_queries,
                                            seed=seed, parameters=p))
    failures, gaps = write_report(experiment, output)
    experiment['mismatches'], experiment['inconclusive'] = failures, gaps
    (output / 'experiment.json').write_text(json.dumps(experiment, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    rows = [r for case in experiment['cases'] for r in case['records']]
    fields = ('case', 'origin', 'destination', 'method', 'status', 'candidate_count',
              'matches_reference', 'candidate_sha256', 'median_query_ms', 'query_peak_python_bytes')
    with (output / 'queries.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    if make_plot:
        plot(experiment, output)
    return experiment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--random-queries', type=int, default=5)
    parser.add_argument('--seed', type=int, default=29)
    parser.add_argument('--cases', nargs='+', choices=CASES, default=CASES)
    args = parser.parse_args()
    result = run(**vars(args))
    print(json.dumps({'cases': len(result['cases']), 'mismatches': result['mismatches'],
                      'inconclusive': result['inconclusive'], 'api_calls': 0,
                      'report': str(args.output / 'report.md')}))
    if result['mismatches'] or result['inconclusive']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

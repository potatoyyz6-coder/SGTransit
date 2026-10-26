"""Offline provenance and display-cost checks; never collect arrivals."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time
import tracemalloc

from experiments.local_planner import LocalPlanner, ROOT
from sg_transit.route_combinations import CombinationIndex
from sg_transit.snapshot_reference import SGT


def run():
    def forbidden():
        raise AssertionError('API collection forbidden in this experiment')
    planner = LocalPlanner(now=lambda: datetime(2026, 10, 23, 10, tzinfo=SGT), provider_factory=forbidden)
    jobs = [('school', dict(case='school')), ('home', dict(case='home')),
            ('custom', dict(query_type='stations', network='school',
                origins=[dict(stop='42161'), dict(stop='28109')],
                destinations=[dict(stop='16159')], departure_time='2026-10-23T10:00'))]
    output = []
    for label, body in jobs:
        plan = planner.plan({**body, 'mode': 'model'})
        state = planner.state(plan['plan_id'])
        network, _, _, source, _, routes, _ = state['data']
        before = json.dumps(state['rows'], sort_keys=True)
        entries = [(row['id'], route) for row, route in zip(state['rows'], routes) if row['recommendable']]
        start = time.perf_counter()
        index = CombinationIndex(network, entries)
        build_ms = (time.perf_counter()-start)*1000
        state['combination_index'] = index
        elapsed = []
        for _ in range(5):
            start = time.perf_counter()
            view = planner.combinations(dict(plan_id=plan['plan_id']))
            elapsed.append((time.perf_counter()-start)*1000)
        tracemalloc.start()
        allocated = CombinationIndex(network, entries)
        retained, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert set(index.route_ids) == set(allocated.route_ids) == {rid for rid, _ in entries}
        assert json.dumps(state['rows'], sort_keys=True) == before
        # Every route can be reached through legal child choices, including
        # variants that never appeared in the homepage shortlist.
        reached = []
        stack = list(index.roots.values())
        while stack:
            node = index.nodes[stack.pop()]
            reached.extend(node.terminal)
            stack.extend(node.children.values())
        assert sorted(reached) == sorted(index.route_ids)
        output.append(dict(case=label, candidates=len(routes), eligible=len(entries),
            groups=len(index.roots), prefix_nodes=len(index.nodes), build_ms=build_ms,
            warm_median_ms=statistics.median(elapsed), warm_ms=elapsed,
            python_retained_bytes=retained, python_peak_bytes=peak,
            response_bytes=len(json.dumps(view, ensure_ascii=False).encode('utf-8')),
            displayed_nodes=view['displayed_nodes'], all_ids_preserved=True,
            original_rows_sha256=hashlib.sha256(before.encode()).hexdigest(),
            network_sha256=source['network_sha256'], api_calls=0))
    paths = ['src/sg_transit/route_combinations.py', 'experiments/local_planner.py',
             'experiments/combinations_check.py']
    return dict(reference_time='2026-10-23T10:00:00+08:00', measured_at=datetime.now(SGT).isoformat(), python=platform.python_version(),
        platform=platform.platform(), rows=output,
        source_sha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths})


def main():
    report = run()
    output = ROOT/'results/route_combinations'
    output.mkdir(parents=True, exist_ok=True)
    (output/'workload.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    lines = ['# Route combination display workload', '',
        'Offline historical topology and assumed timing. Reference: 2026-10-23 10:00 SGT.',
        f"Measured at {report['measured_at']}, unreleased working tree, not a published version.", '',
        '| Case | Candidates | Eligible | OD groups | Build ms | Warm view median ms | Python retained / peak KiB | Response KiB |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in report['rows']:
        lines.append(f"| {r['case']} | {r['candidates']} | {r['eligible']} | {r['groups']} | {r['build_ms']:.1f} | "
                     f"{r['warm_median_ms']:.1f} | {r['python_retained_bytes']/1024:.1f} / "
                     f"{r['python_peak_bytes']/1024:.1f} | {r['response_bytes']/1024:.1f} |")
    lines += ['', 'All original row IDs, cost fields and transfer counts unchanged. API calls: 0.', '',
        '## Method and limits', '',
        '- Route search and reference estimation run before measurement; this measures the display layer only.',
        '- One index build, five warm first-page responses; no browser time or network latency.',
        '- Separate tracemalloc pass measures Python allocations, not total process RSS/native memory.',
        '- Original route objects and topology are excluded from index allocation measurements.',
        '- Response size is UTF-8 JSON for one default OD page, not every possible expansion.',
        '- All terminal route references are checked; paging does not discard underlying candidates.',
        '- No claim of faster journeys, all-island scalability or calibrated catch probability.',
        '- Source/network/row hashes and per-repeat timings are in generated workload.json.', '',
        'Reproduce from repository root: `python -m experiments.combinations_check`.', '']
    (output/'workload.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(report['rows'], indent=2))


if __name__ == '__main__':
    main()

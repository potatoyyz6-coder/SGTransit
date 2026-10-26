"""Offline acceptance workload for selectable endpoints and imported coverage."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time
import tracemalloc

from experiments.blk18_cde_case import ROOT
from experiments.local_planner import LocalPlanner, network_data
from experiments.station_networks import imported_bundle
from sg_transit.models import validate_route


def workload():
    jobs = [('school', '28109', '17159'), ('school','28019','16159'),
            ('home','12061','42171'), ('home','12071','42071')]
    for service in imported_bundle('service97')[0].services.values():
        jobs.extend(('service97',service.stops[a],service.stops[b]) for a,b in ((0,12),(8,23),(19,35)))
    return jobs


def run(repeats=3):
    if not isinstance(repeats, int) or repeats < 1:
        raise ValueError('Positive repeat count required')
    def forbidden():
        raise AssertionError('This experiment must not call an API')
    planner = LocalPlanner(provider_factory=forbidden)
    planner.config()  # File loading and import are outside the query timing.
    rows = []
    for network, origin, destination in workload():
        body = dict(query_type='stations', network=network, origins=[dict(stop=origin)],
                    destinations=[dict(stop=destination)], departure_time='2026-10-26T10:00:00+08:00')
        planner.stations.cache.clear()
        begin = time.perf_counter()
        first = planner.plan(body)
        cold_ms = (time.perf_counter()-begin)*1000
        state = planner.state(first['plan_id'])
        for route in state['data'][5]:
            validate_route(route, state['data'][0])
        signature = lambda r: hashlib.sha256(json.dumps(
            [asdict(x) for x in planner.state(r['plan_id'])['data'][5]], sort_keys=True).encode()).hexdigest()
        digest = signature(first)
        elapsed = []
        for _ in range(repeats):
            start = time.perf_counter()
            again = planner.plan(body)
            elapsed.append((time.perf_counter()-start)*1000)
            if signature(again) != digest:
                raise AssertionError('Repeated query changed candidates')
        planner.plans.clear()
        planner.stations.cache.clear()
        tracemalloc.start()
        measured = planner.plan(body)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        if signature(measured) != digest:
            raise AssertionError('Allocation measurement changed candidates')
        rows.append(dict(network=network,origin=origin,destination=destination,cold_query_ms=cold_ms,
            warm_median_ms=statistics.median(elapsed),warm_samples_ms=elapsed,
            python_query_peak_bytes=peak, candidate_count=first['candidate_count'], eligible_count=first['eligible_count'],
            candidate_sha256=digest,query_sha256=first['query_sha256'],network_sha256=first['topology']['network_sha256'],
            method=first['search']['pairs'][0]['method'],complete=first['search']['complete'],
            expansions=first['search']['expansions'],api_calls=first['info']['requests']))
    paths = ['experiments/station_planner.py','experiments/local_planner.py','experiments/station_networks.py',
             'src/sg_transit/station_catalog.py','src/sg_transit/directed_import.py','experiments/station_planning_check.py']
    return dict(data_kind='offline_historical_topology_and_assumed_timing', departure='2026-10-26T10:00:00+08:00',
                repeats=repeats,python=platform.python_version(),platform=platform.platform(),rows=rows,
                source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path, default=ROOT/'results/station_planning')
    args = parser.parse_args()
    result = run(args.repeats)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'workload.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    text = ['# Selectable-station workload', '',
        'Offline, frozen historical topology. Reference departure: 2026-10-26 10:00 SGT.',
        'Not a live journey, timetable validation, or comparison with external navigation products.', '',
        '| Network | Origin | Destination | Candidates | Eligible | Method | Cold ms | Warm median ms | Python peak KiB |',
        '| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |']
    for row in result['rows']:
        text.append(f"| {row['network']} | {row['origin']} | {row['destination']} | {row['candidate_count']} | "
                    f"{row['eligible_count']} | {row['method']} | {row['cold_query_ms']:.1f} | "
                    f"{row['warm_median_ms']:.1f} | {row['python_query_peak_bytes']/1024:.1f} |")
    text.extend(['', 'All returned routes validated; repeated queries retained identical candidate hashes. API calls: 0.',
        '', '## Measurement limits', '',
        '- One cold query and three warm repeats by default, after loading topology and the catalog.',
        '- Query timing includes reference estimates, grouping and response construction, not browser rendering.',
        '- Allocation is a separate cold-query tracemalloc pass; not RSS or native memory. Input topology is excluded.',
        '- Warm reuse caches topology candidates only. Date/readiness/window estimates are recomputed.',
        '- Larger networks use bounded corridor discovery, not exhaustive search or an optimality guarantee.',
        '- Ordinary enumeration is complete only inside the declared network and configured constraints.',
        '- These small directed networks do not establish all-island performance. Repeated-stop patterns remain unsupported.',
        '- Full inputs, source/query/network hashes and per-query measurements are in locally generated workload.json.',
        '', 'Reproduce: `python -m experiments.station_planning_check`.', '',
        'This project is an independent research project and is not affiliated with,',
        'endorsed by, or sponsored by the Land Transport Authority of Singapore,',
        'Google, or Citymapper.', ''])
    (args.output/'workload.md').write_text('\n'.join(text),encoding='utf-8')
    print(f'Wrote {args.output}; {len(result["rows"])} offline endpoint checks')


if __name__ == '__main__':
    main()

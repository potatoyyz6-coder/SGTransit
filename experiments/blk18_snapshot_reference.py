"""Rank the Blk 18 case using a saved departure-time snapshot. No network access."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from data.real.build_subset import RAW, load_rows
from experiments.blk18_cde_case import (
    ROOT, ORIGIN, DESTINATION, LIMITED, DISCLAIMER, Settings, build_network, route_text,
)
from sg_transit.eta_matching import instant
from sg_transit.reference import shortlist
from sg_transit.routing import SearchBudgetExceeded, enumerate_routes
from sg_transit.snapshot_reference import FrozenForecasts, pattern_bindings, projected_choices, snapshot_estimate

INPUT = ROOT / 'data/recorded/raw/blk18_cde_20261008_1120.jsonl'
OUTPUT = ROOT / 'results/blk18_cde_snapshot_20261008_1120'


def load_snapshot(path):
    raw = Path(path).read_bytes()
    rows = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    observations = [(str(i), r) for i, r in enumerate(rows, 1) if r.get('type') == 'observation']
    if not observations:
        raise ValueError('No observations in snapshot')
    for _, record in observations:
        if instant(record['requested_at']) > instant(record['received_at']):
            raise ValueError('Response received before request')
    decision = max(instant(r['received_at']) for _, r in observations)
    metadata = next((r for r in rows if r.get('type') == 'metadata'), {})
    completion = next((r for r in reversed(rows) if r.get('type') == 'completion'), {})
    provenance = dict(raw_sha256=hashlib.sha256(raw).hexdigest(), input_name=Path(path).name,
        source=metadata.get('source'), endpoint=metadata.get('endpoint'),
        collected_from=min(instant(r['received_at']) for _, r in observations).isoformat(),
        collected_through=decision.isoformat(), collection_status=completion.get('status', 'incomplete_or_unknown'),
        observation_count=len(observations), successful_observations=sum(r['status'] == 'ok' for _, r in observations),
        processing='Frozen forecasts; line numbers are 1-based; entries 0-based; no vehicle matching',
        new_api_calls=0, new_collection_scheduled=False)
    return observations, decision, provenance


def run(output=OUTPUT, snapshot=INPUT, settings=Settings(), *, origin=ORIGIN, destination=DESTINATION):
    observations, decision, source = load_snapshot(snapshot)
    network, windows, patterns, topology = build_network(settings)
    bindings = pattern_bindings(patterns, load_rows(RAW / 'BusRoutes.csv'))
    forecasts = FrozenForecasts(observations, decision, bindings)
    parameters, stats = settings.routing(), {}
    report = dict(schema_version=1, origin=origin, destination=destination,
        decision_at=forecasts.decision.isoformat(), day=forecasts.day,
        settings={k: v for k, v in asdict(settings).items() if k not in {'day', 'departure'}},
        parameters=asdict(parameters), forecast_freshness_seconds=90,
        provenance=source, topology=topology, bindings=bindings,
        search=stats, candidate_search_complete=False, candidates=[], shortlist=[])
    routes = []
    try:
        routes = enumerate_routes(network, origin, destination, parameters, stats=stats)
        report.update(status='completed' if routes else 'no_route_in_declared_network', candidate_search_complete=True)
    except SearchBudgetExceeded as exc:
        report.update(status='search_budget_exceeded', error=str(exc))
    for i, route in enumerate(routes, 1):
        row = snapshot_estimate(route, network, windows, parameters, forecasts, limited=LIMITED)
        row.update(id=f'R{i:05d}', text=route_text(row, network))
        report['candidates'].append(row)
    records = report['candidates']
    eligible = [r for r in records if r['recommendable']]
    report['shortlist'] = shortlist(records)
    order = lambda r: (r['estimated_total_minutes'], r['transfers'], r['id'])
    report['preferences'] = {label: min(eligible, key=key)['id'] for label, key in (
        ('estimated_fastest', order),
        ('fewest_transfers', lambda r: (r['transfers'], *order(r))),
        ('least_outdoor_wait', lambda r: (r['wait_minutes']+r['buffer_minutes'], *order(r))),
    )} if eligible else {}
    report['recommendable_count'] = len(eligible)
    report['exclusion_counts'] = dict(Counter(x for r in records for x in r['exclusion_reasons']))
    report['fallback_boarding_counts'] = dict(Counter(l['fallback_reason'] for r in records for l in r['legs'] if l['fallback_reason']))
    report['projected_choices'] = projected_choices(records, network, report['preferences'].values())
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'reference.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    (output / 'report.md').write_text(render(report, network), encoding='utf-8')
    return report


def render(report, network):
    lookup = {r['id']: r for r in report['candidates']}
    name = lambda s: f'{network.stops[s].name} ({s})'
    lines = ['# Blk 18: historical snapshot-conditioned route references', '', DISCLAIMER, '',
        f"Departure / frozen knowledge cutoff: **{report['decision_at']}**; day: {report['day']}.",
        f"{name(report['origin'])} -> {name(report['destination'])}.",
        'The cutoff is the LAST response receipt, not the scheduled 11:20:00 start. No response from after this cutoff is used.',
        'No new API calls. This is a saved forecast plus a ride/wait model, NOT current navigation or an observed journey.', '',
        f"Search: {report['status']}; complete within declared bounds: {report['candidate_search_complete']}. Candidates: {len(lookup)}; reference-eligible: {report['recommendable_count']}.",
        'All candidates, exclusions, per-leg sources and service-sequence variants remain in reference.json.',
        f"Exclusions (overlap): {json.dumps(report['exclusion_counts'], sort_keys=True)}.", '',
        '## Route comparison', '',
        'Both columns use the SAME route and riding/delay assumptions. A difference is not measured time saved.',
        'Wait excludes the separately charged transfer buffer; delay is charged once per boarding.', '',
        '| ID | Services | Snapshot + model min | Model only min | Difference | Ride | Wait | Buffer | Delay | ETA / modeled boardings |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
    for family in report['shortlist']:
        r = lookup[family['representative_id']]
        lines.append(f"| {r['id']} | {' -> '.join(r['services']) or 'Already there'} | {r['estimated_total_minutes']:.2f} | {r['model_only_total_minutes']:.2f} | {r['difference_from_model_minutes']:+.2f} | {r['ride_minutes']:.2f} | {r['wait_minutes']:.2f} | {r['buffer_minutes']:.2f} | {r['delay_minutes']:.2f} | {r['snapshot_boardings']} / {r['modeled_boardings']} |")
    lines += ['', '## Preference references', '',
        'These are separate reference choices, not a calibrated risk ranking. Waiting preference includes transfer buffer, excludes modeled boarding delay.', '']
    for preference, identifier in report['preferences'].items():
        r = lookup[identifier]
        lines.append(f"- {preference}: {identifier}, {' -> '.join(r['services'])}; {r['estimated_total_minutes']:.2f} min, {r['transfers']} transfers, {r['wait_minutes']+r['buffer_minutes']:.2f} min wait including buffer.")
    for family in report['shortlist']:
        r = lookup[family['representative_id']]
        lines += ['', f"### {r['id']}: {' -> '.join(r['services']) or 'Already there'}", '',
            f"Estimated arrival: {r['estimated_arrival_at']}. Timing/availability: {r['availability']}. Eligible stop variants: {len(family['variant_ids'])}.", '',
            '| Service | Board -> alight | Predicted/model board -> model alight | Wait | Timing source | Monitored |',
            '| --- | --- | --- | ---: | --- | --- |']
        for leg in r['legs']:
            label = leg['timing_source'] + (f" ({leg['fallback_reason']})" if leg['fallback_reason'] else '')
            lines.append(f"| {leg['service_id']} | {name(leg['board_stop'])} -> {name(leg['alight_stop'])} | {leg['board_at'][11:19]} -> {leg['alight_at'][11:19]} | {leg['wait_minutes']:.2f} | {label} | {leg['monitored']} |")
    lines += ['', '## Projected along-the-way alternatives', '',
        'All eligible candidates participate, not only the displayed families. Options share the same travelled service/stop prefix.',
        'These are projected choices using the departure snapshot, NOT new observations at the future stop. Total means the complete trip from the origin.',
        'Continue on the same vehicle: zero new waiting, boarding delay or transfer. No service-count bonus; no claim of independent arrivals.', '',
        '| Reference | Stop / onboard | Action | Best candidate for action | Total min | New wait incl. buffer | Source |',
        '| --- | --- | --- | --- | ---: | ---: | --- |']
    for item in report['projected_choices']:
        for option in item['alternatives']:
            action = ('Stay on ' if option['continuing'] else 'Transfer to ') + option['service']
            lines.append(f"| {item['reference_id']} | {name(item['stop'])} / {item['onboard']} | {action} | {option['candidate_id']} | {option['total_minutes']:.2f} | {option['wait_including_buffer_minutes']:.2f} | {option['timing_source']} |")
    lines += ['', '## Assumptions and missing evidence', '',
        '- Direction binding uses historical full-service endpoints plus stop visit ordinal, not service number alone. Mismatches fall back to a model; they do not prove no service.',
        '- Select the earliest matching ETA after modeled readiness including the transfer buffer. Monitored=True, False and unknown are preserved; none establishes an actual arrival.',
        '- Snapshot freshness is tested at the departure cutoff (90 seconds), not against future simulated stop times. Forecast lead time can still be long and uncertain.',
        '- No eligible slot beyond the saved horizon, missing service, stale/error response or unknown pattern: use headway/2 and label availability unknown. No invented vehicle departure or catch probability.',
        '- 106 has missing predictions in this capture: its valid topology alternatives are retained with modeled timing. 106A remains limited and excluded from default references.',
        '- Riding remains distance-based. The same extra mean boarding-delay allowance is retained for both columns; it is NOT calibrated forecast error and may overlap uncertainty already represented by the ETA.',
        '- Do not match a bus at different stops using NextBus/NextBus2 rank. No vehicle identity or cross-stop ETA-derived riding time is used.',
        '- Selecting the earliest forecast and a mean ride is a heuristic, not an optimal time-dependent policy. Forecast differences across stops can change the chosen transfer stop without proving it is better.',
        '- Historical operating windows are checked at each estimated boarding; missing windows retain topology but exclude default references. Model limits are not verified fare rules.',
        '- Existing strict retrospective replay, offline reports and local synthetic examples are unchanged. No Google comparison or real journey outcome is inferred.', '',
        '## Reproduce and provenance', '',
        '`python -m experiments.blk18_snapshot_reference`', '',
        'Requires the local ignored snapshot file; the command does not fetch missing data. Synthetic unit fixtures exercise the same logic without credentials.',
        f"Raw SHA256: `{report['provenance']['raw_sha256']}`.",
        f"Source: {report['provenance']['source']}; endpoint: {report['provenance']['endpoint']}.",
        f"Receipt range: {report['provenance']['collected_from']} to {report['provenance']['collected_through']}.",
        f"Model settings: `{json.dumps(report['settings'], sort_keys=True)}`.",
        'reference.json records topology hashes, matching bindings, complete candidates, per-leg evidence line/entry references, exclusions and search statistics.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=INPUT)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    for field in ('speed_kmh', 'headway', 'delay_max', 'transfer_buffer'):
        parser.add_argument('--'+field.replace('_', '-'), type=float, default=getattr(Settings(), field))
    args = vars(parser.parse_args())
    snapshot, output = args.pop('snapshot'), args.pop('output')
    report = run(output, snapshot, Settings(**args))
    print(json.dumps({k: report[k] for k in ('status', 'decision_at', 'recommendable_count', 'preferences')}, indent=2))
    return 0 if report['candidate_search_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

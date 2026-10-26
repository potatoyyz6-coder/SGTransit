"""Small additional declared networks imported from the frozen local source."""
from dataclasses import asdict
from functools import lru_cache
import hashlib
import json

from data.real.build_subset import RAW, load_rows
from experiments.blk18_cde_case import ROOT
from sg_transit.directed_import import import_patterns

EXTRA_NETWORKS = {
    'service97': dict(label='97 全方向 · 历史拓扑扩展', patterns=(('97','1'), ('97','2'))),
}


@lru_cache(maxsize=2)
def imported_bundle(name):
    spec = EXTRA_NETWORKS[name]
    manifest_path = ROOT/'data/real/sources.json'
    source = json.loads(manifest_path.read_text(encoding='utf-8'))
    hashes = {name: hashlib.sha256((RAW/name).read_bytes()).hexdigest() for name in ('BusStops.csv','BusRoutes.csv')}
    if hashes != source['raw_sha256']:
        raise ValueError('Frozen source hash mismatch')
    imported = import_patterns(load_rows(RAW/'BusStops.csv'), load_rows(RAW/'BusRoutes.csv'), spec['patterns'])
    inventory = {key: [asdict(e) for e in events] for key, events in imported.events.items()}
    provenance = dict(data_kind='historical_topology_with_assumed_timing', source_url=source['source_url'],
        raw_urls=source['raw_urls'], accessed_at=source['accessed_at'], source_commit=source['commit'],
        raw_sha256=hashes, sources_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        scope='Only the explicitly selected complete directed service patterns; not all-island coverage',
        selected_patterns=spec['patterns'], stop_event_count=sum(map(len, imported.events.values())),
        event_inventory_sha256=hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest(),
        coverage_gaps=imported.gaps, processing='Preserve service/direction/sequence/visit; exclude unsupported repeated-stop patterns without splitting',
        assumed_timing=dict(speed_kmh=20, min_segment_minutes=.5, headway_minutes=15, delay_max_minutes=3),
        api_calls=0, new_collection_scheduled=False)
    payload = dict(events=inventory, services=[asdict(s) for s in imported.network.services.values()],
                   stops=[asdict(s) for s in imported.network.stops.values()], provenance=provenance)
    provenance['network_sha256'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    # This network is offline-only; do not infer ETA bindings for unsupported patterns.
    return imported.network, imported.windows, {}, provenance

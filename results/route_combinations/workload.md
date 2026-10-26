# Route combination display workload

Offline historical topology and assumed timing. Reference: 2026-10-23 10:00 SGT.
Measured at 2026-10-26T14:01:40.211698+08:00, unreleased working tree, not a published version.

| Case | Candidates | Eligible | OD groups | Build ms | Warm view median ms | Python retained / peak KiB | Response KiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| school | 7212 | 4558 | 1 | 138.3 | 6.3 | 11636.2 / 11636.8 | 39.3 |
| home | 66 | 66 | 1 | 1.7 | 0.5 | 198.2 / 200.4 | 31.8 |
| custom | 11272 | 6629 | 2 | 206.2 | 16.9 | 15872.7 / 15873.3 | 33.2 |

All original row IDs, cost fields and transfer counts unchanged. API calls: 0.

## Method and limits

- Route search and reference estimation run before measurement; this measures the display layer only.
- One index build, five warm first-page responses; no browser time or network latency.
- Separate tracemalloc pass measures Python allocations, not total process RSS/native memory.
- Original route objects and topology are excluded from index allocation measurements.
- Response size is UTF-8 JSON for one default OD page, not every possible expansion.
- All terminal route references are checked; paging does not discard underlying candidates.
- No claim of faster journeys, all-island scalability or calibrated catch probability.
- Source/network/row hashes and per-repeat timings are in generated workload.json.

Reproduce from repository root: `python -m experiments.combinations_check`.

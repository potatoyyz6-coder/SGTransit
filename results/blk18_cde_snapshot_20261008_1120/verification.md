# Snapshot reference verification

Verified locally on 2026-10-08. No new API calls or collection tasks.

## Scope

- New frozen-forecast estimator: `src/sg_transit/snapshot_reference.py`.
- New standalone case: `python -m experiments.blk18_snapshot_reference`.
- New tests: `tests/test_snapshot_reference.py`.
- README documents reproduction, numerical references and timing limitations.
- Existing offline case, adaptive policy and strict ETA replay code unchanged.

## Tests

`python -m pytest tests/test_snapshot_reference.py -q -p no:cacheprovider`

16 passed in 2.04 seconds. The initial sandbox run passed 14 tests but could
not create pytest temporary directories for two tests; the approved outside-
sandbox rerun passed all 16. This was a filesystem setup failure, not a route failure.

`python -m pytest -q -p no:cacheprovider`

243 passed in 26.09 seconds.

Coverage includes causal receipt cutoff, latest-error handling, freshness,
transfer readiness, later ETA slot selection, monitoring flags, missing forecasts,
expired forecasts, exhausted horizons, malformed ETA, direction/visit mismatch,
full-pattern endpoint/loop visit binding, historical operating windows,
trip/gap/transfer bounds, model fallback without topology deletion,
same-vehicle continuation, alternatives from undisplayed candidates,
same endpoint, no route, explicit search-budget exhaustion, and deterministic
artifacts with urllib and socket connections prohibited.

## Saved-data run and audit

- Ran the standalone command successfully against the saved 25-stop snapshot.
- Departure and knowledge cutoff: 2026-10-08T11:20:01.741685+08:00.
- 7,212 full candidates; 4,558 eligible; eight distinct displayed service families.
- Independently parsed every candidate in the saved JSON and checked component
  sums, boarding after readiness, eligible operating windows and complete family
  variant membership.
- Checked all 14,478 forecast boarding references against the exact raw line and
  entry: receipt no later than cutoff, exact ETA, direction endpoint/visit binding.
- Checked all 24,969 model boarding references have fallback reasons and no
  invented selected prediction. These counts repeat evidence across candidates;
  they are not counts of independent buses or observed journeys.
- Checked projected alternative IDs exist; staying onboard has zero new wait,
  zero new boarding delay and no new transfer.
- Read the complete generated Markdown report, including transfer stop names,
  forecast/model sources, missing 106 coverage and preference choices.
- Raw input SHA256 remains
  `d626c6afd63fd49475aa52c155e42caa204b74d1077b8cb5ec37a0fda8f41474`.

The fastest reference is 173 -> 188 at 40.29 minutes, versus 40.50 for
173 -> 183. This small modeled difference does not establish actual superiority.
The 183 prediction used is unmonitored. Riding and boarding delay remain modeled;
the 96 connection via Clementi falls beyond the forecast horizon. No measured
journey time, calibrated catch probability or Google comparison is claimed.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

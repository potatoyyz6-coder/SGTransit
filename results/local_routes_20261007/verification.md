# Verification

Scope: one specified home OD plus twenty seeded random local OD pairs, automatic
transfer search, common-world fixed/dynamic comparisons and bounded home timing
sensitivity. No live data collection or Google comparison.

## Completed Checks

- `python -m experiments.local_routes` completed all 21 base queries and four
  home sensitivity variants, with 1,000 held-out worlds per case. No failed query
  was replaced. The manifest was saved before evaluating results.
- `python -m pytest -q -p no:cacheprovider --basetemp tmp/pytest_local_full_20261007_b`:
  **186 passed in 16.45 seconds**, including eight new local-route tests.
- Tests ran outside the Windows filesystem sandbox with permission because of
  its previously verified pytest temporary-directory access failure.
- Frozen CSV hashes checked at load. Source-code hashes saved in manifest and
  independently verified after execution.
- Sample sizes and strata verified: seven zero-transfer, seven one-transfer,
  six two-transfer OD pairs plus the specified home case. Each stratum agrees
  with minimum transfers from actual route enumeration under the declared model.
- All candidates checked against the original, uncompressed stop sequences for
  legal direction, connectivity, riding time and no repeated stop/service pattern.
- All graph candidate-closure audits pass; dynamic graph recombination does not
  grant paths absent from the fixed candidate pool.
- Blk 109 to Pei Hwa direction verified for 61, 52, 184 and 75. Candidate tests
  explicitly include 151/61 direct and 151/52-or-184-or-75/174 alternatives.
- Dynamic world-0 example routes are actual executed decisions. Continuing on
  the same service is merged into one ride; sample transfer counts match the
  resulting ride-leg counts. Examples are not reconstructed from aggregate counts.
- Tests reject network requests in the experiment path and retain search budget
  failures as errors without resampling. A later execution budget error does not
  incorrectly label a completed candidate search incomplete.
- Independently read 25 JSON/NPZ pairs and verified **200,000 strategy-world
  outcome records**, selected training winners, actual example durations/counts,
  completion fractions, means, P95 and total = wait + buffer + ride.
  These are paired policy outputs, not 200,000 independent measured trips.

## Limits

The 96 stops and 16 direction-specific service segments are a selected historical
local network, not the whole island or all routes in either neighborhood. Only
12 declared nodes permit transfers; all retained original stops can be sampled
as endpoints. Search permits at most two transfers. No walking connections.
The 500-candidate/30,000-expansion cap was not reached in this run, but completeness
applies only within that restricted model.

Travel speeds, headways, delay distributions and buffers remain assumptions.
Sensitivity tests vary those assumptions, not measured travel conditions. Mean
improvements were limited, and reliable did not improve the home base P95.
Lower station waiting sometimes worsened total time and P95. Negative cases
are retained in the full report and the overview.

New code is confined to `experiments/local_routes.py` and its tests. README and
new result directories were updated; existing data, algorithms, recorded ETA
files and prior experiment results were not overwritten. No credentials read,
no API calls, no running collectors or test processes, and no broad Git staging
or commits. The existing uncommitted workspace remains intact.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

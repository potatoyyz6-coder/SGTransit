# Verification: adjacent-fragment experiment

Date: 2026-10-24 (Asia/Singapore).

- Local experiment branch: `codex/fragment-index-experiment`, based on public
  commit `35bdab47079b0db0082d2767539993f50e9d3639`.
- Existing routing, CLI, local planner and historical reports were not changed.
  Only independent experimental modules/tests and documentation were added.
- No LTA/Google API calls, collection schedules, remote publication or deployment.
- Full suite: `python -m pytest -q -p no:cacheprovider --tb=short`:
  **278 passed in 40.91s**. The test fixture prohibits external networking.
- Focused coverage includes all endpoint pairs in five seeded small directed
  networks, continued riding at the transfer cap, floating-point time boundaries,
  forbidden reboarding/cycles, detours, unknown/unreachable/equal endpoints,
  explicit budget exhaustion, snapshot isolation, deterministic candidate hashes,
  and deliberate benchmark mismatch injection.
- Default experiment: four networks, six OD pairs each, three methods, five
  timing repeats. **Zero route/cost mismatches and zero inconclusive comparisons.**
- The 42161 -> 16159 primary query returns the same 7,212 topology candidates
  in every arm. This is not a count of currently operating or fare-valid routes.
- In the 25-stop network, cached downstream connections number 196; adjacent
  fragments number 50. Retained traced Python index memory is about 94.5 KiB
  versus 38.5 KiB. Query peaks remain about 7 MiB, including output routes.
- Local-network workload times are close (about 130/126/125 ms for rebuild,
  cached legs and fragments). These are sums of six query medians, not passenger
  travel times or statistically established speed advantages. The primary query
  alone was about 102/95/103 ms, so fragments did not win every query.
- Runtime allocation checks are separate from timings; they do not measure full
  process RSS. Input network loading is outside all query/build measurements.
- Final chart layout was re-rendered from the saved experiment JSON without
  rerunning or changing the timing samples. Its vertical scale is logarithmic.
- Generated `experiment.json` and `queries.csv` are Git-ignored; the command in
  the report recreates them. Inputs, model parameters, source hashes, workload
  seed, per-query results and environment metadata are retained locally.

Conclusion: the small experiment supports feasibility and smaller reusable
indexes, not a claim that adjacent-fragment routing is generally faster than
ordinary caching. Do not replace production routing on this evidence alone.

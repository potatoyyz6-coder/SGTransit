# Verification: Fair Benchmark and Counterexamples

Verified locally on 2026-10-06. Scope: the requested steps 1 and 2, not a new
real-world calibration, public navigation service, or risk-optimized policy.

## Requirement Evidence

| Requirement | Evidence |
| --- | --- |
| Same network and candidate coverage | Each case JSON includes topology, candidate routes and candidate SHA-256. The structural closure audit rejects any additional path created by shared graph recombination. All eight cases pass. |
| Same costs and constraints | All four labels execute through `sg_transit.benchmark.execute`. Fixed routes restrict the policy to their preselected path. Tests cover buffer accounting, continuation, missed connection, transfer-gap rejection and realized trip overrun. |
| Fair fixed baseline | All candidate routes evaluated on 2,000 training worlds (seed 7001); mean-plus-transfer and P95 winners frozen before 10,000 held-out worlds (seed 9001). All training scores and selected paths retained. |
| First-eligible and downstream-scored strategies | Both use the same full shared graph. Scored decisions call the existing `SharedSuffixPolicy.update`; observations contain only local departures, not future realized delays. |
| Matched random conditions | Same read-only keyed phase/delay arrays passed to every controller in a case. World fingerprints retained; repeatability and service-order independence tested. |
| Independent and correlated arrivals | Independent and synchronized tail services use equal topology and marginal costs; synchronization eliminates the alternative-service benefit. |
| Correlated delay stress | Independent-delay and common-delay pair shares topology, headways, phase groups and eight-minute delay bounds; only delay dependence changes. Not a physical fleet/congestion model. |
| Tight connections | One-minute slack after a three-minute buffer. A hand-computed test checks catching and missing the intended bus; pre-specified diagnostic retained separately from selected baselines. |
| Detour and transfer cost | First-eligible mean 26.15 minutes versus scored/fixed 17.98. Remaining onboard has no additional boarding delay, wait or transfer. |
| Negative results preserved | Synchronized/no-choice controls show no benefit. Mean-tail conflict: scored mean 21.98, P95 39.97; P95-selected fixed mean 26.01, P95 27.80. No universal superiority claim. |
| Reproducible outputs | One command produces eight JSON configurations/results, paired NPZ samples, summary CSV, report and mean/P95 plot. Requires no API credentials or local recorded ETA files. |

## Commands and Checks

```powershell
python -m experiments.fair_benchmark
python -m pytest -q -p no:cacheprovider --basetemp tmp/pytest_fair_full_20261006_a
```

- Full suite: **160 passed in 14.48 seconds**. This includes 25 new benchmark tests.
- Windows sandbox denied pytest temporary-directory access on the initial focused
  run. Tests were rerun outside that sandbox with permission; this was not an
  algorithm failure. No test or experiment process remains running.
- An independent read of all eight saved JSON/NPZ pairs verified **320,000**
  held-out strategy-world outcomes: current source hashes, training winners,
  candidate equality, sample counts, means, nearest-rank P95, total = waiting +
  transfer buffer + riding, long-wait probabilities and paired mean differences.
- All default experiment journeys completed. Separate tests retain infinite
  durations and unknown/bounded risk when constraints prevent completion.
- The single-service control agrees sample by sample. The independent uniform
  wait test matches H/(n+1), not H/n. Synchronized alternatives do not get that
  independent-choice reduction.
- The generated eight-panel PNG was opened and visually inspected; titles,
  labels, mean bars and P95 marks are visible without overlap.
- No LTA/Google calls, credentials, passenger data or Google route content were
  used. Existing ETA recordings and previous experiment outputs were not changed.
- The existing workspace has no commits and files remain untracked; no broad
  staging, cleanup or commit was performed.

## Remaining Limits

These are small synthetic networks, not the Information Technology-to-home
journey forecast. Perfect local departure observations, periodic phases and
once-per-boarding delay are experimental assumptions. Statistical intervals are
conditional Monte Carlo uncertainty, not empirical accuracy or policy-training
uncertainty. Scored decisions still target stationary mean plus transfer penalty,
not P95 or outdoor comfort. No additional real-data collection was authorized.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

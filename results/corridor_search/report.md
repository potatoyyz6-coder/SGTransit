# Destination Corridor Search Audit

Independent synthetic research, stop to stop; not a Singapore ETA claim.
Reproduce: `python -m experiments.corridor_search`.

Selection seed 7; held-out seed 100; future-value quadrature seed 29.
Full search enumerates all legal routes within the stated small-network bounds.
Both adaptive variants use the same local decision rule; neither is a globally optimal policy.

## Search and Candidate Loss

| Case | Full / bounded routes | Full / bounded expansions | Recall | Missed selected reliable route |
| --- | ---: | ---: | ---: | --- |
| shared_corridor | 65 / 17 | 91 / 37 | 0.262 | False |
| onboard_continuation | 30 / 9 | 46 / 30 | 0.300 | False |
| candidate_loss | 5 / 1 | 14 / 4 | 0.200 | True |

Recall counts enumerated route descriptions, not all recombinations in the shared graph.
Ordinary and hub-bypassing candidates are reserved before hub proposals.
Bypassing routes are searched separately; budgets or no such route may prevent retention.

## Held-Out Journey Results

| Case | Strategy | Mean | P90 | P95 | Missed | Completed |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| shared_corridor | shortest_expected | 30.95 | 38.04 | 39.58 | 0.063 | 1.000 |
| shared_corridor | minimum_transfers | 36.06 | 39.25 | 39.62 | 0.000 | 1.000 |
| shared_corridor | minimum_ride | 30.95 | 38.04 | 39.58 | 0.063 | 1.000 |
| shared_corridor | full_fixed_reliable | 30.95 | 38.04 | 39.58 | 0.063 | 1.000 |
| shared_corridor | bounded_fixed_reliable | 30.95 | 38.04 | 39.58 | 0.063 | 1.000 |
| shared_corridor | full_adaptive | 24.79 | 29.80 | 31.74 | 0.000 | 1.000 |
| shared_corridor | bounded_adaptive | 24.79 | 29.80 | 31.74 | 0.000 | 1.000 |
| onboard_continuation | shortest_expected | 20.99 | 25.79 | 26.46 | 0.000 | 1.000 |
| onboard_continuation | minimum_transfers | 20.99 | 25.79 | 26.46 | 0.000 | 1.000 |
| onboard_continuation | minimum_ride | 20.99 | 25.79 | 26.46 | 0.000 | 1.000 |
| onboard_continuation | full_fixed_reliable | 20.99 | 25.79 | 26.46 | 0.000 | 1.000 |
| onboard_continuation | bounded_fixed_reliable | 20.99 | 25.79 | 26.46 | 0.000 | 1.000 |
| onboard_continuation | full_adaptive | 20.99 | 25.79 | 26.46 | 0.000 | 1.000 |
| onboard_continuation | bounded_adaptive | 20.99 | 25.79 | 26.46 | 0.000 | 1.000 |
| candidate_loss | shortest_expected | 21.95 | 37.81 | 39.87 | 0.000 | 1.000 |
| candidate_loss | minimum_transfers | 21.95 | 37.81 | 39.87 | 0.000 | 1.000 |
| candidate_loss | minimum_ride | 21.95 | 37.81 | 39.87 | 0.000 | 1.000 |
| candidate_loss | full_fixed_reliable | 23.97 | 25.58 | 25.79 | 0.000 | 1.000 |
| candidate_loss | bounded_fixed_reliable | 21.95 | 37.81 | 39.87 | 0.000 | 1.000 |
| candidate_loss | full_adaptive | 21.95 | 37.52 | 39.72 | 0.000 | 1.000 |
| candidate_loss | bounded_adaptive | 21.95 | 37.81 | 39.87 | 0.000 | 1.000 |

## Computation and Shared Structure

| Case | Full search ms | Index ms | Bounded query ms | Full / bounded value states |
| --- | ---: | ---: | ---: | ---: |
| shared_corridor | 1.31 | 0.22 | 0.72 | 91 / 91 |
| onboard_continuation | 0.39 | 0.26 | 0.53 | 43 / 43 |
| candidate_loss | 0.22 | 0.16 | 0.11 | 14 / 4 |

These timings are single local runs; fewer expansions do not guarantee lower total latency.
JSON includes compilation/simulation time, shared node/arc counts, unshared segment counts,
local update counts, cache hits, truncation reasons and a fully correlated phase stress test.

## Interpretation

The deliberately narrow candidate_loss configuration can omit the more reliable fixed route.
It is retained as a negative result, not tuned away.
The dynamic objective is estimated remaining time plus a transfer penalty; P95 is measured,
not globally optimized. More alternatives can change both mean and tail behavior.

Future-state values include history but use stationary waits. Actual local arrival clocks
and observed departures are evaluated anew; no per-trip future delay is exposed to decisions.
Continuation on the same bus adds neither a wait nor a boarding delay nor a transfer.

No city-wide performance, fare compliance, or live navigation claim is made.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

# alternative_services

Generated from held-out Monte Carlo samples.

- Origin: `A1`
- Destination: `A6`
- Held-out samples per strategy: `10000`
- Selection seed: `8`
- Held-out evaluation seed: `101`
- Recommended strategy: `reliability_policy`
- Recommended route count: `2`

## Results

| Strategy | Routes | Mean | P90 | P95 | Mean wait | Missed | Invalid | Fare invalid |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_expected_time | 1 | 44.95 | 54.67 | 56.48 | 15.95 | 0.000 | 0.000 | 0.000 |
| minimum_transfers | 1 | 44.95 | 54.67 | 56.48 | 15.95 | 0.000 | 0.000 | 0.000 |
| minimum_ride_time | 1 | 44.95 | 54.67 | 56.48 | 15.95 | 0.000 | 0.000 | 0.000 |
| reliability_policy | 2 | 44.47 | 52.05 | 53.68 | 9.95 | 0.000 | 0.000 | 0.000 |

## Interpretation

The experiment does not force a reliability win. Mean/tail conflicts are reported only when observed in the held-out measurements.

- Executable multi-branch policy: `True`.
- Observed mean/tail conflicts: `0`.
- Reliability-policy P95 change under shared phase: `-2.26` minutes.

## Artifacts

- `alternative_services.summary.json`
- `alternative_services.samples.csv`
- `alternative_services.phase_correlation_1.csv`
- `alternative_services.duration_quantiles.png`
- `alternative_services.waiting_distribution.png`
- `alternative_services.failure_rates.png`
- `alternative_services.network.png`
- `alternative_services.policy.png`
- `alternative_services.phase_correlation_1.png`

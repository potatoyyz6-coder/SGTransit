# single_critical_transfer

Generated from held-out Monte Carlo samples.

- Origin: `S1`
- Destination: `S8`
- Held-out samples per strategy: `10000`
- Selection seed: `7`
- Held-out evaluation seed: `100`
- Recommended strategy: `reliability_policy`
- Recommended route count: `2`

## Results

| Strategy | Routes | Mean | P90 | P95 | Mean wait | Missed | Invalid | Fare invalid |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_expected_time | 1 | 55.89 | 64.54 | 66.34 | 14.89 | 0.000 | 0.000 | 0.000 |
| minimum_transfers | 1 | 55.89 | 64.54 | 66.34 | 14.89 | 0.000 | 0.000 | 0.000 |
| minimum_ride_time | 1 | 63.92 | 73.59 | 76.02 | 20.92 | 0.000 | 0.000 | 0.000 |
| reliability_policy | 2 | 54.51 | 62.81 | 64.88 | 12.95 | 0.000 | 0.000 | 0.000 |

## Interpretation

The experiment does not force a reliability win. Mean/tail conflicts are reported only when observed in the held-out measurements.

- Executable multi-branch policy: `True`.
- Observed mean/tail conflicts: `0`.
- Reliability-policy P95 change under shared phase: `-1.82` minutes.

## Artifacts

- `single_critical_transfer.summary.json`
- `single_critical_transfer.samples.csv`
- `single_critical_transfer.phase_correlation_1.csv`
- `single_critical_transfer.duration_quantiles.png`
- `single_critical_transfer.waiting_distribution.png`
- `single_critical_transfer.failure_rates.png`
- `single_critical_transfer.network.png`
- `single_critical_transfer.policy.png`
- `single_critical_transfer.phase_correlation_1.png`

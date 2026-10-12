# transfer_tradeoff

Generated from held-out Monte Carlo samples.

- Origin: `T1`
- Destination: `T7`
- Held-out samples per strategy: `10000`
- Selection seed: `9`
- Held-out evaluation seed: `102`
- Recommended strategy: `reliability_policy`
- Recommended route count: `2`

## Results

| Strategy | Routes | Mean | P90 | P95 | Mean wait | Missed | Invalid | Fare invalid |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_expected_time | 1 | 33.55 | 51.64 | 53.84 | 0.99 | 0.000 | 0.000 | 0.000 |
| minimum_transfers | 1 | 33.55 | 51.64 | 53.84 | 0.99 | 0.000 | 0.000 | 0.000 |
| minimum_ride_time | 1 | 33.55 | 51.64 | 53.84 | 0.99 | 0.000 | 0.000 | 0.000 |
| reliability_policy | 2 | 34.88 | 39.38 | 40.58 | 7.00 | 0.000 | 0.000 | 0.000 |

## Interpretation

The experiment does not force a reliability win. Mean/tail conflicts are reported only when observed in the held-out measurements.

- Executable multi-branch policy: `True`.
- Observed mean/tail conflicts: `3`.
- Reliability-policy P95 change under shared phase: `-4.97` minutes.

## Artifacts

- `transfer_tradeoff.summary.json`
- `transfer_tradeoff.samples.csv`
- `transfer_tradeoff.phase_correlation_1.csv`
- `transfer_tradeoff.duration_quantiles.png`
- `transfer_tradeoff.waiting_distribution.png`
- `transfer_tradeoff.failure_rates.png`
- `transfer_tradeoff.network.png`
- `transfer_tradeoff.policy.png`
- `transfer_tradeoff.phase_correlation_1.png`

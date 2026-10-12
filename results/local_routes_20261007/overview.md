# Local Route Experiment: Result Overview

This is a frozen-topology simulation, not a measured journey or live forecast.
No LTA/Google API was called. Full route details are in [report.md](report.md).

## Design

- 96 real stop IDs, 16 directed service segments from existing local CSV files.
- Information Technology (16189) to Signature Pk Condo (42171) is the specified case.
- Twenty additional OD pairs sampled before evaluation with seed 20261007:
  seven requiring zero transfers, seven one, six two in the restricted model.
- Sampling pools: 1,215 direct, 588 one-transfer and 78 two-transfer pairs.
- The original home corridor had no minimum-two-transfer pairs. Existing
  Clementi/Jurong East segments were therefore included before sampling, without
  downloading anything or manufacturing a multi-transfer requirement.
- 1,000 test worlds, 256 separate training worlds, 64 separate rollout draws per case.
- All strategies share each query's candidates, constraints and test worlds.
- 12 declared transfer stops; other stops are possible endpoints, but not extra
  transfer opportunities. Original intermediate riding times are retained.
- All 21 base searches and four home sensitivity cases completed within budgets;
  no case was replaced or silently discarded. This is not exhaustive area routing.

## Random Pair Results

Twelve of the twenty random pairs have only one legal route in this model.
Relative to their matching trained fixed baseline:

| Dynamic preference | Metric | Lower | Equal | Higher |
| --- | --- | ---: | ---: | ---: |
| Fast | Mean trip time | 3 | 17 | 0 |
| Cool | Mean station waiting | 3 | 17 | 0 |
| Reliable | P95 trip time | 3 | 17 | 0 |

Equality uses a 1e-8 minute tolerance. These are descriptive point comparisons,
not significance counts. Correlated OD routes and the restricted local sample
cannot establish a Singapore-wide success rate. Different preferences need not
reduce the other metrics.

The three improved fast cases (modeled mean minutes):

| Origin | Destination | Fixed | Dynamic |
| --- | --- | ---: | ---: |
| Aft Kent Ridge Dr (16191) | Bef Seventh-Day Advent Ch (28449) | 58.37 | 56.70 |
| Ctrl Lib (16181) | Nan Hua Pr Sch (20101) | 46.10 | 43.77 |
| Ctrl Lib (16181) | Jurong East Int (28009) | 60.80 | 59.13 |

These all use the same selected corridor, not three independent geographical
replications. Fixed routes and actual dynamic world-0 illustrations include
service numbers, boarding stops and alighting stops in the full report.

## Home Case

All 94 candidates passed direction and original-stop loop validation. The set
includes 151 to Blk 109, then 61 directly, or 52/75/184 to Pei Hwa followed by
an onward service. Staying on 61 through Pei Hwa pays no second boarding cost.

| Strategy | Mean trip | P95 trip | Mean station wait |
| --- | ---: | ---: | ---: |
| Trained fixed fast | 40.58 | 51.17 | 14.79 |
| Dynamic fast | 40.28 | 50.50 | 14.16 |
| Dynamic cool | 41.14 | 53.09 | 11.42 |
| Dynamic reliable | 40.58 | 51.17 | 14.74 |
| First eligible | 44.27 | 56.79 | 9.69 |
| Legacy scorer | 40.25 | 50.50 | 13.98 |

Against fixed fast, dynamic fast improves the mean by only 0.31 minute in this
model. Its paired 95% Monte Carlo mean-difference interval is [-0.40, -0.22].
That interval does not include error in the assumed speeds, headways or delays.

Cool reduces waiting by 3.37 minutes versus its fixed baseline, but adds 0.55
minute of mean trip time and 1.92 minutes of P95. Reliable adds no meaningful
P95 benefit here. The old scorer is slightly faster in mean than the new fast
distributional heuristic; no universal superiority claim is supported.

The 52/75/184 branches are not merely unused route descriptions: dynamic fast
boards them 49 times in total, and cool 96 times, in the 1,000 base worlds.
In this simulation those boardings occur at Bef Dunearn Rd (42141), not Blk 109;
the model often prefers remaining on 151 farther along before transferring.
The Blk 109 alternatives remain available. This is a model outcome, not a
recommendation to change the user's actual boarding habits.

## Home Sensitivity

Each row changes one aspect of the base timing model, holding OD and samples fixed.

| Model | Fixed fast mean/P95 | Dynamic fast mean/P95 | Dynamic cool mean/P95 |
| --- | --- | --- | --- |
| Base: H15, delay max3, buffer3 | 40.58 / 51.17 | 40.28 / 50.50 | 41.14 / 53.09 |
| Headway 20 | 45.36 / 59.27 | 44.47 / 57.47 | 45.21 / 59.89 |
| Delay max 8 | 46.00 / 57.46 | 46.02 / 57.44 | 46.78 / 59.17 |
| Buffer 5 | 42.83 / 53.57 | 42.80 / 53.53 | 43.48 / 55.17 |
| Shared service phase draw | 45.19 / 61.45 | 45.25 / 53.00 | 43.02 / 50.62 |

These contrasting results are retained. Shared phase draws are a synthetic
dependence stress, not a physical congestion or bus-bunching calibration.
The stationary independent rollout model does not infer those correlations.

## Reproduction and Limits

```powershell
python -m experiments.local_routes
```

This overview records the default run, not arbitrary later CLI configurations.
The manifest records all sampled endpoints, frozen source hashes and actual
parameters. Per-case JSON/NPZ files contain training scores, fixed choices,
examples, summaries and paired outcomes; summary.csv permits further analysis.

Search took about 19 milliseconds for the home candidate set on this run;
its training and 1,000-world, eight-strategy batch took about 49 seconds.
These are local diagnostic timings, not a production navigation latency claim.

All times depend on assumed 20km/h speed, at least 0.5 minute per original
segment, stationary headways and boarding delays. No date-specific schedules,
pedestrian links, capacity, actual fare calculation or ETA error calibration.
Station waiting excludes the separately accounted transfer buffer.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

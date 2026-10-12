# Pei Hwa Offline Corridor: 2026-10-01

Information Technology (16189) -> Signature Pk Condo (42171), bus stop to bus stop.
**No API requests, credentials, new ETA samples, or Google content are used by this experiment.**
Departure labels: 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, Singapore (+08:00).

## What These Times Mean

All six slots share one stationary simulation, NOT six measured or scheduled time-of-day predictions.
The calendar date is comparison metadata. There is no date-specific timetable, rush-hour profile,
service calendar or future ETA in this model. Identical slot values are intentional.
Do not compare these means to a Google displayed duration and claim a speed advantage.

Static source access date: 2026-09-27; pinned commit: `5b9ed168436b4efe260feef997e66aa39932996e`.
This access date is not a guarantee that every route operates unchanged on 2026-10-01.
Network SHA256: `2e132dd6b7ab05286d0af9f55bff15e6266da283ef6e2c51ebbc66991f55977c`.
Topology uses the existing raw CSV files; no freshly collected nighttime arrivals were loaded.
Timing assumptions: {"delay_max_minutes": 3.0, "live_api_used": false, "minimum_segment_minutes": 0.5, "speed_kmh": 20.0, "time_of_day_profiles": false, "uniform_headway_minutes": 15.0}.

## Network and Search

47 stops and 10 directed service segments in the base snapshot; not the complete local network.
151 is allowed to continue to Bef Dunearn Rd (42141). 154 reaches 42141 but not Pei Hwa (42071).
52/61/184 connect 12061 to 42071; 61/157/174/970/985 connect 42071 to 42171.
95/970 provides a separate feeder corridor. Same-stop transfers only; no campus walking model.
Full route enumeration: 45018 candidates, 82584 expansions.
Bounded search: 26 candidates, 9409 expansions.
Retained shortest-expected route: True.
Candidate recall: 0.000578; truncation reasons: ['hub_or_corridor_limit', 'prefix_or_ordinary_limit'].
Automatically selected hub IDs: ['42161', '11261'].
Common downstream service sets can select another stop on the same corridor rather than 42071.
Shared retained edges can recombine, so low route-description recall is not policy-path recall.
Full means exhaustive in this selected network and bounds, not a globally optimal stochastic policy.

## Common Held-Out Results

Samples per strategy: 10000; evaluation seed 100;
stationary downstream-value seed 29. Decisions see current-stop departures, not future delays.

| Strategy | Mean | P90 | P95 | Missed target | Completed | Within model limits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| shortest_expected | 40.85 | 49.40 | 51.30 | 0.1005 | 1.0000 | 1.0000 |
| minimum_transfers | 40.85 | 49.40 | 51.30 | 0.1005 | 1.0000 | 1.0000 |
| minimum_ride | 40.85 | 49.40 | 51.30 | 0.1005 | 1.0000 | 1.0000 |
| reference_151_61 | 40.85 | 49.40 | 51.30 | 0.1005 | 1.0000 | 1.0000 |
| reference_95_970 | 54.22 | 62.82 | 64.74 | 0.0942 | 1.0000 | 1.0000 |
| full_adaptive | 40.62 | 48.94 | 50.90 | 0.0749 | 1.0000 | 1.0000 |
| bounded_adaptive | 40.84 | 49.39 | 51.28 | 0.1000 | 1.0000 | 1.0000 |

Missed target is a model-specific counterfactual nominal-departure diagnostic, not a field-measured
probability of being stranded. Adaptive service switching changes the selected target.
Fixed journeys finish even when limits are exceeded; adaptive journeys may stop. Compare
within-model-limit/completion rates before interpreting duration. Uncompleted durations are
infinite internally and non-finite JSON metrics are null; no failures are silently dropped.

### Fixed route structures

- shortest_expected: 151-D2: 16189->12061 | 61-D2: 12061->42171
- minimum_transfers: 151-D2: 16189->12061 | 61-D2: 12061->42171
- minimum_ride: 151-D2: 16189->12061 | 61-D2: 12061->42171
- reference_151_61: 151-D2: 16189->12061 | 61-D2: 12061->42171
- reference_95_970: 95-D1: 16189->11401 | 970-D2: 11401->42171

## Six Requested Departure Slots

| Departure (SGT) | Fixed mean / P95 | Full adaptive mean / P95 | Bounded mean / P95 |
| --- | ---: | ---: | ---: |
| 2026-10-01T10:00:00+08:00 | 40.85 / 51.30 | 40.62 / 50.90 | 40.84 / 51.28 |
| 2026-10-01T12:00:00+08:00 | 40.85 / 51.30 | 40.62 / 50.90 | 40.84 / 51.28 |
| 2026-10-01T14:00:00+08:00 | 40.85 / 51.30 | 40.62 / 50.90 | 40.84 / 51.28 |
| 2026-10-01T16:00:00+08:00 | 40.85 / 51.30 | 40.62 / 50.90 | 40.84 / 51.28 |
| 2026-10-01T18:00:00+08:00 | 40.85 / 51.30 | 40.62 / 50.90 | 40.84 / 51.28 |
| 2026-10-01T20:00:00+08:00 | 40.85 / 51.30 | 40.62 / 50.90 | 40.84 / 51.28 |

## Sensitivity, Not Fitted Traffic

The timing alternatives below are assumed scenarios, not measured peak/off-peak profiles.
Each is replanned and evaluated without Google data; none is assigned to a departure hour.

| Assumptions | Fixed mean / P95 | Full adaptive mean / P95 | Bounded mean / P95 |
| --- | ---: | ---: | ---: |
| slow_15kmh_headway20 | 52.41 / 66.83 | 51.50 / 65.13 | 51.50 / 65.13 |
| fast_25kmh_headway10 | 31.91 / 38.85 | 31.91 / 38.85 | 31.91 / 38.85 |

## Paired Differences

Negative durations favor the left-hand strategy. Bootstrap intervals only describe
Monte Carlo uncertainty in this assumed model, not real-world timing uncertainty.

```json
{
  "bounded_adaptive": {
    "definition": "left minus right; negative means lower duration",
    "mean_difference": -0.005789397630559901,
    "mean_ci95": [
      -0.012374651433743979,
      3.829313184561641e-06
    ],
    "p95_difference": -0.02383510463180727,
    "p95_ci95": [
      -0.06559842744004651,
      7.105427357601002e-15
    ],
    "resamples": 400,
    "seed": 801
  },
  "full_adaptive": {
    "definition": "left minus right; negative means lower duration",
    "mean_difference": -0.22826550971616125,
    "mean_ci95": [
      -0.250748235437253,
      -0.203588157509736
    ],
    "p95_difference": -0.4028019778947467,
    "p95_ci95": [
      -0.5257241366879247,
      -0.2814655306010534
    ],
    "resamples": 400,
    "seed": 801
  },
  "bounded_minus_full_adaptive": {
    "definition": "left minus right; negative means lower duration",
    "mean_difference": 0.2224761120856014,
    "mean_ci95": [
      0.19823839889077988,
      0.24542886712877388
    ],
    "p95_difference": 0.37896687326293943,
    "p95_ci95": [
      0.2542124716943624,
      0.5007317334654537
    ],
    "resamples": 400,
    "seed": 801
  }
}
```

## Google Reference Pending

No new Google observations have been entered. The old 2026-09-28 screenshots are not
relabelled as October 1. `google_manual_template.csv` is intentionally blank except for
endpoints, departure times and the frozen model hash.
Manually record route services, boarding/transfer stops, displayed duration, walking
duration and observation time. Keep screenshots and large responses out of this repository.
Walking or a different boarding stop means the result is not a matched stop-to-stop comparison.
Future-date Google planned routes can be recorded before the departure date; this runner
does not access Google or turn its durations into model parameters.

## Limits and Reproduction

`python -m experiments.pei_hwa_case run` rebuilds the frozen offline snapshot, runs
the base/pressure/sensitivity comparisons and writes the six-slot report. Existing manual
Google entries are not overwritten. There is no network request on build/run paths.
All service calendars, congestion profiles and actual fares remain unmodeled.
Independent service phases can overstate the benefit of alternatives; JSON includes a
fully synchronized-phase pressure comparison (not a measured congestion model).
Local value heuristics optimize estimated remaining time plus transfer penalties, not global P95.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

# Information Technology to Signature Pk Condo

## Case

- Origin: Information Technology, stop 16189.
- Destination: Signature Pk Condo, stop 42171.
- Requested departure: 2026-09-28 16:00, Singapore time.
- Endpoints and calendar date supplied by the user; the screenshot itself
  shows route times but does not show endpoints or the date.
- Google reference, manually transcribed: 151 -> 61, 50 minutes;
  151 -> walk -> 174/970, 54 minutes; 151 -> walk -> 157/174,
  58 minutes (3 minutes walking shown); 95 -> 970, 67 minutes.
  Slash-separated labels are preserved without inferring an exact journey.
  The two options starting at 16:30 are not included in this comparison.
  No screenshot or Google response payload has been copied into the repo.

## Model and Results

This is a 47-stop corridor subset with 151-D2, 95-D1, 61-D2 and
970-D2. It allows at most one same-stop transfer and no access/egress
walking. The cross-stop walking itineraries in the screenshot and other
area services are not modeled. Nine fixed routes were evaluated.

LTA ETA snapshots were collected three times, one minute apart, at 16189,
11401 and 12061 on 2026-09-28 between 13:00:08 and 13:02:09 (+08:00).
Median headways applied (minutes): 151 14.68, 95 12.00, 61 15.16,
970 15.21. Each has only 2-3 clustered predicted arrival gaps.
These are short-window ETA predictions, not observed vehicle passage
times, a complete day's distribution, or a 16:00 schedule.

The 16:00 simulation extrapolates those midday headways; it retains
the existing 20 km/h distance-to-ride-time assumption, 3-minute
transfer buffer and uniform 0-3 minute delay per leg.

| Strategy | Mean minutes | P90 | P95 | Simulated missed-connection rate |
| --- | ---: | ---: | ---: | ---: |
| Shortest expected time | 40.62 | 48.87 | 51.00 | 9.90% |
| Minimum transfers | 40.62 | 48.87 | 51.00 | 9.90% |
| Minimum ride time | 40.62 | 48.87 | 51.00 | 9.90% |
| Reliability selection | 40.62 | 48.87 | 51.00 | 9.90% |

All four strategies use 151 then 61. The reliability selection is a
single route, transferring at Blk 116 (12071). The shortest-time
baseline transfers at Blk 109 (12061). Their outcomes are numerically
equivalent under the model's constant-speed and shared-service-phase
assumptions; tiny floating-point differences are not improvements.
There is **no demonstrated multi-branch advantage in this case**.

For the two screenshot service pairs covered by the subset:

| Service pair | Google displayed minutes | Model mean | Model P95 |
| --- | ---: | ---: | ---: |
| 151 -> 61 | 50 | 40.62 | 51.00 |
| 95 -> 970 | 67 | 52.82 | 62.54 |

For each pair, the model picks its shortest-expected-time same-stop transfer;
the screenshot does not establish Google's exact transfer stop. Thus even
these service-pair comparisons are not verified identical itineraries.

The model mean is 9.38 minutes shorter than Google's displayed 50
minutes, but both use the same service pair. This gap is not evidence
of better routing. It can reflect estimated ride times, midday headways
extrapolated to the afternoon, or random-phase waits versus a specific
departure. Google's displayed total and our Monte Carlo mean/P95 are
different kinds of predictions. The screenshot's 16:16 first boarding
time is visible for its third option only; do not impose it on all routes.

## Reproduce

From the repository root with dependencies installed:

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
python -m experiments.information_technology_case build
python -m experiments.information_technology_case run `
  --network data\real\network_information_technology_lta_midday.json
```

This replays the retained derived network with 512 selection scenarios
(seed 7) and 10,000 held-out evaluation scenarios (seed 100).
The output JSON contains the network SHA256, parameters, candidate
routes, selected policy, API collection window and reference fields.

Local, Git-ignored raw and calibration files:
`data/recorded/raw/information_technology_20260928_midday.json` and
`data/recorded/calibrated/information_technology_20260928_midday.json`.
Recalibrating requires those local files or a fresh authorized collection.

Next validation should inspect the detailed 151 -> 61 itinerary's
boarding time, transfer station and in-vehicle times; improve travel-time
estimates independently of Google rather than tuning to its 50 minutes.
Adding verified pedestrian links is necessary before evaluating the
151 -> 174/970 alternatives as executable strategies.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

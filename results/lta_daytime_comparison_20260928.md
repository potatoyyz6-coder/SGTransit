# Daytime LTA ETA calibration: Ctrl Lib to Jurong East Int

Independent research experiment, not an official journey prediction.

## Data and method

- LTA DataMall Bus Arrival v3, queried at stops 16181, 16009, 17161 and
  28009 every 60 seconds for 12 snapshots, from 2026-09-28 10:01:22 to
  10:12:25 Singapore time. Raw local data:
  `data/recorded/raw/route_headway_daytime_20260928.json`
  (SHA256 `3ed2d3f92c7160dd1940acb8949dfcc3b64005985793900e22ce377b124755ff`).
  Raw ETA snapshots are not included in Git.
- ETA-derived median headways (minutes, observed gaps in parentheses), chosen
  from the earliest observed stop in the modeled direction: 151 at 16181:
  7.60 (3); 10 at 16009: 18.89 (2); 201 at 16009: 12.00 (3);
  105 at 17161: 12.51 (3); 183 at 17161: 7.04 (3).
  The 151 ETA at 16009 and 105 ETA at 28009 are in the opposite direction
  and are not mixed into the selected headways.
- Derived network: `data/real/network_lta_daytime_20260928.json`
  (SHA256 `150521f3bd90456a678cc634aea41e1c21f07cdc56a6ee012b0f67552328377d`).
  All five service headways were replaced, with at least two observed
  gaps each. Stop order/coordinates came from the pinned static dataset;
  in-vehicle times, transfer buffers and delay bounds remain model estimates.
- Both strategies use the same 10,000 seeded simulated scenarios. The
  selection seed (7) differs from the evaluation seed (100).
  Departures are uniformly randomized over each calibrated headway, not
  sampled from the actual vehicle arrival sequence.

## Same-network algorithm comparison (10:00 departure, stop to stop)

| Strategy | Mean (min) | P90 | P95 | Modeled missed-connection rate |
| --- | ---: | ---: | ---: | ---: |
| Shortest expected time, fixed route | 53.17 | 59.37 | 61.07 | 30.92% |
| Minimum transfers, fixed route | 53.17 | 59.37 | 61.07 | 30.92% |
| Minimum ride time, fixed route | 54.43 | 61.82 | 63.60 | 22.64% |
| Reliability policy, accept first of 105/183 at 17161 | 52.12 | 58.41 | 59.99 | 22.00% |

In this simulation, the reliability policy is 1.05 minutes faster on
average and 1.08 minutes faster at P95 than the fixed shortest-time
baseline. Its modeled missed-connection rate is 8.92 percentage points
lower. It boarded 105 in 2,761 simulated runs and 183 in 7,239; the
first two legs (151, 201) were common. Here "missed connection" is a
simulation indicator relative to a nominal arrival and is **not** a
count of empirically missed LTA vehicles. Fare invalidity and actual
vehicle travel time were not observed.

At the separately requested 16:00 departure, **reusing the morning
headways** gives a model mean/P95 of 53.20/60.98 minutes for the fixed
baseline and 52.15/60.07 for the flexible policy. This is an
out-of-time scenario, **not 16:00 LTA calibration**.

The user's manually recorded Google Maps suggestions for 16:00 were
46-54 minutes. Their Central Library place origin and walking/boarding
options differ from this experiment's stop 16181 origin, and the
model includes zero access/egress walking. Thus the displayed Google
range and the model's 52.15-minute mean can be placed side by side as
predictions only, not ranked as like-for-like travel times or evidence
that either router is faster. No Google route responses or screenshots
were collected by this project.

## Reproduce locally

With the project's Python dependencies installed, from the repository root:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m sg_transit calibrate-headways `
  --input data\recorded\raw\route_headway_daytime_20260928.json `
  --output data\recorded\calibrated\route_headway_daytime_20260928.json
python -m sg_transit apply-headways `
  --network data\real\network.json `
  --calibration data\recorded\calibrated\route_headway_daytime_20260928.json `
  --output data\real\network_lta_daytime_20260928.json `
  --min-observations 2
python -m sg_transit plan `
  --network data\real\network_lta_daytime_20260928.json `
  --origin 16181 --destination 28009 `
  --departure 2026-09-28T10:00:00+08:00 `
  --samples 10000 --seed 100 --selection-seed 7 --selection-samples 512 `
  --output results\central_library_jurong_east_20260928_1000_lta_daytime.json
```

The retained derived network allows the Monte Carlo comparison to be
replayed without API access. Reproducing calibration from raw snapshots
requires the local raw file or a fresh authorized collection; fresh
ETA observations will differ. Only three headway gaps for most services
and two for service 10 were observed in this 11-minute window. These
are not official schedules or enough evidence for a time-of-day
distribution, and headway does not validate ride time or 16:00 traffic.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

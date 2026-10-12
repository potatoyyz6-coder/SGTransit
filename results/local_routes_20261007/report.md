# Local Stop-Pair Experiment

Historical real bus topology; all timing is assumed, not observed or live.
No API or Google data used. Twenty stratified random OD pairs plus the specified home trip.
Seven pairs require zero transfers, seven one, six two, within the declared local transfer model.
Sampling seed: 20261007. Manifest is saved before evaluating any pair.

## Scope

Transfer decisions are allowed only at: 11261, 11401, 12061, 12071, 16009, 16089, 16189, 17161, 28009, 42071, 42141, 42171.
Other stops remain eligible endpoints. Intermediate riding time is summed, not removed.
Complete search means only within this restricted model, at most two transfers, 120 minutes,
45-minute transfer gap; not complete area or Singapore routing. Direction and expanded original-stop
loop validity are checked for every candidate. Graph recombination must not give dynamic extra routes.
Search caps: 500 routes, 30,000 expansions. Budget/error cases remain listed; no replacement sampling.
Timing: 20km/h distance conversion, at least 0.5min per original segment; headway15, delay U(0,3), buffer3.
Home sensitivities change headway, delay, buffer or phase dependence one at a time.
All are stationary assumptions, not forecasts for a calendar departure. Static provenance is in manifest.json.
Default 1,000 held-out worlds / 256 training worlds per query, 64 separate rollout draws.
Each mode selects a fixed route on training data; dynamic modes use the same candidate graph and test worlds.
Fast=min mean; cool=mean+2*wait+3*transfers; reliable=projected P95. Completion takes priority.
Independent stationary rollouts do not learn phase correlations; no global-P95 optimality claim.

## Results

Minutes; LWP = model probability of a transfer wait >10min. Wait excludes transfer buffer.
| Query | Variant | Strategy | Mean | P95 | Wait | LWP | Completion |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| home | base | fixed_fast | 40.58 | 51.17 | 14.79 | 0.33 | 1.00 |
| home | base | fixed_cool | 40.58 | 51.17 | 14.79 | 0.33 | 1.00 |
| home | base | fixed_reliable | 40.58 | 51.17 | 14.79 | 0.33 | 1.00 |
| home | base | dynamic_fast | 40.28 | 50.50 | 14.16 | 0.28 | 1.00 |
| home | base | dynamic_cool | 41.14 | 53.09 | 11.42 | 0.17 | 1.00 |
| home | base | dynamic_reliable | 40.58 | 51.17 | 14.74 | 0.33 | 1.00 |
| home | base | first_eligible | 44.27 | 56.79 | 9.69 | 0.04 | 1.00 |
| home | base | legacy_scored | 40.25 | 50.50 | 13.98 | 0.27 | 1.00 |
| random_01 | base | fixed_fast | 35.99 | 42.96 | 7.62 | 0.00 | 1.00 |
| random_01 | base | fixed_cool | 35.99 | 42.96 | 7.62 | 0.00 | 1.00 |
| random_01 | base | fixed_reliable | 35.99 | 42.96 | 7.62 | 0.00 | 1.00 |
| random_01 | base | dynamic_fast | 35.99 | 42.96 | 7.62 | 0.00 | 1.00 |
| random_01 | base | dynamic_cool | 35.99 | 42.96 | 7.62 | 0.00 | 1.00 |
| random_01 | base | dynamic_reliable | 35.99 | 42.96 | 7.62 | 0.00 | 1.00 |
| random_01 | base | first_eligible | 35.99 | 42.96 | 7.62 | 0.00 | 1.00 |
| random_01 | base | legacy_scored | 35.99 | 42.96 | 7.62 | 0.00 | 1.00 |
| random_02 | base | fixed_fast | 34.39 | 41.52 | 7.42 | 0.00 | 1.00 |
| random_02 | base | fixed_cool | 34.39 | 41.52 | 7.42 | 0.00 | 1.00 |
| random_02 | base | fixed_reliable | 34.39 | 41.52 | 7.42 | 0.00 | 1.00 |
| random_02 | base | dynamic_fast | 34.39 | 41.52 | 7.42 | 0.00 | 1.00 |
| random_02 | base | dynamic_cool | 34.39 | 41.52 | 7.42 | 0.00 | 1.00 |
| random_02 | base | dynamic_reliable | 34.39 | 41.52 | 7.42 | 0.00 | 1.00 |
| random_02 | base | first_eligible | 34.39 | 41.52 | 7.42 | 0.00 | 1.00 |
| random_02 | base | legacy_scored | 34.39 | 41.52 | 7.42 | 0.00 | 1.00 |
| random_03 | base | fixed_fast | 20.77 | 27.85 | 7.29 | 0.00 | 1.00 |
| random_03 | base | fixed_cool | 20.77 | 27.85 | 7.29 | 0.00 | 1.00 |
| random_03 | base | fixed_reliable | 20.77 | 27.85 | 7.29 | 0.00 | 1.00 |
| random_03 | base | dynamic_fast | 20.77 | 27.85 | 7.29 | 0.00 | 1.00 |
| random_03 | base | dynamic_cool | 20.77 | 27.85 | 7.29 | 0.00 | 1.00 |
| random_03 | base | dynamic_reliable | 20.77 | 27.85 | 7.29 | 0.00 | 1.00 |
| random_03 | base | first_eligible | 20.77 | 27.85 | 7.29 | 0.00 | 1.00 |
| random_03 | base | legacy_scored | 20.77 | 27.85 | 7.29 | 0.00 | 1.00 |
| random_04 | base | fixed_fast | 22.73 | 29.64 | 7.56 | 0.00 | 1.00 |
| random_04 | base | fixed_cool | 22.73 | 29.64 | 7.56 | 0.00 | 1.00 |
| random_04 | base | fixed_reliable | 22.73 | 29.64 | 7.56 | 0.00 | 1.00 |
| random_04 | base | dynamic_fast | 22.73 | 29.64 | 7.56 | 0.00 | 1.00 |
| random_04 | base | dynamic_cool | 22.73 | 29.64 | 7.56 | 0.00 | 1.00 |
| random_04 | base | dynamic_reliable | 22.73 | 29.64 | 7.56 | 0.00 | 1.00 |
| random_04 | base | first_eligible | 22.73 | 29.64 | 7.56 | 0.00 | 1.00 |
| random_04 | base | legacy_scored | 22.73 | 29.64 | 7.56 | 0.00 | 1.00 |
| random_05 | base | fixed_fast | 10.76 | 17.84 | 7.49 | 0.00 | 1.00 |
| random_05 | base | fixed_cool | 10.76 | 17.84 | 7.49 | 0.00 | 1.00 |
| random_05 | base | fixed_reliable | 10.76 | 17.84 | 7.49 | 0.00 | 1.00 |
| random_05 | base | dynamic_fast | 10.76 | 17.84 | 7.49 | 0.00 | 1.00 |
| random_05 | base | dynamic_cool | 10.76 | 17.84 | 7.49 | 0.00 | 1.00 |
| random_05 | base | dynamic_reliable | 10.76 | 17.84 | 7.49 | 0.00 | 1.00 |
| random_05 | base | first_eligible | 10.76 | 17.84 | 7.49 | 0.00 | 1.00 |
| random_05 | base | legacy_scored | 10.76 | 17.84 | 7.49 | 0.00 | 1.00 |
| random_06 | base | fixed_fast | 13.13 | 19.86 | 7.41 | 0.00 | 1.00 |
| random_06 | base | fixed_cool | 13.13 | 19.86 | 7.41 | 0.00 | 1.00 |
| random_06 | base | fixed_reliable | 13.13 | 19.86 | 7.41 | 0.00 | 1.00 |
| random_06 | base | dynamic_fast | 13.13 | 19.86 | 7.41 | 0.00 | 1.00 |
| random_06 | base | dynamic_cool | 13.13 | 19.86 | 7.41 | 0.00 | 1.00 |
| random_06 | base | dynamic_reliable | 13.13 | 19.86 | 7.41 | 0.00 | 1.00 |
| random_06 | base | first_eligible | 13.13 | 19.86 | 7.41 | 0.00 | 1.00 |
| random_06 | base | legacy_scored | 13.13 | 19.86 | 7.41 | 0.00 | 1.00 |
| random_07 | base | fixed_fast | 36.74 | 43.45 | 7.47 | 0.00 | 1.00 |
| random_07 | base | fixed_cool | 36.74 | 43.45 | 7.47 | 0.00 | 1.00 |
| random_07 | base | fixed_reliable | 36.74 | 43.45 | 7.47 | 0.00 | 1.00 |
| random_07 | base | dynamic_fast | 36.74 | 43.45 | 7.47 | 0.00 | 1.00 |
| random_07 | base | dynamic_cool | 36.74 | 43.45 | 7.47 | 0.00 | 1.00 |
| random_07 | base | dynamic_reliable | 36.74 | 43.45 | 7.47 | 0.00 | 1.00 |
| random_07 | base | first_eligible | 36.74 | 43.45 | 7.47 | 0.00 | 1.00 |
| random_07 | base | legacy_scored | 36.74 | 43.45 | 7.47 | 0.00 | 1.00 |
| random_08 | base | fixed_fast | 36.15 | 46.60 | 15.12 | 0.34 | 1.00 |
| random_08 | base | fixed_cool | 36.15 | 46.60 | 15.12 | 0.34 | 1.00 |
| random_08 | base | fixed_reliable | 36.15 | 46.60 | 15.12 | 0.34 | 1.00 |
| random_08 | base | dynamic_fast | 36.15 | 46.60 | 15.12 | 0.34 | 1.00 |
| random_08 | base | dynamic_cool | 36.15 | 46.60 | 15.12 | 0.34 | 1.00 |
| random_08 | base | dynamic_reliable | 36.15 | 46.60 | 15.12 | 0.34 | 1.00 |
| random_08 | base | first_eligible | 36.15 | 46.60 | 15.12 | 0.34 | 1.00 |
| random_08 | base | legacy_scored | 36.15 | 46.60 | 15.12 | 0.34 | 1.00 |
| random_09 | base | fixed_fast | 46.09 | 56.77 | 15.17 | 0.33 | 1.00 |
| random_09 | base | fixed_cool | 46.09 | 56.77 | 15.17 | 0.33 | 1.00 |
| random_09 | base | fixed_reliable | 46.09 | 56.77 | 15.17 | 0.33 | 1.00 |
| random_09 | base | dynamic_fast | 46.09 | 56.77 | 15.17 | 0.33 | 1.00 |
| random_09 | base | dynamic_cool | 46.09 | 56.77 | 15.17 | 0.33 | 1.00 |
| random_09 | base | dynamic_reliable | 46.09 | 56.77 | 15.17 | 0.33 | 1.00 |
| random_09 | base | first_eligible | 46.09 | 56.77 | 15.17 | 0.33 | 1.00 |
| random_09 | base | legacy_scored | 46.09 | 56.77 | 15.17 | 0.33 | 1.00 |
| random_10 | base | fixed_fast | 38.81 | 49.06 | 15.10 | 0.33 | 1.00 |
| random_10 | base | fixed_cool | 38.81 | 49.06 | 15.10 | 0.33 | 1.00 |
| random_10 | base | fixed_reliable | 38.81 | 49.06 | 15.10 | 0.33 | 1.00 |
| random_10 | base | dynamic_fast | 38.81 | 49.06 | 15.10 | 0.33 | 1.00 |
| random_10 | base | dynamic_cool | 38.81 | 49.06 | 15.10 | 0.33 | 1.00 |
| random_10 | base | dynamic_reliable | 38.81 | 49.06 | 15.10 | 0.33 | 1.00 |
| random_10 | base | first_eligible | 38.81 | 49.06 | 15.10 | 0.33 | 1.00 |
| random_10 | base | legacy_scored | 38.81 | 49.06 | 15.10 | 0.33 | 1.00 |
| random_11 | base | fixed_fast | 46.20 | 57.04 | 15.07 | 0.34 | 1.00 |
| random_11 | base | fixed_cool | 46.20 | 57.04 | 15.07 | 0.34 | 1.00 |
| random_11 | base | fixed_reliable | 46.20 | 57.04 | 15.07 | 0.34 | 1.00 |
| random_11 | base | dynamic_fast | 46.20 | 57.04 | 15.07 | 0.34 | 1.00 |
| random_11 | base | dynamic_cool | 46.20 | 57.04 | 15.07 | 0.34 | 1.00 |
| random_11 | base | dynamic_reliable | 46.20 | 57.04 | 15.07 | 0.34 | 1.00 |
| random_11 | base | first_eligible | 46.20 | 57.04 | 15.07 | 0.34 | 1.00 |
| random_11 | base | legacy_scored | 46.20 | 57.04 | 15.07 | 0.34 | 1.00 |
| random_12 | base | fixed_fast | 47.40 | 58.24 | 15.07 | 0.34 | 1.00 |
| random_12 | base | fixed_cool | 47.40 | 58.24 | 15.07 | 0.34 | 1.00 |
| random_12 | base | fixed_reliable | 47.40 | 58.24 | 15.07 | 0.34 | 1.00 |
| random_12 | base | dynamic_fast | 47.40 | 58.24 | 15.07 | 0.34 | 1.00 |
| random_12 | base | dynamic_cool | 47.40 | 58.24 | 15.07 | 0.34 | 1.00 |
| random_12 | base | dynamic_reliable | 47.40 | 58.24 | 15.07 | 0.34 | 1.00 |
| random_12 | base | first_eligible | 47.40 | 58.24 | 15.07 | 0.34 | 1.00 |
| random_12 | base | legacy_scored | 47.40 | 58.24 | 15.07 | 0.34 | 1.00 |
| random_13 | base | fixed_fast | 41.05 | 51.22 | 14.98 | 0.30 | 1.00 |
| random_13 | base | fixed_cool | 41.05 | 51.22 | 14.98 | 0.30 | 1.00 |
| random_13 | base | fixed_reliable | 41.05 | 51.22 | 14.98 | 0.30 | 1.00 |
| random_13 | base | dynamic_fast | 41.05 | 51.22 | 14.98 | 0.30 | 1.00 |
| random_13 | base | dynamic_cool | 41.05 | 51.22 | 14.98 | 0.30 | 1.00 |
| random_13 | base | dynamic_reliable | 41.05 | 51.22 | 14.98 | 0.30 | 1.00 |
| random_13 | base | first_eligible | 41.05 | 51.22 | 14.98 | 0.30 | 1.00 |
| random_13 | base | legacy_scored | 41.05 | 51.22 | 14.98 | 0.30 | 1.00 |
| random_14 | base | fixed_fast | 28.33 | 38.19 | 14.86 | 0.30 | 1.00 |
| random_14 | base | fixed_cool | 28.33 | 38.19 | 14.86 | 0.30 | 1.00 |
| random_14 | base | fixed_reliable | 28.33 | 38.19 | 14.86 | 0.30 | 1.00 |
| random_14 | base | dynamic_fast | 28.33 | 38.19 | 14.86 | 0.30 | 1.00 |
| random_14 | base | dynamic_cool | 28.33 | 38.19 | 14.86 | 0.30 | 1.00 |
| random_14 | base | dynamic_reliable | 28.33 | 38.19 | 14.86 | 0.30 | 1.00 |
| random_14 | base | first_eligible | 28.33 | 38.19 | 14.86 | 0.30 | 1.00 |
| random_14 | base | legacy_scored | 28.33 | 38.19 | 14.86 | 0.30 | 1.00 |
| random_15 | base | fixed_fast | 49.40 | 62.58 | 22.38 | 0.57 | 1.00 |
| random_15 | base | fixed_cool | 49.40 | 62.58 | 22.38 | 0.57 | 1.00 |
| random_15 | base | fixed_reliable | 49.40 | 62.58 | 22.38 | 0.57 | 1.00 |
| random_15 | base | dynamic_fast | 49.40 | 62.58 | 22.38 | 0.57 | 1.00 |
| random_15 | base | dynamic_cool | 49.40 | 62.58 | 22.38 | 0.57 | 1.00 |
| random_15 | base | dynamic_reliable | 49.40 | 62.58 | 22.38 | 0.57 | 1.00 |
| random_15 | base | first_eligible | 49.40 | 62.58 | 22.38 | 0.57 | 1.00 |
| random_15 | base | legacy_scored | 49.40 | 62.58 | 22.38 | 0.57 | 1.00 |
| random_16 | base | fixed_fast | 49.40 | 62.45 | 22.27 | 0.55 | 1.00 |
| random_16 | base | fixed_cool | 49.40 | 62.45 | 22.27 | 0.55 | 1.00 |
| random_16 | base | fixed_reliable | 49.40 | 62.45 | 22.27 | 0.55 | 1.00 |
| random_16 | base | dynamic_fast | 49.40 | 62.45 | 22.27 | 0.55 | 1.00 |
| random_16 | base | dynamic_cool | 49.40 | 62.45 | 22.27 | 0.55 | 1.00 |
| random_16 | base | dynamic_reliable | 49.40 | 62.45 | 22.27 | 0.55 | 1.00 |
| random_16 | base | first_eligible | 49.40 | 62.45 | 22.27 | 0.55 | 1.00 |
| random_16 | base | legacy_scored | 49.40 | 62.45 | 22.27 | 0.55 | 1.00 |
| random_17 | base | fixed_fast | 58.37 | 71.31 | 22.35 | 0.57 | 1.00 |
| random_17 | base | fixed_cool | 58.37 | 71.31 | 22.35 | 0.57 | 1.00 |
| random_17 | base | fixed_reliable | 58.37 | 71.31 | 22.35 | 0.57 | 1.00 |
| random_17 | base | dynamic_fast | 56.70 | 69.04 | 20.08 | 0.42 | 1.00 |
| random_17 | base | dynamic_cool | 58.22 | 74.12 | 18.62 | 0.31 | 1.00 |
| random_17 | base | dynamic_reliable | 56.70 | 69.04 | 20.09 | 0.42 | 1.00 |
| random_17 | base | first_eligible | 62.18 | 79.94 | 18.69 | 0.32 | 1.00 |
| random_17 | base | legacy_scored | 56.70 | 69.04 | 20.09 | 0.42 | 1.00 |
| random_18 | base | fixed_fast | 46.10 | 59.28 | 22.38 | 0.57 | 1.00 |
| random_18 | base | fixed_cool | 46.10 | 59.28 | 22.38 | 0.57 | 1.00 |
| random_18 | base | fixed_reliable | 46.10 | 59.28 | 22.38 | 0.57 | 1.00 |
| random_18 | base | dynamic_fast | 43.77 | 56.13 | 19.94 | 0.41 | 1.00 |
| random_18 | base | dynamic_cool | 45.34 | 61.06 | 18.62 | 0.32 | 1.00 |
| random_18 | base | dynamic_reliable | 43.75 | 56.11 | 20.05 | 0.42 | 1.00 |
| random_18 | base | first_eligible | 48.87 | 65.76 | 18.78 | 0.33 | 1.00 |
| random_18 | base | legacy_scored | 43.75 | 56.11 | 20.05 | 0.42 | 1.00 |
| random_19 | base | fixed_fast | 60.80 | 73.98 | 22.38 | 0.57 | 1.00 |
| random_19 | base | fixed_cool | 60.80 | 73.98 | 22.38 | 0.57 | 1.00 |
| random_19 | base | fixed_reliable | 60.80 | 73.98 | 22.38 | 0.57 | 1.00 |
| random_19 | base | dynamic_fast | 59.13 | 71.35 | 20.10 | 0.42 | 1.00 |
| random_19 | base | dynamic_cool | 60.74 | 76.59 | 18.66 | 0.32 | 1.00 |
| random_19 | base | dynamic_reliable | 59.13 | 71.35 | 20.12 | 0.42 | 1.00 |
| random_19 | base | first_eligible | 64.69 | 81.96 | 18.78 | 0.33 | 1.00 |
| random_19 | base | legacy_scored | 59.13 | 71.35 | 20.12 | 0.42 | 1.00 |
| random_20 | base | fixed_fast | 48.50 | 61.55 | 22.27 | 0.55 | 1.00 |
| random_20 | base | fixed_cool | 48.50 | 61.55 | 22.27 | 0.55 | 1.00 |
| random_20 | base | fixed_reliable | 48.50 | 61.55 | 22.27 | 0.55 | 1.00 |
| random_20 | base | dynamic_fast | 48.50 | 61.55 | 22.27 | 0.55 | 1.00 |
| random_20 | base | dynamic_cool | 48.50 | 61.55 | 22.27 | 0.55 | 1.00 |
| random_20 | base | dynamic_reliable | 48.50 | 61.55 | 22.27 | 0.55 | 1.00 |
| random_20 | base | first_eligible | 48.50 | 61.55 | 22.27 | 0.55 | 1.00 |
| random_20 | base | legacy_scored | 48.50 | 61.55 | 22.27 | 0.55 | 1.00 |
| home | headway20 | fixed_fast | 45.36 | 59.27 | 19.57 | 0.47 | 1.00 |
| home | headway20 | fixed_cool | 45.36 | 59.27 | 19.57 | 0.47 | 1.00 |
| home | headway20 | fixed_reliable | 45.36 | 59.27 | 19.57 | 0.47 | 1.00 |
| home | headway20 | dynamic_fast | 44.47 | 57.47 | 17.52 | 0.38 | 1.00 |
| home | headway20 | dynamic_cool | 45.21 | 59.89 | 14.54 | 0.30 | 1.00 |
| home | headway20 | dynamic_reliable | 45.23 | 58.95 | 18.72 | 0.46 | 1.00 |
| home | headway20 | first_eligible | 47.74 | 62.34 | 13.26 | 0.18 | 1.00 |
| home | headway20 | legacy_scored | 44.13 | 57.27 | 16.60 | 0.32 | 1.00 |
| home | delay8 | fixed_fast | 46.00 | 57.46 | 15.23 | 0.38 | 1.00 |
| home | delay8 | fixed_cool | 46.00 | 57.46 | 15.23 | 0.38 | 1.00 |
| home | delay8 | fixed_reliable | 46.00 | 57.46 | 15.23 | 0.38 | 1.00 |
| home | delay8 | dynamic_fast | 46.02 | 57.44 | 15.11 | 0.37 | 1.00 |
| home | delay8 | dynamic_cool | 46.78 | 59.17 | 11.79 | 0.23 | 1.00 |
| home | delay8 | dynamic_reliable | 46.03 | 57.46 | 15.19 | 0.38 | 1.00 |
| home | delay8 | first_eligible | 50.38 | 64.00 | 9.83 | 0.06 | 1.00 |
| home | delay8 | legacy_scored | 46.02 | 57.40 | 14.97 | 0.37 | 1.00 |
| home | buffer5 | fixed_fast | 42.83 | 53.57 | 15.04 | 0.36 | 1.00 |
| home | buffer5 | fixed_cool | 42.83 | 53.57 | 15.04 | 0.36 | 1.00 |
| home | buffer5 | fixed_reliable | 42.83 | 53.57 | 15.04 | 0.36 | 1.00 |
| home | buffer5 | dynamic_fast | 42.80 | 53.53 | 14.84 | 0.35 | 1.00 |
| home | buffer5 | dynamic_cool | 43.48 | 55.17 | 11.70 | 0.22 | 1.00 |
| home | buffer5 | dynamic_reliable | 42.85 | 53.57 | 15.01 | 0.36 | 1.00 |
| home | buffer5 | first_eligible | 47.19 | 59.81 | 9.88 | 0.06 | 1.00 |
| home | buffer5 | legacy_scored | 42.78 | 53.50 | 14.69 | 0.35 | 1.00 |
| home | synchronized | fixed_fast | 45.19 | 61.45 | 14.88 | 0.20 | 1.00 |
| home | synchronized | fixed_cool | 45.19 | 61.45 | 14.95 | 0.20 | 1.00 |
| home | synchronized | fixed_reliable | 46.39 | 53.00 | 20.60 | 1.00 | 1.00 |
| home | synchronized | dynamic_fast | 45.25 | 53.00 | 18.32 | 0.74 | 1.00 |
| home | synchronized | dynamic_cool | 43.02 | 50.62 | 13.62 | 0.20 | 1.00 |
| home | synchronized | dynamic_reliable | 46.39 | 53.00 | 20.60 | 1.00 | 1.00 |
| home | synchronized | first_eligible | 43.02 | 50.62 | 13.62 | 0.20 | 1.00 |
| home | synchronized | legacy_scored | 43.02 | 50.62 | 13.62 | 0.20 | 1.00 |

## Route Details and Search

### home / base

Information Technology (16189) -> Signature Pk Condo (42171)
Status: completed; search: {'expansions': 260, 'candidates': 94}; total experiment seconds: 48.74.

- Fixed fast: 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)
- Fixed cool: 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)
- Fixed reliable: 151-D2: Information Technology (16189) -> Bef Dunearn Rd (42141) | 61-D2: Bef Dunearn Rd (42141) -> Signature Pk Condo (42171)
- Dynamic fast, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Bef Dunearn Rd (42141) | 61-D2: Bef Dunearn Rd (42141) -> Signature Pk Condo (42171)
- Dynamic cool, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Bef Dunearn Rd (42141) | 61-D2: Bef Dunearn Rd (42141) -> Signature Pk Condo (42171)
- Dynamic reliable, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)

### random_01 / base

Heng Mui Keng Terr (16069) -> Bef Old Toh Tuck Rd (28709)
Status: completed; search: {'expansions': 3, 'candidates': 1}; total experiment seconds: 0.69.

- Fixed fast: 183-D1: Heng Mui Keng Terr (16069) -> Bef Old Toh Tuck Rd (28709)
- Fixed cool: 183-D1: Heng Mui Keng Terr (16069) -> Bef Old Toh Tuck Rd (28709)
- Fixed reliable: 183-D1: Heng Mui Keng Terr (16069) -> Bef Old Toh Tuck Rd (28709)
- Dynamic fast, test world 0 only (complete=True): 183-D1: Heng Mui Keng Terr (16069) -> Bef Old Toh Tuck Rd (28709)
- Dynamic cool, test world 0 only (complete=True): 183-D1: Heng Mui Keng Terr (16069) -> Bef Old Toh Tuck Rd (28709)
- Dynamic reliable, test world 0 only (complete=True): 183-D1: Heng Mui Keng Terr (16069) -> Bef Old Toh Tuck Rd (28709)

### random_02 / base

Galen (16121) -> Opp Toh Guan Ctr (28689)
Status: completed; search: {'expansions': 3, 'candidates': 1}; total experiment seconds: 0.70.

- Fixed fast: 183-D1: Galen (16121) -> Opp Toh Guan Ctr (28689)
- Fixed cool: 183-D1: Galen (16121) -> Opp Toh Guan Ctr (28689)
- Fixed reliable: 183-D1: Galen (16121) -> Opp Toh Guan Ctr (28689)
- Dynamic fast, test world 0 only (complete=True): 183-D1: Galen (16121) -> Opp Toh Guan Ctr (28689)
- Dynamic cool, test world 0 only (complete=True): 183-D1: Galen (16121) -> Opp Toh Guan Ctr (28689)
- Dynamic reliable, test world 0 only (complete=True): 183-D1: Galen (16121) -> Opp Toh Guan Ctr (28689)

### random_03 / base

Garlick Ville (11341) -> Signature Pk Condo (42171)
Status: completed; search: {'expansions': 7, 'candidates': 5}; total experiment seconds: 2.77.

- Fixed fast: 970-D2: Garlick Ville (11341) -> Signature Pk Condo (42171)
- Fixed cool: 970-D2: Garlick Ville (11341) -> Signature Pk Condo (42171)
- Fixed reliable: 970-D2: Garlick Ville (11341) -> Signature Pk Condo (42171)
- Dynamic fast, test world 0 only (complete=True): 970-D2: Garlick Ville (11341) -> Signature Pk Condo (42171)
- Dynamic cool, test world 0 only (complete=True): 970-D2: Garlick Ville (11341) -> Signature Pk Condo (42171)
- Dynamic reliable, test world 0 only (complete=True): 970-D2: Garlick Ville (11341) -> Signature Pk Condo (42171)

### random_04 / base

Inst of Micro-electronics (16101) -> Aft Clementi Ave 1 (17091)
Status: completed; search: {'expansions': 2, 'candidates': 1}; total experiment seconds: 0.38.

- Fixed fast: 183-D1: Inst of Micro-electronics (16101) -> Aft Clementi Ave 1 (17091)
- Fixed cool: 183-D1: Inst of Micro-electronics (16101) -> Aft Clementi Ave 1 (17091)
- Fixed reliable: 183-D1: Inst of Micro-electronics (16101) -> Aft Clementi Ave 1 (17091)
- Dynamic fast, test world 0 only (complete=True): 183-D1: Inst of Micro-electronics (16101) -> Aft Clementi Ave 1 (17091)
- Dynamic cool, test world 0 only (complete=True): 183-D1: Inst of Micro-electronics (16101) -> Aft Clementi Ave 1 (17091)
- Dynamic reliable, test world 0 only (complete=True): 183-D1: Inst of Micro-electronics (16101) -> Aft Clementi Ave 1 (17091)

### random_05 / base

Bef Old Toh Tuck Rd (28709) -> Opp Uni-Tech Ctr (28699)
Status: completed; search: {'expansions': 2, 'candidates': 1}; total experiment seconds: 0.38.

- Fixed fast: 183-D1: Bef Old Toh Tuck Rd (28709) -> Opp Uni-Tech Ctr (28699)
- Fixed cool: 183-D1: Bef Old Toh Tuck Rd (28709) -> Opp Uni-Tech Ctr (28699)
- Fixed reliable: 183-D1: Bef Old Toh Tuck Rd (28709) -> Opp Uni-Tech Ctr (28699)
- Dynamic fast, test world 0 only (complete=True): 183-D1: Bef Old Toh Tuck Rd (28709) -> Opp Uni-Tech Ctr (28699)
- Dynamic cool, test world 0 only (complete=True): 183-D1: Bef Old Toh Tuck Rd (28709) -> Opp Uni-Tech Ctr (28699)
- Dynamic reliable, test world 0 only (complete=True): 183-D1: Bef Old Toh Tuck Rd (28709) -> Opp Uni-Tech Ctr (28699)

### random_06 / base

Pandan Valley Condo (12031) -> Blk 109 (12061)
Status: completed; search: {'expansions': 2, 'candidates': 1}; total experiment seconds: 0.38.

- Fixed fast: 61-D2: Pandan Valley Condo (12031) -> Blk 109 (12061)
- Fixed cool: 61-D2: Pandan Valley Condo (12031) -> Blk 109 (12061)
- Fixed reliable: 61-D2: Pandan Valley Condo (12031) -> Blk 109 (12061)
- Dynamic fast, test world 0 only (complete=True): 61-D2: Pandan Valley Condo (12031) -> Blk 109 (12061)
- Dynamic cool, test world 0 only (complete=True): 61-D2: Pandan Valley Condo (12031) -> Blk 109 (12061)
- Dynamic reliable, test world 0 only (complete=True): 61-D2: Pandan Valley Condo (12031) -> Blk 109 (12061)

### random_07 / base

Aft Clementi Rd (16089) -> Bef Toh Tuck Lk (28181)
Status: completed; search: {'expansions': 3, 'candidates': 1}; total experiment seconds: 0.69.

- Fixed fast: 183-D1: Aft Clementi Rd (16089) -> Bef Toh Tuck Lk (28181)
- Fixed cool: 183-D1: Aft Clementi Rd (16089) -> Bef Toh Tuck Lk (28181)
- Fixed reliable: 183-D1: Aft Clementi Rd (16089) -> Bef Toh Tuck Lk (28181)
- Dynamic fast, test world 0 only (complete=True): 183-D1: Aft Clementi Rd (16089) -> Bef Toh Tuck Lk (28181)
- Dynamic cool, test world 0 only (complete=True): 183-D1: Aft Clementi Rd (16089) -> Bef Toh Tuck Lk (28181)
- Dynamic reliable, test world 0 only (complete=True): 183-D1: Aft Clementi Rd (16089) -> Bef Toh Tuck Lk (28181)

### random_08 / base

Aft Palm Green Condo (16081) -> Opp 8 @Tradehub 21 (28021)
Status: completed; search: {'expansions': 3, 'candidates': 1}; total experiment seconds: 0.78.

- Fixed fast: 183-D1: Aft Palm Green Condo (16081) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Opp 8 @Tradehub 21 (28021)
- Fixed cool: 183-D1: Aft Palm Green Condo (16081) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Opp 8 @Tradehub 21 (28021)
- Fixed reliable: 183-D1: Aft Palm Green Condo (16081) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Opp 8 @Tradehub 21 (28021)
- Dynamic fast, test world 0 only (complete=True): 183-D1: Aft Palm Green Condo (16081) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Opp 8 @Tradehub 21 (28021)
- Dynamic cool, test world 0 only (complete=True): 183-D1: Aft Palm Green Condo (16081) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Opp 8 @Tradehub 21 (28021)
- Dynamic reliable, test world 0 only (complete=True): 183-D1: Aft Palm Green Condo (16081) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Opp 8 @Tradehub 21 (28021)

### random_09 / base

Opp University Hall (18319) -> Clementi N'hood Pk (12081)
Status: completed; search: {'expansions': 44, 'candidates': 23}; total experiment seconds: 18.62.

- Fixed fast: 95-D1: Opp University Hall (18319) -> Holland Village (11261) | 61-D2: Holland Village (11261) -> Clementi N'hood Pk (12081)
- Fixed cool: 95-D1: Opp University Hall (18319) -> Holland Village (11261) | 61-D2: Holland Village (11261) -> Clementi N'hood Pk (12081)
- Fixed reliable: 95-D1: Opp University Hall (18319) -> Holland Village (11261) | 61-D2: Holland Village (11261) -> Clementi N'hood Pk (12081)
- Dynamic fast, test world 0 only (complete=True): 95-D1: Opp University Hall (18319) -> Holland V Stn/Blk 12 (11401) | 61-D2: Holland V Stn/Blk 12 (11401) -> Clementi N'hood Pk (12081)
- Dynamic cool, test world 0 only (complete=True): 95-D1: Opp University Hall (18319) -> Holland V Stn/Blk 12 (11401) | 61-D2: Holland V Stn/Blk 12 (11401) -> Clementi N'hood Pk (12081)
- Dynamic reliable, test world 0 only (complete=True): 95-D1: Opp University Hall (18319) -> Holland V Stn/Blk 12 (11401) | 61-D2: Holland V Stn/Blk 12 (11401) -> Clementi N'hood Pk (12081)

### random_10 / base

Opp Kent Ridge Stn Exit A (18339) -> Pine Gr Condo (12051)
Status: completed; search: {'expansions': 8, 'candidates': 3}; total experiment seconds: 2.19.

- Fixed fast: 95-D1: Opp Kent Ridge Stn Exit A (18339) -> Holland Village (11261) | 61-D2: Holland Village (11261) -> Pine Gr Condo (12051)
- Fixed cool: 95-D1: Opp Kent Ridge Stn Exit A (18339) -> Holland Village (11261) | 61-D2: Holland Village (11261) -> Pine Gr Condo (12051)
- Fixed reliable: 95-D1: Opp Kent Ridge Stn Exit A (18339) -> Holland Village (11261) | 61-D2: Holland Village (11261) -> Pine Gr Condo (12051)
- Dynamic fast, test world 0 only (complete=True): 95-D1: Opp Kent Ridge Stn Exit A (18339) -> Holland V Stn/Blk 12 (11401) | 61-D2: Holland V Stn/Blk 12 (11401) -> Pine Gr Condo (12051)
- Dynamic cool, test world 0 only (complete=True): 95-D1: Opp Kent Ridge Stn Exit A (18339) -> Holland V Stn/Blk 12 (11401) | 61-D2: Holland V Stn/Blk 12 (11401) -> Pine Gr Condo (12051)
- Dynamic reliable, test world 0 only (complete=True): 95-D1: Opp Kent Ridge Stn Exit A (18339) -> Holland V Stn/Blk 12 (11401) | 61-D2: Holland V Stn/Blk 12 (11401) -> Pine Gr Condo (12051)

### random_11 / base

Whitehaven (16049) -> Bef The Synergy (28031)
Status: completed; search: {'expansions': 3, 'candidates': 1}; total experiment seconds: 0.78.

- Fixed fast: 183-D1: Whitehaven (16049) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Bef The Synergy (28031)
- Fixed cool: 183-D1: Whitehaven (16049) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Bef The Synergy (28031)
- Fixed reliable: 183-D1: Whitehaven (16049) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Bef The Synergy (28031)
- Dynamic fast, test world 0 only (complete=True): 183-D1: Whitehaven (16049) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Bef The Synergy (28031)
- Dynamic cool, test world 0 only (complete=True): 183-D1: Whitehaven (16049) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Bef The Synergy (28031)
- Dynamic reliable, test world 0 only (complete=True): 183-D1: Whitehaven (16049) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Bef The Synergy (28031)

### random_12 / base

Whitehaven (16049) -> The Synergy (28041)
Status: completed; search: {'expansions': 3, 'candidates': 1}; total experiment seconds: 0.79.

- Fixed fast: 183-D1: Whitehaven (16049) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> The Synergy (28041)
- Fixed cool: 183-D1: Whitehaven (16049) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> The Synergy (28041)
- Fixed reliable: 183-D1: Whitehaven (16049) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> The Synergy (28041)
- Dynamic fast, test world 0 only (complete=True): 183-D1: Whitehaven (16049) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> The Synergy (28041)
- Dynamic cool, test world 0 only (complete=True): 183-D1: Whitehaven (16049) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> The Synergy (28041)
- Dynamic reliable, test world 0 only (complete=True): 183-D1: Whitehaven (16049) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> The Synergy (28041)

### random_13 / base

Blk S17 (18309) -> Sixth Ave Ctr (42011)
Status: completed; search: {'expansions': 8, 'candidates': 3}; total experiment seconds: 2.18.

- Fixed fast: 95-D1: Blk S17 (18309) -> Holland Village (11261) | 970-D2: Holland Village (11261) -> Sixth Ave Ctr (42011)
- Fixed cool: 95-D1: Blk S17 (18309) -> Holland Village (11261) | 970-D2: Holland Village (11261) -> Sixth Ave Ctr (42011)
- Fixed reliable: 95-D1: Blk S17 (18309) -> Holland Village (11261) | 970-D2: Holland Village (11261) -> Sixth Ave Ctr (42011)
- Dynamic fast, test world 0 only (complete=True): 95-D1: Blk S17 (18309) -> Holland Village (11261) | 970-D2: Holland Village (11261) -> Sixth Ave Ctr (42011)
- Dynamic cool, test world 0 only (complete=True): 95-D1: Blk S17 (18309) -> Holland Village (11261) | 970-D2: Holland Village (11261) -> Sixth Ave Ctr (42011)
- Dynamic reliable, test world 0 only (complete=True): 95-D1: Blk S17 (18309) -> Holland V Stn/Blk 12 (11401) | 970-D2: Holland V Stn/Blk 12 (11401) -> Sixth Ave Ctr (42011)

### random_14 / base

Blk 43 (11189) -> Opp Regent Villa (11321)
Status: completed; search: {'expansions': 8, 'candidates': 3}; total experiment seconds: 2.19.

- Fixed fast: 95-D1: Blk 43 (11189) -> Holland Village (11261) | 970-D2: Holland Village (11261) -> Opp Regent Villa (11321)
- Fixed cool: 95-D1: Blk 43 (11189) -> Holland Village (11261) | 970-D2: Holland Village (11261) -> Opp Regent Villa (11321)
- Fixed reliable: 95-D1: Blk 43 (11189) -> Holland Village (11261) | 970-D2: Holland Village (11261) -> Opp Regent Villa (11321)
- Dynamic fast, test world 0 only (complete=True): 95-D1: Blk 43 (11189) -> Holland Village (11261) | 970-D2: Holland Village (11261) -> Opp Regent Villa (11321)
- Dynamic cool, test world 0 only (complete=True): 95-D1: Blk 43 (11189) -> Holland Village (11261) | 970-D2: Holland Village (11261) -> Opp Regent Villa (11321)
- Dynamic reliable, test world 0 only (complete=True): 95-D1: Blk 43 (11189) -> Holland V Stn/Blk 12 (11401) | 970-D2: Holland V Stn/Blk 12 (11401) -> Opp Regent Villa (11321)

### random_15 / base

Ctrl Lib (16181) -> Opp 8 @Tradehub 21 (28021)
Status: completed; search: {'expansions': 6, 'candidates': 1}; total experiment seconds: 1.19.

- Fixed fast: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Opp 8 @Tradehub 21 (28021)
- Fixed cool: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Opp 8 @Tradehub 21 (28021)
- Fixed reliable: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Opp 8 @Tradehub 21 (28021)
- Dynamic fast, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Opp 8 @Tradehub 21 (28021)
- Dynamic cool, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Opp 8 @Tradehub 21 (28021)
- Dynamic reliable, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Opp 8 @Tradehub 21 (28021)

### random_16 / base

Ctrl Lib (16181) -> Tentera Diraja Mque (16141)
Status: completed; search: {'expansions': 4, 'candidates': 1}; total experiment seconds: 1.18.

- Fixed fast: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 10-D2: Kent Ridge Ter (16009) -> Aft Clementi Rd (16089) | 183-D1: Aft Clementi Rd (16089) -> Tentera Diraja Mque (16141)
- Fixed cool: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 10-D2: Kent Ridge Ter (16009) -> Aft Clementi Rd (16089) | 183-D1: Aft Clementi Rd (16089) -> Tentera Diraja Mque (16141)
- Fixed reliable: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 10-D2: Kent Ridge Ter (16009) -> Aft Clementi Rd (16089) | 183-D1: Aft Clementi Rd (16089) -> Tentera Diraja Mque (16141)
- Dynamic fast, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 10-D2: Kent Ridge Ter (16009) -> Aft Clementi Rd (16089) | 183-D1: Aft Clementi Rd (16089) -> Tentera Diraja Mque (16141)
- Dynamic cool, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 10-D2: Kent Ridge Ter (16009) -> Aft Clementi Rd (16089) | 183-D1: Aft Clementi Rd (16089) -> Tentera Diraja Mque (16141)
- Dynamic reliable, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 10-D2: Kent Ridge Ter (16009) -> Aft Clementi Rd (16089) | 183-D1: Aft Clementi Rd (16089) -> Tentera Diraja Mque (16141)

### random_17 / base

Aft Kent Ridge Dr (16191) -> Bef Seventh-Day Advent Ch (28449)
Status: completed; search: {'expansions': 8, 'candidates': 3}; total experiment seconds: 2.53.

- Fixed fast: 151-D1: Aft Kent Ridge Dr (16191) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Bef Seventh-Day Advent Ch (28449)
- Fixed cool: 151-D1: Aft Kent Ridge Dr (16191) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Bef Seventh-Day Advent Ch (28449)
- Fixed reliable: 151-D1: Aft Kent Ridge Dr (16191) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Bef Seventh-Day Advent Ch (28449)
- Dynamic fast, test world 0 only (complete=True): 151-D1: Aft Kent Ridge Dr (16191) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Bef Seventh-Day Advent Ch (28449)
- Dynamic cool, test world 0 only (complete=True): 151-D1: Aft Kent Ridge Dr (16191) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Bef Seventh-Day Advent Ch (28449)
- Dynamic reliable, test world 0 only (complete=True): 151-D1: Aft Kent Ridge Dr (16191) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Bef Seventh-Day Advent Ch (28449)

### random_18 / base

Ctrl Lib (16181) -> Nan Hua Pr Sch (20101)
Status: completed; search: {'expansions': 8, 'candidates': 3}; total experiment seconds: 2.53.

- Fixed fast: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Nan Hua Pr Sch (20101)
- Fixed cool: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Nan Hua Pr Sch (20101)
- Fixed reliable: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Nan Hua Pr Sch (20101)
- Dynamic fast, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Nan Hua Pr Sch (20101)
- Dynamic cool, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Nan Hua Pr Sch (20101)
- Dynamic reliable, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Nan Hua Pr Sch (20101)

### random_19 / base

Ctrl Lib (16181) -> Jurong East Int (28009)
Status: completed; search: {'expansions': 8, 'candidates': 3}; total experiment seconds: 2.52.

- Fixed fast: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Jurong East Int (28009)
- Fixed cool: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Jurong East Int (28009)
- Fixed reliable: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Jurong East Int (28009)
- Dynamic fast, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Jurong East Int (28009)
- Dynamic cool, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Jurong East Int (28009)
- Dynamic reliable, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 201-D1: Kent Ridge Ter (16009) -> Blk 455 (17161) | 105-D1: Blk 455 (17161) -> Jurong East Int (28009)

### random_20 / base

Ctrl Lib (16181) -> Opp Kent Ridge Ter (16131)
Status: completed; search: {'expansions': 4, 'candidates': 1}; total experiment seconds: 1.19.

- Fixed fast: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 10-D2: Kent Ridge Ter (16009) -> Aft Clementi Rd (16089) | 183-D1: Aft Clementi Rd (16089) -> Opp Kent Ridge Ter (16131)
- Fixed cool: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 10-D2: Kent Ridge Ter (16009) -> Aft Clementi Rd (16089) | 183-D1: Aft Clementi Rd (16089) -> Opp Kent Ridge Ter (16131)
- Fixed reliable: 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 10-D2: Kent Ridge Ter (16009) -> Aft Clementi Rd (16089) | 183-D1: Aft Clementi Rd (16089) -> Opp Kent Ridge Ter (16131)
- Dynamic fast, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 10-D2: Kent Ridge Ter (16009) -> Aft Clementi Rd (16089) | 183-D1: Aft Clementi Rd (16089) -> Opp Kent Ridge Ter (16131)
- Dynamic cool, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 10-D2: Kent Ridge Ter (16009) -> Aft Clementi Rd (16089) | 183-D1: Aft Clementi Rd (16089) -> Opp Kent Ridge Ter (16131)
- Dynamic reliable, test world 0 only (complete=True): 151-D1: Ctrl Lib (16181) -> Kent Ridge Ter (16009) | 10-D2: Kent Ridge Ter (16009) -> Aft Clementi Rd (16089) | 183-D1: Aft Clementi Rd (16089) -> Opp Kent Ridge Ter (16131)

### home / headway20

Information Technology (16189) -> Signature Pk Condo (42171)
Status: completed; search: {'expansions': 260, 'candidates': 94}; total experiment seconds: 47.24.

- Fixed fast: 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)
- Fixed cool: 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)
- Fixed reliable: 151-D2: Information Technology (16189) -> Bef Dunearn Rd (42141) | 61-D2: Bef Dunearn Rd (42141) -> Signature Pk Condo (42171)
- Dynamic fast, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Bef Dunearn Rd (42141) | 61-D2: Bef Dunearn Rd (42141) -> Signature Pk Condo (42171)
- Dynamic cool, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Bef Dunearn Rd (42141) | 61-D2: Bef Dunearn Rd (42141) -> Signature Pk Condo (42171)
- Dynamic reliable, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)

### home / delay8

Information Technology (16189) -> Signature Pk Condo (42171)
Status: completed; search: {'expansions': 260, 'candidates': 94}; total experiment seconds: 50.15.

- Fixed fast: 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)
- Fixed cool: 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)
- Fixed reliable: 151-D2: Information Technology (16189) -> Bef Dunearn Rd (42141) | 61-D2: Bef Dunearn Rd (42141) -> Signature Pk Condo (42171)
- Dynamic fast, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)
- Dynamic cool, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)
- Dynamic reliable, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)

### home / buffer5

Information Technology (16189) -> Signature Pk Condo (42171)
Status: completed; search: {'expansions': 260, 'candidates': 94}; total experiment seconds: 49.13.

- Fixed fast: 151-D2: Information Technology (16189) -> Bef Dunearn Rd (42141) | 61-D2: Bef Dunearn Rd (42141) -> Signature Pk Condo (42171)
- Fixed cool: 151-D2: Information Technology (16189) -> Bef Dunearn Rd (42141) | 61-D2: Bef Dunearn Rd (42141) -> Signature Pk Condo (42171)
- Fixed reliable: 151-D2: Information Technology (16189) -> Bef Dunearn Rd (42141) | 61-D2: Bef Dunearn Rd (42141) -> Signature Pk Condo (42171)
- Dynamic fast, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)
- Dynamic cool, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)
- Dynamic reliable, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)

### home / synchronized

Information Technology (16189) -> Signature Pk Condo (42171)
Status: completed; search: {'expansions': 260, 'candidates': 94}; total experiment seconds: 56.12.

- Fixed fast: 151-D2: Information Technology (16189) -> Blk 109 (12061) | 184-D1: Blk 109 (12061) -> Pei Hwa Presby Pr Sch (42071) | 157-D1: Pei Hwa Presby Pr Sch (42071) -> Signature Pk Condo (42171)
- Fixed cool: 151-D2: Information Technology (16189) -> Blk 109 (12061) | 52-D2: Blk 109 (12061) -> Pei Hwa Presby Pr Sch (42071) | 157-D1: Pei Hwa Presby Pr Sch (42071) -> Signature Pk Condo (42171)
- Fixed reliable: 151-D2: Information Technology (16189) -> Blk 109 (12061) | 61-D2: Blk 109 (12061) -> Signature Pk Condo (42171)
- Dynamic fast, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Bef Dunearn Rd (42141) | 184-D1: Bef Dunearn Rd (42141) -> Pei Hwa Presby Pr Sch (42071) | 157-D1: Pei Hwa Presby Pr Sch (42071) -> Signature Pk Condo (42171)
- Dynamic cool, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Bef Dunearn Rd (42141) | 184-D1: Bef Dunearn Rd (42141) -> Pei Hwa Presby Pr Sch (42071) | 157-D1: Pei Hwa Presby Pr Sch (42071) -> Signature Pk Condo (42171)
- Dynamic reliable, test world 0 only (complete=True): 151-D2: Information Technology (16189) -> Bef Dunearn Rd (42141) | 61-D2: Bef Dunearn Rd (42141) -> Signature Pk Condo (42171)

## Interpretation

Every sampled pair is retained, including equal, worse and uncomputed outcomes.
A world-0 route is an illustration, not a fixed prescription for the adaptive strategy.
Riding through Pei Hwa on 61 does not add a transfer, wait or second boarding delay.
Incomplete trips retain infinite durations (JSON null); wait/count metrics then describe prefixes.
JSON includes all candidates, selected fixed routes, actual dynamic examples, source-backed names,
paired Monte Carlo intervals and per-strategy evaluation time. Timings are batch timings, not production latency.
No walking links, vehicle capacity, actual timetables or calibrated catch probabilities are modeled.
This small preselected corridor and stratified sample cannot represent all Singapore trips.

Reproduce: `python -m experiments.local_routes` (no credentials required).

This project is an independent research project and is not affiliated with, endorsed by, or sponsored
by the Land Transport Authority of Singapore, Google, or Citymapper.

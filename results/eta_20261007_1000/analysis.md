# Recorded ETA window analysis

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

## Scope

Offline analysis only; zero new API requests. Times use Singapore UTC+08:00.
Four virtual demands are not four observed passenger trips or independent samples.
No Google comparison or actual catch/long-wait probability is possible from this recording alone.

## Coverage

| Stop | Responses | Errors | Max gap (s) | Monitored entries | Unmonitored entries |
| --- | ---: | ---: | ---: | ---: | ---: |
| 11261 | 120 | 0 | 60.60 | 1860 | 300 |
| 11401 | 120 | 0 | 60.77 | 911 | 529 |
| 12061 | 120 | 0 | 60.06 | 2043 | 477 |
| 12071 | 120 | 0 | 60.07 | 2088 | 432 |
| 16189 | 120 | 0 | 60.10 | 263 | 817 |
| 42071 | 120 | 0 | 60.13 | 3781 | 539 |
| 42141 | 120 | 0 | 60.16 | 2234 | 286 |
| 42171 | 120 | 0 | 60.53 | 2474 | 46 |

Fresh departure/stop snapshots: 32/32.
Fresh snapshots do not guarantee continuous monitored vehicle evidence.

## Conditional replay

Three-minute transfer buffer; zero alighting ETA shift.
Fixed routes and both flexible policies expose the same recorded intermediate stops.
Fixed routes are declared in advance, not chosen from their realized outcomes.
The flexible pool contains all three fixed paths plus the Blk 109 -> Pei Hwa branches.
No walking alternative is replayed: its connecting stops were not collected.
The 96 -> 173 route is also outside this capture. No results are imputed for either.

| Departure | Strategy | Status | Modeled total (min) | Prefix wait (min) |
| --- | --- | --- | ---: | ---: |
| 10:00 | fixed_151_61 | boarding_identity_ambiguous | unknown | 0.20 |
| 10:00 | fixed_95_970 | modeled_complete | 52.25 | 14.65 |
| 10:00 | fixed_151_61_blk109 | boarding_identity_ambiguous | unknown | 0.20 |
| 10:00 | first_eligible | boarding_identity_ambiguous | unknown | 0.20 |
| 10:00 | stationary_suffix | boarding_identity_ambiguous | unknown | 0.20 |
| 10:15 | fixed_151_61 | boarding_identity_ambiguous | unknown | 11.87 |
| 10:15 | fixed_95_970 | modeled_complete | 60.32 | 21.02 |
| 10:15 | fixed_151_61_blk109 | boarding_identity_ambiguous | unknown | 11.87 |
| 10:15 | first_eligible | modeled_complete | 60.32 | 21.02 |
| 10:15 | stationary_suffix | boarding_identity_ambiguous | unknown | 11.87 |
| 10:30 | fixed_151_61 | boarding_identity_ambiguous | unknown | 4.62 |
| 10:30 | fixed_95_970 | modeled_complete | 45.32 | 6.47 |
| 10:30 | fixed_151_61_blk109 | boarding_identity_ambiguous | unknown | 4.62 |
| 10:30 | first_eligible | modeled_complete | 45.32 | 6.47 |
| 10:30 | stationary_suffix | boarding_identity_ambiguous | unknown | 4.62 |
| 10:45 | fixed_151_61 | boarding_between_polls_unknown | unknown | 10.78 |
| 10:45 | fixed_95_970 | modeled_complete | 57.05 | 19.55 |
| 10:45 | fixed_151_61_blk109 | modeled_complete | 43.02 | 23.82 |
| 10:45 | first_eligible | modeled_complete | 57.05 | 19.55 |
| 10:45 | stationary_suffix | boarding_between_polls_unknown | unknown | 10.78 |

Unknown is not a failed transfer, slow trip, or successful completion.
Prefix waiting is a partial accounted lower bound, not a complete journey score.
Never rank completed-only results against censored alternatives.
Full traces and all 1/3/5-minute-buffer x -60/0/+60-second-shift scenarios are in analysis.json and replay.csv.
The nine scenarios per demand are correlated sensitivity checks, not probability samples.

## Blk 109 forecast opportunities

At each of 120 response times compare 61 alone against 61/52/75/184, with a three-minute buffer.
A station probe assumes availability now; a 151 probe uses that snapshot's earliest future 151 ETA.
The latter is NOT matched to the bus boarded at the origin. Only same-flag predictions are paired.
Wait includes the transfer buffer. Paired rows require both sets to have a future eligible prediction.
Unmonitored and monitored forecasts are deliberately not pooled; missing predictions remain unknown.

| Monitored | Probe | Paired / all snapshots | 61 mean forecast wait | Multi mean forecast wait | 61 >10m count | Multi >10m count |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| True | station now | 120/120 | 10.98 | 4.99 | 65 | 1 |
| True | 151 | 106/120 | 11.28 | 5.10 | 51 | 0 |
| False | station now | 0/120 | unknown | unknown | 0 | 0 |
| False | 151 | 0/120 | unknown | unknown | 0 | 0 |

These are overlapping forecast snapshots, not independent waits or long-wait probabilities.
Taking the minimum over a superset cannot increase this local forecast wait by construction.
This does not establish a faster full trip: alternative services may require another transfer.

## Forecast revisions

Only unique monitored temporal associations passing fixed gates are used.
Positive means a later absolute ETA, not countdown time elapsed and not measured lateness.
The matcher rejects revisions over 120 seconds and ambiguous/missing positions.
Thus these conditional quantiles are selection-truncated and MUST NOT calibrate ETA errors.

| Stop | Service | Matched updates | Median absolute revision (s) | P95 absolute revision (s) | Later >30s | Earlier >30s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 11261 | 61 | 280 | 18.00 | 56.00 | 46 | 26 |
| 11261 | 75 | 248 | 19.00 | 57.00 | 34 | 34 |
| 11261 | 95 | 174 | 18.00 | 63.00 | 28 | 23 |
| 11261 | 970 | 343 | 17.00 | 64.00 | 50 | 49 |
| 11401 | 61 | 283 | 15.00 | 51.00 | 43 | 22 |
| 11401 | 95 | 161 | 18.00 | 67.00 | 28 | 24 |
| 11401 | 970 | 344 | 17.00 | 64.00 | 57 | 46 |
| 12061 | 151 | 138 | 14.00 | 61.00 | 23 | 11 |
| 12061 | 184 | 342 | 16.00 | 60.00 | 48 | 33 |
| 12061 | 52 | 245 | 18.00 | 61.00 | 38 | 41 |
| 12061 | 61 | 278 | 17.00 | 54.00 | 41 | 26 |
| 12061 | 75 | 331 | 19.00 | 56.00 | 44 | 43 |
| 12071 | 151 | 154 | 16.00 | 64.00 | 30 | 14 |
| 12071 | 184 | 340 | 16.00 | 60.00 | 47 | 34 |
| 12071 | 52 | 259 | 17.00 | 64.00 | 38 | 40 |
| 12071 | 61 | 275 | 17.00 | 54.00 | 38 | 26 |
| 12071 | 75 | 332 | 18.00 | 58.00 | 41 | 42 |
| 16189 | 151 | 33 | 25.00 | 62.00 | 10 | 5 |
| 16189 | 95 | 17 | 21.00 | 61.00 | 4 | 3 |
| 42071 | 184 | 342 | 15.00 | 60.00 | 44 | 31 |
| 42071 | 52 | 295 | 16.00 | 61.00 | 42 | 41 |
| 42071 | 61 | 260 | 17.00 | 56.00 | 33 | 22 |
| 42071 | 75 | 345 | 17.00 | 59.00 | 43 | 40 |
| 42071 | 970 | 346 | 14.00 | 61.00 | 40 | 39 |
| 42141 | 151 | 205 | 16.00 | 62.00 | 36 | 19 |
| 42141 | 184 | 342 | 15.00 | 58.00 | 41 | 31 |
| 42141 | 52 | 288 | 15.00 | 62.00 | 43 | 43 |
| 42141 | 61 | 267 | 16.00 | 55.00 | 33 | 24 |
| 42141 | 75 | 343 | 17.00 | 59.00 | 43 | 39 |
| 42171 | 61 | 252 | 17.00 | 56.00 | 29 | 25 |
| 42171 | 970 | 347 | 15.00 | 58.00 | 44 | 40 |

## Reverse-search check

Both existing full enumeration and hub-oriented candidate discovery already use reverse directed ride-time bounds.
This check compares those existing searches, not a new fluid algorithm. Maximum two transfers on the projected network.
Full enumeration: 21 routes / 31 expansions.
Hub-oriented search: 18 routes / 29 expansions; selected hubs: ['42071'].
Candidate recall: 0.857; missing route descriptions: 3.
Truncated: True; reasons: ['prefix_or_ordinary_limit'].
Search counts exclude indexing overhead and do not prove a wall-clock speedup.
Candidate recall is not executable shared-graph recall; shared branches may recombine into omitted descriptions.
No quality gain is claimed and this audit does not change the declared ETA-replay candidate pool.
Raw bus count is not an adequate downstream value: remaining riding, transfer waits, direction,
vehicle continuation and correlated arrivals all matter. The current ride lower bound has no waiting-risk model.
Cache reusable downstream structure, retain bypasses and measure omissions before more aggressive hub pruning.

## Assumptions and next decision

ETA-as-event replay remains conditional on provisional identity, freshness <=90s and five-second onboard observation grace.
Same-bus continuation has no extra boarding, transfer or waiting. Ambiguity remains unknown.
Only evidence received by the virtual decision time can enter a decision; later updates only advance replay chronologically.
The stationary suffix policy uses existing mean-plus-transfer scoring, H=15min, distance/20kmh (>=0.5min per original segment),
delay_max=3min, 64 draws/seed29 and a five-minute transfer penalty. These assumptions are NOT fitted to today's data.
Limits of 5 transfers/45-minute gap/120-minute trip are model constraints, not verified fare law.
Reverse downstream propagation can reuse shared route structure, but cannot fix missing vehicle identity or ETA error.
Do not loosen identity gates or substitute unmonitored forecasts merely to manufacture complete trips.
Priority before a catch-probability claim: independently observed arrival evidence or a separately validated error model.
No additional collection window is authorized or started by this analysis.

## Reproduce

`python -m experiments.analyze_eta_window --config experiments/eta_window_20261007.json`

Requires the locally retained, git-ignored recording and frozen BusRoutes.csv. Source hashes and parameters are in analysis.json.
Detailed revision/probe evidence is in data/recorded/cleaned; analysis parameters in data/recorded/parameters.

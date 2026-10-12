# Detailed Reference: 2026-10-04 16:00 SGT

Latest user transcription supersedes the overview for this comparison only. Original records are unchanged.
First total (48 minutes) is derived from 16:00 to 16:48; other totals are in the supplied headers.
Final stop 42171 is inferred from the name Signature Pk Condo, not an ID printed in the details.

## Google Planned Time Components

| Services | Initial wait | Riding | Transfer interval | Walk within interval | Final walk | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 151 -> 61 | 16 | 17 | 15 | 0 | 0 | 48 |
| 151 -> 174 | 16 | 19 | 17 | 5 | 0 | 52 |
| 95 -> 970 | 12 | 35 | 16 | 0 | 0 | 63 |
| 96 -> 173 | 15 | 32 | 13 | 0 | 5 | 65 |

Transfer interval INCLUDES the transfer walk; do not add that walk twice.
Walking estimates are approximate; residual waiting is inferred, not separately measured.
No walking leg is present for 151/61 or 95/970 in the latest text; this revises the earlier overview.
These are planned times, not observed journeys.

## Exact Transfer Route Simulation

10000 samples, seed 100; unchanged headway 15 min, speed 20 km/h and delay bound 3 min.
95 is extended to 11261 from the frozen static CSV, not from Google's route timings.

| Route / transfer stop | Google total | Model mean | Model P95 | Google riding | Model riding, no delay |
| --- | ---: | ---: | ---: | ---: | ---: |
| 151_61 / 42141 | 48 | 40.85 | 51.30 | 17 | 19.80 |
| 95_970 / 11261 | 63 | 54.22 | 64.74 | 35 | 33.30 |

Exact transfer geometry is now modeled, but no dated timetable is fitted.
The first Google wait of 16 minutes exceeds the model's assumed Uniform(0,15) initial wait.
A difference against Google here measures model/schedule disagreement, not an algorithm win.

## Same-Model Algorithm Comparison

| Strategy | Mean | P95 |
| --- | ---: | ---: |
| shortest_expected | 40.85 | 51.30 |
| full_adaptive | 40.60 | 50.84 |
| bounded_adaptive | 40.83 | 51.22 |

## Still Outside This Bus-Only Experiment

151 -> walk -> 174: transfer walk between Opp King Albert Pk Stn and King Albert Pk (42061).
96 -> 173: alights at Bef Jln Jurong Kechil, then walks about 400 m / 5 min to the destination place.
Neither walking itinerary is silently replaced by a different bus-only route or assigned an invented duration.
This comparison does not require any new API request. No Google screenshot or bulk route content is saved.

Reproduce: `python -m experiments.pei_hwa_details`.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

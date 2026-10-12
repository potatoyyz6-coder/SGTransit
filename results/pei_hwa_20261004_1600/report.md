# Google Reference: 2026-10-04 16:00 SGT

Information Technology (16189) to intended Signature Pk Condo (42171).
Manual user observations only; no screenshot saved or API accessed.

The full date comes from the user. The crop shows Sunday, not the calendar date or destination.
Model values reuse the October 1 stationary experiment; no new Sunday simulation or timetable is implied.

| Services | Google displayed min | Model mean min | Model P95 min | Status |
| --- | ---: | ---: | ---: | --- |
| 151 -> 61 | 53 | 40.85 | 51.30 | Service-pair reference only; transfer/alighting stops and walking not matched |
| 151 -> 174 | 57 | N/A | N/A | Interchange walking edge not modeled |
| 95 -> 970 | 67 | 54.22 | 64.74 | Service-pair reference only; transfer/alighting stops and walking not matched |
| 96 -> 173 | 67 | N/A | N/A | Service pair not represented in the current model |

## Scope Differences

151 -> 61 shows boarding at 16:16 after a 16:00 query, a 16-minute pre-boarding interval,
and 5 minutes walking with unknown allocation. Do not label 53 minutes as in-vehicle time
or assume 53 minus 5 matches the model. The model includes random initial waiting.

- All four Google options show final walking; the model ends at bus stop 42171.
- The destination is not visible in the crop. Same service numbers do not establish identical routes.
- No subtraction of walking or initial waiting from totals: components and endpoints are unverified.
- No Google-minus-model speedup is computed. Google observations do not change any model parameter.
- The October 1 experiment remains unchanged; only the external query is dated October 4.

## Next Evidence

For 151 -> 61, request the transfer stop, final alighting stop, and walking-leg endpoints/durations.
For 151 -> walk -> 174, a pedestrian connection must be identified before representing the itinerary.
96 -> 173 needs a separately verified network extension; no runtime is invented for it.

Reproduce: `python -m experiments.compare_pei_hwa_reference`.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

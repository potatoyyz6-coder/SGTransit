# October 4, 12:45 manual reference and capture status

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

## Status

No live API requests were made for this observation during this task.
At the pre-launch clock check it was already 13:52 Singapore time, after all
three quoted arrivals. No contemporaneous capture exists from this task.
Do not substitute later ETAs or the older stationary simulation for missing
12:45 observations. A future departure must be agreed after capture is ready.

Minimum manually transcribed reference fields are in
`data/validation/google_pei_hwa_20261004_1245.json`. No Google API, scraping,
screenshots, or full route payloads were used or saved. Observation time is
unknown; October 4 is inherited from the conversation, not independently
verified against a screenshot.

| Services | Start in supplied text | Arrival | Duration | Caveat |
| --- | --- | --- | --- | --- |
| 151 -> 61 | 12:47 | 13:21 | 34 min from shown start; 36 from 12:45 | Derived, not a displayed total; transfer at 12071 shows 13:12 for both buses |
| 95 -> 970 | 12:45 | 13:48 | 63 min | Transfer at 11261 |
| 96 -> 173 -> walk | 12:45 | 13:50 | 65 min | Includes 5 min final walking; transfer at 17009 |

Minute-rounded equal times establish neither success nor failure. With the
existing model's 3-minute transfer buffer, nominal 13:12 arrival cannot catch
a nominal 13:12 departure. That is a model assumption, not an observation of
the actual buses, and cannot yield a calibrated missed-connection probability.
The next 61's waiting time is unknown in this reference.

## Ready for a future pilot

`src/sg_transit/eta_pilot.py` collects normalized LTA ETA predictions with
request and response timestamps and the original NextBus/NextBus2/NextBus3
slot. Slots and VisitNumber are not unique vehicle identities. Each record
is flushed to disk; an empty successful response is distinct from a failure.

Proposed stops: 16189, 12071, 12061, 42141, 42071, 11261, 17009, 42231, 42171.
This covers the manual references and selected alternative transfer nodes;
it does not establish that every service combination is feasible.

Start before the agreed departure. Set a timezone-aware future deadline no
more than two hours ahead. The collector permits at most 1,200 requests,
paces each stop to at least 60 seconds between request starts, and stops
on the first API failure without retries. An in-flight request can finish
after the deadline; no further requests start. Computer sleep or loss of
network creates missing observations, not reconstructed history.

Run from the repository root in PowerShell, replacing the deadline before
running and using a new output filename for each session:

```powershell
$env:PYTHONPATH = "src"
$deadline = Read-Host "Future deadline in ISO format, including +08:00"
python -m sg_transit.eta_pilot `
  --stop 16189 --stop 12071 --stop 12061 --stop 42141 --stop 42071 `
  --stop 11261 --stop 17009 --stop 42231 --stop 42171 `
  --until $deadline --max-requests 1200 `
  --output data/recorded/raw/eta_pilot_new_session.jsonl
```

The existing `LTA_DATAMALL_API_KEY` environment variable supplies credentials.
Stop with Ctrl+C, or create the output's same-stem `.stop` file. Existing
output files are never overwritten. Raw-observation storage is git-ignored;
these are normalized predictions, not verbatim API responses. Keep future
cleaning, fitted parameters, and derived results in separate directories.

Terms checked on October 4:
[LTA API Terms](https://datamall.lta.gov.sg/content/datamall/en/api-terms-of-service.html).
This pilot uses a conservative local request budget independent of any
account quota, and makes no assurance about service availability.

## Subsequent analysis, not yet implemented by this pilot

- Replay only observations received by each decision time, without future leakage.
- Match possible vehicles with uncertainty; do not align NextBus ranks across stops.
- Mark ambiguous arrival/departure events unknown, not observed successes/failures.
- Treat staying onboard 61 as continuation, not another boarding or wait.
- Report available-service waits and long-wait events separately from model estimates.
- Calibrate catch probabilities using multiple independent events and suitable
  outcome evidence. A single ETA trace is not actual arrival ground truth.

Neither a Google duration nor the earlier uniform-headway simulations supply
an empirical catch probability for this trip. No speedup claim is made.

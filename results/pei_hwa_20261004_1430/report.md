# October 4, 14:30 ETA observation pilot

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

## Experiment registration

### Completed capture audit

Both collectors have exited. Offline audit confirms 1,126 requests in total:
1,125 successful and one error; persisted counts agree with completion records.
The original nine stops each have 105 successful observations, from 13:58 to
15:42. At 15:43:50 the main collector stopped after an LTAApiError, before its
planned 15:50 cutoff. The retained safe error type does not establish the cause.
The supplementary two stops each have 90 observations, from 14:01 to 15:30;
their collector stopped normally at its 180-request budget.

No within-window response gap exceeds 90 seconds; the largest across all
stops is 63.66 seconds. None of the successful stop responses has an empty
arrival list. This is coverage evidence, not proof that every individual
service has usable, accurate, or monitored predictions.

Detailed reproducible results: [audit.md](audit.md), with source hashes,
per-stop coverage, and as-of diagnostics in `audit.json`. Replay the audit:

```powershell
python -m experiments.audit_eta_pilot `
  --input data/recorded/raw/eta_pilot_20261004_1430.jsonl `
  --input data/recorded/raw/eta_pilot_20261004_1430_walk.jsonl `
  --output results/pei_hwa_20261004_1430
```

The 15:05 diagnostic at 12071 uses the response received at 15:04:43.906426,
not a later observation. It predicts the next 151 at 15:05:20 and the next
61 at 15:09:38, a nominal separation of 4 minutes 18 seconds. Both entries
have Monitored=true. This does not identify the origin-boarded bus, prove a
successful transfer, or establish the final destination arrival time.
Similarly, at 15:29 the future 151 and 61 predictions are 15:31:21 and
15:33:08, only 1 minute 47 seconds apart. With a 3-minute transfer buffer,
that nominal pair is insufficient, but this is not an observed missed bus.

Conditional ETA-driven route replay is now implemented; actual-trip validation
and calibrated catch/long-wait probabilities remain unfinished. See
[replay.md](replay.md) and `replay.json` for explicit event assumptions and nine
buffer/arrival-shift scenarios. In the base scenario the first-eligible hub
strategy selects 151 -> 52 -> 157, with a conditional modeled total of 45.50
minutes. The 95 -> 970 and walking-174 variants yield 60.30 and 51.76 minutes.
The fixed 151 -> 61 result is unknown because its pending boarding ETA crosses
between polling times. It is not assigned an extra headway or a fabricated
complete-trip duration. These outcomes cannot establish a speedup against
Google or rank all strategies when one outcome is unknown.

The original shared-suffix decision module is now integrated as
`stationary_suffix_policy`, alongside `first_eligible_shared_stops` on identical
recorded-stop paths. Its local objective is stationary expected remaining time
plus transfer penalties, not the aggregate P90/P95 reliability objective and
not a calibrated catch probability. Its base conditional replay chooses
151 -> 61 via Blk 109, staying onboard through Pei Hwa, and yields 40.27
modeled minutes with one transfer and maximum transfer wait 11.47 minutes.
First-eligible on the same decision stops yields 45.50 minutes, two transfers,
and maximum transfer wait 9.02 minutes. This is a conditional tradeoff between
the longest single wait, total time, and transfer count, not a demonstrated
real-world performance advantage or a probability estimate.

The adapter uses the existing value model and current-stop departure inputs,
restricting executable actions to the retained path prefixes. Continuation
preserves earlier cross-stop associations through unique, fresh temporal
chains; it neither creates a new boarding nor relaxes spatial matching gates.
No new API calls or Google-derived ride-time calibration were used.

Actual outcome validation remains incomplete. Additional prediction-only
snapshots cannot by themselves supply independent ground-truth catch labels.

Provisional cross-stop and temporal associations are implemented
in `src/sg_transit/eta_matching.py`; see [matching.md](matching.md). They retain
ambiguous candidates separately, reject unmonitored or invalid positions, and
timestamp when each association becomes available. These heuristic relations
are not verified vehicle IDs and must not be promoted to boarding/alighting truth.
The replay uses common observations, explicit modeled events and unknown
outcomes. Missing cross-stop evidence is not treated as absence of a local bus.
Do not fit the earlier synthetic timings to either Google or these snapshots.

For example, the 151 evidence anchored at 14:38:42 links an origin ETA of
14:39:17 to Blk 116 ETA 14:50:34. The downstream forecast can be followed through
14 sequential entries to the final response at 14:51:43 (ETA 14:51:16).
The final ETA is a retrospective prediction, not an actual alighting timestamp;
it was unavailable at the initial decision and cannot be used as a future oracle.

Static topology verification also confirms a directed 75 service segment from
12061 to 42071. This is an additional candidate absent from the earlier network,
not proof that boarding 75 is always beneficial. Static source validity is still
limited to the pinned source snapshot.

Audit tests: 5 passed (future-response exclusion, stale/missing observations,
expired and invalid ETA handling, coverage errors/gaps, timezone validation).

- User-selected departure: 2026-10-04 14:30, Asia/Singapore.
- Origin: Information Technology, 16189.
- Destination: Signature Pk Condo, 42171.
- Actual collection start: 2026-10-04 13:58:42, Asia/Singapore.
- Scheduled cutoff: 2026-10-04 15:50, Asia/Singapore.
- Stops: 16189, 12071, 12061, 42141, 42071, 11261, 17009, 42231, 42171.
- Per-stop polling interval: at least 60 seconds. Hard request cap: 1,200.
- Launch verification: first nine requests succeeded, output persisted, process
  52864 was running. This is a launch-time observation, not a completion claim.
- Google reference: user supplied four alternatives, recorded minimally in
  `data/validation/google_pei_hwa_20261004_1430.json`; actual lookup time unknown.

## Manual comparison clock

| Alternative | Shown start | Arrival | Google shown duration | Elapsed from 14:30 | Nominal transfer margin |
| --- | --- | --- | --- | --- | --- |
| 151 -> 61 | 14:40 | 15:14 | 34 min | 44 min | 0 min at 12071 |
| 151 -> walk -> 174 | 14:30 | 15:22 | 52 min | 52 min | 12 min after 5-min walk |
| 95 -> 970 | 14:30 | 15:33 | 63 min | 63 min | 16 min at 11261 |
| Later 151 -> 61 | 15:04 | 15:38 | 34 min | 68 min | 0 min at 12071 |

The comparison clock assumes availability at the origin at 14:30. The added
10 or 34 minutes before later displayed starts are pre-departure elapsed
time, not necessarily outdoor waiting. Keep that distinction for heat/discomfort
preferences. Do not describe either 34-minute alternative as 34 minutes from
14:30. The later alternative is not evidence of the fallback time after
missing the earlier 61.

The two 151 -> 61 alternatives show incoming arrival and onward departure in
the same minute. Rounded times do not prove either feasibility or failure;
the model's 3-minute transfer buffer would reject these nominal connections.
For 151 -> walk -> 174, the 17-minute transfer interval already includes
the 5-minute walk. The residual 12 minutes is before any added buffer, not
a guaranteed catch probability.

## Supplemental walking-transfer coverage

The new reference exposed two stops absent from the original nine-stop set:
Opp King Albert Pk Stn (42059) and King Albert Pk (42061), checked against the
local static stop-name mapping. A separate bounded collector was launched
for these two stops (PID 51480), leaving the original collection unchanged.
Its limit is 180 additional requests, at least 60 seconds per stop, ending
at the budget or 15:35 Singapore time, whichever comes first. Exact start
and completion status are in its JSONL metadata and completion records.

Supplement: `data/recorded/raw/eta_pilot_20261004_1430_walk.jsonl`.
Stop control: `data/recorded/raw/eta_pilot_20261004_1430_walk.stop`.
Capturing these stops enables inspection; walking-aware route replay is
not thereby implemented or validated. Do not infer missing walk outcomes.

## Local artifacts

- Normalized ETA observations: `data/recorded/raw/eta_pilot_20261004_1430.jsonl`.
- Completion summary: final JSONL record and corresponding `.stdout.log`.
- Stop control: create `data/recorded/raw/eta_pilot_20261004_1430.stop`.
- Collector: `src/sg_transit/eta_pilot.py`.

The local artifacts are git-ignored. Credentials are read from the existing
environment variable, never written into observation records. The hidden
background collector stops at the deadline, budget, stop file, or first API
error. The computer must stay awake and connected. The process is not a
scheduled Codex follow-up and does not automatically produce an analysis.

## Analysis boundaries

The earlier 12:45 Google references remain a separate observation and must
not be relabeled 14:30. Older stationary simulations are not predictions for
this departure. Captured ETAs are predictions, not verified vehicle arrival
events; rank slots cannot identify a vehicle across stops. Evaluate coverage
and matching uncertainty before attempting chronological route replay.

No catch probabilities, completed-trip times, calibrated waiting model, or
comparative speedup are claimed at launch. Any later analysis must distinguish
observed ETA records, inferred events, model assumptions, and manual external
references. Preserve missing or ambiguous outcomes as unknown.

## Verification

Full offline suite: 91 passed (one existing pytest cache permission warning).
After the final internal-error status change, focused collector suite:
10 passed. Tests use fake transports and clocks, not the live API.

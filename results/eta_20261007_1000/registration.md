# Registered ETA Capture Window

- User-approved collection: 2026-10-07 09:55 to 11:55, Asia/Singapore (+08:00).
- Virtual departures: 10:00, 10:15, 10:30, 10:45. These are query times, not assumed bus headways.
- Origin: Information Technology (16189); destination: Signature Pk Condo (42171).
- Stops: 16189, 12061, 12071, 42141, 42071, 11401, 11261, 42171.
- Minimum per-stop request interval: 60 seconds. Maximum total requests: 960.
- Request timeout: 8 seconds. No retries, supplementary authentication probe or extra window.
- Stop on first API error, deadline, request budget or local stop file.
- A start missed by more than 90 seconds stops the worker without collecting.
- Machine must remain awake and connected; the local worker cannot wake a sleeping computer.

Configuration: `experiments/eta_window_20261007.json`.
Launcher: `python -m experiments.scheduled_eta --plan experiments/eta_window_20261007.json`.
Do not relaunch a duplicate worker. Existing schedule logs and recordings prevent overwrite.

## Local Outputs

- Normalized response records: `data/recorded/raw/eta_pilot_20261007_1000.jsonl`.
- Schedule status/heartbeat: the same stem with `.schedule.jsonl`.
- Stop file: the same stem with `.stop`; creating it cancels waiting or collection.
- After capture: `data/recorded/cleaned/eta_pilot_20261007_1000_queries.json` indexes the
  latest response received at or before each virtual departure, separately per stop.
  Responses over 90 seconds old and error/missing records are marked unusable.
- Local recording directories are Git-ignored. No credentials or authenticated headers are logged.

## Analysis Boundaries

The worker collects forecasts and creates causal query indexes. It does not perform
Google queries, issue navigation advice, or prove actual boarding/arrival events.
Subsequent fixed-versus-dynamic replay must use only records received by each decision
time. Four overlapping departures are not independent real-world journey samples.
Separate schedule-based and location-based ETA estimates. Keep vehicle matching
ambiguity, missing snapshots and incomplete follow-up as unknown. Do not equate a
last forecast or disappearing response slot with actual arrival or bus identity.

Validation before launch: 16 tests passed using fake APIs and clocks. The worker
was confirmed alive in waiting state, with zero real requests before 09:55.
This registration is not a completion report; inspect the latest process and log
state before claiming collection succeeded.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

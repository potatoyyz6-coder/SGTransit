# Blk 18: historical snapshot-conditioned route references

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

Departure / frozen knowledge cutoff: **2026-10-08T11:20:01.741685+08:00**; day: weekday.
Blk 18 (42161) -> Coll of Design & Engrg (16159).
The cutoff is the LAST response receipt, not the scheduled 11:20:00 start. No response from after this cutoff is used.
No new API calls. This is a saved forecast plus a ride/wait model, NOT current navigation or an observed journey.

Search: completed; complete within declared bounds: True. Candidates: 7212; reference-eligible: 4558.
All candidates, exclusions, per-leg sources and service-sequence variants remain in reference.json.
Exclusions (overlap): {"limited_service_not_default": 2654, "outside_historical_window": 2654}.

## Route comparison

Both columns use the SAME route and riding/delay assumptions. A difference is not measured time saved.
Wait excludes the separately charged transfer buffer; delay is charged once per boarding.

| ID | Services | Snapshot + model min | Model only min | Difference | Ride | Wait | Buffer | Delay | ETA / modeled boardings |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| R00146 | 173-D1 -> 188-D1 | 40.29 | 42.60 | -2.31 | 21.60 | 12.69 | 3.00 | 3.00 | 2 / 0 |
| R00261 | 173-D1 -> 183-D1 | 40.50 | 42.60 | -2.10 | 21.60 | 12.90 | 3.00 | 3.00 | 2 / 0 |
| R00001 | 173-D1 -> 96-D1 | 41.72 | 43.80 | -2.08 | 22.80 | 12.92 | 3.00 | 3.00 | 1 / 1 |
| R00057 | 173-D1 -> 105-D2 -> 183-D1 | 47.74 | 54.60 | -6.86 | 21.60 | 15.64 | 6.00 | 4.50 | 2 / 1 |
| R00059 | 173-D1 -> 105-D2 -> 96-D1 | 47.74 | 54.60 | -6.86 | 21.60 | 15.64 | 6.00 | 4.50 | 2 / 1 |
| R02615 | 41-D1 -> 106-D1 -> 183-D1 | 51.05 | 52.80 | -1.75 | 19.80 | 20.75 | 6.00 | 4.50 | 1 / 2 |
| R02617 | 41-D1 -> 106-D1 -> 96-D1 | 51.05 | 52.80 | -1.75 | 19.80 | 20.75 | 6.00 | 4.50 | 1 / 2 |
| R00262 | 173-D1 -> 183-D1 -> 96-D1 | 52.50 | 54.60 | -2.10 | 21.60 | 20.40 | 6.00 | 4.50 | 2 / 1 |

## Preference references

These are separate reference choices, not a calibrated risk ranking. Waiting preference includes transfer buffer, excludes modeled boarding delay.

- estimated_fastest: R00146, 173-D1 -> 188-D1; 40.29 min, 1 transfers, 15.69 min wait including buffer.
- fewest_transfers: R00146, 173-D1 -> 188-D1; 40.29 min, 1 transfers, 15.69 min wait including buffer.
- least_outdoor_wait: R00146, 173-D1 -> 188-D1; 40.29 min, 1 transfers, 15.69 min wait including buffer.

### R00146: 173-D1 -> 188-D1

Estimated arrival: 2026-10-08T12:00:19+08:00. Timing/availability: forecast_only_not_confirmed. Eligible stop variants: 2.

| Service | Board -> alight | Predicted/model board -> model alight | Wait | Timing source | Monitored |
| --- | --- | --- | ---: | --- | --- |
| 173-D1 | Blk 18 (42161) -> Aft Clementi Fire Stn (20109) | 11:25:27 -> 11:39:33 | 5.42 | snapshot_eta | True |
| 188-D1 | Aft Clementi Fire Stn (20109) -> Coll of Design & Engrg (16159) | 11:49:49 -> 12:00:19 | 7.27 | snapshot_eta | True |

### R00261: 173-D1 -> 183-D1

Estimated arrival: 2026-10-08T12:00:32+08:00. Timing/availability: forecast_only_not_confirmed. Eligible stop variants: 3.

| Service | Board -> alight | Predicted/model board -> model alight | Wait | Timing source | Monitored |
| --- | --- | --- | ---: | --- | --- |
| 173-D1 | Blk 18 (42161) -> Aft Toh Tuck Ave (28019) | 11:25:27 -> 11:37:45 | 5.42 | snapshot_eta | True |
| 183-D1 | Aft Toh Tuck Ave (28019) -> Coll of Design & Engrg (16159) | 11:48:14 -> 12:00:32 | 7.48 | snapshot_eta | False |

### R00001: 173-D1 -> 96-D1

Estimated arrival: 2026-10-08T12:01:45+08:00. Timing/availability: unknown_where_modeled. Eligible stop variants: 1.

| Service | Board -> alight | Predicted/model board -> model alight | Wait | Timing source | Monitored |
| --- | --- | --- | ---: | --- | --- |
| 173-D1 | Blk 18 (42161) -> Clementi Int (17009) | 11:25:27 -> 11:41:39 | 5.42 | snapshot_eta | True |
| 96-D1 | Clementi Int (17009) -> Coll of Design & Engrg (16159) | 11:52:09 -> 12:01:45 | 7.50 | modeled_wait (beyond_forecast_horizon) | None |

### R00057: 173-D1 -> 105-D2 -> 183-D1

Estimated arrival: 2026-10-08T12:07:46+08:00. Timing/availability: unknown_where_modeled. Eligible stop variants: 12.

| Service | Board -> alight | Predicted/model board -> model alight | Wait | Timing source | Monitored |
| --- | --- | --- | ---: | --- | --- |
| 173-D1 | Blk 18 (42161) -> Aft Clementi Fire Stn (20109) | 11:25:27 -> 11:39:33 | 5.42 | snapshot_eta | True |
| 105-D2 | Aft Clementi Fire Stn (20109) -> Blk 365 (17159) | 11:45:16 -> 11:50:58 | 2.72 | snapshot_eta | False |
| 183-D1 | Blk 365 (17159) -> Coll of Design & Engrg (16159) | 12:01:28 -> 12:07:46 | 7.50 | modeled_wait (beyond_forecast_horizon) | None |

### R00059: 173-D1 -> 105-D2 -> 96-D1

Estimated arrival: 2026-10-08T12:07:46+08:00. Timing/availability: unknown_where_modeled. Eligible stop variants: 3.

| Service | Board -> alight | Predicted/model board -> model alight | Wait | Timing source | Monitored |
| --- | --- | --- | ---: | --- | --- |
| 173-D1 | Blk 18 (42161) -> Aft Clementi Fire Stn (20109) | 11:25:27 -> 11:39:33 | 5.42 | snapshot_eta | True |
| 105-D2 | Aft Clementi Fire Stn (20109) -> Blk 365 (17159) | 11:45:16 -> 11:50:58 | 2.72 | snapshot_eta | False |
| 96-D1 | Blk 365 (17159) -> Coll of Design & Engrg (16159) | 12:01:28 -> 12:07:46 | 7.50 | modeled_wait (beyond_forecast_horizon) | None |

### R02615: 41-D1 -> 106-D1 -> 183-D1

Estimated arrival: 2026-10-08T12:11:05+08:00. Timing/availability: unknown_where_modeled. Eligible stop variants: 6.

| Service | Board -> alight | Predicted/model board -> model alight | Wait | Timing source | Monitored |
| --- | --- | --- | ---: | --- | --- |
| 41-D1 | Blk 18 (42161) -> SMRT Ulu Pandan Depot (28109) | 11:25:47 -> 11:32:59 | 5.75 | snapshot_eta | True |
| 106-D1 | SMRT Ulu Pandan Depot (28109) -> Blk 365 (17159) | 11:43:29 -> 11:54:17 | 7.50 | modeled_wait (service_missing) | None |
| 183-D1 | Blk 365 (17159) -> Coll of Design & Engrg (16159) | 12:04:47 -> 12:11:05 | 7.50 | modeled_wait (beyond_forecast_horizon) | None |

### R02617: 41-D1 -> 106-D1 -> 96-D1

Estimated arrival: 2026-10-08T12:11:05+08:00. Timing/availability: unknown_where_modeled. Eligible stop variants: 1.

| Service | Board -> alight | Predicted/model board -> model alight | Wait | Timing source | Monitored |
| --- | --- | --- | ---: | --- | --- |
| 41-D1 | Blk 18 (42161) -> SMRT Ulu Pandan Depot (28109) | 11:25:47 -> 11:32:59 | 5.75 | snapshot_eta | True |
| 106-D1 | SMRT Ulu Pandan Depot (28109) -> Blk 365 (17159) | 11:43:29 -> 11:54:17 | 7.50 | modeled_wait (service_missing) | None |
| 96-D1 | Blk 365 (17159) -> Coll of Design & Engrg (16159) | 12:04:47 -> 12:11:05 | 7.50 | modeled_wait (beyond_forecast_horizon) | None |

### R00262: 173-D1 -> 183-D1 -> 96-D1

Estimated arrival: 2026-10-08T12:12:32+08:00. Timing/availability: unknown_where_modeled. Eligible stop variants: 6.

| Service | Board -> alight | Predicted/model board -> model alight | Wait | Timing source | Monitored |
| --- | --- | --- | ---: | --- | --- |
| 173-D1 | Blk 18 (42161) -> Aft Toh Tuck Ave (28019) | 11:25:27 -> 11:37:45 | 5.42 | snapshot_eta | True |
| 183-D1 | Aft Toh Tuck Ave (28019) -> UTown - Cendana (17099) | 11:48:14 -> 11:58:08 | 7.48 | snapshot_eta | False |
| 96-D1 | UTown - Cendana (17099) -> Coll of Design & Engrg (16159) | 12:08:38 -> 12:12:32 | 7.50 | modeled_wait (beyond_forecast_horizon) | None |

## Projected along-the-way alternatives

All eligible candidates participate, not only the displayed families. Options share the same travelled service/stop prefix.
These are projected choices using the departure snapshot, NOT new observations at the future stop. Total means the complete trip from the origin.
Continue on the same vehicle: zero new waiting, boarding delay or transfer. No service-count bonus; no claim of independent arrivals.

| Reference | Stop / onboard | Action | Best candidate for action | Total min | New wait incl. buffer | Source |
| --- | --- | --- | --- | ---: | ---: | --- |
| R00146 | Aft Jln Jurong Kechil (42239) / 173-D1 | Stay on 173-D1 | R00146 | 40.29 | 0.00 | same_vehicle_continuation |
| R00146 | Aft Jln Jurong Kechil (42239) / 173-D1 | Transfer to 41-D1 | R02525 | 64.47 | 14.67 | snapshot_eta |
| R00146 | Aft Toh Tuck Rise (42209) / 173-D1 | Stay on 173-D1 | R00146 | 40.29 | 0.00 | same_vehicle_continuation |
| R00146 | Aft Toh Tuck Rise (42209) / 173-D1 | Transfer to 41-D1 | R02104 | 64.47 | 13.23 | snapshot_eta |
| R00146 | SMRT Ulu Pandan Depot (28109) / 173-D1 | Stay on 173-D1 | R00146 | 40.29 | 0.00 | same_vehicle_continuation |
| R00146 | SMRT Ulu Pandan Depot (28109) / 173-D1 | Transfer to 106-D1 | R00375 | 52.52 | 10.50 | modeled_wait |
| R00146 | SMRT Ulu Pandan Depot (28109) / 173-D1 | Transfer to 963-D1 | R01054 | 55.04 | 13.47 | snapshot_eta |
| R00146 | Aft Toh Tuck Lk (28189) / 173-D1 | Stay on 173-D1 | R00146 | 40.29 | 0.00 | same_vehicle_continuation |
| R00146 | Aft Toh Tuck Lk (28189) / 173-D1 | Transfer to 106-D1 | R01305 | 52.52 | 10.50 | modeled_wait |
| R00146 | Aft Toh Tuck Lk (28189) / 173-D1 | Transfer to 963-D1 | R01719 | 55.04 | 13.08 | snapshot_eta |
| R00146 | Aft Toh Tuck Ave (28019) / 173-D1 | Stay on 173-D1 | R00146 | 40.29 | 0.00 | same_vehicle_continuation |
| R00146 | Aft Toh Tuck Ave (28019) / 173-D1 | Transfer to 183-D1 | R00261 | 40.50 | 10.48 | snapshot_eta |
| R00146 | Aft Toh Tuck Ave (28019) / 173-D1 | Transfer to 188-D1 | R00285 | 41.19 | 11.17 | snapshot_eta |
| R00146 | Aft Toh Tuck Ave (28019) / 173-D1 | Transfer to 105-D2 | R00147 | 48.77 | 6.75 | snapshot_eta |
| R00146 | Aft Toh Tuck Ave (28019) / 173-D1 | Transfer to 106-D1 | R00204 | 52.52 | 10.50 | modeled_wait |
| R00146 | Aft Clementi Fire Stn (20109) / 173-D1 | Transfer to 188-D1 | R00146 | 40.29 | 10.27 | snapshot_eta |
| R00146 | Aft Clementi Fire Stn (20109) / 173-D1 | Stay on 173-D1 | R00048 | 40.52 | 0.00 | same_vehicle_continuation |
| R00146 | Aft Clementi Fire Stn (20109) / 173-D1 | Transfer to 183-D1 | R00131 | 40.52 | 10.50 | modeled_wait |
| R00146 | Aft Clementi Fire Stn (20109) / 173-D1 | Transfer to 105-D2 | R00057 | 47.74 | 5.72 | snapshot_eta |
| R00146 | Aft Clementi Fire Stn (20109) / 173-D1 | Transfer to 106-D1 | R00094 | 52.52 | 10.50 | modeled_wait |

## Assumptions and missing evidence

- Direction binding uses historical full-service endpoints plus stop visit ordinal, not service number alone. Mismatches fall back to a model; they do not prove no service.
- Select the earliest matching ETA after modeled readiness including the transfer buffer. Monitored=True, False and unknown are preserved; none establishes an actual arrival.
- Snapshot freshness is tested at the departure cutoff (90 seconds), not against future simulated stop times. Forecast lead time can still be long and uncertain.
- No eligible slot beyond the saved horizon, missing service, stale/error response or unknown pattern: use headway/2 and label availability unknown. No invented vehicle departure or catch probability.
- 106 has missing predictions in this capture: its valid topology alternatives are retained with modeled timing. 106A remains limited and excluded from default references.
- Riding remains distance-based. The same extra mean boarding-delay allowance is retained for both columns; it is NOT calibrated forecast error and may overlap uncertainty already represented by the ETA.
- Do not match a bus at different stops using NextBus/NextBus2 rank. No vehicle identity or cross-stop ETA-derived riding time is used.
- Selecting the earliest forecast and a mean ride is a heuristic, not an optimal time-dependent policy. Forecast differences across stops can change the chosen transfer stop without proving it is better.
- Historical operating windows are checked at each estimated boarding; missing windows retain topology but exclude default references. Model limits are not verified fare rules.
- Existing strict retrospective replay, offline reports and local synthetic examples are unchanged. No Google comparison or real journey outcome is inferred.

## Reproduce and provenance

`python -m experiments.blk18_snapshot_reference`

Requires the local ignored snapshot file; the command does not fetch missing data. Synthetic unit fixtures exercise the same logic without credentials.
Raw SHA256: `d626c6afd63fd49475aa52c155e42caa204b74d1077b8cb5ec37a0fda8f41474`.
Source: LTA DataMall BusArrival v3; endpoint: https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival.
Receipt range: 2026-10-08T03:20:00.178645+00:00 to 2026-10-08T03:20:01.741685+00:00.
Model settings: `{"delay_max": 3, "headway": 15, "max_candidates": 10000, "max_expansions": 100000, "max_transfer_gap": 45, "max_transfers": 5, "max_trip_minutes": 120, "speed_kmh": 20, "transfer_buffer": 3}`.
reference.json records topology hashes, matching bindings, complete candidates, per-leg evidence line/entry references, exclusions and search statistics.

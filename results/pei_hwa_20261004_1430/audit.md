# ETA pilot audit: October 4, 14:30

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

## Collection integrity

All times below are Singapore time. No live API requests are made by this audit.

- eta_pilot_20261004_1430.jsonl: 946 requests; completion=api_error; completion counts match=True.
- eta_pilot_20261004_1430_walk.jsonl: 180 requests; completion=request_budget; completion counts match=True.

| Stop | OK | Errors | First | Last | Max gap (sec) | Gaps >90s | Empty |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |
| 11261 | 105 | 0 | 13:58:42 | 15:42:45 | 61.65 | 0 | 0 |
| 12061 | 105 | 0 | 13:58:42 | 15:42:44 | 61.83 | 0 | 0 |
| 12071 | 105 | 0 | 13:58:42 | 15:42:43 | 61.68 | 0 | 0 |
| 16189 | 105 | 1 | 13:58:42 | 15:42:42 | 61.72 | 0 | 0 |
| 17009 | 105 | 0 | 13:58:42 | 15:42:45 | 61.62 | 0 | 0 |
| 42059 | 90 | 0 | 14:01:41 | 15:30:39 | 63.66 | 0 | 0 |
| 42061 | 90 | 0 | 14:01:41 | 15:30:43 | 62.55 | 0 | 0 |
| 42071 | 105 | 0 | 13:58:42 | 15:42:44 | 61.74 | 0 | 0 |
| 42141 | 105 | 0 | 13:58:42 | 15:42:44 | 61.75 | 0 | 0 |
| 42171 | 105 | 0 | 13:58:42 | 15:42:45 | 61.46 | 0 | 0 |
| 42231 | 105 | 0 | 13:58:42 | 15:42:45 | 61.52 | 0 | 0 |

## Predictions available at selected decision times

These are fixed-time diagnostics, NOT reconstructed passenger arrival times.
Select the latest response received at or before each decision; reject responses
older than 90 seconds and exclude ETAs already before the decision time.
Monitored flags are reported literally; rows are not verified arrival events.

### 16189 at 14:30

Snapshot status: available; age: 17.890335 seconds.

| Service | Predicted arrival | Minutes from decision | Monitored | Slot |
| --- | --- | ---: | --- | --- |
| 96 | 14:40:18 | 10.30 | True | NextBus |
| 151 | 14:40:44 | 10.73 | False | NextBus |
| 95 | 14:42:36 | 12.60 | False | NextBus2 |
| 96 | 14:53:15 | 23.25 | False | NextBus2 |
| 151 | 14:53:44 | 23.73 | False | NextBus2 |
| 95 | 14:56:36 | 26.60 | False | NextBus3 |
| 151 | 15:06:18 | 36.30 | False | NextBus3 |
| 96 | 15:09:15 | 39.25 | False | NextBus3 |

### 12061 at 14:30

Snapshot status: available; age: 17.286693 seconds.

| Service | Predicted arrival | Minutes from decision | Monitored | Slot |
| --- | --- | ---: | --- | --- |
| 52 | 14:39:21 | 9.35 | True | NextBus2 |
| 61 | 14:43:23 | 13.38 | True | NextBus |
| 61 | 14:46:12 | 16.20 | True | NextBus2 |
| 75 | 14:46:23 | 16.38 | True | NextBus2 |
| 184 | 14:51:45 | 21.75 | True | NextBus2 |
| 52 | 14:57:25 | 27.42 | True | NextBus3 |
| 61 | 14:58:58 | 28.97 | True | NextBus3 |
| 184 | 14:59:37 | 29.62 | True | NextBus3 |
| 75 | 15:00:38 | 30.63 | True | NextBus3 |

### 12071 at 15:05

Snapshot status: available; age: 16.093574 seconds.

| Service | Predicted arrival | Minutes from decision | Monitored | Slot |
| --- | --- | ---: | --- | --- |
| 151 | 15:05:20 | 0.33 | True | NextBus |
| 61 | 15:09:38 | 4.63 | True | NextBus |
| 151 | 15:18:18 | 13.30 | False | NextBus2 |
| 61 | 15:28:08 | 23.13 | True | NextBus2 |
| 151 | 15:30:18 | 25.30 | False | NextBus3 |
| 61 | 15:32:14 | 27.23 | True | NextBus3 |

### 12071 at 15:29

Snapshot status: available; age: 16.070231 seconds.

| Service | Predicted arrival | Minutes from decision | Monitored | Slot |
| --- | --- | ---: | --- | --- |
| 151 | 15:31:21 | 2.35 | True | NextBus |
| 61 | 15:33:08 | 4.13 | True | NextBus2 |
| 151 | 15:43:18 | 14.30 | False | NextBus2 |
| 61 | 15:47:21 | 18.35 | True | NextBus3 |
| 151 | 15:56:45 | 27.75 | False | NextBus3 |

### 42059 at 15:01

Snapshot status: available; age: 20.27577 seconds.

| Service | Predicted arrival | Minutes from decision | Monitored | Slot |
| --- | --- | ---: | --- | --- |
| 151 | 15:10:30 | 9.50 | True | NextBus |
| 151 | 15:22:42 | 21.70 | False | NextBus2 |
| 151 | 15:35:42 | 34.70 | False | NextBus3 |

### 42061 at 15:18

Snapshot status: available; age: 16.554077 seconds.

| Service | Predicted arrival | Minutes from decision | Monitored | Slot |
| --- | --- | ---: | --- | --- |
| 174 | 15:33:59 | 15.98 | True | NextBus |
| 174 | 15:45:00 | 27.00 | True | NextBus2 |
| 174 | 15:57:14 | 39.23 | True | NextBus3 |

### 11261 at 15:04

Snapshot status: available; age: 15.049182 seconds.

| Service | Predicted arrival | Minutes from decision | Monitored | Slot |
| --- | --- | ---: | --- | --- |
| 970 | 15:11:28 | 7.47 | True | NextBus |
| 95 | 15:17:00 | 13.00 | True | NextBus |
| 970 | 15:23:31 | 19.52 | True | NextBus2 |
| 95 | 15:27:43 | 23.72 | False | NextBus2 |
| 970 | 15:37:01 | 33.02 | True | NextBus3 |
| 95 | 15:41:43 | 37.72 | False | NextBus3 |

### 11261 at 15:20

Snapshot status: available; age: 14.929233 seconds.

| Service | Predicted arrival | Minutes from decision | Monitored | Slot |
| --- | --- | ---: | --- | --- |
| 970 | 15:24:50 | 4.83 | True | NextBus |
| 970 | 15:37:20 | 17.33 | True | NextBus2 |
| 970 | 15:53:13 | 33.22 | True | NextBus3 |

## Interpretation limits

- The main collector stopped on an LTAApiError; the safe log does not retain
  HTTP status or underlying exception details. Root cause is unknown; do not
  assert a timeout or exhausted quota from request duration alone.
- The 90-second gap audit concerns cadence within each observed window, not
  coverage after early termination. Main observations end before 15:50.
- Repeated predictions are not independent bus events or actual arrival truth.
- Missing or expired ETA entries do not prove a bus departed or was missed.
- Rank slots cannot match vehicles between stations. No catch probabilities,
  actual journey durations, or Google speedup are calculated here.
- A fixed-time alternative service prediction alone does not prove a feasible
  full route; direction, passenger arrival, and continuation must be checked.
- Manual Google totals remain 44, 52, 63, 68 minutes from 14:30. They are
  external forecasts, not observed outcomes or model calibration labels.

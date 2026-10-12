# Provisional ETA-entry associations

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

## Method

Associations use only monitored entries with finite, nonzero positions and matching
service, endpoint and visit fields. These are NOT guaranteed vehicle identities.
Cross-stop links require direction verified in the frozen static topology,
response skew <=5 seconds, position separation <=30m, and ordered ETAs.
Temporal links require consecutive usable snapshots <=90 seconds apart,
ETA drift <=120 seconds, and displacement <=70km/h plus 30m slack.
These fixed gates are heuristic, not measured confidence or fitted parameters.
Only isolated candidate edges are retained; ambiguous components are not assigned.
A temporal chain breaks on missing/unmonitored/error evidence. Slots are not IDs.
Events process in receive order; every edge has an available_at timestamp.
A replay may not use an edge before that timestamp. Do not collapse all edges
into definitive identity components: compounded errors and later ambiguity remain.

## Counts

Accepted provisional edges: 22257.
Ambiguous candidate edges retained separately: 1472.
Rejected entries: {"not_monitored": 8917}.

Counts are observation associations, not independent buses, journeys, or accuracy rates.

## Origin-to-transfer examples

All times Singapore. Each row is a same-time spatial association, not an observed ride.
| Service | Evidence available | Origin ETA | Transfer stop | Transfer ETA | Position gap (m) |
| --- | --- | --- | --- | --- | ---: |
| 95 | 14:30:43 | 14:30:19 | 11261 | 14:48:12 | 0.0 |
| 151 | 14:38:42 | 14:39:17 | 12071 | 14:50:34 | 0.0 |
| 151 | 14:39:42 | 14:40:23 | 12071 | 14:51:40 | 0.0 |
| 95 | 14:39:43 | 14:41:24 | 11261 | 14:59:17 | 0.0 |
| 95 | 14:40:43 | 14:42:12 | 11261 | 15:00:05 | 0.0 |
| 151 | 14:41:42 | 14:40:37 | 12071 | 14:51:54 | 0.0 |
| 95 | 14:41:43 | 14:42:27 | 11261 | 15:00:20 | 0.0 |
| 95 | 14:42:43 | 14:41:51 | 11261 | 14:59:45 | 0.0 |
| 151 | 14:52:43 | 14:53:33 | 12071 | 15:04:30 | 0.0 |
| 151 | 14:53:43 | 14:53:15 | 12071 | 15:04:12 | 0.0 |
| 151 | 14:54:43 | 14:53:39 | 12071 | 15:04:36 | 11.2 |
| 95 | 14:57:44 | 14:58:32 | 11261 | 15:16:12 | 0.0 |
| 95 | 14:58:44 | 14:58:37 | 11261 | 15:16:18 | 0.0 |
| 95 | 14:59:44 | 14:58:52 | 11261 | 15:16:34 | 0.0 |
| 151 | 15:06:43 | 15:06:29 | 12071 | 15:18:24 | 0.0 |
| 151 | 15:07:43 | 15:07:20 | 12071 | 15:18:13 | 8.9 |
| 151 | 15:08:43 | 15:07:43 | 12071 | 15:18:37 | 0.0 |
| 95 | 15:10:44 | 15:11:29 | 11261 | 15:29:13 | 0.0 |
| 95 | 15:11:45 | 15:12:30 | 11261 | 15:30:14 | 0.0 |
| 95 | 15:12:44 | 15:11:44 | 11261 | 15:29:29 | 0.0 |
| 151 | 15:19:43 | 15:19:44 | 12071 | 15:30:40 | 0.0 |

## Continuity of transfer forecasts

Trace endpoints use later observations and belong to retrospective diagnostics,
NOT information available at initial boarding. Multiple anchors may belong to the
same inferred chain; row counts are not independent trials. No last ETA is treated
as an actual arrival event, and a disappearing entry is not proof of alighting.

| Service | Anchor evidence time | Trace entries | Last response | Last transfer ETA | End status |
| --- | --- | ---: | --- | --- | --- |
| 95 | 14:30:43 | 21 | 14:50:44 | 14:50:56 | no_successor_in_prefix |
| 151 | 14:38:42 | 14 | 14:51:43 | 14:51:16 | no_successor_in_prefix |
| 151 | 14:39:42 | 13 | 14:51:43 | 14:51:16 | no_successor_in_prefix |
| 95 | 14:39:43 | 24 | 15:02:44 | 15:02:11 | no_successor_in_prefix |
| 95 | 14:40:43 | 23 | 15:02:44 | 15:02:11 | no_successor_in_prefix |
| 151 | 14:41:42 | 11 | 14:51:43 | 14:51:16 | no_successor_in_prefix |
| 95 | 14:41:43 | 22 | 15:02:44 | 15:02:11 | no_successor_in_prefix |
| 95 | 14:42:43 | 21 | 15:02:44 | 15:02:11 | no_successor_in_prefix |
| 151 | 14:52:43 | 14 | 15:05:43 | 15:05:20 | no_successor_in_prefix |
| 151 | 14:53:43 | 13 | 15:05:43 | 15:05:20 | no_successor_in_prefix |
| 151 | 14:54:43 | 12 | 15:05:43 | 15:05:20 | no_successor_in_prefix |
| 95 | 14:57:44 | 21 | 15:17:45 | 15:18:03 | no_successor_in_prefix |
| 95 | 14:58:44 | 20 | 15:17:45 | 15:18:03 | no_successor_in_prefix |
| 95 | 14:59:44 | 19 | 15:17:45 | 15:18:03 | no_successor_in_prefix |
| 151 | 15:06:43 | 15 | 15:20:43 | 15:19:48 | no_successor_in_prefix |
| 151 | 15:07:43 | 14 | 15:20:43 | 15:19:48 | no_successor_in_prefix |
| 151 | 15:08:43 | 13 | 15:20:43 | 15:19:48 | no_successor_in_prefix |
| 95 | 15:10:44 | 24 | 15:33:45 | 15:32:49 | no_successor_in_prefix |
| 95 | 15:11:45 | 23 | 15:33:45 | 15:32:49 | no_successor_in_prefix |
| 95 | 15:12:44 | 22 | 15:33:45 | 15:32:49 | no_successor_in_prefix |
| 151 | 15:19:43 | 13 | 15:31:43 | 15:30:37 | no_successor_in_prefix |

## Remaining work

Use these provisional links in a chronological replay with explicit unknown outcomes.
An expired ETA, disappearing entry or matched position does not establish boarding,
alighting, actual arrival or missed connection. Probability calibration still needs
independent outcome evidence. No actual-trip time or speedup is reported here.

Reproduce: `python -m experiments.match_eta_pilot` from the repository root.
Detailed entry-level evidence and parameters remain in git-ignored data/recorded
directories; summary results contain hashes and trace references.

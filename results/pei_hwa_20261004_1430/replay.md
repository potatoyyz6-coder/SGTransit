# Conditional ETA route replay

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

## What this evaluates

One virtual departure at 2026-10-04 14:30 Singapore time. Fixed service sequences
and a first-eligible hub policy see the same received observations. This is not
a replay of a real passenger, a calibrated reliability score, or a Google speed test.
The hub policy admits 151 -> Blk 109 -> 61 directly, or 52/75/184 to Pei Hwa
followed by 61/157/174/985. It also admits 95 -> 970 via Holland Village.
It selects the first currently eligible matched bus, not the best hindsight outcome.
The existing SharedSuffixPolicy.update is also run on the same recorded-stop
network as first_eligible_shared_stops. The original first_eligible_hub_strategy
uses longer ride legs; use the shared-stops pair to isolate the decision rule.
Suffix values use fixed 15-minute headways, distance/20kmh segment times (at least
0.5 minutes each), delay_max=3 minutes and a 5-minute transfer penalty. They are
not fitted to this capture or Google. Only current-stop departures enter decisions.
The existing local score is expected remaining time plus transfer penalties,
NOT a calibrated P90/P95 or catch-probability objective. Current executable arcs
are restricted to retained path prefixes; the downstream value model is unchanged.

## Explicit event assumptions

- A future boarding ETA is revised while new observations arrive before boarding.
- A ride advances on the tracked destination ETA. This ETA-as-event assumption
  is a model substitute, not evidence of actual arrival or successful boarding.
- Only provisional monitored-position associations are used; gaps, ambiguities,
  stale evidence (>90 seconds), and the end of the capture produce unknown outcomes.
- Local boarding forecasts without cross-stop matches cannot be silently skipped
  in favor of a later matched bus. A pending boarding forecast that moves behind
  the next polling time is unknown, not an observed missed bus or extra headway.
- Same-vehicle continuation has no new boarding, waiting time, or transfer penalty.
  It preserves a previous cross-stop association while both endpoints retain
  unique, fresh temporal chains. It does not require a new spatial match from
  scratch at every intermediate stop; ambiguous chains remain unknown.
  A bounded five-second observation grace accommodates sequential stop requests;
  this modeled onboard time is counted as riding, not as station waiting. It does
  not establish actual dwell time. Longer missing continuation evidence is unknown.
- Walking is a five-minute scenario input for the manually referenced connector,
  not a validated pedestrian route; it is counted once. The transfer buffer is
  added after the walk. Initial and transfer waiting are kept separate from walking.
- The limits are modeling constraints (5 transfers, 45-minute gaps, 2-hour trip),
  not a verified implementation of current Singapore fare law.
- No independent Monte Carlo samples are created from repeated ETA updates.
  Sensitivity scenarios are not independent journeys and do not yield probabilities.

## Base scenario: three-minute transfer buffer, no ETA shift

| Strategy | Status | Modeled total (min) | Prefix wait (min) | Max transfer wait (min) | Transfers |
| --- | --- | ---: | ---: | ---: | ---: |
| fixed_151_61 | boarding_between_polls_unknown | unknown | 9.28 | unknown | 0 |
| fixed_95_970 | modeled_complete | 60.30 | 24.45 | 12.00 | 1 |
| fixed_151_walk_174 | modeled_complete | 51.76 | 21.88 | 12.60 | 1 |
| first_eligible_hub_strategy | modeled_complete | 45.50 | 23.28 | 9.02 | 2 |
| first_eligible_shared_stops | modeled_complete | 45.50 | 23.28 | 9.02 | 2 |
| stationary_suffix_policy | modeled_complete | 40.27 | 20.75 | 11.47 | 1 |

Prefix waits for incomplete trips are lower bounds, not full-journey scores.
Do not rank completed-only rows against censored rows or impute missing time.

An early implementation silently skipped unresolved boarding forecasts and
produced an inflated 65.27-minute fixed 151 -> 61 result. That result is invalid
and superseded: the corrected outcome is unknown at the boarding interval.

Configured long-wait threshold: strictly greater than 10 minutes.
This is a per-replay event flag, not a probability. Unknown trip flags stay null.
The suffix policy uses 151 -> 61 at Blk 109, whereas the fixed external-reference
variant transfers at Blk 116. Do not attribute their difference solely to scoring.

## Sensitivity

Buffers: 1, 3, 5 minutes. Alighting-event shifts: -60, 0, +60 seconds.
The shift tests an assumption; it is not an empirically fitted error distribution.

| Scenario | Strategy | Status | Modeled total (min) |
| --- | --- | --- | ---: |
| buffer_60_shift_-60 | fixed_151_61 | boarding_between_polls_unknown | unknown |
| buffer_60_shift_-60 | fixed_95_970 | modeled_complete | 59.08 |
| buffer_60_shift_-60 | fixed_151_walk_174 | modeled_complete | 40.37 |
| buffer_60_shift_-60 | first_eligible_hub_strategy | boarding_between_polls_unknown | unknown |
| buffer_60_shift_-60 | first_eligible_shared_stops | boarding_between_polls_unknown | unknown |
| buffer_60_shift_-60 | stationary_suffix_policy | modeled_complete | 39.62 |
| buffer_60_shift_0 | fixed_151_61 | boarding_between_polls_unknown | unknown |
| buffer_60_shift_0 | fixed_95_970 | modeled_complete | 60.30 |
| buffer_60_shift_0 | fixed_151_walk_174 | modeled_complete | 41.75 |
| buffer_60_shift_0 | first_eligible_hub_strategy | boarding_between_polls_unknown | unknown |
| buffer_60_shift_0 | first_eligible_shared_stops | boarding_between_polls_unknown | unknown |
| buffer_60_shift_0 | stationary_suffix_policy | modeled_complete | 40.27 |
| buffer_60_shift_60 | fixed_151_61 | boarding_between_polls_unknown | unknown |
| buffer_60_shift_60 | fixed_95_970 | missing_or_stale_vehicle | unknown |
| buffer_60_shift_60 | fixed_151_walk_174 | missing_or_stale_vehicle | unknown |
| buffer_60_shift_60 | first_eligible_hub_strategy | boarding_between_polls_unknown | unknown |
| buffer_60_shift_60 | first_eligible_shared_stops | boarding_between_polls_unknown | unknown |
| buffer_60_shift_60 | stationary_suffix_policy | modeled_complete | 41.63 |
| buffer_180_shift_-60 | fixed_151_61 | boarding_between_polls_unknown | unknown |
| buffer_180_shift_-60 | fixed_95_970 | modeled_complete | 59.08 |
| buffer_180_shift_-60 | fixed_151_walk_174 | modeled_complete | 40.37 |
| buffer_180_shift_-60 | first_eligible_hub_strategy | modeled_complete | 44.18 |
| buffer_180_shift_-60 | first_eligible_shared_stops | modeled_complete | 44.18 |
| buffer_180_shift_-60 | stationary_suffix_policy | modeled_complete | 39.62 |
| buffer_180_shift_0 | fixed_151_61 | boarding_between_polls_unknown | unknown |
| buffer_180_shift_0 | fixed_95_970 | modeled_complete | 60.30 |
| buffer_180_shift_0 | fixed_151_walk_174 | modeled_complete | 51.76 |
| buffer_180_shift_0 | first_eligible_hub_strategy | modeled_complete | 45.50 |
| buffer_180_shift_0 | first_eligible_shared_stops | modeled_complete | 45.50 |
| buffer_180_shift_0 | stationary_suffix_policy | modeled_complete | 40.27 |
| buffer_180_shift_60 | fixed_151_61 | boarding_between_polls_unknown | unknown |
| buffer_180_shift_60 | fixed_95_970 | missing_or_stale_vehicle | unknown |
| buffer_180_shift_60 | fixed_151_walk_174 | missing_or_stale_vehicle | unknown |
| buffer_180_shift_60 | first_eligible_hub_strategy | modeled_complete | 46.76 |
| buffer_180_shift_60 | first_eligible_shared_stops | modeled_complete | 46.76 |
| buffer_180_shift_60 | stationary_suffix_policy | modeled_complete | 41.63 |
| buffer_300_shift_-60 | fixed_151_61 | boarding_between_polls_unknown | unknown |
| buffer_300_shift_-60 | fixed_95_970 | modeled_complete | 59.08 |
| buffer_300_shift_-60 | fixed_151_walk_174 | modeled_complete | 51.20 |
| buffer_300_shift_-60 | first_eligible_hub_strategy | modeled_complete | 44.18 |
| buffer_300_shift_-60 | first_eligible_shared_stops | modeled_complete | 44.18 |
| buffer_300_shift_-60 | stationary_suffix_policy | modeled_complete | 39.62 |
| buffer_300_shift_0 | fixed_151_61 | boarding_between_polls_unknown | unknown |
| buffer_300_shift_0 | fixed_95_970 | modeled_complete | 60.30 |
| buffer_300_shift_0 | fixed_151_walk_174 | modeled_complete | 51.76 |
| buffer_300_shift_0 | first_eligible_hub_strategy | modeled_complete | 47.43 |
| buffer_300_shift_0 | first_eligible_shared_stops | modeled_complete | 47.43 |
| buffer_300_shift_0 | stationary_suffix_policy | modeled_complete | 40.27 |
| buffer_300_shift_60 | fixed_151_61 | boarding_between_polls_unknown | unknown |
| buffer_300_shift_60 | fixed_95_970 | missing_or_stale_vehicle | unknown |
| buffer_300_shift_60 | fixed_151_walk_174 | missing_or_stale_vehicle | unknown |
| buffer_300_shift_60 | first_eligible_hub_strategy | modeled_complete | 48.60 |
| buffer_300_shift_60 | first_eligible_shared_stops | modeled_complete | 48.60 |
| buffer_300_shift_60 | stationary_suffix_policy | modeled_complete | 41.63 |

## External reference

The manually reported Google alternatives were 44/52/63/68 minutes from the
common 14:30 clock. Their observed actual outcomes are unknown. First bus selection
here follows observed ETA updates, not Google's specified departure, so differences
are not algorithm speedups. Google times are not used to generate ride events.

## Reproduction

`python -m experiments.replay_eta_pilot`

Source hashes, scenario parameters, route definitions, trace entry references and
decision timestamps are in replay.json. No new API calls are made.

# Offline analysis verification

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

Verified on 2026-10-07 after the scheduled collection had ended.

## Implemented scope

- Added `sg_transit.eta_diagnostics` for causal snapshot selection, flag-separated
  forecast opportunities and provisional matched absolute ETA revisions.
- Added `experiments.analyze_eta_window` to analyze the saved window, not collect
  new data. Three fixed paths and two flexible rules share recorded decision stops.
- All four departures were replayed under all nine buffer/shift configurations:
  180 strategy/scenario runs, not 180 independent observed trips.
- Audited existing reverse-bound full search against bounded hub search on the
  projected static network. This is not a new fluid solver or a speedup claim.
- README and analysis.md explain forecast provenance, unknown outcomes, missing
  walking/96-173 coverage, matcher selection bias and stationary scoring assumptions.

## Evidence

- `python -m pytest -q -p no:cacheprovider`: **201 passed in 18.09s**.
  Windows sandbox temp-directory errors required rerunning the suite with approval
  outside the sandbox; these were setup errors, not suppressed test failures.
- The new runner test forbids urllib network access, preserves input bytes,
  checks repeatability and rejects inconsistent completion counts.
- Repeated real-recording runs produced byte-identical analysis.json, analysis.md
  and replay.csv. Config, raw recording and topology hashes match report provenance.
- 32/32 departure/stop snapshots are causal and no older than 90 seconds.
- All 180 outputs were checked for unknown-score preservation, unique boarded
  services, transfer bounds and selected actions belonging to allowed arcs.
- 67 conditional completions satisfy total-time accounting and model limits.
  The other 113 runs remain unknown; neither total is an actual success/failure rate.
- Reverse search: 21/18 candidate descriptions, 31/29 expansions, three omitted
  descriptions and an explicit truncation flag. No replay candidates were changed.
- Raw, cleaned and parameter paths are git-ignored. No keys, Google route content
  or passenger records were added. No new live API requests were made.

## Not established

Actual arrivals, actual missed transfers, calibrated catch/long-wait probabilities,
whole-trip superiority, Google/Citymapper parity and production search speed are
not established. ETA revision quantiles are truncated by matching gates and must
not be reused as a calibrated ETA-error distribution.

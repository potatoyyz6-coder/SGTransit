# Verification and remaining validation boundary

Verification performed on 2026-10-06. Experiment departure remains
2026-10-04 14:30 Asia/Singapore; no data dates have been relabeled.

## Verified local work

- Full offline test suite: 135 passed in 13.60 seconds. The sandboxed attempt
  encountered Windows temporary-directory permissions; the approved rerun
  completed successfully with a separate temporary directory.
- Audited 54 strategy/scenario results: completed journey durations equal
  waiting plus walking plus riding; unknown trips retain null risk flags;
  boarding and continuation evidence is available no later than the modeled
  decision/event time. This arithmetic audit does not prove actual outcomes.
- Original SharedSuffixPolicy.update is integrated using a restricted set
  of executable current arcs and unchanged stationary downstream values.
- Same-vehicle continuation preserves unique provisional temporal bridges,
  with no added boarding or transfer count. Ambiguous links remain unknown.
- Matching gates remain 5-second cross-response skew and 30-metre position
  separation. They were not relaxed to obtain a desired route result.
- Long-wait threshold and stationary transfer penalty are configurable.
- No new LTA calls, Google scraping, credential inspection, or screenshot
  storage occurred during this verification.

Reproduction:

```powershell
python -m experiments.audit_eta_pilot --input data/recorded/raw/eta_pilot_20261004_1430.jsonl --input data/recorded/raw/eta_pilot_20261004_1430_walk.jsonl --output results/pei_hwa_20261004_1430
python -m experiments.match_eta_pilot
python -m experiments.replay_eta_pilot
python -m pytest -q
```

The raw capture remains local and git-ignored, so a checkout without those
files can run synthetic tests but cannot reproduce this recorded-data pilot.

## What is not established

- Actual boarding, alighting, trip duration, or a Google/Citymapper speedup.
- Calibrated catch-connection or long-wait probabilities, or an empirical P95
  arrival-time benefit across independent journeys.
- Vehicle identity ground truth: spatial/temporal associations remain heuristic.
- Current legal fare compliance or a validated walking route.
- A P95-optimizing online selector: the integrated local selector currently
  minimizes stationary expected remaining time plus transfer penalties.

The base conditional totals (40.27, 45.50, 51.76 and 60.30 minutes) are model
outputs, not observations. The fixed Blk 116 transfer remains unknown and
must not be imputed or excluded to manufacture a favorable comparison.

## User decision required for the next validation stage

The current bounded API authorization has ended. No new capture is scheduled.
Before expanding the empirical claim, choose one of these distinct scopes:

1. Continue an offline research project, reporting simulation-based risk
   explicitly under assumptions, without calling it real-world calibration.
2. Plan empirical calibration: confirm new bounded collection windows and
   an independent source of actual bus arrival/departure outcomes. These
   may be anonymous station/service/time observations, not passenger identities
   or personal movement traces. More prediction snapshots alone cannot verify
   true arrival errors. The user need not personally ride each route.

This choice is not a claim that the entire project or real-world validation
goal has been completed. Goal mode is paused at the user's conditional request
to be notified when their input is needed.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

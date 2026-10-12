# Preference Experiment Verification

Verified on 2026-10-06. Scope: implement preferences in fixed selection, extend
them to distributional multi-branch decisions, and evaluate the original eight
regression scenarios without new live data. A ninth declared comfort control
tests a direct tradeoff between station waiting and riding time.

## Requirement Audit

| Requirement | Current evidence |
| --- | --- |
| Fast, low-wait and reliable preferences change decisions | `Preference` defines mean, mean-plus-wait/transfer cost, and nearest-rank P95 objectives. Tests exercise different fixed routes, different live local choices and configurable comfort weights. |
| Fixed selection before testing | All candidates evaluated on 2,000 training worlds per case. Each preference's rank and selected route are stored before creating held-out worlds. Tests change the test seed without changing selection. |
| Dynamic decisions consider distributions | `DistributionalPolicy.project` projects legal fixed suffixes using independent model samples of future waiting and boarding delay. The policy chooses a suffix before realization, executes its first arc, then replans at the next stop. |
| No hindsight oracle | Tests reject sample-wise future route minima and show that changing hidden realized delays cannot alter the initial decision. Only current-stop departures are passed by the shared executor. |
| Retain legal paths and controls | All nine candidate-closure audits pass. Tests cover explicit suffix/state budgets, remaining onboard, transfer buffer/window, incomplete projections, restricted arcs and unchanged candidate sets across rollout sizes. |
| Preserve prior cases and honest negatives | Eight original cases retained with unchanged scenario generators. Synchronization/no-choice controls remain equal. Tight-connection reliable P95 is slightly worse than legacy; low-wait preference can increase transfers. |
| Demonstrate tail-risk tradeoff | Heavy-tail case: dynamic fast mean 21.98, P95 39.97; reliable mean 26.01, P95 27.80. Higher mean cost is retained, not hidden. |
| Demonstrate outdoor-wait preference tradeoff | Comfort control: mean station wait falls from 6.00 to 2.32 minutes, while total time rises from 14.39 to 16.24. Buffer time is separately accounted and not called a validated heat-exposure metric. |
| Independent-alternative benefit survives | Dynamic P95 remains 34.49 versus fixed-fast 43.16 in independent_alternatives. Tests also cover the synchronized null. |
| Reproduction and outputs | One command produces JSON parameters/training ranks/results, paired NPZ samples, CSV, report and plot. README documents objectives, assumptions, configuration and negative results. |

## Executed Checks

```powershell
python -m experiments.preference_benchmark
python -m pytest -q -p no:cacheprovider --basetemp tmp/pytest_preferences_full_20261006_b
```

- Full regression suite: **178 passed in 15.59 seconds**, including 18 new tests.
- Test runner executed outside the Windows filesystem sandbox with permission,
  because its pytest temporary-directory permission failure was already verified.
- All nine cases used 10,000 held-out worlds, 2,000 training worlds, and 256
  separate stationary rollout draws. No selection uses held-out outcomes.
- An independent read of all saved artifacts checked **720,000 strategy-world
  outcome records** against current source hashes, selected training winners,
  candidate closure, counts, means, P95, total-time decomposition, long-wait
  probabilities, paired mean/P95 differences and comfort tradeoffs. These are
  eight policy outputs per world, not 720,000 independent measured journeys.
- All default journeys completed; incomplete projections and executable limits
  are covered separately in tests. Incomplete durations are never dropped.
- The generated nine-panel plot was opened and visually checked: titles, bars,
  numbers and axis labels are visible and do not overlap.
- All experiment and test processes terminated successfully. No live collector
  was started, no API called, and no secrets read or written.

## Boundaries

Only `src/sg_transit/preferences.py`, `experiments/preference_benchmark.py`,
`tests/test_preferences.py`, the README and new preference result directories
were added/updated. Existing route algorithms, ETA replay, raw records and prior
fair-benchmark artifacts were not rewritten. Files remain untracked in the
existing uncommitted workspace; no broad staging or cleanup occurred.

These are synthetic probabilities. Rollouts assume independent stationary waits
even in correlated test cases. Fixed training evaluates each case's world model,
whereas dynamic lookahead does not learn correlations. Recursively replanning a
conditional suffix percentile is not globally optimal P95 dynamic programming.
The current comfort objective penalizes expected station wait, not directly the
probability of a long wait. Results therefore establish working preference
tradeoffs under explicit assumptions, not actual catch probabilities or universal
improvement over Google, Citymapper, fixed routes, or the previous heuristic.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

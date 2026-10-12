# SG-Transit-Reliability Route Map

## Current objective

Complete the fourth-stage reproducible experiment:

- Compare deterministic routing with reliability-aware routing.
- Run three fixed scenarios with 10,000 Monte Carlo samples each.
- Produce CSV/JSON summaries and charts.
- Provide a manual Google Maps validation workflow for real cases such as Central Library to Jurong East.

## Task board

- [x] T1. Audit the existing implementation and identify gaps.
- [x] T2. Organize public transit data recommendations.
- [x] T3. Implement explicit multi-branch candidate generation.
- [x] T4. Add three experiment scenarios and automated outputs.
- [x] T5. Add Google Maps validation CSV/template workflow.
- [x] T6. Run tests, execute experiments, and perform acceptance review.

## Roles

- Dispatch/review agent: audit requirements and review implementation.
- Local-data agent: organize GTFS/LTA references and validation data format.
- Work agent: implement routing and experiment features.
- Main agent: integrate changes, run tests, and complete acceptance.

## Acceptance gates

1. Existing tests remain green.
2. Three scenarios run reproducibly with 10,000 samples each.
3. Results include mean, median, P90, P95, waiting time, and failure rates.
4. Multi-branch output exposes alternatives, not only a single selected route.
5. A user can record Google Maps results for the same origin, destination, and departure time.
6. README documents assumptions, reproduction commands, validation steps, and limitations.

## Evidence

- `python -m pytest -q -p no:cacheprovider`: 27 passed.
- `python -m experiments.run_all`: three scenarios completed with 10,000 held-out samples per strategy.
- `data/real/network.json`: 50-stop reproducible subset with provenance and fixed source commit.
- `results/central_library_jurong_east.json`: CLI planning run for stop `16181` to `28009`.
- `compare` rejects the blank Google fields until a completed observation is recorded.

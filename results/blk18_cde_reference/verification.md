# Verification: Blk 18 reference case

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

## Offline deliverables

- Entry point: `python -m experiments.blk18_cde_case`.
- 25 full original stops and nine declared directed fragments, including limited
  106A topology. No manual complete itineraries are injected into search.
- Default complete search: 7,212 candidates, 24,948 expansions, 4,558 default
  eligible references. All excluded limited/out-of-window paths remain in outputs.
- Report contains eight service families and all their eligible stop variants;
  full candidates are in CSV/JSON. Synthetic local scoring uses all 4,558 eligible
  routes, not the displayed eight families.
- Five local scenarios demonstrate direct-versus-feeder choices and continuation
  on 173, 106 and 183 without another wait, boarding delay or transfer.
- All 7,212 serialized candidates independently checked for forward connectivity,
  loop/reboarding validity and exact ride/wait/buffer/delay time accounting.
- Source hashes verified against the frozen manifest. No input datasets changed.
- Focused offline tests: 22 passed. Full suite before adding the separately
  authorized sampling wrapper: 223 passed in 25.16 seconds.
- Repeatability test compares report, JSON, CSV and PNG byte-for-byte while network
  calls are forbidden. Full candidate results are deterministic for fixed inputs.
- Route diagram visually inspected: labels readable, directed order preserved,
  limited 106A dashed, and only dots denote stops. Lines crossing columns do not
  imply that a service stops there.

## Separate live sampling authorization

On October 8 the user additionally requested sampling at 11:20 Singapore time.
This does not change the offline runner: a separate scheduled script uses the
same 25-stop set, one request per stop, no retries, no recurring task, and stops
starting requests at 11:22. Request/receive timestamps are preserved individually.
An in-flight request has an eight-second timeout. A late wakeup over 90 seconds
aborts rather than silently moving the experiment. Duplicate output/log paths
prevent a second launch. Raw data and scheduler logs remain git-ignored.

Four fake-clock wrapper tests passed before launch, covering timing, request cap,
error sanitization, duplicate prevention, stop controls, deadlines and path bounds.
Live collection results are not evidence of actual arrivals, and must not be
backdated to 11:20 if the corresponding response was received later.

Final full suite including the wrapper: **227 passed in 25.09 seconds**. The final
nonnegative-wait boundary adjustment was followed by all four wrapper tests passing
again. The live run completed at 11:20:01.742904 with 25/25 successful responses,
no errors and no further rounds; see snapshot_20261008_1120.md for source hash and
selected forecasts. Offline report estimates were not relabeled as live estimates.

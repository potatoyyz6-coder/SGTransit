# Adjacent-fragment index experiment

Offline topology/model comparison, not observed travel-time improvement.

## Method

- `rebuild`: unchanged production enumerate_routes, including graph reconstruction each query.
- `cached_legs`: reuse all downstream ride connections and their graph; a caching control.
- `fragments`: reuse only adjacent, service-labeled connections; merge same-service continuation.
- Both experimental arms share a traversal implementation; cached_legs also caches traversed stops.
- No completed routes, destination bounds, ETA, or live vehicle identities are cached.
- Every query recomputes the reverse optimistic ride-time bound. No geographic-heading pruning.
- Indexes freeze input records; changed topology/timing requires rebuilding the index.
- Same transfer, minimum-time and count budgets; expansion units differ between representations.
- Compare full route keys AND ride/wait/buffer/expected costs, not merely the fastest route.
- Numerical pruning tolerance never relaxes the completed-route minimum-time limit.

## Measurement

- 5 repeats; seeded shuffled method order; correctness/allocation passes warm the process first.
- Build samples include snapshot hashing and graph preparation, but exclude file loading/imports.
- Warm query samples exclude build, correctness validation, plotting and tracemalloc overhead.
- Allocation figures are separately measured Python tracemalloc bytes, not process RSS/native memory.
- Query allocation excludes the retained index and input network, but includes output routes.
- Workload time is the SUM of per-query medians, not a timed end-to-end batch.
- First-workload estimate = median build + sum of query medians; not application startup latency.
- Seeded OD workload includes unreachable pairs; this is not representative passenger demand.

## Results

| Network | Method | Connections | Build ms | Workload ms | First workload ms | Match / total | Max query Python KiB | Index Python KiB |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| shared_corridor | rebuild | rebuilt | 0.000 | 1.094 | 1.094 | 6/6 | 59.2 | 0.0 |
| shared_corridor | cached_legs | 30 | 0.226 | 0.523 | 0.749 | 6/6 | 46.9 | 21.1 |
| shared_corridor | fragments | 20 | 0.189 | 0.547 | 0.736 | 6/6 | 46.8 | 18.7 |
| onboard_continuation | rebuild | rebuilt | 0.000 | 0.834 | 0.834 | 6/6 | 35.0 | 0.0 |
| onboard_continuation | cached_legs | 31 | 0.183 | 0.340 | 0.523 | 6/6 | 22.9 | 19.5 |
| onboard_continuation | fragments | 16 | 0.143 | 0.312 | 0.455 | 6/6 | 23.1 | 15.4 |
| candidate_loss | rebuild | rebuilt | 0.000 | 0.627 | 0.627 | 6/6 | 19.1 | 0.0 |
| candidate_loss | cached_legs | 25 | 0.177 | 0.127 | 0.304 | 6/6 | 6.3 | 19.2 |
| candidate_loss | fragments | 13 | 0.141 | 0.128 | 0.269 | 6/6 | 7.6 | 15.9 |
| blk18_cde | rebuild | rebuilt | 0.000 | 129.836 | 129.836 | 6/6 | 7194.4 | 0.0 |
| blk18_cde | cached_legs | 196 | 0.778 | 126.122 | 126.899 | 6/6 | 7129.1 | 94.5 |
| blk18_cde | fragments | 50 | 0.387 | 125.432 | 125.819 | 6/6 | 7225.9 | 38.5 |

Candidate/cost mismatches: **0**. Inconclusive method/query comparisons: **0**.

A budget-exceeded query is inconclusive, not unreachable or an empty successful result.

## Interpretation and limits

Compare fragments against BOTH controls. Beating rebuild alone does not establish that
fragment search is better than ordinary caching. Reuse shifts work into index creation
and consumes retained memory; adjacent expansion can visit more intermediate states.
Repeated-query gains do not imply a faster first query or faster actual bus journeys.

Small millisecond differences are descriptive measurements, not statistical evidence
of a speed advantage. Five repeats on these small networks do not establish scaling.

The local case preserves all declared direction fragments, including limited 106A,
solely to compare topology enumeration. Operating windows, fare continuity, live arrivals
and catch probabilities are not evaluated. Minimum-time bounds omit random waiting.
One-pattern repeated stops remain unsupported by the existing model; cycles across
services and reboarding are rejected. This is not an all-island or timetable solver.

Timing and allocation results depend on Python, hardware, GC and tracing behavior.
The workload, network hashes, candidate hashes and route counts are reproducible;
milliseconds and allocation byte counts are not guaranteed identical across runs.

## Reproduce

```sh
python -m experiments.fragment_benchmark
```

Default parameters: 5 repeats, seed 29, 5 seeded additional OD pairs per case.
See experiment.json for exact inputs, per-query budgets, build samples, hashes and provenance;
queries.csv contains per-method/query results. JSON/CSV are generated locally and Git-ignored.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

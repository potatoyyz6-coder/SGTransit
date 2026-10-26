# Selectable-station workload

Offline, frozen historical topology. Reference departure: 2026-10-26 10:00 SGT.
Not a live journey, timetable validation, or comparison with external navigation products.

| Network | Origin | Destination | Candidates | Eligible | Method | Cold ms | Warm median ms | Python peak KiB |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| school | 28109 | 17159 | 1968 | 930 | enumeration | 538.8 | 578.1 | 16776.9 |
| school | 28019 | 16159 | 497 | 497 | enumeration | 129.7 | 154.8 | 3971.8 |
| home | 12061 | 42171 | 61 | 61 | bounded_corridor | 72.8 | 13.3 | 2992.4 |
| home | 12071 | 42071 | 42 | 42 | bounded_corridor | 17.7 | 9.1 | 569.9 |
| service97 | 41009 | 28211 | 1 | 1 | bounded_corridor | 13.9 | 0.3 | 792.7 |
| service97 | 28279 | 18079 | 1 | 1 | bounded_corridor | 9.5 | 0.2 | 797.8 |
| service97 | 17149 | 14119 | 1 | 1 | bounded_corridor | 11.9 | 0.3 | 803.6 |
| service97 | 02101 | 05649 | 1 | 1 | bounded_corridor | 11.1 | 0.2 | 795.3 |
| service97 | 03539 | 15041 | 1 | 1 | bounded_corridor | 12.6 | 0.3 | 800.4 |
| service97 | 14131 | 20021 | 1 | 1 | bounded_corridor | 14.1 | 0.5 | 804.2 |

All returned routes validated; repeated queries retained identical candidate hashes. API calls: 0.

## Measurement limits

- One cold query and three warm repeats by default, after loading topology and the catalog.
- Query timing includes reference estimates, grouping and response construction, not browser rendering.
- Allocation is a separate cold-query tracemalloc pass; not RSS or native memory. Input topology is excluded.
- Warm reuse caches topology candidates only. Date/readiness/window estimates are recomputed.
- Larger networks use bounded corridor discovery, not exhaustive search or an optimality guarantee.
- Ordinary enumeration is complete only inside the declared network and configured constraints.
- These small directed networks do not establish all-island performance. Repeated-stop patterns remain unsupported.
- Full inputs, source/query/network hashes and per-query measurements are in locally generated workload.json.

Reproduce: `python -m experiments.station_planning_check`.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

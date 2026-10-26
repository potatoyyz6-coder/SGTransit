# Changelog

## Unreleased

Source development changes, not a new versioned GitHub release:

- Provenance-preserving route combination view with prefix selection, shared
  physical corridors, path-dependent continuation, paging and original detail links.
- Read-only loopback `/api/route-combinations` using existing request and expiry guards.
- Offline custom endpoints and nearby-stop discovery inside declared local networks;
  separate fragment-index benchmark, without replacing the routing algorithm.
- Archived the old route map, split the experiment guide from README and documented
  generation of the previously assumed Central Library comparison artifact.

Acceptance and limitations: [local verification](docs/COMBINATIONS_VERIFICATION.md).

## Publication Evidence (Not A New Version)

The [2026-10-23 audit](docs/PUBLICATION_AUDIT_20261023.md) observed a non-draft
`v0.1.0` GitHub release while the repository was private. That audit date is not
the release creation date or a public-visibility change date. Local commit
`35bdab47079b0db0082d2767539993f50e9d3639` (2026-10-24) records public-research
documentation preparation; a documentation commit alone does not prove when
visibility changed. No additional release has been created by this work.

## 0.1.0 - 2026-10-12

Initial private source release in `potatoyyz6-coder/SGTransit`.
Windows/Linux CI on Python 3.10 and 3.12 passed for the initial source commit;
see [publication evidence](docs/RELEASE_VERIFICATION.md#github-publication).

- Reproducible synthetic routing, simulation and reliability baselines.
- Historical directed bus topology with bounded candidate search, transfer
  variants and shared onward choices, including remaining onboard.
- Loopback-only Chinese UI for two local case networks, with offline estimates,
  optional explicitly confirmed ETA requests and private saved-snapshot support.
- Strict ETA evidence analysis kept separate from model-based references.
- MIT project code license, separate dataset/vendor attribution, offline test
  guard, CI configuration and publication audit/export utility.

Limitations: local bus-only cases, historical topology, assumed ride times and
headways without calibrated catch probabilities, no full distance-fare engine,
no citywide completeness or demonstrated superiority over external planners.

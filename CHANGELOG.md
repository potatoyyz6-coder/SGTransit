# Changelog

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

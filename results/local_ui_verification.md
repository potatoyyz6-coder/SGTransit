# Local UI verification

Verified 2026-10-11, Singapore time. Personal loopback-only interface, not a
public navigation service. No real LTA requests were made during development QA.

## Deliverables

- `python -m experiments.local_app` serves the interface on 127.0.0.1:8765.
- Two declared corridor cases: Blk 18 -> CDE (25 stops) and Information Technology
  -> Signature Pk (47 stops). The first preserves the 7,212-candidate search;
  the second uses the existing bounded corridor discovery (66 candidates at
  the default buffer), explicitly labeled as potentially missing alternatives.
- Offline current-clock estimates, optional private historical snapshot, and
  explicitly confirmed single-round current ETA collection.
- Eight service-sequence families with transfer-stop variants, per-leg timing
  provenance, sortable references and summary export.
- Manual en-route position/onboard status, continuation versus transfers,
  bounded ETA refresh and adoption of an alternative for subsequent stop selection.
- Route history remains in memory; continuation adds no boarding delay, waiting
  or transfer. A waiting transfer's alighting clock is preserved across refreshes
  and identical travelled prefixes. Historical projections cannot use today's ETA.
- Existing CLI experiments and strict retrospective ETA replay remain unchanged.

## Backend tests

`python -m pytest -q -p no:cacheprovider`

**252 passed in 51.24 seconds** on the final backend code.

The nine new tests in `tests/test_local_app.py` cover both case adapters,
offline operation with network prohibited, private snapshot availability,
historical/current separation, per-leg continuation accounting, reboarding
prevention, waiting-window expiration, route adoption, current refresh with
synthetic responses, bounded collection, no retries, sanitized API failure,
missing credentials, cooldown, deadline, source metadata and in-memory expiry.

HTTP checks cover loopback binding, Host/Origin/CSRF validation, CSP, JSON/body
validation, asset serving, non-whitelisted paths and credential-free responses.
Real LTA authentication/arrival accuracy was not tested or claimed.

## Browser checks

Chrome through Playwright CLI, using `tests/local_ui_browser.js`:

```text
{"passed":true,"viewports":[1440,390,320],"liveRequestsIntercepted":1,
 "realLtaCalls":0,"consoleErrors":[]}
```

The check covers initial rendering, all three data modes, historical 40.3-minute
reference, source tags, route switching, variant switching, sort, en-route
continuation/transfer choices, adopting a new onward itinerary, network image
loading, summary download, second case, historical refresh disabled, live
confirmation scope, cancellation and Escape after previous confirmation.
The one attempted live action is intercepted as a synthetic HTTP 503 to exercise
the error state. That expected resource error is not a JavaScript exception.

No horizontal document overflow at 390px or 320px. Desktop and narrow-screen
screenshots were inspected for readable labels and non-overlapping controls.
Screenshots are local ignored QA artifacts in `output/playwright/`, including
`desktop-saved.png`, `mobile-320.png` and `mobile-detail-390.png`.

Browser-check reproduction needs Playwright CLI and the private Oct 8 snapshot;
the Python tests use synthetic fixtures and do not need that private file.
The browser check intercepts live actions and never confirms a real collection.

## Runtime and privacy

Final service listener verified: **127.0.0.1:8765**, not 0.0.0.0 or a LAN address.
Only that computer can open the UI; narrow-screen QA is not phone/LAN access.
Browser assets are local, with vendored Lucide 1.55.0 and its license preserved.
The key is read only by the Python backend. No passenger location tracking,
accounts or PII collection is added. Raw ETA snapshots contain source metadata,
not the manual journey selections. No automatic collector or scheduler starts.

Each explicit collection has one request per case stop, at most 25 or 47 calls,
a 60-second inter-round cooldown, a 90-second start-new-request cutoff and a
6-second request timeout. Partial/error observations retain modeled references
with uncertainty labels, not invented live arrivals or successful journeys.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

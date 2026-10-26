# Route Combination Verification

Initial verification: **2026-10-25**. Final pagination audit: **2026-10-26**.
Version: **Unreleased local working tree** on
`codex/custom-stop-planning`, based on commit
`35bdab47079b0db0082d2767539993f50e9d3639`.
This document does not imply a commit, push, CI run or GitHub Release of these changes.

## Functional evidence

- Final full offline Python suite: **330 passed in 63.09s** on 2026-10-26,
  Windows / Python 3.14.6. The 2026-10-25 snapshot passed 329 tests locally
  and **329 passed in 86.78s** in a Git-eligible clean export, before the final
  large-graph pagination regression was added. Counts describe collected test cases,
  including parametrization, not the number of `test_` functions.
- Unit and integration coverage includes prefix/suffix sharing, direction and OD
  separation, empty/same-stop/single routes, continuation versus transfer,
  incompatible branch selection, cycle/reboarding rejection, paging, unknown
  access, plan expiry and Host/Origin/CSRF protection of the new endpoint.
- Original row IDs, time components and transfer counts remain unchanged.
  All eligible candidates participate, including non-shortlisted variants.
- A 196-route synthetic shared corridor spans multiple graph pages. Expansion
  of the final node on each page keeps the same page boundaries and at most
  60 visible nodes. A 12-choice fixture checks accurate hidden counts on both
  pages. These are display regression fixtures, not travel-time evidence.
- Playwright combination, legacy UI and custom-station flows passed at desktop
  1440px, 390px and 320px. No JavaScript exceptions or horizontal overflow.
  The unsupported-stop check intentionally receives a validation HTTP 400.
- Verified branch selection/undo, stop expansion, shared-service inspection,
  original-route adoption, onward continuation and multiple actual OD groups.
- The browser test server removed both LTA key variables, had no private snapshot,
  and used a provider that fails if collection is attempted. External API calls: 0.
- Inspected the project-generated desktop and narrow screenshots. README image:
  `docs/images/route-combinations.png`, fixed 2026-10-23 10:00 SGT model reference.

## Workload

[Generated workload report](../results/route_combinations/workload.md) checks both
original cases and a two-origin custom query. It records display construction,
five warm view responses, separate Python allocation measurements and JSON size.
Search and timing estimation are outside the measured display cost.
Raw parameters, candidate/source hashes and individual timings are regenerated
with `python -m experiments.combinations_check`; full JSON is not committed.

## Publication checks

- `python -m tools.release_check` found no selected credential patterns, exact
  active environment secrets or prohibited paths in Git-eligible working files.
  This is not a new Git-history, image-OCR or comprehensive security audit.
- `python -m tools.check_doc_links` passed for inline local file links against
  the publishable inventory, not merely files left on disk. External URLs and
  heading anchors are outside this automated check; the moved guide links were
  reviewed separately. `git diff --check` passed.
- Exported the Git-eligible file set under ignored `tmp/`, without private ETA
  records, ignored plan JSON or environment files. No source commits were made.
  Used existing installed dependencies, not a newly provisioned virtualenv.
- In that export, ran the documented `sg_transit plan` command with the committed
  `data/real/network.json`, 10,000 evaluation samples and fixed seeds. It generated
  the absent Central Library JSON (31 candidates), then `compare` succeeded with
  six existing manually recorded rows. No Google/LTA call was made, and no
  observation fields were changed. This verifies reproduction, not actual speedup.
- The exported source, rather than the original editable installation, was used
  through its `src` path. Its 329-test snapshot passed without private captured data.
- New local UI responds at `127.0.0.1:8766`; no timer or automatic collection starts.
- [Prepared release notes](RELEASE_NOTES_COMBINATIONS.md) remain unpublished.
  Commit, push and GitHub release require separate owner confirmation.

Runtime source fingerprints for this verification:

| File | SHA256 |
| --- | --- |
| `src/sg_transit/route_combinations.py` | `000ab9f660beb921f249df1f083b9b52cc8be8687dc5bfd0c99d898544388e97` |
| `experiments/local_planner.py` | `785e907050b9cde3cc1ec1538262dcab5a18d2915bd26148f06699a554e82d5f` |
| `experiments/web/combinations.js` | `2551e05a2c505f56609311388ef3edb2624aac9554e210988afcda8200f44ab0` |

## Limits

The browser shows a bounded prefix explorer plus shared-corridor annotations,
not an unrestricted graph editor. Downstream decisions are progressively revealed;
physical sharing does not make every incoming/outgoing service pair legal.
Unknown availability remains unknown. There is no recalibrated arrival model,
actual speedup claim, real-time guarantee or new public navigation service.

The Windows sandbox initially prevented pytest temporary-directory creation and
Chrome startup; approved outside-sandbox runs completed without weakening tests.

## Completion cross-check

| Plan requirement | Evidence |
| --- | --- |
| Presentation only; no search/replay or timing change | No diff in routing, simulation, adaptive or strict replay modules; original-row comparison tests |
| All default candidates, actual OD and plan/time isolation | Index built from aligned eligible rows in each plan; custom-OD tests; per-plan cache and expiry |
| Common prefixes, service direction, shared tails and continuation states | Combination unit tests, home-case browser walkthrough and inspected screenshot |
| No invalid edge stitching or repeat/cycle introduction | Child-only prefix selection; validation and incompatible-selection counterexamples |
| Original IDs, cost fields and transfer counts preserved | Both original-case tests and workload hashes; original detail equality |
| Combination/independent views; original adoption and onward reference | Combination, legacy and custom-station Playwright flows |
| Read-only guarded API, exclusions and unknown states | Existing HTTP guards and new endpoint tests; custom unknown-access tests; response search/exclusion metadata |
| At most 60 nodes, 8 choices; reversible expansion and paging | Long-corridor and 12-choice tests; browser original-route paging and undo |
| Performance and own-project demonstration | Generated workload report and README screenshot, no external route images |
| Archived roadmap, corrected reproduction and shorter README | Archived ROUTE_MAP; moved guide; successful plan/compare in clean export |
| Dated evidence, honest release status and security checks | This record, CHANGELOG, unpublished release notes, release/link/whitespace checks |
| No unauthorized publication or collection | Working-tree-only changes; no commits/push/release or new external API requests |

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

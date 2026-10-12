# Publishing v0.1.0

This release is a local research reference tool, not a public navigation service.
Publishing source on GitHub does not authorize deploying the UI publicly.

## Contents

- Include source, tests, examples, documentation, LICENSE and NOTICE.
- Include the attributed, hash-checked historical BusStops/BusRoutes CSVs and
  small derived networks needed by offline cases.
- Keep reviewed result Markdown and project-generated PNG diagrams. The UI
  needs `results/blk18_cde_reference/routes.png`.
- Keep `results/pei_hwa_20261001/experiment.json` as a small regression input.
  Its network path is repository-relative; numerical results are unchanged.
- Exclude raw ETA captures, all keys, SDK PDFs, IDE settings, caches, smoke
  output, large candidate JSON/CSV files and Monte Carlo sample arrays.
- Google data is limited to small manually observed comparison fields. Never
  add screenshots, scraped content, bulk responses or a replacement dataset.

See [NOTICE](../NOTICE.md) for dataset licenses, access dates and attribution.
Do not regenerate historical results merely to make them look better.

## Local release gate

From the repository root, after installing the development dependencies:

```sh
python -m tools.release_check
python -m pytest -q -p no:cacheprovider
python -m tools.release_check --export tmp/release-clean
```

Use a new export name each run. No files are staged or deleted. The export is
exactly the Git-eligible working-file set, with a sibling SHA-256 manifest.
Create a fresh virtual environment and install `.[dev]` in the exported copy;
run the complete test suite, `python -m examples.demo`, and
`python -m experiments.local_app --port 8766` there. Confirm offline results,
route details, the diagram and no-key / missing-snapshot states.
All Python tests block non-loopback network connections and remove real LTA
keys before each test. Fake providers exercise API paths without LTA requests.
The optional browser test `tests/local_ui_browser.js` has a separate historical
snapshot mode; see its header. It is not part of the Python CI gate.

The lightweight audit checks excluded paths, a 5 MiB per-file budget, selected
credential patterns and exact active environment keys. It never prints values.
It is NOT a comprehensive secret scan, a Git-history audit or a legal opinion.
Inspect the staged diff and file list before publishing. If any credential was
exposed, revoke/rotate it before trying to remove it from Git history.

## Before the first push

1. Review README, LICENSE, NOTICE, this checklist and the verification record.
2. Review `git status --short`; stage only the reviewed publication files.
3. Inspect `git diff --cached --stat`, `git diff --cached --check`, and the actual
   staged changes. Verify no secrets or unreviewed screenshots are present.
4. Create the initial commit and configure the user's intended GitHub repository.
   Do not embed a token in the remote URL. Prefer a private first push while
   reviewing repository settings and checking the clean-checkout CI results.
5. Publish/tag `v0.1.0` after those checks. Do not claim the CI passed until it
   has actually run on GitHub. Release notes: [CHANGELOG](../CHANGELOG.md).

CI is configured for Windows/Linux and Python 3.10/3.12. Installation needs
package-index access; test execution needs no LTA key or external data fetch.
The UI remains loopback-only. This project is not yet a standalone wheel-based
application: run the UI and experiments from the source checkout.

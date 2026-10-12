# v0.1.0 Publication Verification

Prepared on 2026-10-12. The first sections record local preparation;
the final section records the subsequent private GitHub publication.

## Checks performed

- Added the MIT license with owner approval and separate data/vendor notices.
  Checked the pinned mirror's NOTICE: its code is MIT, but LTA bus data remains
  subject to the Singapore Open Data Licence. Original CSV bytes are unchanged.
- Excluded raw captures, credentials, SDK PDF, IDE configuration, caches,
  large generated candidate files and simulation arrays. Preserved the UI diagram,
  small historical regression input, reports and project-generated plots.
- The publication audit found no matches for its credential patterns or exact
  active environment credentials in Git-eligible files. It only reports paths
  and reasons, never matched values. This is not a comprehensive security audit.
- The source repository had no commits and no configured remote at inspection.
  No source-repository files were staged or committed; nothing was pushed.
- Corrected a machine-specific regression network path and future case-report
  serialization. Numeric historical experiment results were not recalculated.
- Added Git attributes to preserve byte-hashed CSV/JSON inputs across Windows
  and Linux checkouts. Original local raw captures and large outputs remain intact.

## Runtime evidence

- Existing development environment: **256 tests passed** after adding four
  publication/network/portability checks. The suite blocks non-loopback network
  access and clears real LTA keys per test; mocked providers cover API behavior.
- Exported only publication-eligible files to a new directory, without private
  recorded data. Created a fresh virtual environment (no system site-packages),
  then installed `.[dev]` from the exported source.
- Fresh environment: Python 3.14 on Windows, NumPy 2.5.4, NetworkX 3.7,
  Matplotlib 3.11.2, pytest 9.1.1. **256 tests passed**; `pip check` passed.
- Also created a temporary Git snapshot under ignored `tmp/`, cloned it locally
  with `core.autocrlf=true`, and installed from that actual checkout. All **256
  tests passed again (41.81s)**. Both raw CSV hashes matched the source; the full
  initial-commit whitespace check passed. Temporary verification commits are
  not commits in the user's source repository and were not pushed anywhere.
- The documented `python -m examples.demo` command ran successfully. Its
  reported means/P95 are synthetic, not Singapore journey measurements.
- The documented school-case generator completed in the cloned copy: 7,212
  topology candidates, 4,558 default-eligible candidates and eight displayed
  service families. It regenerated the report, candidate files and diagram.
- Started the exported UI on loopback with both LTA key variables removed.
  Playwright verified both offline cases, missing-snapshot/no-key states,
  intermediate choices, onboard versus alighted behavior, and the route diagram.
  Desktop 1440px and narrow 390/320px views had no horizontal overflow or
  JavaScript exceptions. No live request was attempted. Screenshots were inspected.
- Repeated that browser smoke test on the final cloned UI, including the added
  data attribution. The server error log was empty. Local Markdown file links
  resolved in the publication checkout without excluded private/generated files.
- `docs/images/local-reference.png` is our own offline UI, not third-party map
  content. It is an illustrative model result captured during this verification.

The sandbox initially blocked pytest/pip temporary-directory creation and a Git
helper process for the local clone. Those
commands were rerun successfully outside the sandbox; no tests were removed,
skipped or weakened to handle that environment limitation.

## Publication Checklist At Preparation Time

Choose the GitHub repository, review/stage the intended files, make the initial
commit and push. CI is configured for Windows/Linux with Python 3.10/3.12 but
has **not** yet run on GitHub. Tag/release only after checking that result.
No remote repository, public deployment, scheduled collection or LTA API request
was created by this preparation. See [release steps](RELEASING.md).

## GitHub Publication

On 2026-10-12, the owner authorized creating the **private** repository
[potatoyyz6-coder/SGTransit](https://github.com/potatoyyz6-coder/SGTransit).
GitHub authenticated the intended owner, and repository visibility was verified
as private before pushing. The initial source commit is
`46e40623f4ea50c95efda1c90c92530b15d4a293`; GitHub's `main` matched the local commit.

[Initial CI run 38231889226](https://github.com/potatoyyz6-coder/SGTransit/actions/runs/38231889226)
completed successfully across Windows/Linux and Python 3.10/3.12. Each job ran
dependency installation, the publication audit, the offline test suite and
the synthetic example. This is actual GitHub-run evidence, not only local tests.

The repository contains 183 reviewed source/data/documentation files at initial
publication (about 5.6 MB before Git compression). Credentials, raw private ETA
captures, SDK PDF, large generated outputs and local verification helpers were
excluded. No Actions secret or LTA key was uploaded. Authentication used the
existing local Git Credential Manager authorization without storing tokens in
the repository or remote URL. Commits use the account's GitHub privacy email.

Publication does not deploy a website or start data collection. Access to this
repository and its release/CI pages requires the owner's permission. The code
remains MIT-licensed; third-party data retains its separate attribution and terms.

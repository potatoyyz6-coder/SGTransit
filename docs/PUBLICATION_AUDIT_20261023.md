# Pre-publication audit: 2026-10-23

## Decision

No blocking credential or prohibited-file finding was detected by the checks
below. Publishing this version as a research prototype for portfolio review is
reasonable after the documentation and privacy decisions below are addressed.
This is not approval to deploy a public navigation service, a comprehensive
security assessment, or a legal clearance.

At the time of this audit the repository was **private**. This audit did not change visibility, push
commits, modify algorithms, or call LTA/Google APIs.

## Findings at audit time

This section records the pre-publication findings, not the current completion
status. The subsequent publication preparation updates current labels and
documentation without rewriting historical commits or changing route results.

1. Review the personal-location association. README describes the examples as
   going "home" and to "school", while listing specific stops. Public stop
   coordinates are not secret, but associating them with the author's routine
   may reveal more than intended. Prefer neutral case names. Renaming current
   text alone does not remove old wording from published Git history.
2. Align the Google comparison instructions. README's older numbered workflow
   includes recording screenshots, whereas its publication boundary prohibits
   committing them. Restrict the workflow to minimal manually observed fields
   and explicitly exclude screenshots from published material.
3. When visibility actually changes, update README's current-private wording.
   Preserve dated statements describing the historical private release.
4. Review and commit `docs/RESUME_PROJECT.md` before expecting recruiters to
   see it. It is currently untracked and contains the explicit OpenAI Codex
   collaboration disclosure. Add a short disclosure/link to README so it is
   visible from the repository entry page; the current README has no Codex
   disclosure. Update the resume document's access-status wording as needed.

## Audited snapshot

- Repository: `potatoyyz6-coder/SGTransit`; GitHub reported `private: true`.
- Remote branch: `main`.
- Branch and tag `v0.1.0`: `d050939f8ad88288749de7c9933d80c76953e5f9`.
- All remote branches/tags were enumerated: one branch and one tag.
- Two reachable commits; 185 unique historical blobs, totaling 5,581,338 bytes.
- Git-eligible working tree before this report: 184 files, 5,596,450 bytes.
- The existing untracked resume document was included in the working-tree scan,
  but is not part of the remote snapshot.

## Checks and outcomes

- Scanned reachable historical blobs and commit metadata, plus current eligible
  files, for selected credential patterns, credential-bearing URLs, long bearer
  literals, generic secret assignments, and exact available environment/GitHub
  credentials. No matches were reported. Matched values were never printed.
- Checked historical paths for private captures, temporary output, environment
  files, SDK PDFs, key files and logs. No prohibited historical paths were found.
- GitHub has three completed successful Actions runs: `38231889226`,
  `38232341763`, and `38273776369`. Each has one attempt. All three available
  log archives were scanned in memory: 24 archive members total. No selected
  credential patterns or active credential values were detected.
- No Actions artifacts or separately uploaded release assets were listed.
  GitHub's automatic source archives correspond to the audited tag, not an
  additional uploaded binary. One non-draft release, `v0.1.0`, was listed.
- No issues, issue comments, pull-request review comments, or commit comments
  were returned by the queried endpoints. Wiki is disabled.
- Reviewed LICENSE, NOTICE, provenance references, release instructions, CI
  configuration, and public claims. MIT covers original code/documentation;
  the LTA topology and Lucide assets are separately attributed. Older generated
  `license: MIT` fields have an explicit correction in NOTICE, not silently
  changed historical results.
- Manually viewed the README UI screenshot and the Blk 18 route diagram. These
  show the local modeled interface and project-generated topology, not a Google
  map screenshot. This was a visual sample, not an OCR audit of every image.
- Fresh full local suite: **256 passed in 43.93s**. The first sandboxed run
  encountered Windows temporary-directory permission errors; the approved
  rerun completed successfully. Tests prohibit external network connections.
- `python -m tools.release_check` passed; `git diff --check` passed before this
  report was added. Functional source files were unchanged.

## Limits and evidence

The temporary read-only helper and redacted machine-readable inventory are in
ignored `tmp/audit_publication.py` and `tmp/publication_audit_20261023.json`.
Credentials and raw Actions archives were not saved. Downloads used a separate
unauthenticated request after GitHub's signed redirect.

The scan uses selected patterns and exact currently available credential values,
not a complete credential detector. It cannot rule out unknown or encoded
secrets, secrets inside images, deleted/expired remote content, or external
copies. Only reachable published refs were audited; local Codex internal refs
are not remote publication history. This audit did not re-review legal terms,
audit dependency vulnerabilities, or independently verify every data licence.

Recheck staged changes and any new CI logs before publication. The above
findings apply to this snapshot, not to later commits. The original raw ETA
captures remain excluded, so historical analyses requiring them are not fully
reproducible from the public source alone; the offline examples and synthetic
tests are the intended reproducible entry points.

This project is an independent research project and is not affiliated with,
endorsed by, or sponsored by the Land Transport Authority of Singapore,
Google, or Citymapper.

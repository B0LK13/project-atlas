# Contributing to Project Atlas

## Who this document is for

Project Atlas is currently a private repository with a single
collaborator (`B0LK13`) plus explicitly authorized governed agents.
There is no public external contribution path today. This document
describes the internal workflow the repository owner and any
explicitly authorized agent must follow; it will be revisited if the
repository's visibility or contribution model changes.

There is no separate `CODE_OF_CONDUCT.md` for the same reason: a
generic code of conduct aimed at an open public contributor community
would be either vacuous or misleading about who it actually applies to
today. This omission is a deliberate decision, not an oversight, and
is recorded here per `docs/adr/ADR-006-github-repository-governance-baseline.md`.

## Workflow

1. Identify or open a tracked work package (`AS-xxx`) or issue before
   starting substantial work.
2. Branch from `main`: `<type>/<as-xxx-id>-<short-description>`
   (e.g. `fix/as-mvp-001-r1-relation-edge-tests`), matching this
   project's existing branch-naming convention.
3. Implement with this project's established bounded-scope discipline:
   prefer test-first changes, keep production changes minimal and
   justified by a failing test, and keep evidence-only changes in
   their own commits, separate from behavioral changes (see this
   repository's AS-MVP-001 history for the pattern:
   `test(...)` / `fix(...)` / `docs(evidence): ...` commit sequencing).
4. Run the real local validation commands documented in `AGENTS.md`
   and `CLAUDE.md` before opening a pull request:
   ```
   python -m pytest
   python -m ruff check .
   python -m mypy src
   ```
5. Open a pull request using `.github/pull_request_template.md` and
   fill in every field — work-package ID, exact base/implementation/
   evidence hashes, changed paths, command results, security and
   documentation impact, rollback considerations, known limitations,
   and the prohibited-history-operations acknowledgement.
6. Wait for CI to pass and for the required review, then integrate
   using whichever GitHub-supported method is actually enabled and
   verified for this repository (see ADR-006's "Required-check
   activation" and "GitHub settings strategy" sections — this
   repository does not assume rebase-merge, squash, or merge-commit is
   available until that has been independently confirmed).
7. Do not use `git push --force`, rebase or amend any commit already
   on `main`, or otherwise rewrite certified history at any point in
   this workflow.

## Governed-agent sessions

For governed-agent work specifically, `AGENT-BOOTSTRAP.md` documents a
separate, existing session-lifecycle control plane
(`atlas-vault-documentation/scripts/atlas_agent.py`:
`bootstrap -> preflight -> session-start -> work milestones ->
validation -> completion -> postflight -> receipt -> close`). That
control plane governs internal session discipline; it does not replace
the GitHub PR review described above. A governed session's receipt
should be referenced from step 5's pull request description.

## Scope and support

There is no separate user base distinct from contributors today, so
there is no separate support document. Questions about this project's
architecture and conventions are answered in `AGENTS.md` and
`CLAUDE.md`; questions about a specific work package's status are
answered in that package's `docs/evidence/<PKG>-receipt.yaml` and
`docs/work-packages/<PKG>.md` (when one exists) or `docs/backlog.md`/
`docs/master-roadmap.md` otherwise.

Security vulnerabilities must never be reported through this workflow
or through ordinary GitHub Issues — see `SECURITY.md`.

# Contributing

This is currently a private repository maintained by a single owner
(`B0LK13`) together with governed agent sessions working under
`AGENT-BOOTSTRAP.md`. There is no public external contribution path today.
This document describes the internal workflow for the repository owner and
any explicitly authorized agents; it will be revisited if the repository's
visibility or contribution model changes.

## Branching

Branch names follow the existing repository convention:
`<type>/<AS-xxx-id>-<short-description>` (for example,
`fix/as-mvp-001-r1-relation-edge-tests`). Governance/architecture packages
use `architecture/<AS-xxx-id>-<slug>` for architecture-only branches and
`implementation/<AS-xxx-id>-<slug>` for implementation branches.

## Integration is pull-request only

All changes land on `main` through a pull request. Direct pushes to `main`
are not permitted. Force pushes, history rewriting, and unauthorized
squashing of certified history are prohibited on any branch that carries
certified or evidence-bearing commits.

For governed work packages (`AS-xxx`), be aware of the exact base commit
your branch is built on — record it in the PR description (see the pull
request template) so reviewers and later verifiers can confirm ancestry
independently.

## Before requesting review

Run the real local validation commands documented in `AGENTS.md`/
`CLAUDE.md` (for example `pytest`, `ruff check .`, `mypy src`) and record
their results. Do not open a PR with unrun or invented validation results.

## Review and merge

- All review conversations must be resolved before merge.
- The current live required-approving-review count is **`0`**, not `1`.
  This is a deliberately temporary bootstrap state recorded in
  `docs/adr/ADR-006-github-repository-governance-baseline.md` — the
  repository has exactly one collaborator today, self-approval is
  unavailable, and administrator bypass is unavailable, so a `1`-approval
  requirement would be an unconditional merge lockout. The count returns
  to `1` only once a second trusted collaborator exists, has review
  rights, a test PR has proven their approval satisfies branch
  protection, the Project Owner authorizes restoration, and an
  independent verifier confirms the resulting rule.
- Do not merge with unresolved review threads or a failing required
  check.

## Documentation and evidence expectations

Governance-sensitive or work-package changes should keep evidence-only
corrections (e.g. `docs/evidence/*.yaml`) separate from behavioral changes,
in their own commits, mirroring this project's existing `test(...)` /
`fix(...)` / `docs(evidence): ...` commit sequencing convention.

## Three stages of governance change

This repository distinguishes three separate stages, which are not
interchangeable:

1. **Architecture certification** — an ADR/work-package is independently
   reviewed and certified (no repository files beyond the architecture
   documents themselves change).
2. **Implementation certification** — the certified architecture is
   implemented in repository files and independently verified before
   merge.
3. **Platform activation** — live GitHub settings (e.g. branch protection,
   required checks) are changed and independently verified against the
   actual GitHub API/UI state, never assumed from a narrative claim.

A PR being approved and merged at one stage does not by itself authorize
the next stage.

## Governed-agent sessions

For agents doing governed work inside the vault, `AGENT-BOOTSTRAP.md`
documents the internal `atlas_agent.py` session lifecycle
(bootstrap → preflight → session-start → validation → completion →
postflight → receipt → close). That internal discipline should already
have produced the receipt referenced in your PR description; this document
does not duplicate it — GitHub PR review is the enforcement mechanism for
the GitHub-facing surface.

## Support and scope

There is no external user base distinct from contributors today. Questions
about this repository's governance should go through the same private
channel described in `SECURITY.md`, not a public issue.

# Governance

This document describes how Project Atlas is governed on GitHub and in
local evidence practice. It records real roles and stop boundaries; it
does not claim live GitHub settings that have not been independently
verified and activated.

Authoritative architecture: `docs/adr/ADR-006-github-repository-governance-baseline.md`
Work package: `docs/work-packages/AS-GH-001.md`

## Roles

| Role | Who | May | Must not |
| --- | --- | --- | --- |
| Project Owner | Repository owner (`B0LK13`) | Authorize scope, merge, release, exceptions, and settings activation | Self-certify technical work as Independent Verifier for the same candidate |
| Architecture Governor | Designated agent or human for the package | Approve architecture and boundary decisions | Implement the candidate under review for that package |
| Implementation Agent | Designated agent or human for the package | Change only authorized branch/paths | Issue independent certification or architecture approval for that candidate |
| Independent Verifier | Separate agent or human from the implementer | Reproduce validation, check evidence, certify or block | Implement the candidate under review |
| Merge Operator | Owner-authorized actor | Integrate the exact authorized head after checks | Treat a branch name or PR number as sufficient authorization |
| Repository Administrator | Owner (sole collaborator today) | Capture and, when authorized, change GitHub settings | Bypass protected-branch rules; invent lockout-safe exceptions |

One person may hold different roles across packages. The same actor must
not both **implement** and **independently verify** the same candidate.

## Decision and publication lifecycle

Governed work follows this sequence (stages are not interchangeable):

1. **Authorize** — Owner (or Owner-backed directive) defines package scope and baseline.
2. **Implement** — Implementation Agent works on a bounded branch from the authorized base.
3. **Independent verification (IV)** — Independent Verifier reproduces validation and evidence checks.
4. **Certify** — Verifier records pass/block; certification is not merge authority.
5. **Owner merge authorization** — Owner grants integration of an exact HEAD/TREE.
6. **Publish / integrate** — Merge Operator integrates the authorized candidate without squash, amend, cherry-pick, or rebase of certified commits.
7. **Post-merge IV** (when required) — Confirm resulting `main` tip/tree and validation still hold.
8. **Baseline update** — Receipts/roadmap record the new certified tip when Owner accepts it.

Platform (live GitHub settings) activation is a **separate** stage after
repository-file implementation. A merged PR of documents or workflows does
not by itself activate branch protection, required checks, CODEOWNERS
enforcement, or signed-commit requirements.

## Exact-hash and evidence rules

- Authorization is by full commit SHA (and tree when recorded), never by
  branch name alone.
- Receipts under `docs/evidence/` record base, candidate, validation
  commands/results, limitations, and authorization state.
- Evidence-only corrections are separate commits; prior receipt content
  remains reachable in history.
- Do not rewrite, force-push, or squash certified or evidence-bearing history.

## Stop boundaries

Stop and escalate to the Owner (do not invent a workaround) when:

- `main` has moved past the authorized base and the candidate is no longer
  a descendant of that base without a new Owner decision;
- receipt tip and working-tree tip disagree;
- validation fails or cannot be reproduced;
- a change would require inventing contacts, teams, SLAs, bots, portals,
  or email addresses;
- a settings change risks sole-collaborator merge lockout (for example
  restoring required approvals to `1` or enabling CODEOWNERS reviews while
  only one collaborator exists);
- Core / Control Plane / production Atlas semantics would change outside
  the authorized package scope.

## Emergency recovery

There is no administrator bypass under the current branch-protection
bootstrap. Recovery is Owner-executed and evidence-recorded:

1. Prefer a forward-fix PR from the last known-good tip.
2. Restore GitHub settings from a captured before/after snapshot (UI/API),
   not via `git reset` or force-push of `main`.
3. If a bad merge landed, revert with a normal PR; do not rewrite history.
4. Record the incident in a receipt or WORKLOG entry with exact hashes.

Detailed backup/restore drills (`BACKUP-AND-RECOVERY.md`) remain a
recommended follow-up and are not claimed complete by this document.

## Live settings honesty

As of the AS-GH-001 bounded slice and subsequent artifact-closure work:

- Repository-file governance artifacts may be present and tested.
- Live GitHub settings activation (required checks, approval count
  restoration, CODEOWNERS enforcement, force-push/deletion hardening,
  signed commits) remains **deferred** unless and until a separately
  authorized activation package is independently verified.
- Documents in this repository must not claim those live settings are
  active while they remain deferred.

See also: `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, `VERSIONING.md`,
`RELEASING.md`, `CODE_OF_CONDUCT.md`.

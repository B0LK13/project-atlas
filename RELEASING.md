# Releasing

This policy describes how Project Atlas publishes an authorized software
or documentation baseline. It reflects current practice: Owner-gated,
evidence-bound, and without automated tag/release bots.

## Lifecycle (required order)

1. **Implement** on a bounded branch from the Owner-authorized base.
2. **Independent verification (IV)** — separate actor reproduces validation
   and evidence checks.
3. **Certify** — IV records pass (or block). Certification is not merge.
4. **Owner merge authorization** — Owner names the exact HEAD (and TREE
   when used) that may integrate.
5. **Publish / integrate** — Merge Operator integrates that exact candidate
   to `main` without squash, amend, cherry-pick, or rebase of certified
   commits.
6. **Post-merge IV** (when the package requires it) — confirm resulting
   `main` tip/tree and gates.
7. **Baseline update** — receipts/roadmap record the accepted tip.
8. **Optional tag / GitHub Release** — only if the Owner explicitly
   authorizes a software release for that tip (see below).

Platform settings activation (branch protection, required checks, signing
enforcement) is **not** part of an ordinary release and remains deferred
until a separately authorized package (planned as AS-GH-002 or successor)
is executed and verified.

## Identity requirements

Every release or package-closure record must identify:

- package / work-package ID;
- exact base commit SHA;
- exact candidate HEAD SHA;
- exact TREE SHA when recorded in the receipt or closure report;
- validation commands and results;
- IV disposition and Owner authorization state.

A branch name or PR number alone is never sufficient.

## CI and gates

Before Owner merge authorization, run the repository-backed gates
appropriate to the change (at minimum those documented in `AGENTS.md` /
`CLAUDE.md`: Ruff, mypy, Core pytest, and Control Plane pytest when
control-plane paths change). Do not invent green results.

Live GitHub required-check enforcement may still be **off**; a green
Actions run is evidence, not proof that branch protection requires it.

## Tags and GitHub Releases

- Tags are optional and Owner-authorized only.
- If tagged, use annotated tags `vMAJOR.MINOR.PATCH` pointing at the
  exact authorized commit (see `VERSIONING.md`).
- CI must not auto-create tags or GitHub Releases.
- No registry publish pipeline is claimed here.

## Rollback

- Prefer a forward-fix revert PR from the last known-good tip.
- Do not force-push `main` or rewrite certified history to “undo” a release.
- Settings rollback (if a settings package was activated) restores prior
  API/UI values from a captured snapshot — separate from git rollback.

## Prohibited

- Squashing or rebasing certified commits to manufacture a cleaner tag.
- Claiming a release from an unverified tip.
- Publishing invented support/SLA/contact channels as part of release notes.

See also: `GOVERNANCE.md`, `VERSIONING.md`, `CONTRIBUTING.md`.

# AS-GH-001 — GitHub Repository Governance Baseline

**Status:** architecture-entry-gate-passed, implementation-not-started
**ADR:** `docs/adr/ADR-006-github-repository-governance-baseline.md`
**Architecture commit:** (recorded below once committed)
**Baseline (repository state this architecture was designed against):**
`a7a6ebc41ea884f7ce4ec2d70da89e6a44097381` (`main`, AS-MVP-001 closed,
independently confirmed identical to `origin/main` at
`https://github.com/B0LK13/project-atlas.git`)

## Summary

Establishes the durable, GitHub-native governance, contribution,
review, CI, security-disclosure, dependency-automation, versioning/
release, commit-signing, backup, and evidence-provenance baseline for
the newly authoritative `B0LK13/project-atlas` repository, without
touching any existing certified code, test, fixture, or `AS-001`
through `AS-MVP-001` evidence. Full rationale, threat model, and
per-section design live in ADR-006; this file is the executable
tracking record (mirroring `docs/backlog.md`'s role for the Core
package, adapted for this repository-governance package which has no
natural home in that Epic-lettered backlog).

This package does not modify, supersede, or reopen AS-MVP-001 or any
earlier certified work package.

## Scope boundary

In scope: repository governance documents, `.github/` templates and
workflows, `.gitignore` hardening, dependency automation, versioning/
release policy, commit-signing policy, backup policy, evidence-model
extension, and (Phase 6) verified GitHub repository settings.

Out of scope (see ADR-006 §4 for full list): any change to `src/`,
`tests/`, `tests/fixtures/`, existing `docs/adr/ADR-00[1-5]*.md`,
`docs/evidence/*.yaml`, `docs/backlog.md`, `docs/master-roadmap.md`,
or `atlas-vault-documentation/`; enabling GitHub Advanced Security
features unavailable on the current plan; rewriting, signing, or
rebasing any existing commit.

## Phase tracking

| Phase | Description | Status | PR(s) | Evidence |
|---|---|---|---|---|
| 1 | Governance and contributor documents (`README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `VERSIONING.md`, `RELEASING.md`; `.gitignore` hardening) | not started | — | — |
| 2 | PR, issue, ownership, and review templates (`CODEOWNERS`, PR template, issue templates) | not started | — | — |
| 3 | CI workflow baseline (extend `ci.yml`; control-plane tests, compileall, YAML/duplicate-key checks) | not started | — | — |
| 4 | Dependency and security automation (`dependabot.yml`) | not started | — | — |
| 5 | Release, signing, backup, and evidence policies (exercise `VERSIONING.md`/`RELEASING.md`; first tag) | not started | — | — |
| 6 | GitHub settings and required-check activation (independently verified, not owner-reported) | not started | — | — |
| 7 | Independent verification and closure | not started | — | — |

## Required artifacts (see ADR-006 §6 for full rationale)

- [ ] `README.md`
- [ ] `SECURITY.md`
- [ ] `CONTRIBUTING.md` (including the explicit "no `CODE_OF_CONDUCT.md`
      today" decision and folded-in support/scope section)
- [ ] `GOVERNANCE.md`
- [ ] `VERSIONING.md`
- [ ] `RELEASING.md`
- [ ] `.gitignore` updated to exclude `.session-preservation/`
- [ ] `.github/CODEOWNERS`
- [ ] `.github/pull_request_template.md`
- [ ] `.github/ISSUE_TEMPLATE/bug_report.yml`
- [ ] `.github/ISSUE_TEMPLATE/feature_request.yml`
- [ ] `.github/ISSUE_TEMPLATE/security_or_governance_gap.yml`
- [ ] `.github/ISSUE_TEMPLATE/config.yml`
- [ ] `.github/workflows/ci.yml` extended (control-plane tests,
      compileall, YAML validation, duplicate-key check,
      `.session-preservation/` tracked-path guard)
- [ ] `.github/dependabot.yml`

## Acceptance criteria

See ADR-006 §18 for the full, objective, independently-checkable list.
Summarized:

- Every required document exists with its specified sections.
- `CODEOWNERS`, PR template, and issue templates all parse correctly.
- Every workflow/evidence YAML file parses with zero duplicate keys.
- Every workflow action reference is pinned; no untrusted-fork secret
  exposure; least-privilege permissions.
- Every required branch-protection check maps to a real, previously
  successful job (never a placeholder).
- Dependabot ecosystems exactly match what's actually present
  (`pip`, `github-actions`).
- No existing certified history is rewritten; `main` remains a strict,
  fast-forward-only descendant of `a7a6ebc41ea884f7ce4ec2d70da89e6a44097381`.
- `.session-preservation/` never becomes tracked.
- No secret is introduced.
- Local and remote `main` remain aligned after every phase.
- Every Phase 6 settings claim is independently verified (GitHub
  UI/API evidence), not narrative-only.

## Known limitations (carried from ADR-006 §21)

- GitHub branch-protection/security settings reported by the Project
  Owner as already configured were **not independently verified** by
  this architecture review; they must be independently confirmed in
  Phase 6 before being treated as certified.
- GitHub Advanced Security (secret scanning, push protection, private
  vulnerability reporting) is unavailable under the current plan;
  `SECURITY.md`'s disclosure path is a compensating workaround, not an
  equivalent automated control.
- Whether `atlas-vault-documentation/` needs its own Dependabot entry
  was not conclusively determined; must be verified with real
  directory inspection before Phase 4.
- No secondary/offsite backup beyond GitHub + local clone +
  `.session-preservation/` bundles is mandated; recorded only as an
  open recommendation.

## Handoff

- **Agent One (implementation):** ADR-006 §22.
- **Agent Two (independent verification):** ADR-006 §23.

## Change log

- Architecture entry gate: this file and ADR-006 created by Agent
  Three (Architecture Governor), against baseline
  `a7a6ebc41ea884f7ce4ec2d70da89e6a44097381`. No production code,
  test, fixture, or existing evidence/ADR file changed.

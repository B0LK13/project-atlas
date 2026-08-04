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
- Every workflow action reference is pinned, or the implementation records
  an explicitly approved governed-version policy; no untrusted-fork secret
  exposure; least-privilege permissions.
- Every required branch-protection check maps to a real, previously
  successful job (never a placeholder).
- Dependabot ecosystems exactly match what's actually present
  (`pip`, `github-actions`).
- No existing certified history is rewritten. GitHub rebase merging may
  create new post-rebase commit IDs, so the resulting `main` tip must be
  independently verified before owner closure; the reviewed candidate hash
  is never represented as the post-rebase hash.
- `.session-preservation/` never becomes tracked.
- No secret is introduced.
- Local and remote `main` remain aligned after every phase.
- Every Phase 6 settings claim is independently verified (GitHub
  UI/API evidence), not narrative-only.

## Known limitations (carried from ADR-006 §21)

- Agent Four's read-only platform report is the current factual input for
  Phase 6: classic branch protection is active, no repository or
  organization ruleset applies, required checks are currently empty, and
  the repository has one collaborator (`B0LK13`). Phase 6 must still
  capture fresh settings evidence before activation and must resolve the
  one-approval/one-collaborator administrative lockout before instructing
  an implementation agent to merge.
- GitHub Advanced Security (secret scanning, push protection, private
  vulnerability reporting) is unavailable under the current plan;
  `SECURITY.md`'s disclosure path is a compensating workaround, not an
  equivalent automated control.
- Dependabot scope is limited to the verified `pip` and `github-actions`
  ecosystems. The GitHub-managed `update-pip-graph` check is not a
  Project Atlas quality gate. `atlas-documentation-gate.yml` remains
  manual (`workflow_dispatch` only) unless a later implementation phase
  explicitly adds an automatic trigger or a separate governance check.
- No secondary/offsite backup beyond GitHub + local clone +
  `.session-preservation/` bundles is mandated; recorded only as an
  open recommendation.

## Platform reconciliation amendment (Agent Four, 2026-08-04)

This section is authoritative for the verified platform facts and
supersedes conflicting wording above. It is architecture-only; no GitHub
setting or implementation file is changed by this amendment.

- The current protection mechanism is classic branch protection. No
  repository or organization ruleset is active.
- GitHub currently requires a PR and one approving review, with
  administrator enforcement, while only `B0LK13` is a collaborator. This
  is an operational lockout risk: independent certification does not count
  as a GitHub approval. Before any merge instruction, the owner must add a
  separately authorized reviewer or complete a governed, verified review
  rule transition that the repository can satisfy.
- GitHub rebase merging is the selected normal PR model because merge and
  squash are disabled. It creates new commit IDs, so post-rebase exact-tip
  verification and owner authorization are mandatory; the reviewed branch
  hash must not be presented as the resulting `main` hash.
- No required checks are active. The only project-owned candidate is the
  real `quality` check. `update-pip-graph` is GitHub-managed and is not a
  project quality gate. Activation is staged: successful workflow run,
  exact-name capture, independent verification, then branch-protection
  update and lockout check.
- `atlas-documentation-gate.yml` remains manual (`workflow_dispatch` only)
  and is not an automatic PR/push gate. Any automatic governance check is a
  separate later implementation decision.
- Current tracked actions use `actions/checkout@v4` and
  `actions/setup-python@v5`; implementation must adopt authentic SHA
  pinning or an explicitly governed-version policy, never invented hashes.
- Actions are enabled with all actions allowed and read-default tokens.
  Forking is enabled and cannot be disabled in the reported account setup;
  workflows must therefore avoid `pull_request_target`, secrets on fork PRs,
  and write permissions.
- Hosted secret scanning, push protection, private vulnerability reporting,
  and CodeQL default setup are unavailable. Compensating local/CI scans and
  private disclosure guidance are required, without publishing owner
  contact data without authorization.
- The only verified Dependabot ecosystems are `pip` and `github-actions`.
  Projects are enabled. Existing history has 135 unsigned commits; signing
  adoption is prospective and cannot rewrite history.

### Phase 6 gate correction

Phase 6 is not complete merely because the settings are reported. Agent
Four's platform report is factual input; Agent Two must verify the exact
settings and the owner must resolve the approval lockout before the package
can be considered merge-operable. The documentation gate and
`update-pip-graph` must not be added to required Project Atlas checks.

## Handoff

- **Agent One (implementation):** ADR-006 §22.
- **Agent Two (independent verification):** ADR-006 §23.

## Change log

- Architecture entry gate: this file and ADR-006 created by Agent
  Three (Architecture Governor), against baseline
  `a7a6ebc41ea884f7ce4ec2d70da89e6a44097381`. No production code,
  test, fixture, or existing evidence/ADR file changed.

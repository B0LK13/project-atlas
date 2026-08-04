# ADR-006 — GitHub repository governance baseline

**Status:** accepted for implementation
**Date:** 2026-08-04
**Work package:** AS-GH-001
**Author:** Architecture Governor (entry-gate authorization)

## 1. Problem statement

Project Atlas is now published to an authoritative, private GitHub
repository (`B0LK13/project-atlas`, default branch `main`, tip
`a7a6ebc41ea884f7ce4ec2d70da89e6a44097381`, 135 commits, AS-MVP-001
closed). Until now, all governance (work-package receipts, ADRs,
worklog entries, session-preservation bundles) has been enforced purely
by convention inside this repository's own `docs/` tree and by the
disciplined multi-agent workflow observed across AS-CORE-002 through
AS-MVP-001. None of that discipline is yet expressed as GitHub-native
controls: there is no `CODEOWNERS`, no PR/issue template, no dependency
automation, no documented security-disclosure path, no versioning or
release policy, no commit-signing policy, and no backup/continuity plan
beyond the local working copy and the manually preserved
`.session-preservation/` bundle. A single existing CI workflow
(`.github/workflows/ci.yml`: ruff, mypy, pytest, CLI smoke) and one
on-demand documentation-gate workflow
(`.github/workflows/atlas-documentation-gate.yml`) are the only GitHub
Actions present. There is no top-level `README.md`.

Without a durable, repository-native governance baseline, the
discipline this project has relied on so far (bounded remediation
scope, evidence-only corrections, fast-forward-only merges, explicit
owner authorization, receipt-based provenance) is enforceable only by
the diligence of whichever agent or human is currently working in the
repository — it does not survive a change of contributor, a new clone,
or a GitHub UI-driven merge.

## 2. Current-state assessment

Inspected directly (commit `a7a6ebc41ea884f7ce4ec2d70da89e6a44097381`,
local `main` == remote `main`, confirmed via `git fetch origin main` +
`git diff --exit-code main origin/main` -> zero diff):

| Area | Finding |
|---|---|
| CI | `.github/workflows/ci.yml` runs `ruff check .`, `mypy src`, `pytest`, and an `atlas init`/`atlas version` CLI smoke test, on `push` to `main` and on every `pull_request`. This is the only always-on workflow. |
| Documentation gate | `.github/workflows/atlas-documentation-gate.yml` is `workflow_dispatch`-only; it invokes `atlas-vault-documentation/scripts/atlas_agent.py repository-gate` with an explicit receipt path and changed-file list. It is not wired to run automatically on PR/push. |
| README | None exists at the repository root. |
| CODEOWNERS | Does not exist. |
| PR/issue templates | Do not exist. |
| Dependabot | No `.github/dependabot.yml`. Ecosystems actually present: `pip` (root `pyproject.toml`) and `github-actions` (`.github/workflows/*.yml` use `actions/checkout@v4`, `actions/setup-python@v5`). No `npm`, `docker`, `bundler`, etc. anywhere in the tree. |
| Governance docs | `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SUPPORT.md`, `GOVERNANCE.md`, `VERSIONING.md`, `RELEASING.md` do not exist. |
| Versioning | `pyproject.toml` declares `version = "0.1.0"`; nothing else in the repository references or bumps it. No git tags exist (`git tag` is empty). |
| Commit signing | `git log --show-signature` on the last 20 commits shows no GPG/SSH signatures; the certified AS-MVP-001 history is entirely unsigned. |
| Branch protection / GitHub settings | Agent Four's read-only platform report records classic branch protection, no active ruleset, PR + 1 approval, administrator enforcement, rebase-only merging, no required checks, and the other settings reconciled authoritatively in §24. This architecture commit does not itself modify or independently re-query GitHub settings. |
| Evidence preservation | `.session-preservation/as-mvp-001-b/` (containing `as-mvp-001-b-9161d0b.bundle` and a `patches/` directory) exists on disk, is untracked, and is **not currently excluded by `.gitignore`** — nothing today prevents an incautious `git add -A` from accidentally tracking and pushing it. This is a real, actionable gap this ADR must close. |
| `.gitignore` | Covers Python/build artifacts, `.tmp/`, and local agent/editor state (`.agents/`, `.codex/`, `.claude/`) but not `.session-preservation/`. |
| `pyproject.toml` | `ruff` scope is `include = ["src/**/*.py", "tests/**/*.py"]` (explicitly excludes `atlas-vault-documentation/`, per that sibling deliverable's own tooling); `mypy` targets `packages = ["project_atlas"]`, `strict = true`. These are the real, authoritative lint/type commands — matched verbatim in `ci.yml`. |
| Governed-session control plane | `AGENT-BOOTSTRAP.md` documents a separate, existing `atlas-vault-documentation/scripts/atlas_agent.py` session lifecycle (`bootstrap -> preflight -> session-start -> work milestones -> validation -> completion -> postflight -> receipt -> close`) used for *governed agent* work inside the vault. AS-GH-001 governs the GitHub-facing contribution/review/CI surface and must not duplicate or conflict with that control plane; it may *reference* it from `CONTRIBUTING.md` for agents doing governed work, but GitHub PR review is the enforcement mechanism for human/GitHub-facing contributions. |
| Docs conventions | `docs/adr/ADR-001` through `ADR-005` exist; there is no `docs/work-packages/` directory yet, and no prior AS-xxx package has one — receipts live in `docs/evidence/<PKG>-receipt.yaml`, plans/erratum docs live directly under `docs/<PKG>-*.md`, and `docs/backlog.md` is the single executable backlog (Epics A-K plus a cross-cutting section) with `docs/master-roadmap.md` as the program-level status roll-up. AS-GH-001 introduces `docs/work-packages/` as a new, small registry specifically for architecture/governance packages (this ADR's own directive requested this path); it does not retroactively reorganize existing AS-xxx evidence. |

## 3. Goals

1. Make the discipline this project has already demonstrated by hand
   (bounded scope, evidence-only corrections, fast-forward-only merges,
   explicit authorization, receipt-based provenance) enforceable by
   GitHub itself for every future contributor, not just by convention.
2. Give every future work package a predictable, minimal-friction PR
   surface that captures exactly the fields this project's receipts
   already track (base hash, implementation hash, evidence hash,
   changed paths, test results, known limitations, owner
   authorization) so PR review and the existing receipt convention
   reinforce each other instead of diverging.
3. Close the concrete evidence-preservation gap found during this
   review (`.session-preservation/` not gitignored).
4. Establish real, verifiable CI required-checks mapped 1:1 to jobs
   that actually exist and actually pass today (`ruff`, `mypy`,
   `pytest`, CLI smoke, YAML/duplicate-key validation), plus a small
   number of new, clearly-scoped jobs (workflow-syntax lint,
   `.github/dependabot.yml`) — never a placeholder check.
5. Define a safe, honest private-vulnerability-disclosure path given
   that GitHub's native private reporting is unavailable on the
   current plan.
6. Define a versioning/release policy that distinguishes "work-package
   closure" (this project's existing receipt-driven unit of work) from
   "software release" (a tagged, versioned artifact) — the two are not
   the same thing today and conflating them would be a regression.
7. Propose, but do not force, commit signing and settings changes that
   could lock out the sole maintainer if staged incorrectly.

## 4. Explicit non-goals

- Rewriting, rebasing, squashing, or re-signing any existing commit,
  including all AS-MVP-001 history. The unsigned history up to
  `a7a6ebc...` is accepted permanently as-is.
- Replacing or duplicating the existing `atlas-vault-documentation`
  governed-agent-session control plane. AS-GH-001 governs the
  GitHub-facing human/PR surface; it is a sibling control, not a
  replacement.
- Reorganizing or renaming any existing `docs/evidence/*.yaml`,
  `docs/adr/ADR-00[1-5]-*.md`, `docs/backlog.md`, or
  `docs/master-roadmap.md` structure.
- Enabling GitHub Advanced Security features (secret scanning, push
  protection, private vulnerability reporting) that are unavailable
  under the current account plan. This ADR documents the gap and a
  compensating control instead.
- Adding Dependabot ecosystems that do not exist in this repository
  today (no `npm`, `docker`, `bundler`, `nuget`, etc.).
- Guessing, inferring, or embedding any secret, token, or personal
  contact detail as part of the security-disclosure mechanism.
- Making any GitHub settings change in this architecture phase. This
  ADR specifies *what* should be configured and in *what order*;
  actual GitHub UI/API configuration is Phase 6 of AS-GH-001's
  implementation, executed and verified separately.

## 5. Threat and failure model

| Risk | Mitigation designed here |
|---|---|
| A future contributor (human or agent) pushes directly to `main`, bypassing review. | Branch protection (PR required, 1 approval, admin enforcement) — already reported configured; this ADR's Phase 6 defines the *verification* procedure, since this review could not independently confirm GitHub settings. |
| A required status check is added to branch protection before the corresponding workflow job exists or has ever passed, permanently locking out all PRs. | §13's required-check naming contract: every protected check name must map to a job that has run at least once successfully on this exact repository before protection is turned on (Phase 6, staged activation). |
| `.session-preservation/` (containing a Prototype B git bundle with real, if unmerged, commit history) is accidentally committed and pushed. | Add `.session-preservation/` to `.gitignore` (Phase 1) and a CI check that fails if any tracked path matches it (Phase 3). |
| A PR from an untrusted fork exfiltrates repository secrets via workflow injection (e.g. `pull_request_target` misuse, unpinned third-party actions). | CI workflow permissions kept at least-privilege (`contents: read` unless a job needs more); no `pull_request_target` trigger is introduced; third-party actions pinned to a major version tag from a well-known publisher (`actions/checkout`, `actions/setup-python` — both already in use); no workflow reads secrets on `pull_request` from forks. |
| A security vulnerability is reported publicly (GitHub Issue) because private reporting is unavailable, exposing it before a fix ships. | `SECURITY.md` defines an explicit non-GitHub-native disclosure path (see §Security disclosure workflow) and issue templates route "security or governance gap" reports away from the public bug tracker. |
| Dependabot opens PRs for ecosystems/paths that do not exist, or floods the repo with low-value PRs. | Dependabot config scoped to exactly the two present ecosystems (`pip`, `github-actions`), weekly cadence, grouped updates, capped open-PR count (§Dependency automation). |
| A "release" is claimed without corresponding tagged, tested evidence (mirroring the fabricated-attestation risk this project has repeatedly guarded against at the work-package level). | `RELEASING.md` requires a tag, a green required-check run at the tagged commit, and an explicit release-evidence note; prohibits retroactive/fabricated release claims, mirroring this repository's existing receipt discipline. |
| Backup single point of failure: only the local disk clone and the new GitHub remote exist; no offline/secondary copy policy. | Backup and continuity policy (§Backup and restore strategy) formalizes what already exists (local canonical clone, GitHub remote, `.session-preservation/` bundles) and adds a minimal periodic-bundle recommendation without inventing new infrastructure. |

## 6. Required artifacts

Governance documents (repository root unless noted):

- `README.md` — currently absent; minimal project entry point (what
  Project Atlas is, how to install/run, where to find `AGENTS.md`/
  `CLAUDE.md` for agent-facing detail, link to `CONTRIBUTING.md` and
  `SECURITY.md`).
- `SECURITY.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md` — **explicit decision, not deferred**: this is a
  private, single-maintainer-plus-governed-agents repository, not a
  public open-source project soliciting outside contributions today.
  A generic Code of Conduct would be either vacuous or misleading about
  who it applies to. Decision: **do not add `CODE_OF_CONDUCT.md`**;
  instead, `CONTRIBUTING.md` states the actual contribution boundary
  (governed agents + the repository owner only, no public external
  contribution path today) and that this decision will be revisited if
  the repository's visibility or contribution model changes.
- `SUPPORT.md` — not a separate file; folded into a short "Support and
  scope" section at the end of `CONTRIBUTING.md`, since there is no
  external user base yet distinct from contributors.
- `GOVERNANCE.md`
- `VERSIONING.md`
- `RELEASING.md`

Ownership and review:

- `.github/CODEOWNERS`
- Review policy is specified inside `GOVERNANCE.md` (§Ownership and
  review below), not a separate file — GitHub has no native
  "review-policy" file format beyond branch-protection settings and
  `CODEOWNERS`.

Pull-request infrastructure:

- `.github/pull_request_template.md` (single template; the repository
  has one contribution shape — a governed work-package change — not
  multiple PR "kinds" that would justify the `PULL_REQUEST_TEMPLATE/`
  multi-template directory).

Issue infrastructure:

- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/ISSUE_TEMPLATE/security_or_governance_gap.yml`
- `.github/ISSUE_TEMPLATE/config.yml` (disables blank issues; points
  security reports at `SECURITY.md`'s disclosure path instead of this
  template, per GitHub's own `contact_links` mechanism)

CI:

- New/changed workflow(s) under `.github/workflows/` — see §7. No
  existing workflow file is deleted; `ci.yml` gains jobs, it is not
  replaced.

Dependency automation:

- `.github/dependabot.yml`

Registry/tracking (this package's own artifacts, per this directive):

- `docs/adr/ADR-006-github-repository-governance-baseline.md` (this
  file)
- `docs/work-packages/AS-GH-001.md` (new registry; see §14)

## 7. CI job architecture

Every job below either already exists (unchanged) or maps to a
concrete, already-verified repository command. No command is invented.

Existing, unchanged (`.github/workflows/ci.yml`, job `quality`):

| Job step | Real command | Verified present |
|---|---|---|
| Ruff | `python -m ruff check .` | `pyproject.toml` `[tool.ruff]`, scope `src/**/*.py` + `tests/**/*.py` |
| Mypy | `python -m mypy src` | `pyproject.toml` `[tool.mypy]`, `strict = true` |
| Pytest | `python -m pytest` | `pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]` |
| CLI smoke | `atlas --help`, `atlas version`, `atlas init --output .tmp/atlas-vault --dry-run`, `atlas init --output .tmp/atlas-vault`, then asserts `index.md` and `00-system/vault-charter.md` exist | AT-001 scaffold contract, already in `ci.yml` |

New jobs proposed (Phase 3), each added to the **same** `quality` job
or as additional jobs in `ci.yml` — not a new workflow file, to keep
one required-check surface:

| New job/step | Real command | Rationale |
|---|---|---|
| Control-plane tests | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider atlas-vault-documentation/tests --tb=short -q` | Currently exercised manually by agents every work package (146 tests, per WORKLOG.md); never run in CI today — a real gap, not an invented one, since the command is copy-pasted verbatim from every governed session's WORKLOG entry. |
| Python compile validation | `python -m compileall -q src atlas-vault-documentation` | Already run manually every work package per WORKLOG.md; trivial to add, catches syntax errors mypy's import resolution might miss on unreachable modules. |
| YAML validation (schema-agnostic) | `python -c "import yaml,glob,sys; [yaml.safe_load(open(p)) for p in glob.glob('docs/evidence/*.yaml') + glob.glob('.github/**/*.yml', recursive=True)]"` | Confirms every evidence receipt and every workflow/template YAML file is at least syntactically valid YAML. |
| Duplicate-key-sensitive YAML check | Reuse the exact duplicate-key-sensitive loader pattern already used by every AS-MVP-001 evidence-correction commit (`yaml.SafeLoader` subclass overriding the mapping constructor to raise on repeated keys), applied to `docs/evidence/*.yaml` | This project has independently re-derived this exact check by hand at least six times during AS-MVP-001; it belongs in CI, not human memory. |
| Workflow syntax check | `actionlint` (pinned third-party action, `rhysd/actionlint`) *or*, if a fully self-hosted-only check is preferred, `python -m yaml` parse of every `.github/workflows/*.yml` (already covered by the YAML validation step above) plus a minimal "every `uses:` entry is pinned to a tag or SHA" grep | Recommendation: adopt `actionlint` in Phase 3 if third-party actions are acceptable per repository policy (they already are — `actions/checkout`, `actions/setup-python` are in use); otherwise the grep-based fallback is sufficient and introduces zero new external dependencies. |
| Determinism/governance check already present | No dedicated CI job proposed beyond what pytest already covers: `tests/integration/test_as_mvp_001_release_closure.py::test_k005_settled_rebuild_is_byte_identical_to_golden_state` and the AS-SEC-001/fuzz suites already assert determinism and are already part of `python -m pytest`. Adding a second, separate "determinism job" would duplicate coverage `pytest` already provides. |

Documentation gate (`atlas-documentation-gate.yml`): left
`workflow_dispatch`-only, unchanged. It requires a receipt path
supplied by a governed agent session and is not a suitable
always-on PR gate (it has no meaning without a receipt argument).

## 8. Required-check naming contract

A required status check's *name*, as it will appear in GitHub branch
protection, must be the literal `<workflow name> / <job name>` string
GitHub reports after the workflow has run at least once. Concretely,
for the existing and proposed jobs above (workflow file `ci.yml`,
`name: ci`, single job `quality`):

- Required check name: `quality`

If Phase 3 splits `quality` into multiple jobs (e.g. `quality` and a
new `control-plane` job) for parallelism, each job's required-check
name must be recorded here **after** it has run successfully at least
once — this ADR does not pre-declare a check name for a job that has
not yet executed, per §12's "no placeholder required checks" rule.
Phase 6's staged activation procedure (§17) is the only place actual
required-check names get added to branch protection, and only after
each has been observed passing.

## 9. Branch and merge policy

Formalizes what the Project Owner reported as already configured,
pending Phase 6 independent verification (§17):

- Default branch: `main`.
- Direct pushes to `main` disallowed for everyone including
  administrators once enforcement is verified active (admin
  enforcement reported enabled).
- Every change lands via pull request, minimum 1 approval, stale
  approvals dismissed on new pushes, conversation resolution required.
- Linear history required; **rebase merge only** — merge commits and
  squash merges disabled. GitHub rebase merging produces new commit IDs;
  it does not preserve the exact reviewed candidate hash. Therefore the
  final post-rebase `main` tip, not the pre-merge PR tip, must receive the
  final independent verification and owner authorization recorded by the
  release gate.
- Force-push and branch deletion disabled on `main`.
- Feature/work-package branches follow the existing repository
  convention observed throughout AS-MVP-001:
  `<type>/<AS-xxx-id>-<short-description>` (e.g.
  `fix/as-mvp-001-r1-relation-edge-tests`). `GOVERNANCE.md` codifies
  this naming convention; it is not new, only newly written down.
- Source branches are retained after merge by default (mirroring this
  project's explicit "retain for audit provenance" practice throughout
  AS-MVP-001); auto-delete-branches stays disabled, matching the
  Project Owner's reported setting.

## 10. Contribution workflow

`CONTRIBUTING.md` codifies the workflow this repository has already
executed by hand, mapped onto GitHub PRs:

1. Open or reference a tracking issue/work-package ID (`AS-xxx`).
2. Branch from `main`: `<type>/<AS-xxx-id>-<short-description>`.
3. Implement with the existing bounded-scope discipline: test-first
   where practical, minimal production changes, evidence-only changes
   kept separate from behavioral changes in their own commits (as
   AS-MVP-001-R1's `test(...)` / `fix(...)` / `docs(evidence): ...`
   commit sequencing already demonstrates).
4. Run the real local commands from `AGENTS.md`/`CLAUDE.md` (`pytest`,
   `ruff check .`, `mypy src`) before opening a PR.
5. Open a PR using `.github/pull_request_template.md`; fill in every
   field (§Pull-request infrastructure in the directive: work-package
   ID, base hash, implementation hash, evidence hash, changed paths,
   test results, security impact, documentation impact, rollback
   considerations, known limitations, reviewer certification, owner
   authorization, prohibited history operations acknowledgement).
6. Wait for the `quality` required check and at least one
   approval; resolve all review conversations.
7. Merge via **rebase merge** only (§9). Do not use the GitHub UI's
   "Squash and merge" or "Create a merge commit" options — they are
   disabled by branch protection once Phase 6 is active, but
   `CONTRIBUTING.md` states the expectation explicitly regardless.
8. For governed-agent sessions specifically, `CONTRIBUTING.md`
   references (not duplicates) `AGENT-BOOTSTRAP.md`'s existing
   `atlas_agent.py` session lifecycle as the *internal* discipline that
   should already have produced the receipt referenced in step 5's PR
   description.

Given this is currently a private, single-owner-plus-governed-agents
repository (§6's `CODE_OF_CONDUCT.md` decision), `CONTRIBUTING.md`
states plainly that there is no public external contribution path
today, and that this document describes the internal workflow for the
repository owner and any explicitly authorized agents.

## 11. Security disclosure workflow

`SECURITY.md` must define a disclosure path that does not depend on
GitHub's private vulnerability reporting (confirmed unavailable) and
does not embed a secret or personal credential. Design:

- **Supported versions:** `main` only (pre-1.0, no maintained release
  branches yet — consistent with §Versioning and release policy).
- **Private disclosure mechanism:** a GitHub Issue is **not** used for
  suspected vulnerabilities. Instead, `SECURITY.md` directs reporters
  to open a *minimal, non-descriptive* placeholder issue using the
  `security_or_governance_gap` template (title only, e.g. "Security
  report — see contact instructions", no vulnerability detail in the
  issue body) and states that the repository owner will follow up
  through a private channel once contacted. This avoids requiring any
  embedded email address or secret in the repository while still
  giving reporters an unambiguous, discoverable first step. If/when
  GitHub Advanced Security's private vulnerability reporting becomes
  available on this repository's plan, `SECURITY.md` should be updated
  to point at it directly and this placeholder-issue workaround
  retired — recorded here as a tracked follow-up, not implemented now.
- **Response-time expectations:** `SECURITY.md` explicitly states this
  is a best-effort, single-maintainer project and does **not** commit
  to an SLA, per this ADR's own instruction not to promise a guarantee
  that isn't operationally supported.
- **Non-public handling:** confirmed vulnerabilities are fixed on a
  private branch or a minimally-scoped PR before public disclosure of
  exploit details; the existing receipt/evidence convention
  (`docs/evidence/AS-SEC-xxx-receipt.yaml`) is reused for the fix's own
  evidence trail, exactly as `AS-SEC-001` already did for the
  prompt-injection/quarantine boundary.
- **Scope exclusions:** issues in `atlas-vault-documentation/`'s own
  sibling tooling are in scope but should reference that its build/test
  tooling is separate; findings against the reader's own third-party
  dependencies (not this repository's code) should be reported
  upstream first.

## 12. Dependency-update policy

Ecosystems actually present in this repository today:

- `pip` — root `pyproject.toml` (production deps: `pydantic`, `PyYAML`,
  `jsonschema`; dev deps: `pytest`, `ruff`, `mypy`, `types-PyYAML`).
  `atlas-vault-documentation/` has its own tooling per `CLAUDE.md`/
  `AGENTS.md` but was not found to declare a separate
  `pyproject.toml`/`requirements.txt` during this review; if one
  exists it should get its own Dependabot entry in Phase 4's
  implementation, verified against the actual file, not assumed here.
- `github-actions` — `.github/workflows/*.yml` (`actions/checkout@v4`,
  `actions/setup-python@v5`).

No other ecosystem (`npm`, `docker`, `composer`, `bundler`, `gomod`,
`nuget`, `cargo`, etc.) exists anywhere in this repository; none is
added.

`.github/dependabot.yml` design:

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      python-dependencies:
        patterns: ["*"]
    open-pull-requests-limit: 5
    labels: ["dependencies", "python"]
    reviewers: ["B0LK13"]
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      actions-dependencies:
        patterns: ["*"]
    open-pull-requests-limit: 3
    labels: ["dependencies", "github-actions"]
    reviewers: ["B0LK13"]
```

- **Cadence:** weekly (not daily) — this is a low-churn, small
  dependency surface; daily checks would add PR noise without benefit.
- **Grouping:** one group per ecosystem, so a week's updates arrive as
  a single PR per ecosystem rather than one PR per package.
- **Max open PRs:** capped (5 for pip, 3 for actions) to bound review
  burden.
- **Labels/reviewers:** labeled for triage; reviewer defaults to the
  repository owner (`B0LK13`) since there is no other maintainer today
  — `GOVERNANCE.md` should be updated if/when that changes.
- **Version-update policy:** Dependabot's default (respects existing
  version constraints in `pyproject.toml`; does not bump
  `requires-python`).
- **Security-update interaction:** Dependabot security updates operate
  independently of this scheduled config and are already implicitly
  enabled once Dependabot is enabled at all on the repository (GitHub
  default) — no separate configuration is required for that half, only
  confirmation in Phase 6 that "Dependabot alerts" and "Dependabot
  security updates" are toggled on in repository settings (the Project
  Owner reported these already enabled).

## 13. Versioning and release policy

`VERSIONING.md`:

- Project Atlas adopts **Semantic Versioning** (`MAJOR.MINOR.PATCH`)
  starting from the current `pyproject.toml` value, `0.1.0`, once the
  first tagged release is cut (see below). Pre-1.0, minor version bumps
  may include breaking changes to the CLI or OKF schema, consistent
  with SemVer's own pre-1.0 convention; this must be called out in that
  release's notes.
- **Work-package closure is not a software release.** An AS-xxx work
  package (e.g. AS-MVP-001) closing means its own acceptance criteria
  and evidence are certified and merged to `main` — it does not by
  itself imply a new version tag, changelog entry, or published
  artifact. Conflating the two was an implicit risk in this project's
  history (multiple work packages merged to `main` with no
  corresponding version bump); `VERSIONING.md` makes the distinction
  explicit going forward.

`RELEASING.md`:

- **Tag format:** `v<MAJOR>.<MINOR>.<PATCH>` (e.g. `v0.2.0`), applied
  only to a commit on `main` that has an all-green `quality`
  required-check run recorded against that exact commit SHA.
- **Release-branch policy:** none maintained pre-1.0; all releases are
  tagged directly on `main`. Revisit if/when a maintenance-branch model
  becomes necessary post-1.0.
- **Changelog policy:** a `CHANGELOG.md` entry per tagged release,
  summarizing merged work packages/PRs since the previous tag by their
  real PR numbers and AS-xxx IDs — never a narrative summary invented
  without linking to the actual merged PRs.
- **Release-evidence requirements:** the release commit's message or
  an accompanying `docs/evidence/RELEASE-v<version>.yaml` records the
  tagged SHA, the required-check run URL/ID, and the list of AS-xxx
  work packages included — mirroring this project's existing receipt
  discipline, applied one level up (release, not work-package).
- **Explicit prohibition:** no release may be described as complete,
  tagged, or published without the tag actually existing on the
  authoritative remote and the required check actually having passed
  at that SHA — mirroring this ADR's own review discipline (never
  claim remote state without independently verifying it, as this
  review did for `origin/main` before treating AS-MVP-001 as closed).

## 14. Commit-signing adoption strategy

- **Existing history:** all 135 commits through
  `a7a6ebc41ea884f7ce4ec2d70da89e6a44097381` are unsigned and remain
  permanently unsigned. No retroactive signing, no history rewrite.
- **Adoption point:** signing becomes *recommended* starting
  immediately (Phase 5) and *required* only once (a) the repository
  owner has configured a working signing key (SSH or GPG) locally and
  verified `git log --show-signature` produces a `Good signature` on a
  test commit, and (b) branch protection's "Require signed commits"
  setting has been staged and verified not to lock out the sole
  maintainer's current signing setup (§12's lockout-prevention rule).
  Until both are true, signing stays recommended-only.
- **Recommended mechanism:** SSH signing (`git config gpg.format ssh`,
  `git config user.signingkey <path-to-existing-SSH-key>`) is
  preferred over GPG for a solo/small-team maintainer, since it reuses
  the SSH key already required for repository push access rather than
  provisioning a separate GPG keypair. GPG remains supported for any
  contributor who prefers it.
- **Repository-rule implications:** enabling "Require signed commits"
  on `main` before every active contributor has a working signing
  setup would block all future PR merges (rebase-merge preserves each
  commit's original signature or lack thereof, so an unsigned commit
  in a PR blocks the merge once the rule is active). §17's staged
  activation defers this specific setting to *after* a dry run confirms
  signed commits merge successfully with rebase-merge.

## 15. Backup and restore strategy

Formalizes existing practice rather than inventing new infrastructure:

- **Local canonical clone:** `/mnt/d/project-atlas-vault` (this
  checkout) remains the working canonical clone.
- **GitHub authoritative remote:** `B0LK13/project-atlas`
  (`https://github.com/B0LK13/project-atlas.git`), private, now holds
  an identical `main` (independently verified, §Current-state
  assessment).
- **Periodic Git bundles:** recommend a `git bundle create
  <date>-main.bundle main` snapshot taken at each tagged release (not
  every commit) stored alongside the existing
  `.session-preservation/as-mvp-001-b/` convention, i.e. under a
  `.session-preservation/<AS-xxx-or-release-id>/` directory,
  gitignored (§6/§17), reusing the exact pattern already established
  for the Prototype B bundle rather than inventing a new location.
- **Mirror/secondary backup:** out of scope to mandate in this ADR
  (would require infrastructure decisions — a second git host, cloud
  storage, etc. — beyond what evidence supports today); recorded as an
  open recommendation for a future, separate infrastructure package if
  the Project Owner decides continuity risk warrants it.
- **Branch and tag coverage:** bundles should include `--all` refs
  (branches and tags), not just `main`, so retained feature branches
  like `fix/as-mvp-001-r1-relation-edge-tests` are recoverable even if
  deleted later.
- **Evidence retention:** `docs/evidence/*.yaml`,
  `docs/architecture-governance/*.md`, and this ADR are version
  controlled and thus already covered by the GitHub remote itself;
  `.session-preservation/*` bundles are the only artifacts requiring a
  *separate* backup path since they are intentionally untracked.
- **Restore verification:** a restore drill (clone from a bundle into
  a disposable directory, verify `git log`/`git diff` against the
  known-good SHA) should be performed once per release at minimum —
  the exact procedure already used throughout AS-MVP-001's independent
  verifications (`git clone --no-local` into `/tmp/...`) is the
  reusable template.
- **Secret-safe storage:** no bundle or backup may ever contain a
  secret; this is already enforced indirectly by the fact that bundles
  are `git bundle`s of the same repository content already scanned by
  this project's own `secrets.py`/AS-SEC-001 quarantine boundary before
  it ever reaches canonical state.
- **Disaster-recovery ownership:** the repository owner (`B0LK13`) is
  the sole named owner of backup/restore responsibility until
  `GOVERNANCE.md` names an additional maintainer.

## 16. Evidence and provenance

A remote-compatible evidence model, extending (not replacing) this
project's existing per-work-package `docs/evidence/<PKG>-receipt.yaml`
convention:

- **Implementation receipts:** unchanged — `docs/evidence/<PKG>-receipt.yaml`,
  now additionally linked from the PR template's "evidence hash" field
  so a reviewer can jump from the PR straight to the receipt commit.
- **Independent verification reports:** unchanged — recorded either
  inline in the receipt (as AS-MVP-001 did throughout) or as a
  dedicated `docs/architecture-governance/VERIFY-<PKG>-*.md`, per the
  existing convention (`VERIFY-AS-RET-SEQUENCING-DECISION.md`).
- **Owner authorization:** for a GitHub-hosted repository, this is now
  the PR's own approval + the "owner authorization" checkbox in the PR
  template, replacing (not duplicating) the free-text
  "NEXT_AGENT_DIRECTIVE" authorization pattern used throughout this
  project's pre-GitHub history. Future work packages should record
  authorization as a real GitHub approval, not a narrative statement.
- **Merge completion / remote publication / closure:** for a
  GitHub-hosted repository, this is the PR's own merge event
  (timestamp, merging actor, resulting SHA) — already fully captured
  by GitHub natively; no separate closure commit is needed purely to
  record that a merge happened (mirroring the Project Owner's own
  instruction earlier in this project's history not to create a commit
  solely to record that a merge occurred).
- **Known limitations / superseded evidence:** unchanged — recorded in
  the receipt's `known_limitations`, exactly as AS-MVP-001's receipt
  already does for the `_promote()` cross-file-atomicity and
  multi-batch-manifest limitations.
- **Preservation bundles:** `.session-preservation/<AS-xxx>/*.bundle`,
  gitignored, referenced by path and SHA-256 from the relevant receipt
  (exactly as AS-MVP-001's receipt already references the Prototype B
  bundle) — never committed, never attached to a GitHub Release asset
  without a separate, explicit evidence-retention decision (per this
  directive's own constraint).

## 17. Implementation phases

Per the directive's suggested structure, adapted where repository
evidence supports a difference:

**Phase 1 — Governance and contributor documents.** `README.md`,
`SECURITY.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `VERSIONING.md`,
`RELEASING.md`; the explicit "no `CODE_OF_CONDUCT.md`" decision
recorded in `CONTRIBUTING.md`; add `.session-preservation/` to
`.gitignore`. Lowest risk, no CI or settings changes, closes the one
concrete gap (`.gitignore`) found during this review.

**Phase 2 — PR, issue, ownership, and review templates.**
`.github/CODEOWNERS`, `.github/pull_request_template.md`,
`.github/ISSUE_TEMPLATE/*.yml` (four files). No CI changes.

**Phase 3 — CI workflow baseline.** Extend `ci.yml` with the
control-plane test job, `compileall`, YAML validation, and
duplicate-key check (§7); add a CI check for accidentally-tracked
`.session-preservation/` paths. Every job must run and be observed
passing on a real PR before Phase 6 references its check name.

**Phase 4 — Dependency and security automation.**
`.github/dependabot.yml` (§12). Verify Dependabot alerts/security
updates are enabled in repository settings (verification only in this
phase; the toggle itself is a repository setting, reported already on
by the Project Owner).

**Phase 5 — Release, signing, backup, and evidence policies.**
No new files beyond what Phase 1 already created (`VERSIONING.md`/
`RELEASING.md`); this phase is about *exercising* those policies for
the first time — cutting the first tag (e.g. `v0.1.0` matching the
existing `pyproject.toml` version, or `v0.2.0` if a version bump is
warranted by work merged since `a7a6ebc`), and recommending (not yet
requiring) commit signing per §14.

**Phase 6 — GitHub settings and required-check activation.**
Independently verify (via GitHub UI/API, not narrative claim) every
branch-protection and security setting the Project Owner reported in
§Current-state assessment as already configured, before treating them
as certified. Stage required-status-check activation strictly after
Phase 3's new jobs have each passed at least once (§8/§12's
lockout-prevention rule). Only after this phase may `main`'s protection
be considered independently verified rather than owner-reported.

**Phase 7 — Independent verification and closure.** Agent Two
(or equivalent) independently re-verifies every acceptance criterion in
§18 against the actual repository and GitHub state, exactly as every
prior AS-xxx package in this project has been independently
re-verified before closure.

## 18. Acceptance criteria

Objective, independently checkable per the directive's requirements:

1. `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`,
   `VERSIONING.md`, `RELEASING.md` exist and each contains the
   sections specified in §6-§16 above (checked by section-heading
   grep, not just file existence).
2. `.github/CODEOWNERS` parses under GitHub's own CODEOWNERS syntax
   rules (no unknown user/team references; validated via
   `gh api repos/:owner/:repo/codeowners/errors` if `gh` CLI access is
   available, otherwise via manual syntax review against GitHub's
   documented grammar).
3. `.github/pull_request_template.md` and every
   `.github/ISSUE_TEMPLATE/*.yml` parse as valid YAML/Markdown and
   every YAML template validates against GitHub's issue-forms schema
   (`name`, `description`, `body` required top-level keys).
4. Every `.github/**/*.yml` and `docs/evidence/*.yaml` file parses with
   zero duplicate keys under the duplicate-key-sensitive loader (§7).
5. Every `uses:` line in every workflow under `.github/workflows/`
   references a pinned tag or SHA of a publicly known action
   (`actions/checkout`, `actions/setup-python`, and any newly added
   action such as `actionlint`), not `@main`/`@master`/unpinned.
6. No workflow triggered by `pull_request` from a fork has `secrets:`
   access beyond the default `GITHUB_TOKEN`, and that token's
   `permissions:` block is the minimum the job needs (verified by
   reading each workflow file, not assumed).
7. Every required branch-protection check name corresponds to a real
   job that has completed successfully at least once, verified by
   cross-referencing the exact check name against the Actions run
   history for that workflow (Phase 6/7).
8. `.github/dependabot.yml`'s `package-ecosystem` values are exactly
   `pip` and `github-actions`, matching the ecosystems independently
   confirmed present in §12 — no other ecosystem appears.
9. `git log a7a6ebc..HEAD` (or the equivalent range once implementation
   lands) contains no `rebase`, `filter-branch`, `commit --amend` on
   any pre-existing commit, or force-push evidence; `main` remains a
   strict descendant of `a7a6ebc41ea884f7ce4ec2d70da89e6a44097381`
   (`git merge-base --is-ancestor a7a6ebc HEAD` exits 0).
10. `.session-preservation/` remains untracked
    (`git ls-files .session-preservation/` returns empty) after every
    phase, and is present in `.gitignore`.
11. No secret-shaped string (reusing this project's own
    `secrets.py` patterns as a sanity check, run manually since
    `secrets.py` is not currently wired into a generic file scanner) is
    introduced by any new file.
12. `git rev-parse main` and `git rev-parse origin/main` are equal
    after every phase's push (the exact check this review already
    performed for AS-MVP-001's own closure).
13. Every GitHub settings change proposed for Phase 6 is verified via
    an independent read of the actual setting (GitHub UI screenshot,
    API response, or `gh api` output attached to that phase's
    evidence) — never asserted from memory of what was "supposed to"
    be configured.

## 19. Verification plan

Mirrors this project's existing two-agent (implementer / independent
verifier) discipline:

1. Agent One implements each phase in its own PR (or a small number of
   tightly-related PRs per phase), referencing this ADR and
   `docs/work-packages/AS-GH-001.md`.
2. Each PR's own CI run (`quality` plus any Phase-3-added jobs)
   must pass before merge — this is the *first* real proof a given
   job/check exists and works, satisfying §8's naming-contract
   precondition for later phases.
3. Agent Two (or an equivalent independent reviewer) re-verifies, per
   phase, the specific acceptance criteria in §18 relevant to that
   phase — using the same fresh-clone/detached-HEAD discipline already
   used for every AS-MVP-001 verification, plus, for Phase 6 only,
   direct GitHub UI/API inspection (not narrative trust) of settings.
4. Phase 6 and 7 are not started until Phases 1-5's artifacts exist and
   have each individually passed their own PR's CI.
5. Final AS-GH-001 closure requires an explicit Project Owner
   authorization statement, exactly mirroring AS-MVP-001's closure
   pattern, referencing the exact final commit SHA and, for Phase 6,
   the verified settings snapshot.

## 20. Rollback and recovery plan

- Every phase is implemented as an independent, revertible PR; if a
  phase's change proves wrong (e.g. a CI job is flaky, a required check
  blocks legitimate merges), `git revert` on `main` via a normal PR is
  the recovery path — no force-push, no history rewrite, no direct
  push to `main`.
- Branch-protection settings changes (Phase 6) are staged one setting
  at a time with a rollback note in that phase's evidence recording the
  exact prior setting value, so any single setting can be reverted via
  the GitHub UI without needing to touch git history at all.
- If a newly required check locks out legitimate merges (the exact
  failure mode §5's threat model calls out), the immediate recovery is
  to remove that specific check from branch protection (a settings
  change, not a code change) while the underlying job is fixed in a
  normal PR — never to disable branch protection wholesale as a
  workaround.
- The `.session-preservation/` bundle and any periodic release bundles
  are the disaster-recovery path if both the local clone and GitHub
  remote were somehow lost simultaneously; §15's restore-drill
  requirement exists specifically to keep this path proven, not just
  assumed.

## 21. Known limitations

- Agent Four's read-only platform report is the current factual input for
  the settings listed in §24. Agent Two must still independently verify the
  exact settings during Phase 6 before treating them as certified, and this
  architecture amendment did not change any setting.
- GitHub Advanced Security (secret scanning, push protection, private
  vulnerability reporting) and CodeQL default setup are unavailable under
  the current plan; the compensating `SECURITY.md` disclosure path (§11),
  local scanning, and future repository-owned CI checks are workarounds,
  not substitutes with equivalent hosted coverage.
- Commit signing is not required for any existing or near-term commit;
  the entire certified history through `a7a6ebc...` remains unsigned
  permanently.
- No secondary/offsite backup beyond GitHub + local clone +
  `.session-preservation/` bundles is mandated by this ADR; it is
  recorded as an open recommendation only.
- Whether `atlas-vault-documentation/` has its own separate dependency
  manifest requiring its own Dependabot entry was not conclusively
  determined during this review and must be verified with a real
  `find`/`ls` against that directory before Phase 4 implementation,
  not assumed from this ADR alone.
- No `docs/work-packages/` directory existed before this package; its
  introduction here is additive and does not imply any retroactive
  reorganization of `AS-001` through `AS-MVP-001`'s existing
  `docs/evidence/`-based provenance.

## 22. Agent One handoff

Implement Phases 1-5 (and, once GitHub UI/API access is available to
the implementing agent, Phase 6) exactly as specified in §6-§17, in the
phase order given, each phase as its own reviewable PR against `main`,
referencing this ADR and `docs/work-packages/AS-GH-001.md`. Do not
implement Phase 6's actual settings changes without first confirming,
via direct GitHub inspection, the *current* actual state of each
setting (not the Project-Owner-reported state) — this ADR explicitly
did not verify those settings and Agent One must not assume this ADR's
"reported" table is itself verified fact. No source, test, fixture, or
existing `docs/evidence/*.yaml`/`docs/adr/ADR-00[1-5]*.md` file may be
modified by this work package. `main` must remain a fast-forward-only
descendant of `a7a6ebc41ea884f7ce4ec2d70da89e6a44097381` throughout.

## 23. Agent Two independent-verification handoff

For each phase's PR, independently reproduce §18's acceptance criteria
relevant to that phase, using a fresh clone/detached-HEAD (never the
implementer's own worktree), before approving. For Phase 6
specifically, independently read the actual GitHub settings (do not
accept a narrative claim, exactly as this review declined to accept
this package's own initiating "remote release completed" claim without
independently running `git fetch`/`git diff --exit-code` first). Final
AS-GH-001 closure requires Agent Two's explicit
"AS-GH-001 INDEPENDENT VERIFICATION PASSED" disposition referencing
the exact final commit SHA and, for every settings-affecting phase, the
specific GitHub API/UI evidence consulted.

## 24. Platform reconciliation amendment (Agent Four, 2026-08-04)

This section is authoritative for the verified GitHub platform facts and
supersedes any earlier candidate wording that conflicts with it. It does
not claim that GitHub settings were changed by this architecture package.

### Verified current state

- Classic branch protection is active on `main`; no repository ruleset and
  no organization ruleset applies.
- Merge commits and squash merging are disabled; rebase merging is enabled.
- Pull requests and one approving review are required, stale approvals are
  dismissed, conversation resolution is required, and administrator
  enforcement is enabled. The only collaborator is `B0LK13`, so the
  current configuration is operationally unable to provide an independent
  GitHub approval for the repository owner. This is a release-blocking
  configuration condition, not an assumption that Agent Two or Agent Four
  has GitHub approval rights.
- No required status checks are currently configured. The project-owned
  check is `quality`; `update-pip-graph` is a GitHub-managed dependency
  graph check and is not a Project Atlas quality gate.
- `atlas-documentation-gate.yml` is `workflow_dispatch`-only and has no
  current automatic PR/push check run. It remains manual; an automatic
  governance check requires a later implementation decision.
- Tracked workflows are `ci.yml` and `atlas-documentation-gate.yml`.
  `dynamic/dependabot/update-graph` is GitHub-managed and must not be
  recreated or edited as a repository file.
- Tracked action references currently use floating major versions
  (`actions/checkout@v4` and `actions/setup-python@v5`). The target policy
  is immutable SHA pinning, or an explicitly documented governed-version
  policy if authentic upstream SHAs cannot yet be adopted. No SHA may be
  invented.
- Actions are enabled, all actions are currently allowed, the default
  `GITHUB_TOKEN` permission is read, and the token cannot approve PRs.
- Forking is enabled and cannot be disabled in the reported personal-account
  configuration. GitHub secret scanning, push protection, private
  vulnerability reporting, and CodeQL default setup are unavailable.
- Projects are enabled. The real dependency ecosystems are only `pip` and
  GitHub Actions.
- The existing history contains 135 unsigned commits and signed-commit
  enforcement is disabled.

### Binding governance decisions

1. **Merge model: certified PR rebase (Model A).** The current platform
   configuration requires a PR and enables rebase merging. A GitHub rebase
   merge creates a new commit ID even when it preserves individual commits;
   it is therefore not an exact-hash merge. Agent Two must certify the
   post-rebase result, and the owner must record both the reviewed PR tip
   and the resulting `main` tip before closure. A local fast-forward is not
   the normal route while the current PR/admin rules remain active.
2. **Approval lockout resolution.** No implementation agent may be told to
   merge while one approving review and one collaborator remain configured.
   The owner must first add a separately authorized GitHub reviewer, or
   execute and verify a governed transition to a review rule that the
   repository can actually satisfy. External independent certification is
   not a GitHub approving review.
3. **Required-check activation.** Run the implementation workflow on a
   published candidate, capture the exact successful check name `quality`,
   independently verify it, and only then add that exact name to classic
   branch protection. Do not require `update-pip-graph`, and do not require
   the manual documentation gate. Recheck that the repository remains
   mergeable after activation.
4. **Rulesets.** No ruleset is current. A future ruleset is permissible
   only as an explicitly additive migration with conflict analysis,
   retention/removal of classic protection decided first, and independent
   verification; it is not an implementation assumption.
5. **Action supply chain.** Agent One must either pin every action to an
   authentic upstream commit SHA with a release-tag comment and reviewed
   ownership check, or document the governed major-version policy and its
   review/update controls. Existing floating references are current state,
   not evidence of compliance with SHA pinning.
6. **Security and forks.** Until unavailable hosted controls change, use
   local and CI secret detection, manual pre-publication review, and the
   private disclosure route defined by `SECURITY.md`. Workflows use
   `contents: read` by default, never use `pull_request_target` for
   untrusted code execution, do not expose secrets to fork PRs, and use
   only synthetic fixtures in security checks. No personal contact address
   is to be added without owner authorization.
7. **Signing.** Signing adoption is prospective. Run a dry-run with the
   owner, ordinary contributors, GitHub-generated commits, and Dependabot
   before considering signed-commit enforcement. Existing unsigned history
   is never rewritten, and enforcement remains disabled until the recovery
   path is independently proven.

The platform facts above are split deliberately: repository-derived facts
come from tracked files and commands; current GitHub settings are Agent
Four's read-only platform report; recommendations are the binding decisions
for later implementation. No GitHub setting, workflow, or repository file
was changed by this amendment.

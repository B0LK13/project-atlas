# 11 — Handoff and Claim Boundaries

**Continuation session:** `AS-20260903T132018Z-claude-design-continuation-20260903-project-atlas-60ba98bb`
**Predecessor session:** `AS-20260903T124744Z-generic-project-atlas-ad915d6d`
**Continuation reason:** `CODEX_EXECUTION_LIMIT_REACHED`
**Capability level:** 2 (`governed-implementation`) — Level 3 supervision authority **not** granted or exercised
**Worktree:** `D:\project-atlas-vault-design` (isolated; the shared dirty checkout at `D:\project-atlas` was not touched)
**Branch:** `design/atlas-product-experience-system`
**Base:** `origin/main` @ `7cb927f7a56e4fc0b137447511d89b5121d2dd14`

---

## 1. What was recovered from Codex, and what was not

The handoff narrative described three specialist lanes as `RUNNING / DISPATCHED`. Direct
inspection of durable state gives a different and more limited picture, and repository
truth outranks the narrative.

| Artefact | Finding |
|---|---|
| Codex worktree | **FOUND**, clean, `b77267bc` — which *was the merge-base with `origin/main`* |
| Codex commits | **ZERO.** `git log origin/main..HEAD` was empty; the tree was unmodified |
| Uncommitted work | **NONE** — `git status --porcelain` returned 0 lines |
| Stashes / reflog | No design-lane entries; reflog held only a `reset: moving to HEAD` |
| Spool | Found at `.atlas-spool` **inside** the worktree (not the sibling path in the brief) |
| Governed sessions | 4 registered: 1 lane + 3 specialist |
| Session contents | Every one: `session-start` event only; `normalized: 0, routed: 0, verified: 0`; every evidence field literally `"Not recorded."` |

### Specialist lane classification

| Lane | Session | Classification |
|---|---|---|
| Market / visual research | `AS-20260903T124913Z-codex-market-research-…` | **NOT_RECOVERABLE** |
| Live surface inventory | `AS-20260903T124911Z-codex-surface-audit-…` | **NOT_RECOVERABLE** |
| Accessibility / form research | `AS-20260903T124919Z-accessibility-form-research-…` | **NOT_RECOVERABLE** |

All three registered a governed session and recorded no findings. The durable Codex
contribution is therefore: **governance bootstrap and four registered sessions.** That was
consumed — the adapters were verified rather than regenerated (`doctor` returned
`adapters: PASS`), so no work was repeated as ritual.

The checkpoint's *narrative* findings were independently re-derived and are reconciled in
`00-SURFACE-AUDIT.md` §1. All held; two were sharpened (CLI 5,855 lines not 2,711 — the
2,711 figure is the parser function; "very broad" quantified as 67 top-level commands with
**zero** argument groups).

One correction to the brief: `MAIN_MOVED_SINCE_CODEX = YES`. Codex's base was 7 commits
behind `origin/main`. The design worktree was fast-forwarded; none of the 7 commits touched
`apps/web`, so the lane was unaffected.

## 2. What was delivered

### IMPLEMENTED (code, tested, in this branch)

| Item | Files |
|---|---|
| 13-state truth vocabulary with invariants as defaults | `apps/web/src/lib/truthState.ts` |
| `TruthChip` — glyph + label, non-interactive | `apps/web/src/components/TruthChip.tsx` |
| Live regions for SC 4.1.3, permanently mounted | `apps/web/src/components/TruthAnnouncer.tsx`, `src/lib/announce.ts` |
| Contrast-verified tokens, light + dark | `apps/web/src/tokens.css` |
| Announcement wiring on the real LIVE→DEMO path | `apps/web/src/hooks/useReadStatus.ts` |
| `ReadStatusPanel` migrated onto the chip system | `apps/web/src/components/ReadStatusPanel.tsx` |
| Automated spec verification (91 checks) | `apps/web/scripts/test-truth-state.mjs` |
| Rendered a11y + responsive suite (20 tests) | `apps/web/e2e/evidence-desk.a11y.spec.ts` |

### PROTOTYPED

`/design-lab/evidence-desk` — navigable prototype of the selected direction, exercising all
13 states including the four the audit found missing from the web layer. Additive: lab
directions A–D are untouched, per ADR-010's consume/preserve rule.

### SPECIFIED

`02` IA · `06` web · `07` CLI · `08` TUI · `09` desktop/mobile · `10` backlog (AX-001,
AX-004–AX-014).

## 3. Validation

| Gate | Result | Evidence |
|---|---|---|
| **BUILD** | **PASS** | `npm run build` — 85 modules, clean |
| **TYPECHECK** | **PASS** | `tsc -b` inside the build |
| **Truth-state spec** | **PASS — 91/91** | `node scripts/test-truth-state.mjs` |
| **Rendered a11y + responsive** | **PASS — 20/20** | `npx playwright test e2e/evidence-desk.a11y.spec.ts` |
| **Contrast** | **PASS** | all 26 token/background pairs ≥ 4.5:1; lowest 5.58:1 |
| **Regression** | **NONE** | see below |
| **LINT (web)** | **NOT RUN** | no JS/TS linter is configured in `apps/web` — see §5 |

### Regression check, done properly

The full Playwright suite reports **3 failed / 22 passed**. Those 3 failures were verified
against a clean `origin/main` worktree, where the *same 3 tests fail* (**3 failed / 2
passed**). They are pre-existing environment failures — the suite needs
`VITE_ATLAS_API_TOKEN` and this host has none, so LIVE_API reads fail closed by SEC-009
design. **No regression was introduced.** The delta is +20 passing tests.

### Truth-boundary validation

| Invariant | How it is enforced now |
|---|---|
| `UNKNOWN != HEALTHY` | `truthStateFor()` maps absent/unrecognised → `unknown`; 3 automated checks |
| `DEMO != LIVE` | `readPlaneState()` returns `live` only for an explicit `live_api`; fallback announced assertively |
| `READ_ONLY_UI != EXECUTION_AUTHORITY` | `TruthChip` is a `<span>` with no handler; rendered test asserts owner-gated chips are non-focusable, non-clickable |
| `UI != CANONICAL` | No writer added; all changes are presentation over read projections |
| Colour is never the sole carrier | Rendered test strips all colour and asserts every state stays readable |
| Contested has no display winner | Rendered test asserts both sides present with the same state |

Notably, the "read failure is announced assertively" test **ran and passed** rather than
skipping — this environment's fail-closed read exercised the real error path.

## 4. Unresolved material findings

1. **A pre-existing marginal contrast failure.** `--atlas-unknown: #b45309` measures
   **4.47:1** on `#f5f0e8` paper — just under AA for normal text. The new
   `--truth-unknown: #8a5300` (5.58:1) supersedes it wherever chips are used, but the old
   token is still referenced elsewhere. Not fixed here to avoid widening the diff into
   pages other lanes may touch. → `AX-007` / `AX-013`.
2. **No axe/automated a11y gate exists.** The 20 rendered tests are targeted assertions,
   which is narrower than an audit. Full-route coverage is unverified. → `AX-013`, the most
   valuable remaining accessibility item.
3. **Touch-target and 400%-zoom audits not performed.** Stated as not done in `09` §B.5
   rather than assumed passing.
4. **`aria-live` remains 0 outside `useReadStatus`.** The other 11 live-data hooks are not
   yet wired to the announcer. The mechanism exists; adoption is incomplete. → `AX-004`.
5. **Web has no linter.** `apps/web` has no ESLint config, so `LINT` cannot be reported as
   a pass. Python `ruff`/`mypy` were not run because no Python file was touched.
6. **Screen-reader verification is by attribute assertion, not by a real AT.** Correct
   roles are necessary, not sufficient. `AX-010`'s combobox especially needs manual
   verification.

## 5. Owner decisions required

These exceed Level 2 and are **not** taken here:

1. **Adopt Evidence Desk as the production direction?** `04` recommends it with evidence.
   Adopting it is a product-architecture decision.
2. **AX-001 (shell/IA) and AX-008 (CLI areas)** — both have wide blast radius across files
   other lanes may be editing. Sequencing is an owner call.
3. **AX-006 (copy revision)** — governance-sensitive. The invariants must stay visible;
   only their register changes. Needs a governance reviewer.
4. **Desktop app** — `09` recommends **against** building one now, with four revisit
   conditions. Recorded as a recommendation, not a decision.

## 6. Claim boundaries

Stated explicitly, because this lane produced polish and polish invites overclaiming.

- This work does **not** claim `WEB APPLICATION ACCEPTED`. ADR-010's boundary stands.
- It does **not** claim WCAG AA conformance for the application. It claims SC 4.1.3 is
  implemented on the read-status path, and that specific listed checks pass.
- It does **not** claim a TUI, desktop app or mobile app exists. All three were searched
  for and found absent; `08` and `09` are specifications.
- It does **not** claim Evidence Desk is implemented. Its truth-state layer is; its shell
  is prototyped in the design lab only.
- It does **not** claim any Atlas truth boundary has changed. No surface gained authority.
- `PROMOTE_ELIGIBLE != MERGED/DEPLOYED/AUTHORITATIVE` — the backlog is a recommendation.
- **Design-lab directions A–D are preserved**, per ADR-010. Direction E is additive.

## 7. Next node

`AX-013` (axe gate in CI) is the highest-value owner-independent item: low risk, no
cross-lane collision, and it converts the accessibility work from "tests someone
remembered to write" into an enforced gate. `AX-001` and `AX-008` are higher value but
have blast radius that makes them owner-sequenced.

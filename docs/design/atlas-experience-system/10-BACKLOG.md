# 10 — Prioritised Implementation Backlog

**Session:** `AS-20260903T132018Z-claude-design-continuation-20260903-project-atlas-60ba98bb`
**Derived from:** audit `00`, research `01`, IA `02`, selected direction `04`

Counts: **P0 = 3** (2 delivered, 1 open) · **P1 = 5** · **P2 = 3** · **P3 = 3**

> `PROMOTE_ELIGIBLE != MERGED/DEPLOYED/AUTHORITATIVE`. This backlog is a recommendation
> derived from evidence. It is not a committed roadmap, and no item below is owner-approved.

---

## P0

### AX-002 — Cross-surface truth-state system · **IMPLEMENTED**

| | |
|---|---|
| **User problem** | Atlas's core claim is honest epistemic state, but the UI expressed it as ad-hoc strings in three casings. `OWNER_REQUIRED` and `RUNNING` could not be expressed at all. |
| **Design intent** | One vocabulary of 13 states, each with glyph + label + contrast-verified token, shared by web/CLI/TUI. Make `unknown != healthy` a default rather than a discipline. |
| **Surface** | Web (done); CLI/TUI adopt the same table |
| **Acceptance criteria** | 13 states declared; each has glyph and label; every token ≥ 4.5:1 on its real backgrounds; `truthStateFor(absent)` → `unknown`; owner-gated chips are non-interactive |
| **Dependencies** | none |
| **Risk** | Low — additive |
| **Complexity** | M |
| **Truth boundary** | Presentation over read-only projections; confers no authority |
| **Accessibility** | Colour never sole carrier; verified with colour stripped |
| **Evidence** | `src/lib/truthState.ts`, `src/components/TruthChip.tsx`, `src/tokens.css`; 91/91 checks in `scripts/test-truth-state.mjs`; rendered checks in `e2e/evidence-desk.a11y.spec.ts` |

### AX-003 — WCAG 2.2 SC 4.1.3 status messages · **IMPLEMENTED**

| | |
|---|---|
| **User problem** | 12 async data hooks and 0 live regions. A silent LIVE→DEMO fallback let a screen-reader user read fixture data believing it was live — a truth-boundary failure reached through an accessibility gap. |
| **Design intent** | Permanently mounted polite + assertive regions; severity chosen by whether a transition changes what the data *means*. |
| **Surface** | Web |
| **Acceptance criteria** | Both regions present before any announcement; `role`/`aria-live` correct; not `display:none`; LIVE→DEMO and read failure assertive; routine load polite; no focus movement |
| **Dependencies** | AX-002 |
| **Risk** | Low |
| **Complexity** | S |
| **Truth boundary** | Makes `DEMO != LIVE` audible, not just visible |
| **Accessibility** | This *is* the accessibility item |
| **Evidence** | `src/components/TruthAnnouncer.tsx`, `src/lib/announce.ts`, `useReadStatus`; 6 rendered tests |

### AX-001 — Job-oriented shell and IA · **OPEN**

| | |
|---|---|
| **User problem** | 15 flat nav items named after subsystems; 3 label clusters indistinguishable; users must know Atlas's module decomposition to find a task. |
| **Design intent** | Five job-areas (`02` §3) with a persistent rail and status strip; all 15 routes retained as redirects. |
| **Surface** | Web |
| **Acceptance criteria** | Nav ≤ 5 top-level items; every one of the 15 routes resolves via redirect preserving `?project=`; each area maps to a job in `02`; landmarks correct; keyboard reachable |
| **Dependencies** | AX-002; AX-010 strongly recommended first (the palette is what makes shrinking nav safe) |
| **Risk** | **Medium-high** — touches every production page; highest collision risk with other lanes |
| **Complexity** | L |
| **Truth boundary** | `UI != CANONICAL`; no route gains write capability |
| **Accessibility** | Rail is `<nav aria-label>`; `aria-current` on the active area; skip link retained |
| **Evidence** | Audit A-1; `02`; `06` §1–2 |

## P1

### AX-010 — Command palette

Breadth (15 routes + 41 endpoints + 67 commands) is preserved rather than deleted (R-3).
**AC:** `Ctrl/Cmd+K` opens; correct ARIA combobox (`aria-activedescendant`, focus stays in
input, trap + restore); rows typed by authority; owner-gated rows non-activatable;
cli-only rows show a copyable command and do not execute; result count announced.
**Deps:** AX-002. **Risk:** medium (ARIA correctness). **Complexity:** M.
**A11y:** the widget *is* the a11y risk — must be tested with a screen reader, not only
by attribute assertions.

### AX-004 — Form semantics on Ask

`aria-describedby`, `aria-invalid`, `role="alert"` all measured at 0 app-wide (A-6).
**AC:** every input has a programmatic label; errors associated via `aria-describedby`;
`aria-invalid` on failure; error announced; focus not stolen. **Deps:** AX-003.
**Risk:** low. **Complexity:** S.

### AX-005 — Responsive system

One media query for a 15-route console (A-7). **AC:** four breakpoints; rail → bottom tabs
at ≤480px; tables → cards with declared column priority; **truth state is priority 1 and
never dropped**; no horizontal page scroll; touch targets ≥ 44px; 400% zoom reflow to
320px. **Deps:** AX-001. **Risk:** medium. **Complexity:** M.
**Note:** overflow and chip-label retention already verified at 4 viewports; touch-target
and zoom audits are **not** done.

### AX-007 — Density tokens

`--atlas-max: 42rem` applied to 400-line operator tables (A-3). **AC:** `--atlas-max-prose`
and `--atlas-max-data`; tables scroll in their own container; page never scrolls
horizontally. **Deps:** none. **Risk:** low. **Complexity:** S.

### AX-006 — Product copy revision

Work-package IDs and `ACCEPTED=YES` in nav copy (A-2). **AC:** no `AS-*` identifier in
nav/hero copy; invariants stated as sentences in the strip; IDs relocated to a
`Build info` disclosure in Estate → System, still fully accessible. **Deps:** AX-001.
**Risk:** **governance-sensitive** — the invariants must remain visible, only their
register changes. Requires a governance reviewer. **Complexity:** S.

## P2

### AX-008 — CLI areas and help hierarchy

67 top-level commands, 0 argument groups. **AC:** `atlas --help` ≤ 12 entries; all 67
legacy names byte-identical (diff test); `<lens>-status` → `--status` with the legacy
retained; `UNKNOWN` exits `0`; glyph + label under `NO_COLOR=1`; no duplicated handlers.
**Deps:** AX-002 (vocabulary). **Risk:** **high** — `cli.py` is referenced by governance
docs, CI and agent skills; the no-rename constraint is absolute. **Complexity:** L.
**Evidence:** `07`.

### AX-011 — Evidence drawer

Provenance inline rather than a `Graph` destination (R-4, J-5). **AC:** opens from any
claim; shows source, ingest time, provenance hash, authority precedence; contested shows
all sources with no winner; **no trust score of any kind**. **Deps:** AX-001, AX-002.
**Risk:** low. **Complexity:** M.

### AX-012 — `ClaimText` reading surface

Dossier's contribution (J-1). **AC:** claims render as prose with inline citations; a
sourceless claim renders `UNKNOWN` inline where the fact belongs, never omitted.
**Deps:** AX-002. **Risk:** low. **Complexity:** S. Prototyped already.

## P3

### AX-009 — Terminal UI

**No TUI exists.** `08` recommends building AX-008 first, since areas become panes.
**AC:** `08` §7. **Deps:** AX-008. **Risk:** medium (new surface + dependency).
**Complexity:** L.

### AX-013 — Automated accessibility gate in CI

There is no axe/`@axe-core/playwright` integration; `AX-002`/`AX-003` are verified by
targeted assertions, which is narrower than a full audit. **AC:** axe runs on every
production route in CI; violations fail the build; the current baseline is recorded so
regressions are distinguishable from pre-existing issues. **Deps:** none.
**Risk:** low. **Complexity:** S. **This is the most valuable remaining a11y item** —
without it, coverage depends on tests someone remembered to write.

### AX-014 — Split `cli.py`

5,855 lines in one module. Real debt, but a refactor with a different risk profile that
must not ride along with a UX change (`07` §8). **Deps:** AX-008. **Risk:** high.
**Complexity:** L.

---

## Status summary

| Status | Items |
|---|---|
| **IMPLEMENTED** | AX-002, AX-003 |
| **PROTOTYPED** | Evidence Desk route (`/design-lab/evidence-desk`), AX-012 partially |
| **SPECIFIED** | AX-001, AX-004–AX-012 |
| **RECOMMENDED** | AX-013, AX-014 |
| **RECOMMENDED-AGAINST** | Desktop app (`09` Part A) — with revisit conditions |
| **OWNER_DECISION_REQUIRED** | Adopting Evidence Desk as the production direction; AX-001 and AX-008 (cross-lane blast radius); AX-006 (governance copy) |

# ADR-010 — Atlas Web UX (production shell vs design-lab)

**Status:** accepted for implementation  
**Date:** 2026-08-09  
**Work package:** AS-WEB-003  
**Alias:** ADR-ATLAS-WEB-UX-001  
**Author:** Project Atlas Web track  
**Directive:** `D-PROJECT-ATLAS-1.0-FINISH-PLUS-2.0-PREP-001` Track A  
**Depends on:** ADR-008 (stack / read-first boundary) · ADR-009 (design tokens)

## Context

AS-WEB-001 shipped a Vite + React foundation. AS-WEB-002 added four
design-lab prototype themes under `#/design-lab/*`. Operators still need a
**production read shell** — Home, Projects, Ops health — plus a named
**Command Center** mode switcher, without promoting the browser to Layer B
authority or claiming web-application acceptance.

Design-lab routes must remain for visual exploration; production chrome must
not delete or replace them.

## Decision

1. **Two UX planes**
   - **Production shell** — read-only operator surfaces: Home, Projects, Ops
     health, and Command Center. Uses shared `--atlas-*` tokens (ADR-009) with
     a Ledger Desk lean for calm readability.
   - **Design lab** — retained prototype themes A–D under `/design-lab/*`
     (AS-WEB-002). Not production acceptance.

2. **Command Center modes (named)** — presentation lenses only; never vault
   writers:

   | Mode ID | Label | Read plane |
   |---|---|---|
   | `overview` | Overview | Combined read-status / estate summary |
   | `projects` | Projects | `web_api.list_projects` / stub inventory |
   | `ops` | Ops | OBS health consume (`unknown` when absent) |
   | `impact` | Impact | Optional derived impact graph **consume** only; Graph ≠ authority |

   The mode switcher navigates these lenses. Missing evidence renders
   **unknown / unavailable** — never fabricated healthy or invented PILOT rows.

3. **Normative invariants (unchanged)**
   - **UI ≠ canonical**
   - **Graph ≠ authority**
   - **Unknown ≠ healthy**

4. **Acceptance boundary** — this ADR does **not** claim
   `WEB APPLICATION ACCEPTED`. Acceptance remains a later governor package.

## Consequences

- New routes under `apps/web` for production shell; design-lab routes stay.
- Soft `web_api` read expansion only when a new read contract is required;
  AS-WEB-003 reuses existing projects/OBS adapters + sample stub.
- No Core truth writers; no REL-001; no Atlas 2.0 production semantics.

## Alternatives considered

| Option | Why not |
|---|---|
| Promote design-lab theme as production | Conflates prototype exploration with operator shell |
| Delete design-lab after production chrome | Violates AS-WEB-002 consume / preserve rule |
| Write vault state from Command Center | Violates UI ≠ canonical and firewall |
| Fabricate healthy when OBS absent | Violates Unknown ≠ healthy (AS-OBS-001) |

# ADR-008 — Atlas Web Application foundation

**Status:** accepted for implementation
**Date:** 2026-08-09
**Work package:** AS-WEB-001
**Author:** Project Atlas Web track
**Directive:** `D-PROJECT-ATLAS-WEB-AND-1.0-AUTONOMOUS-COMPLETION-001`

## Context

Atlas 1.0 requires a first-party web surface for read-oriented vault status
(operational health, project inventory, derived signals). Tip `75fb73d` has
**no** first-party `apps/web/**` (only fixture samples under
`atlas-vault-documentation/`). Core already exposes regenerable OBS health
under `generated/ops/` and project directories under `projects/`; those are
safe to **consume**, not to re-author from a browser.

The web track must not become a second truth store: UI is not Layer B
canonical, graph projections are not authority, and missing evidence must
never be rendered as healthy (Unknown ≠ healthy — AS-OBS-001).

## Decision

1. **Stack: Vite + React (TypeScript).** Chosen over Next.js for the
   foundation scaffold because:
   - Atlas is **local-first / offline**; a static Vite shell needs no Node
     SSR runtime to preview vault read status.
   - Foundation scope is a **read-first status page**, not SEO, App Router,
     or server components — Next.js would add unused surface area.
   - Prototype themes (design-lab) iterate faster as client components with
     a thin `web_api` JSON contract.
   - Python remains the vault adapter owner (`project_atlas.web_api`); the
     UI never writes vault truth.

   Next.js remains a future option if the program later requires SSR, auth
   edges, or multi-route server composition — out of AS-WEB-001 scope.

2. **Read-first API boundary.** All vault reads for the web shell go through
   `project_atlas.web_api` (list projects, consume OBS health snapshot when
   present). Adapters are **read-only**: no writes to `projects/`, `state/`,
   claims, authority, or graph writer modules.

3. **Normative disclaimers (non-negotiable):**
   - **UI ≠ canonical** — browser state never becomes Layer B / claim truth.
   - **Graph ≠ authority** — any graph/health display is derived / ops.
   - **Unknown ≠ healthy** — absent OBS snapshot or missing evidence →
     `unknown` / unread; never fabricate `healthy`.

## Consequences

- New owned surfaces: `apps/web/**`, `src/project_atlas/web_api/**`, this ADR.
- Firewall excludes Core truth writers (`knowledge_compiler`, authority,
  graph writers, `ingestion` / CORE2-009 dual-own).
- Design-lab prototypes may theme the shell but must not invent PILOT data
  or elevate UI to authority.
- Later packages may add a thin HTTP bridge; AS-WEB-001 may use stubs /
  in-process adapters for the smoke shell.

## Alternatives considered

| Option | Why not (foundation) |
|---|---|
| Next.js App Router | Unnecessary SSR/RSC complexity for a local status shell |
| Pure static HTML | Harder TypeScript/component reuse for upcoming prototypes |
| Embedding writes in UI | Violates UI ≠ canonical and vault truth firewall |

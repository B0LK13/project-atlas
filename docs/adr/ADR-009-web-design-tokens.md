# ADR-009 — Atlas Web design tokens (design-lab)

**Status:** accepted for implementation  
**Date:** 2026-08-09  
**Work package:** AS-WEB-002  
**Author:** Project Atlas Web track  
**Directive:** `D-PROJECT-ATLAS-WEB-AND-1.0-AUTONOMOUS-COMPLETION-001`  
**Depends on:** ADR-008 (Vite + React foundation)

## Context

AS-WEB-001 recorded four prototype themes (Ledger Desk, Signal Rack,
Cartograph Quiet, Terminal Honest) and shipped a single Theme-A-lean shell.
AS-WEB-002 needs distinct layouts without duplicating ad-hoc colors or
drifting from the read-first invariants (UI ≠ canonical, Graph ≠ authority,
Unknown ≠ healthy).

## Decision

1. **Shared semantic tokens** live in `apps/web/src/tokens.css` as CSS
   custom properties (`--atlas-*`): ink, muted, paper, panel, line, accent,
   warn/unknown/ok, type stacks, max width.
2. **Theme remaps** use `[data-theme="ledger-desk|signal-rack|cartograph-quiet|terminal-honest"]`
   on `document.documentElement` / page root — layouts stay distinct while
   components bind to token roles, not hard-coded hex.
3. **Tokens are presentation only** — they do not encode trust scores,
   authority, or vault truth. Sample/read-status data remains the sole
   content plane for prototypes.

## Consequences

- Design-lab pages share `LabShell` / `ReadStatusPanel` and swap themes via
  tokens + layout classes.
- Later production chrome may reuse the same token file; acceptance of a
  production UI is **out of scope** for this ADR.
- No Core / `web_api` mutation required.

## Alternatives considered

| Option | Why not |
|---|---|
| Per-page hard-coded CSS only | Drift and duplicated invariant chrome |
| CSS-in-JS theme provider | Extra runtime for static local-first prototypes |
| Promoting UI colors to domain enums | Would blur presentation with authority |

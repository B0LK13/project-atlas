# PROTOTYPE — Atlas 2.0 Agent OS

Status: **PROTOTYPE / PREP ONLY**. Not production. No control-plane wiring in
`src/project_atlas/`. `ATLAS_2_0_IMPLEMENTATION_READY = NO`.

## Purpose

Sketch a governed Agent OS envelope for Atlas 2.0: session lifecycle,
capability boundaries, receipt gates, and skill binding — complementary to the
existing sibling control plane without absorbing it into Core 1.0.

## Non-goals (firewall)

- No production schemas shipped as package data
- No mutation of 1.0 vault authority planes
- No bypass of provenance / validation
- 1.0 wins dependency conflicts

## Candidate surfaces (stubs only)

| Surface | Intent |
|---|---|
| Session bootstrap / preflight / postflight | Deterministic readiness |
| Skill hash binding | Fail-closed version/hash match |
| Receipt gate | Block completion without evidence |
| Protected paths | Agents must not write Core authority trees |

## Cross-links

- [OPENAI-MCP-DESIGN.md](OPENAI-MCP-DESIGN.md) (PROTOTYPE providers)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [PACKAGE-CONTRACT-STUBS.md](PACKAGE-CONTRACT-STUBS.md)

## Explicit

`ATLAS_2_0_IMPLEMENTATION_READY = NO` — this document is not a flip.

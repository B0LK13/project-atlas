# PROTOTYPE — Knowledge Compilation Interface (KCI)

Status: **PROTOTYPE / PREP ONLY**. Not a public API freeze.

## Purpose

Sketch how Atlas 2.0 might expose deterministic knowledge compilation /
query / explain interfaces to Agent OS and UX surfaces without bypassing
1.0 provenance, authority, or validation gates.

## Candidate operations (non-normative)

| Op | Notes |
|---|---|
| compile | Fixture-safe claim/concept compilation |
| query | Read-only multifield / subject query |
| explain | Receipt / provenance sidecars |
| diagnose | Query outcome diagnostics |

## Forbidden

- Model output as authority
- Silent authority winner changes
- Production schemas without §98 freeze + owner auth

## Cross-links

- [CONTEXT.md](CONTEXT.md) · [AGENT-OS.md](AGENT-OS.md) · [PACKAGE-CONTRACT-STUBS.md](PACKAGE-CONTRACT-STUBS.md)

`ATLAS_2_0_IMPLEMENTATION_READY = NO`.

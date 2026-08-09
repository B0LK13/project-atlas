# Atlas 2.0 — Architecture sketch (PREP)

Status: **PREP ONLY**. Non-normative. `ATLAS_2_0_IMPLEMENTATION_READY = NO`.

## Layering (design intent)

```text
┌─────────────────────────────────────────────┐
│ Agent OS / UX / OpenAI-MCP (PROTOTYPE)      │
├─────────────────────────────────────────────┤
│ KCI · Context · Digital Twin (derived)      │
├─────────────────────────────────────────────┤
│ 1.0 Core authority / OKF / provenance       │  ← wins conflicts
├─────────────────────────────────────────────┤
│ Sources / estate (PILOT-gated)              │
└─────────────────────────────────────────────┘
```

## Dependency posture

- 1.0 Core remains the authority substrate until RELEASE CERTIFIED and
  owner auth open 2.0 impl packages.
- Track B docs/prototypes must not ship dependency-bearing production schemas.
- See [DAG.md](DAG.md) and [PACKAGE-CONTRACT-STUBS.md](PACKAGE-CONTRACT-STUBS.md).

## Theme map

| Theme | Doc |
|---|---|
| Agent OS | [AGENT-OS.md](AGENT-OS.md) |
| Digital Twin | [DIGITAL-TWIN.md](DIGITAL-TWIN.md) |
| KCI | [KCI.md](KCI.md) |
| Context | [CONTEXT.md](CONTEXT.md) |
| Providers | [OPENAI-MCP-DESIGN.md](OPENAI-MCP-DESIGN.md) |

## Explicit

This sketch is not an implementation charter flip and does not authorize
production branches.

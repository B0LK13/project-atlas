# Technical Demo — Architecture

> **DEMO** · **NOT AUTHENTIC PILOT** · **NOT RELEASE EVIDENCE**
>
> `AS-DEMO-2.1-001` · `TECHNICAL_PREVIEW`

## Placement in the Atlas system

```text
                    ┌─────────────────────────────┐
                    │  Authentic estate pilot     │
                    │  (release gate · dormant)   │
                    └─────────────▲───────────────┘
                                  │ wake only on
                                  │ AUTHENTIC_ESTATE_ROOT
┌─────────────────────┐   ┌───────┴────────┐
│ DEMO_FIXTURE Mode A │   │ Mode B live    │
│ .../demo/estate     │   │ ATLAS_DEMO_ROOT│
└─────────┬───────────┘   └───────┬────────┘
          │                       │
          └───────────┬───────────┘
                      ▼
        atlas discover → ingest → indexes → validate
                      ▼
              .tmp/demo-vault (disposable)
                      ▼
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   live api-serve   Web shell    MCP invoke
   (127.0.0.1)    DEMO_ONLY=1   read tools
```

Demo consumes the **same Core pipeline and live surfaces** as production
paths, but the **input estate class** is fixture/demo and must be stamped
as such end-to-end.

## DEMO_FIXTURE layout

```text
tests/fixtures/demo/
  README.md                      # corpus banner (not discovered)
  estate/                        # DEMO_FIXTURE discover root
    harbor-api/                  # conflict + stale
      .atlas-project.yaml        # FIXTURE ONLY (under tests/)
      ARCHITECTURE.md            # claims PostgreSQL 15
      REQUIREMENTS.md
      DEPENDENCIES.md
      docs/ADR-001-database.md
      docs/ADR-002-database-superseded.md   # stale
      src/RUNTIME.md             # claims PostgreSQL 16 (conflict)
    harbor-portal/               # cross-project dependency
      .atlas-project.yaml
      README.md
      DEPENDENCIES.md            # requires harbor-api
      docs/ARCHITECTURE.md
    harbor-ops/                  # unknown fields
      .atlas-project.yaml
      README.md
      INVENTORY.md               # explicit unknowns
```

Markers exist **only** under this committed fixture tree. Creating
`.atlas-project.yaml` in unrelated real project directories to simulate
pilot readiness is **out of policy**.

## Env contract

| Variable | Mode | Notes |
|---|---|---|
| `ATLAS_DEMO_MODE=fixture` | A | Default Technical Preview |
| `ATLAS_DEMO_FIXTURE` | A | Absolute path to `tests/fixtures/demo/estate` |
| `ATLAS_DEMO_ROOT` | B | Legitimate root only; optional |
| `VITE_ATLAS_DEMO_ONLY=1` | Web | Forces demo/fixture stamps; no pilot rows |
| `VITE_ATLAS_API_BASE` | Web | Local API base (default `http://127.0.0.1:8765`) |

## Surfaces in scope for the story

| Surface | Demo expectation |
|---|---|
| Core CLI pipeline | Deterministic on DEMO_FIXTURE |
| HTTP API | Real local server; implemented routes only |
| Web | Live/demo data; Projects / Knowledge / Ask / Graph / Mission / Workspace |
| MCP | Read-path parity with API knowledge |
| Receipts | Reconstruct controlled ops when exercised |

## Explicit non-authority

- Graph / KF2 / federation projections are **not** Layer B claim authority.
- Demo stubs must not set `authentic_pilot=true` or populate authentic pilot estate rows.
- Fixture success under owner waiver ≠ authentic `ESTATE PILOT PASSED`.

## Script surface

Windows-first outline: [`scripts/demo.ps1`](../../scripts/demo.ps1).

Linux/macOS may follow the same steps manually; no bash runner is required
for Technical Preview scaffold.

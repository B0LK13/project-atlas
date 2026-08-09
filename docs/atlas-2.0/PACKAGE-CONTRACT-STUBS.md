# Atlas 2.0 — Package contract stubs (§98 seed)

Status: **PREP ONLY** — names reserved; not authorized for production impl.
`ATLAS_2_0_IMPLEMENTATION_READY = NO`.

| Stub ID | Theme | Notes |
|---|---|---|
| AS-2.0-FED-001 | Multi-vault federation | docs/contracts only |
| AS-2.0-UX-001 | Advanced Command Center | after WEB 1.0 accepted |
| AS-2.0-PROV-001 | Provider adapters | optional; provenance non-bypass |
| AS-2.0-SYNC-001 | Estate sync v2 | after INT-013 / CORE2-010 |
| AS-2.0-COMPAT-001 | Compatibility snapshot consumer | post 1.0 freeze |

## Design deepen (2026-08-09c)

- `DAG.md` — gate chain + package dependency sketch
- `OPENAI-MCP-DESIGN.md` — provider/MCP prep notes (no production wiring)
- Threat model register retained; still PREP ONLY

Do not open production branches for these until `ATLAS_1_0_RELEASE_CERTIFIED`
and `ATLAS_2_0_IMPLEMENTATION_READY`.

## Functional requirement stubs (FR-2.0-xxx)

Draft FR IDs for planning traceability only — **not** certified requirements.

### AS-2.0-FED-001 — Multi-vault federation

| FR ID | Requirement (stub) | 1.0 dependency |
|---|---|---|
| FR-2.0-FED-001 | Join two or more vault roots with explicit operator manifest; no implicit merge | AS-ID-001, AS-XPROJ-001 |
| FR-2.0-FED-002 | Federation join must fail closed on identity ambiguity | `lineage.py` |
| FR-2.0-FED-003 | Cross-vault read lenses are consume-only; no cross-vault promote | ingest `_promote` boundary |
| NFR-2.0-FED-001 | Federation fixtures produce deterministic join inventory (no wall-clock) | NFR-001 |

### AS-2.0-UX-001 — Advanced Command Center

| FR ID | Requirement (stub) | 1.0 dependency |
|---|---|---|
| FR-2.0-UX-001 | Command Center advanced modes consume read adapters only | AS-WEB-001, ADR-010 |
| FR-2.0-UX-002 | Impact lens displays derived graph; never elevates graph to authority | AS-J-005 |
| FR-2.0-UX-003 | All modes preserve UI≠canonical / Graph≠authority / Unknown≠healthy | ADR-008 |
| NFR-2.0-UX-001 | Blocked until WEB APPLICATION ACCEPTED = YES | AS-WEB-ACCEPT-001 |

### AS-2.0-PROV-001 — Provider adapters

| FR ID | Requirement (stub) | 1.0 dependency |
|---|---|---|
| FR-2.0-PROV-001 | Provider adapters are optional; disabling leaves MVP functional | NFR-006 |
| FR-2.0-PROV-002 | Model output quarantined until provenance + schema validation pass | FR-004, ingest quarantine |
| FR-2.0-PROV-003 | No provider path bypasses `secrets.scan_text` | NFR-004 |
| NFR-2.0-PROV-001 | Adapter registry documents skill/version pin per provider | AS-CTRL-001 |

### AS-2.0-SYNC-001 — Estate sync v2

| FR ID | Requirement (stub) | 1.0 dependency |
|---|---|---|
| FR-2.0-SYNC-001 | Incremental sync respects tombstones and retention policy | AS-INT-010, AS-INT-009 |
| FR-2.0-SYNC-002 | Sync conflicts surface in review queue; no silent authority overwrite | AS-CORE-003 |
| FR-2.0-SYNC-003 | Promote recovery boundary preserved on partial failure | AS-CORE2-009 |
| NFR-2.0-SYNC-001 | Blocked until INT-013 / CORE2-010 entry gates green | backlog |

### AS-2.0-COMPAT-001 — Compatibility snapshot consumer

| FR ID | Requirement (stub) | 1.0 dependency |
|---|---|---|
| FR-2.0-COMPAT-001 | 2.0 packages declare consumed 1.0 snapshot (HEAD/TREE/tag) | COMPATIBILITY.md |
| FR-2.0-COMPAT-002 | Contract drift against snapshot fails CI, not runtime guess | schema validation |
| FR-2.0-COMPAT-003 | Migration tooling produces reversible audit trail | INT-012 (open) |
| NFR-2.0-COMPAT-001 | No production impl until `ATLAS_1_0_RELEASE_CERTIFIED` | release gate |

## Prep deepen (2026-08-09d)

- `IMPLEMENTATION-READY-GATE.md` — §101 checklist (READY=NO)
- CHARTER / VISION / PRD rewritten as PROTOTYPE / PREP (not stubs-only)
- Firewall unchanged: no 2.0 production semantics

## Prep deepen (2026-08-09)

Added COMPATIBILITY.md, FIXTURE-PLAN.md, OPEN-QUESTIONS.md — still PREP ONLY.
Expanded FR stubs for federation, UX, provider, sync, compat (this revision).

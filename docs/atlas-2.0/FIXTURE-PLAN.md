# Atlas 2.0 — Fixture plan (prep)

Status: **PREP ONLY** — docs/fixtures sketches only; no production schema.
`ATLAS_2_0_IMPLEMENTATION_READY = NO`.

See also: [fixtures/README.md](fixtures/README.md) for per-family inventory sketches.

## Fixture families (names reserved)

| Family | Path (sketch) | Purpose | Mutates vault? |
|---|---|---|---|
| Federation smoke | `fixtures/atlas-2.0/federation-smoke/` | Multi-vault join manifest sketches | **no** (docs-only) |
| UX Command Center | `fixtures/atlas-2.0/ux-command-center/` | Advanced mode read-status stubs | **no** |
| Provider adapter | `fixtures/atlas-2.0/provider-adapter/` | Quarantine + provenance gate samples | **no** |
| Compat snapshot | `fixtures/atlas-2.0/compat-snapshot/` | 1.0 HEAD/TREE pin consumer sketches | **no** |
| Sync v2 tombstone | `fixtures/atlas-2.0/sync-v2-tombstone/` | Incremental sync + tombstone scenarios | **no** |
| MCP read-only surface | `fixtures/atlas-2.0/mcp-readonly-surface/` | Consume-only MCP tool stubs + write-deny matrix | **no** |

Do not create production-mutating fixture harnesses until 2.0 IMPLEMENTATION READY.
`ATLAS_2_0_IMPLEMENTATION_READY = NO`.

## Inventory sketches (per family)

### federation-smoke/

| File (sketch) | Contents | Validates |
|---|---|---|
| `README.md` | Join scenario narrative | operator intent |
| `vault-a.manifest.yaml` | Vault A identity + path roots | AS-ID-001 |
| `vault-b.manifest.yaml` | Vault B identity + path roots | AS-ID-001 |
| `join-request.yaml` | Operator-signed join spec | fail-closed ambiguity |
| `expected-quarantine.json` | Ambiguous join → quarantine sketch | T-2.0-007 |

### ux-command-center/

| File (sketch) | Contents | Validates |
|---|---|---|
| `README.md` | Mode matrix (overview/projects/ops/impact) | ADR-010 |
| `read-status-advanced.json` | Sample read-status with all modes | UI≠canonical |
| `impact-lens-stub.json` | Derived graph consume-only sample | Graph≠authority |
| `health-absent.json` | Missing OBS → unknown rollup | Unknown≠healthy |

### provider-adapter/

| File (sketch) | Contents | Validates |
|---|---|---|
| `README.md` | Adapter quarantine flow narrative | FR-2.0-PROV-002 |
| `adapter-output-sample.json` | Raw provider payload (redacted) | quarantine lane |
| `expected-provenance.json` | Required provenance fields sketch | no bypass |
| `secret-findings-meta.json` | Metadata-only secret scan result | NFR-004 |

### compat-snapshot/

| File (sketch) | Contents | Validates |
|---|---|---|
| `README.md` | Snapshot pin workflow | FR-2.0-COMPAT-001 |
| `snapshot-pin.yaml` | HEAD/TREE/v1.0.0 reference | COMPATIBILITY.md |
| `contract-manifest.json` | Schema IDs consumed by 2.0 stub | drift detection |

### sync-v2-tombstone/

| File (sketch) | Contents | Validates |
|---|---|---|
| `README.md` | Incremental sync + tombstone scenario | AS-INT-010 |
| `before-manifest.json` | Pre-sync inventory sketch | deterministic |
| `after-manifest.json` | Post-sync inventory sketch | tombstone respect |
| `conflict-review-queue.json` | Unresolved conflict → review | AS-CORE-003 |

### mcp-readonly-surface/

| File (sketch) | Contents | Validates |
|---|---|---|
| `README.md` | MCP tool family narrative (read/query/ops only) | OPENAI-MCP-DESIGN.md |
| `tool-allowlist.yaml` | Allowed `atlas.vault.read_*` / `atlas.query.*` / `atlas.ops.*` | consume-only |
| `tool-denylist.yaml` | Forbidden `promote`, claim compile, authority mutate | T-2.0-012 |
| `expected-deny-receipt.json` | Sample deny response shape (no vault write) | NFR-006 |

## Harness policy (prep)

1. Sketches live under `docs/atlas-2.0/fixtures/` until IMPLEMENTATION READY.
2. No JSON Schema shipped as package data from fixture sketches.
3. Golden harnesses that mutate vaults require explicit 2.0 entry gate.
4. WEB APPLICATION ACCEPTED is a prerequisite for UX fixture promotion to production paths.

## Changelog

| Date | Change |
|---|---|
| 2026-08-09 | Initial fixture family names |
| 2026-08-09 | Per-family inventory sketches + compat/sync families |
| 2026-08-09 | Added `mcp-readonly-surface/` family sketch (Z-wave deepen) |

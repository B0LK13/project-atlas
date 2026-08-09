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

## Scenario inventory deepen-f (filenames reserved; payloads absent)

| Scenario ID | Family | Evidence class | Positive sketch | Required negative sketch | Exit still blocked by |
|---|---|---|---|---|---|
| FX-2.0-FED-001 | federation-smoke | fixture rehearsal | two explicit identities join read-only | duplicate identity and unsigned member both quarantine | OQ-001/OQ-016 |
| FX-2.0-FED-002 | federation-smoke | fixture rehearsal | stable member ordering | reordered input must not change inventory bytes | contract freeze |
| FX-2.0-UX-001 | ux-command-center | sample display | source and freshness labels visible | absent health must render unknown | WEB acceptance |
| FX-2.0-UX-002 | ux-command-center | sample display | derived impact lens labelled | route render must not emit acceptance evidence | OQ-017 |
| FX-2.0-PROV-001 | provider-adapter | quarantined sample | provenance-complete redacted result | secret finding or missing pin cannot leave quarantine | OQ-004/OQ-006 |
| FX-2.0-PROV-002 | mcp-readonly-surface | capability rehearsal | pinned read tool accepted | discovered write tool denied after registry drift | OQ-004 |
| FX-2.0-COMPAT-001 | compat-snapshot | reference sample | exact commit/tree pair consumed | tree mismatch and stale pin both fail closed | release certification |
| FX-2.0-SYNC-001 | sync-v2-tombstone | fixture rehearsal | dry plan preserves tombstone | stale winner cannot silently resurrect | OQ-011 |
| FX-2.0-SYNC-002 | sync-v2-tombstone | fixture rehearsal | identical operation replay is idempotent | enqueue without authorization and changed-scope replay denied | OQ-018 |
| FX-2.0-ESTATE-001 | estate-evidence-class | evidence-class sketch | fixture-only waiver remains explicit | fixture receipt must not satisfy PILOT PASSED | OQ-019 |

### Proposed inventory-only additions

The following names may be documented under `docs/atlas-2.0/fixtures/`, but no
JSON/YAML payload or executable harness is authorized yet:

- `estate-evidence-class/README.md`
- `sync-v2-tombstone/queue-state-cases.md`
- `ux-command-center/acceptance-non-evidence.md`
- `compat-snapshot/pin-mismatch-cases.md`

Completeness means every scenario eventually has provenance, expected outcome,
negative outcome, deterministic comparison rule, and evidence-class label. The
current estate is an inventory only and therefore is not complete or ready.

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
| 2026-08-09 | deepen-f: scenario/negative-case/evidence-class inventory; no payload harness |

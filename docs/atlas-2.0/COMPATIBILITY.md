# Atlas 2.0 — Compatibility constraints (prep)

Status: **PREP ONLY**. `ATLAS_2_0_IMPLEMENTATION_READY = NO`.

After `ATLAS_1_0_RELEASE_CERTIFIED`, 2.0 production packages must:

1. Consume the published compatibility snapshot (HEAD/TREE/v1.0.0).
2. Not silently rewrite 1.0 authority / identity / provenance contracts.
3. Keep UI≠canonical / Graph≠authority / Unknown≠healthy for any web surfaces.

## Snapshot pin model (stub)

| Field | Description | Example (sketch) |
|---|---|---|
| `snapshot_id` | Human-readable pin label | `atlas-1.0.0-compat` |
| `git_head` | Certified commit SHA | `28bfa4f…` |
| `git_tree` | Tree hash at certification | TBD at freeze |
| `schema_manifest` | JSON Schema IDs + versions consumed | `project_atlas.domain.v1`, … |
| `adr_manifest` | ADR IDs that 2.0 must not contradict | ADR-001…ADR-010 |

## Drift classes

| Class | Description | 2.0 response (prep) |
|---|---|---|
| **Hard** | Authority / identity / provenance contract change | Fail CI; require new major snapshot |
| **Soft** | Additive schema fields with defaults | Allowed with compat test green |
| **Web** | UI invariant regression | Block UX packages; ADR-008 gate |
| **Graph** | Derived projection format change | Consume-only adapter version bump |

## Non-negotiable 1.0 invariants (carry to 2.0)

- `ingestion._promote(write_plan)` remains the sole canonical write boundary.
- AS-ID-001 lineage locks and ambiguity fail-closed behavior preserved.
- Agent-event quarantine before canonical projection (AS-CTRL-001).
- Secrets metadata-only scanning (NFR-004).

## WEB acceptance dependency

Advanced Command Center fixtures (AS-2.0-UX-001) must not promote to production
paths until **WEB APPLICATION ACCEPTED = YES** (AS-WEB-ACCEPT-001 governor green).

## Open compat work (prep)

- Publish machine-readable `contract-manifest.json` at 1.0 freeze.
- Define CI job sketch for FR-2.0-COMPAT-002 drift detection.
- Resolve INT-012 vs AS-2.0-COMPAT-001 migration ownership (see OPEN-QUESTIONS.md).

# Atlas 2.0 — Compatibility constraints

Status: **PRODUCTION consumer available** via AS-2.0-COMPAT-001.
`ATLAS_2_0_IMPLEMENTATION_READY = YES`.

After `ATLAS_1_0_RELEASE_CERTIFIED`, 2.0 production packages must:

1. Consume the published compatibility snapshot (HEAD/TREE/v1.0.0).
2. Not silently rewrite 1.0 authority / identity / provenance contracts.
3. Keep UI≠canonical / Graph≠authority / Unknown≠healthy for any web surfaces.

## Published snapshot

| Field | Value |
|---|---|
| `snapshot_id` | `atlas-1.0.0-compat` |
| Machine record | `docs/releases/1.0.0/compatibility-anchor.json` |
| Human snapshot | `docs/releases/1.0.0/COMPATIBILITY-SNAPSHOT.md` |
| `git_head` (software freeze) | `f4079813025dd882e0e3608ab7ad5b3b17f95bd9` |
| `git_tree` (software freeze) | `feb0441a13e391812ae07a1a8eb27b0de1061469` |
| Tag | `v1.0.0` @ `bb0957c47b5e2976b5cf358342cf89dffe6e6a55` |
| Consumer | `project_atlas.compat_anchor` / `atlas compat verify` |

## Drift classes

| Class | Description | 2.0 response |
|---|---|---|
| **Hard** | Authority / identity / provenance contract change | Fail closed; require new major snapshot |
| **Soft** | Additive schema fields with defaults | Allowed with compat test green |
| **Web** | UI invariant regression | Block UX packages; ADR-008 gate |
| **Graph** | Derived projection format change | Consume-only adapter version bump |

## Non-negotiable 1.0 invariants (carry to 2.0)

- `ingestion._promote(write_plan)` remains the sole canonical write boundary.
- AS-ID-001 lineage locks and ambiguity fail-closed behavior preserved.
- Agent-event quarantine before canonical projection (AS-CTRL-001).
- Secrets metadata-only scanning (NFR-004).

## WEB acceptance dependency

Advanced Command Center fixtures (AS-2.0-UX-001) may open now that
**WEB APPLICATION ACCEPTED = YES**.

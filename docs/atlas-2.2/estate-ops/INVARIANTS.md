# Estate Ops — hard invariants (PREP)

Package: **AS-2.2-ESTATE-OPS-PREP-001**  
Status: **normative for this PREP tree**; runtime enforcement deferred until unlock.

## 1. unknown ≠ healthy

| Signal | Allowed | Forbidden |
|---|---|---|
| Missing ops evidence | Display `unknown` chip / rollup | Map to `healthy`, `PASS`, or `READY` |
| Partial estate slice | `partial` status | Invent green estate rollup |
| MCP read unavailable | honest unavailable | Fabricate ops snapshot |

Any consumer that coerces unknown → healthy without AS-OBS-001 evidence is
**out of contract**.

## 2. UI ≠ canonical

| Surface | May do | Must not do |
|---|---|---|
| Mission Control panel | Render queue chips; link evidence | Write Layer B / promote tasks |
| Workspace panel | Show active slices | `_promote` / canonical mutation |
| Ops Health receipt | Display operational rollup | Stamp project authority |
| EstateOpsAction | Emit escalate receipt | `canonical_write` / ops mutation |

Truth boundary string (prep):  
`ESTATE OPS ≠ UNKNOWN-AS-HEALTHY / ≠ UI-CANONICAL / ≠ OPS RUNTIME MUTATION / ≠ AUTHORITY`

## 3. LLM ≠ authority

| Field | Const / rule |
|---|---|
| `authority.level` on envelopes | `derived` |
| LLM-suggested healthy rollup | rejected (`unknown_as_healthy`) |
| Subjective confidence / trust | **forbidden** (objective signals only) |

## 4. No runtime `ops_health` / `ops_events` mutation in PREP

This PREP lane **must not** edit:

- `src/project_atlas/ops_health.py`
- `src/project_atlas/ops_events.py`
- shipped package schemas for Core ops health snapshots

Consume-only references to AS-OBS-001 helpers are documentation links, not
code ownership.

## 5. no PILOT invent / certification wall

| Field | Const / rule |
|---|---|
| `pilot_roots` | `0` |
| `authentic_estate` | `false` on fixtures |
| `evidence_class` | `fixture-only` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

Fixture cockpit rehearsal ≠ authentic estate PILOT PASSED ≠ 2.1 RELEASE
CERTIFIED ≠ 2.2 unlock.

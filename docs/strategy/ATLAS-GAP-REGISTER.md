# Atlas Gap Register

**Directive:** `D-PROJECT-ATLAS-GAP-ANALYSIS-TO-EXECUTABLE-ROADMAP-001`  
**Tip at register:** `a1e0972` / TREE `c6cfe95` (revalidate)  
**Backlogs:** keep **2.1 release-critical** and **north-star** separate — do not merge queues.

Legend:

- **RELEASE_BLOCKING** = blocks `v2.1.0` certification only when `YES`
- **Priority** = P0 (now / release) · P1 (next wave) · P2 (2.2) · P3 (2.3/3.0)
- **Maturity** = FAIL / OWNER_BLOCKED / CONTRACT / FIXTURE / BOUNDED / LIVE_READ_ONLY / LIVE_PRODUCTION / EXPERIMENTAL / ABSENT

---

## A. 2.1 release-critical backlog

| GAP_ID | Gap | Maturity | RELEASE_BLOCKING | Priority | Proposed package | Target release | Evidence |
|---|---|---|---|---|---|---|---|
| GAP-2.1-001 | Authentic estate PILOT PASS | DORMANT_BLOCKED | **YES** | P0 | AS-2.1-PILOT-AUTH-001 | v2.1.0 | ACTIVE_WORKER=NONE; wake `AUTHENTIC_ESTATE_ROOT_AVAILABLE` |
| GAP-2.1-002 | SYNC-AUTH on authentic estate | BLOCKED | **YES** (post-PILOT) | P0 | AS-2.1-SYNC-AUTH-001 | v2.1.0 | blocked on GAP-2.1-001 |
| GAP-2.1-003 | TWIN-AUTH on authentic estate | BLOCKED | **YES** (post-PILOT) | P0 | AS-2.1-TWIN-AUTH-001 | v2.1.0 | blocked on GAP-2.1-001 |
| GAP-2.1-004 | LIVE E2E authentic matrix | BLOCKED | **YES** (post-PILOT) | P0 | AS-2.1-LIVE-E2E-001 | v2.1.0 | blocked on GAP-2.1-001..003 |
| GAP-2.1-005 | ADV/SEC fan-out for RC | PARTIAL | **YES** (pre-REL) | P0 | AS-2.1-ADV/SEC RC pack | v2.1.0 | ADV suites exist; RC fan-out pending |
| GAP-2.1-006 | AS-REL-2.1-001 / tag v2.1.0 | NOT OPEN | **YES** | P0 | AS-REL-2.1-001 | v2.1.0 | `ATLAS_2_1_RELEASE_CERTIFIED=NO` |

### 2.1 Track B harden (non-release-blocking unless RC finds CRITICAL/HIGH)

| GAP_ID | Gap | Maturity | RELEASE_BLOCKING | Priority | Proposed package | Target release | Evidence |
|---|---|---|---|---|---|---|---|
| GAP-2.1-H01 | Mission/Workspace LIVE + polish | LIVE_READ_ONLY | NO | P1 | AS-2.1-WEB-MISSION/WORKSPACE-LIVE | v2.1.x / harden | **DRAINED** #153/#155 |
| GAP-2.1-H02 | Ops receipt adapter | LIVE_READ_ONLY / honest empty | NO | P1 | AS-2.1-OBS-RECEIPTS-001 | v2.1.x | **DRAINED** #155 `/v1/ops/receipts` |
| GAP-2.1-H03 | L3 policy→dispatch loop + ADV | BOUNDED + ADV | NO | P1 | AS-2.1-AUTONOMY-L3-LOOP-001 | v2.1.x | **DRAINED** #153/#155 |
| GAP-2.1-H04 | OAI import size/format ADV | BOUNDED | NO | P1 | AS-2.1-OAI-IMPORT-ADV-001 | v2.1.x | **DRAINED** #153 size cap |
| GAP-2.1-H05 | Host/CORS ADV matrix deepen | BOUNDED/ADV | NO | P1 | AS-2.1-ADV-HOST-CORS-001 | v2.1.x | **DRAINED** #154 |
| GAP-2.1-H06 | OAI Responses POC live smoke | EXPERIMENTAL / RATE_LIMITED | **NO** | P2 | AS-2.1-OAI-RESPONSES-POC-001 | experimental | NON_RELEASE_BLOCKING |

---

## B. North-star backlog (2.2 / 2.3 / 3.0) — NOT 2.1 scope wideners

| GAP_ID | Gap | Maturity | RELEASE_BLOCKING | Priority | Proposed package | Target release | Evidence |
|---|---|---|---|---|---|---|---|
| GAP-NS-001 | Estate-scale knowledge intelligence fabric | PARTIAL | NO | P2 | AS-2.2-KF2-* | v2.2.0 | Core KF modules exist; estate unlock post-2.1 |
| GAP-NS-002 | Hybrid retrieval + context packs production | CONTRACT/BOUNDED | NO | P2 | AS-2.2-RET-CTX-001 | v2.2.0 | `hybrid_retrieval` / `context_pack` |
| GAP-NS-003 | Temporal / bitemporal claim validity UX | CONTRACT | NO | P2 | AS-2.2-TEMPORAL-001 | v2.2.0 | `bitemporal` / temporal evaluator |
| GAP-NS-004 | Conflict projection + review cockpit | PARTIAL | NO | P2 | AS-2.2-CONFLICT-UX-001 | v2.2.0 | conflict_projections |
| GAP-NS-005 | Knowledge CI / eval harness live | FIXTURE | NO | P2 | AS-2.2-KCI-001 | v2.2.0 | knowledge_ci_harness |
| GAP-NS-006 | Cross-project registry / edges production | PARTIAL | NO | P2 | AS-2.2-XPROJ-001 | v2.2.0 | xproj_* modules |
| GAP-NS-007 | Live ChatGPT API bridge (quarantine-first) | ABSENT (export-only) | NO | P2 | AS-2.2-CHATGPT-LIVE-001 | v2.2.0 | bridge is export-path |
| GAP-NS-008 | Multi-user collab network plane | ABSENT | NO | P3 | AS-2.3-COLLAB-NET-001 | v2.3.0 | local receipts only |
| GAP-NS-009 | Federation / multi-vault | CONTRACT | NO | P3 | AS-2.3-FED-001 | v2.3.0 | federation.py stubs |
| GAP-NS-010 | AgentOS transitions + eval shadow | CONTRACT | NO | P3 | AS-3.0-AGENTOS-001 | v3.0.0 | agentos_* |
| GAP-NS-011 | Continuous security / scale harness productization | FIXTURE | NO | P3 | AS-3.0-SEC-SCALE-001 | v3.0.0 | security_adv / scale_harness |
| GAP-NS-012 | Provider remote SDK adapters (still quarantine) | DISABLED default | NO | P3 | AS-3.0-PROV-SDK-001 | v3.0.0 | provider_adapters deny live |

---

## C. Counts (at tip `a1e0972`)

| Bucket | Count |
|---|---|
| P0 RELEASE_BLOCKING=YES | **6** (GAP-2.1-001..006) — PILOT OWNER_BLOCKED |
| P1 Track B harden (non-blocking) | **0 open** (H01–H05 **DRAINED** #153–#155) |
| P2 north-star / 2.2 | **7** (NS-001..007) + H06 experimental |
| P3 2.3/3.0 | **5** (NS-008..012) |

---

## D. Discipline

1. Implementing a north-star gap does **not** substitute for GAP-2.1-001.
2. After `v2.1.0` cert, fire `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` and open P2 packages from `ATLAS-2.2-EXECUTABLE-ROADMAP.md`.
3. No invent markers / no fixture waiver for authentic PILOT.

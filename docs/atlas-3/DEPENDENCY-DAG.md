# Atlas 3.0 — Dependency DAG

## Foundation hard chain (D-193)

```text
AT3-001 North Star / FOUNDATION.md
        ↓
AT3-002 Project Twin schema
        ↓
AT3-003 Engineering Event Model
        ↓
AT3-014 Universal Event Ledger
        ↓
AT3-015 Atlas Pulse
```

Parallel after stable contracts: AT3-030 · AT3-035 · AT3-050.
AT3-004 (capability registry) and AT3-005 (compatibility) run from the start.

## First product vertical

```text
AT3-003 Engineering Event Model
        ↓
AT3-014 Universal Event Ledger
        ↓
   ┌────┴────┐
   ↓         ↓
AT3-015   AT3-030
Pulse     Start
   └────┬────┘
        ↓
AT3-050 Agent Proof-of-Work
        ↓
AT3-051 Independent verification binding (IV != MERGE)
AT3-052 ADV binding (ADV != MERGE / != security cert)
```

Start may read Pulse, but Pulse must not require Start.
Proof may read the ledger; it must not require a UI.

## D-192 memory DAG

```text
AT3-047 Privacy / security ─────────────────────────────┐
                                                         │
AT3-035 Connector Framework                              │
        ↓                                                │
AT3-039 Conversation Normalization                       │
        ↓                                                │
AT3-040 Knowledge Extraction ← existing ITEM_TYPES       │
        ↓                                                │
AT3-041 Deduplication                                    │
        ↓                                                │
AT3-042 Conflict Detection                               │
        ↓                                                │
AT3-044 Freshness / Invalidation                         │
        ↓                                                │
AT3-049 Reconciliation                                   │
        ↓                                                │
AT3-048 Unified Memory Search                            │
        ↓                                                │
Context Compiler (consume-only; 2.x runtime_22)          │
                                                         │
Parallel after AT3-035:                                  │
  AT3-036 ChatGPT (first)                                │
  AT3-037 Claude                                         │
  AT3-038 Gemini                                         │
                                                         │
AT3-043 Decision + intent  (fail-closed owner_origin)    │
AT3-061 Honesty wrapper    (INTENT != CURRENT STATE)     │
AT3-060 Causal graph       (declared CAUSED_BY)          │
AT3-062 DECIDED_BY         (owner_origin required)       │
AT3-045 Session lineage                                  │
AT3-046 Incremental sync   (not live ChatGPT history)    │
```

## Cross-program edges

```text
Truth Core ──────────► Pulse / Start / memory freshness (read)
Bitemporal / kdiff ─► Time fields / stale queries (read)
conversation_capture ► AT3-040 taxonomy (reuse, do not fork)
chatgpt_bridge ─────► AT3-036 (compose, do not replace; live history claim fails closed)
Ask2 / runtime_22 ──► consume reconciled memory later (not in this slice as write)
Orch DAG / leases ──► AT3-050 / AT3-053 (project, do not redefine)
AS-GRAPH-003 ───────► twin relationships (derived)
AT3-020 claim-nodes ► declared claim/decision/requirement (graph != authority; no Truth Core)
AT3-021 rel-expand ─► GRAPH_REUSE aliases only (no AS-GRAPH-003 write)
AT3-022 conflict-unknown ► declared conflicts/unknowns (UNKNOWN stays UNKNOWN; no winner)
AT3-023 graph-authority ► graph is never authority (winners/trust fail closed)
AT3-070 surfaces ───► CLI/API/Web/TUI/MCP/A2A contract (transport != authority)
AT3-071 transport ──► HTTP/CLI/MCP/A2A success != authority
AT3-072 register ───► provider/capabilities CLI design (no proliferation)
AT3-080 impact ─────► declared impact rows (graph != authority; no trust scores)
AT3-100 twin-health ► derived signals (health != authority; estate != authorization)
AT3-090 home ───────► Pulse + Start + twin health (UI != truth)
AT3-091 timeline ───► ledger valid-time order (wall-clock != valid-time)
AT3-094 decisions ──► declared owner_origin only (model paraphrase != owner)
AT3-092 truth-graph ► declared claims/relationships (graph != authority; no winners)
AT3-096 mission ────► declared orch DAG/leases (self-merge forbidden; estate != authorization)
AT3-095 impact-ux ──► composes AT3-080 (no new CLI; graph != authority)
AT3-110 multi-proj ► declared siblings (federation != authority; no org mint)
AT3-111 org-id ────► declared only (does not mint; federation != org identity)
AT3-081 stale-intel ► Pulse + memory compose (no winner; stale != current)
AT3-082 next-honesty ► Pulse + next-lens compose (NEXT != command; no write)
AT3-093 time-machine-ux ► kdiff reuse (no second clock; wall-clock != valid-time)
AT3-112 federation-reuse ► FED-001/002 compose (federation != authority; no promote)
AT3-053 autonomy-gate ► orch DAG/lease reuse (no self-dispatch; lease != merge)
AT3-039 normalize ──► canonical envelope (mixed corrupt fail-closed; graph != authority)
AT3-040 extract ────► landed ITEM_TYPES (heuristic only; forged owner != confirmed)
AT3-041 dedup ──────► exact/near collapse (provenance retained; no layer collapse)
AT3-042 conflicts ──► detect only (no winner; state/intent/history stay separate)
AT3-044 freshness ──► STALE != CURRENT; UNKNOWN stays UNKNOWN without stronger evidence
AT3-047 privacy ────► secret scan fail-closed; raw transcript minimized
AT3-048 search ─────► extracted items only (not transcript dump; cross-project fail-closed)
AT3-049 reconcile ──► compose 041/042/044 (never auto-promote; no winner)
AT3-101 ledger-obs ► validated list (ledger != truth; no healthy filter)
AT3-102 provider-sync ► honest states (live history != sync; AT3-046 blocked)
AT3-006 security-catalog ► reviewed catalog (catalog != scanner != cert)
FULL_LIVE_DEMO ─────► hard gate on mutating certified surfaces
```

## Forbidden edges

- Memory ─x─► Truth Core auto-promote
- UI ─x─► new domain model
- Graph ─x─► authority winner
- Model completion claim ─x─► AGENT_PROOF
- Connector ─x─► scrape authenticated UI as default
- Atlas 3 ─x─► dual-write `ops_events` stream
- Atlas 3 ─x─► second temporal engine

## What can run now (`FULL_LIVE_DEMO_READY = NO`)

Independent isolated lanes:

- AT3-002 / 003 / 004 / 005 / 014 / 015 / 030 / 050
- AT3-035 / 036 / 039 / 040 / 041 / 042 / 044 / 047 / 048 / 049
- Chronicle remains ROADMAP_HORIZON (no runtime)

Must wait for demo terminal state before mutating:

- `knowledge_compiler.py`, `api_server.py`, `authz.py`
- `chatgpt_bridge.py`, `chatgpt_capture.py`
- `discovery.py`, `ingestion.py`
- golden demo fixtures

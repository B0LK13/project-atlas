# Atlas 2.1 — Release-critical DAG

**Backlog:** 2.1 release-critical only  
**Stop:** `PROJECT ATLAS 2.1 — LIVE PRODUCTIONIZATION COMPLETE · RELEASE CERTIFIED · CLOSEOUT VERIFIED (v2.1.0)`  
**Tip reference:** `f98be17` · `ATLAS_2_1_RELEASE_CERTIFIED=NO`

```text
                    AUTHENTIC_ESTATE_ROOT (owner)
                              |
                              v
                    AS-2.1-PILOT-AUTH-001  ---- OWNER_BLOCKED if FOUND=0
                              |                 wake: AUTHENTIC_ESTATE_ROOT_AVAILABLE
                              v
              +---------------+---------------+
              |                               |
              v                               v
     AS-2.1-SYNC-AUTH-001            AS-2.1-TWIN-AUTH-001
              |                               |
              +---------------+---------------+
                              |
                              v
                     AS-2.1-LIVE-E2E-001
                              |
                              v
                    ADV/SEC fan-out (RC)
                              |
                              v
                       AS-REL-2.1-001
                              |
                              v
                         tag v2.1.0
                              |
                              v
            ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED
```

## Parallel (non-blocking) while PILOT OWNER_BLOCKED

```text
Track B harden (API/MCP/Web/sched/L3/ADV/perf/docs)
        |
        +-- does NOT unlock SYNC/TWIN/E2E/REL
        |
OAI Responses POC (EXPERIMENTAL, NON_RELEASE_BLOCKING)
        |
Gap register / 2.2 contracts+fixtures+DAG (no 2.1-destabilizing deps)
```

## Hard rules

- No invent `.atlas-project.yaml`
- No default fixture pilot waiver for 2.1
- No whole-disk crawl
- LLM/UI/Graph ≠ authority
- Immutable `v2.0.0` untouched

## Package map

| Node | Status |
|---|---|
| PILOT-AUTH | OWNER_BLOCKED |
| SYNC-AUTH / TWIN-AUTH | BLOCKED on PILOT |
| LIVE-E2E | BLOCKED on PILOT |
| ADV/SEC RC | PARTIAL (suites exist; RC not open) |
| AS-REL-2.1-001 | NOT OPEN |

# Atlas 3.0 — Master roadmap

| Field | Value |
|---|---|
| Directive | D-191 |
| Status | **CANONICAL SUCCESSOR ROADMAP** |
| Historical inputs | `docs/master-roadmap.md`, `docs/implementation-roadmap.md`, `docs/strategy/*` |
| Demo gate | `FULL_LIVE_DEMO_READY = NO` → prepare isolated packages only |

## Waves

| Wave | Name | Intent | Unlock |
|---|---|---|---|
| A | FOUNDATION | Domain, events, temporal reuse, security, maturity | Open for isolated prep + first vertical |
| B | ENGINEERING_ESTATE | Repo/component/file/PR/commit/test/build nodes + ledger | After AT3-003 |
| C | TRUTH_GRAPH_2 | Twin relationships over Truth Core + graph | After ledger + domain |
| D | UNIVERSAL_AGENT_MEMORY | D-192 cross-LLM memory | Parallel isolated; ChatGPT first |
| E | CAUSALITY_AND_INTENT | Caused-by / decided-by / intent vs state | After Pulse + memory freshness |
| F | PROOF_AND_AUTONOMY | AGENT_PROOF + reuse orch gates | After AT3-050 contract |
| G | INTEROPERABILITY | CLI/API/Web/TUI/MCP/A2A same semantics | After contracts stabilize |
| H | PROJECT_INTELLIGENCE | Impact / stale / next honesty | After Pulse + graph |
| I | PRODUCT_EXPERIENCE | Home, Timeline, explorers, Mission CC | After data contracts |
| J | OBSERVABILITY | Twin/ledger/provider health | After ledger + connectors |
| K | ORGANIZATION_TWIN | Multi-project / org identity | After first vertical + federation honesty |
| L | ECOSYSTEM_ENTERPRISE | Third-party adapters / enterprise policy | Last; never before Pulse/Start/Proof |

## First implementation vertical (highest priority)

```text
AT3-003 ENGINEERING EVENT MODEL
     ↓
AT3-014 UNIVERSAL EVENT LEDGER
     ↓
AT3-015 ATLAS PULSE
     ↓
AT3-030 ATLAS START
     ↓
AT3-050 AGENT PROOF-OF-WORK
```

Do not start Waves K–L before this slice works.

## Parallel first memory vertical (D-192)

```text
AT3-035 Connector framework
     ↓
AT3-039 Normalization
     ↓
AT3-040 Extraction
     ↓
AT3-041 Dedup
     ↓
AT3-044 Freshness
     ↓
AT3-048 Memory search
     ↓
AT3-054 Context Compiler consume-only
     ↓
AT3-055 Ranked-context local serve
```

Provider lanes after AT3-035: AT3-036 ChatGPT (first), then AT3-037 Claude,
then AT3-038 Gemini. Privacy/security (AT3-047) runs from the start.

## Execution gate

```text
If FULL_LIVE_DEMO_READY = NO:
  prepare Atlas 3 runtime packages in src/project_atlas/atlas3/
  do not destabilize demo-critical main

If FULL_LIVE_DEMO_READY = YES:
  immediately begin AT3-003 / AT3-014 on the authorized surface
```

Current pin: **NO**. Isolated packages are prepared. Certified 2.x surfaces
are not rewritten.

## Non-goals for this roadmap

- Rebuilding Truth Core
- A second temporal engine
- Silent provider-history scraping
- UI-invented truth
- Self-authorized merge
- Claiming authentic PILOT or commercial GA

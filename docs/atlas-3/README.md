# Atlas 3.0 — Program index

| Field | Value |
|---|---|
| Directives | D-191 · D-192 · D-193 (foundation convergence) |
| Status | **FOUNDATION CONVERGENCE** — isolated contracts + first-vertical runtime |
| Current main pin | `f1b5256510cb66e037e6774aa49d753bdb7dd96f` |
| `FULL_LIVE_DEMO_READY` | **NO** |
| `MERGE_AUTHORIZATION` | **NOT_GRANTED** |
| Demo interference | **NONE INTENDED** — certified 2.x surfaces are not rewritten |

Atlas 3.0 is the successor **program**, not a rewrite of Atlas 2.x.

## Canonical documents

| Document | Role |
|---|---|
| [NORTH-STAR.md](NORTH-STAR.md) | Product north star |
| [FOUNDATION.md](FOUNDATION.md) | D-193 layer ownership + exit criteria |
| [SECURITY.md](SECURITY.md) | Foundation threat model (reviewed, not certified) |
| [chronicle/HORIZON.md](chronicle/HORIZON.md) | Chronicle remains ROADMAP_HORIZON |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Canonical stack, twin domain, reuse map |
| [MASTER-ROADMAP.md](MASTER-ROADMAP.md) | Waves A–L |
| [EPICS.md](EPICS.md) | Epic catalog |
| [DEPENDENCY-DAG.md](DEPENDENCY-DAG.md) | Package DAG |
| [MIGRATION-2X-TO-3X.md](MIGRATION-2X-TO-3X.md) | Compatibility and migration |
| [PRODUCT-EXPERIENCE.md](PRODUCT-EXPERIENCE.md) | Pulse, Start, UX targets |
| [COMPETITIVE-POSITIONING.md](COMPETITIVE-POSITIONING.md) | Differentiation |
| [ACCEPTANCE.md](ACCEPTANCE.md) | Program acceptance |
| [HISTORICAL-INPUTS.md](HISTORICAL-INPUTS.md) | 2.x documents classified as inputs |
| [PACKAGE-MATURITY.json](PACKAGE-MATURITY.json) | Per-package maturity |
| [llm-memory/](llm-memory/) | D-192 cross-LLM memory program |

## Isolated runtime

Runtime lives under `src/project_atlas/atlas3/`. It is additive.

It does **not** own or rewrite:

- `knowledge_compiler.py`
- `chatgpt_bridge.py` / `chatgpt_capture.py`
- `api_server.py` / `authz.py`
- `discovery.py` / `ingestion.py`
- `bitemporal.py` / `compat_anchor.py`

## Honesty

```text
PREP != IMPLEMENTED
DEMO_FIXTURE != AUTHENTIC_PILOT
DEMO != RELEASE
UI != CANONICAL TRUTH
MODEL OUTPUT != AUTHORITY
CONVERSATION != TRUTH CORE
GRAPH != AUTHORITY
FULL_LIVE_DEMO_READY = NO
MERGE_AUTHORIZATION = NOT_GRANTED
```

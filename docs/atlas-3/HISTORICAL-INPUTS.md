# Atlas 3.0 — Historical inputs

D-191 requires successor documents **without erasing** historical roadmaps.
Those documents remain evidence. They are not Atlas 3 authority.

| Document | Classification | Successor |
|---|---|---|
| `docs/product/CODER-ALPHA-NORTH-STAR.md` | Current **Atlas 2.x / Coder Alpha** product direction | `docs/atlas-3/NORTH-STAR.md` extends; does not erase |
| `docs/master-roadmap.md` | Level-4 historical execution planning | `MASTER-ROADMAP.md` |
| `docs/implementation-roadmap.md` | Historical Phases 0–9 | `MASTER-ROADMAP.md` + `EPICS.md` |
| `docs/backlog.md` | 1.x/2.x executable backlog | `EPICS.md` |
| `docs/atlas-2.2/` | Mixed PREP + unlocked 2.2 maturity tree | `PACKAGE-MATURITY.json` |
| `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md` | Historical 2.2 DAG | `DEPENDENCY-DAG.md` |
| `docs/strategy/ATLAS-3.0-NORTH-STAR-BACKLOG.md` | Historical §40 backlog sketch | this program |
| `docs/AS-2.0-TWIN-001.md` | Fixture-waiver twin production | twin domain in `ARCHITECTURE.md` |
| `docs/atlas-2.0/DIGITAL-TWIN.md` | Prototype / PREP sketch | `ARCHITECTURE.md` |
| `docs/AS-2.1-CHATGPT-BRIDGE-001.md` | ChatGPT export bridge (keep) | `llm-memory/` |
| `docs/AS-2.0-CHATGPT-CAPTURE-001.md` | Fixture capture (keep) | `llm-memory/` |
| `docs/AS-2.2-MEM-GOV-001.md` | PREP memory governance | `llm-memory/RECONCILIATION.md` |
| `docs/atlas-2.2/chatgpt-live/` | PREP-frozen live ChatGPT | `llm-memory/PROVIDER-MATRIX.md` |

## Rule

If a historical document and an Atlas 3 document disagree:

1. Owner directive wins.
2. Landed runtime truth on `main` wins over aspiration.
3. Atlas 3 docs win over historical planning for **future** scope.
4. Atlas 3 must not silently invalidate certified 2.x demo surfaces while
   `FULL_LIVE_DEMO_READY = NO`.

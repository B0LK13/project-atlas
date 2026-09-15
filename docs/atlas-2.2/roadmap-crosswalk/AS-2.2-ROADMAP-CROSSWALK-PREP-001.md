# AS-2.2-ROADMAP-CROSSWALK-PREP-001 — PREP → roadmap slot mapping (SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-ROADMAP-CROSSWALK-PREP-001** |
| Class | **PREP ONLY** — docs-only integration |
| Tip audited | `5e2559f096ce6e1a906ee69ded45f8393ff2310b` / TREE `2768267fa1923a3a1108f84fff9d77eae7e794fc` (`docs/atlas-2.2` at sync) |
| Scope | `docs/atlas-2.2/roadmap-crosswalk/**` + strategy roadmap cross-links |
| Production mutation | **NONE** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Close the traceability gap between the **19 landed PREP packages** (#159–#199)
indexed in [`../PREP-STATUS.md`](../PREP-STATUS.md) and the post-unlock
production slots declared in
[`docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`](../../strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md).

Before this package, the strategy roadmap listed only `AS-2.2-RET-HYBRID-001`
in its PREP table despite full package saturation through #199.

## Deliverables

| Doc | Role |
|---|---|
| [`README.md`](README.md) | Package index |
| [`CROSSWALK.md`](CROSSWALK.md) | Authoritative mapping table (PREP → roadmap slot → PR) |
| [`fixtures/crosswalk.fixture.json`](fixtures/crosswalk.fixture.json) | Docs-only rehearsal payload |
| Strategy cross-link | [`ATLAS-2.2-EXECUTABLE-ROADMAP.md`](../../strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md) PREP section refresh |

## Mapping rules

1. **Direct slot** — PREP package names an explicit `AS-2.2-*-001` production
   slot in its package charter (e.g. COMPAT-PIN PREP → `AS-2.2-COMPAT-PIN-001`).
2. **Feeds slot** — PREP package is an upstream sketch for a DAG consumer
   (e.g. RET-HYBRID + CTX-COMPILER → `AS-2.2-RET-CTX-001`).
3. **Enabler / peer** — PREP package has no dedicated DAG node yet; it supports
   multiple consumers or remains a charter-only enabler (e.g. MEM-GOV, DoD).
4. **Optional slot** — roadmap marks package as post-unlock optional
   (e.g. CHATGPT-LIVE).

## Hard invariants

1. **CROSSWALK ≠ UNLOCK** — mapping rows grant no implementation credit.
2. **PREP ≠ PRODUCTION** — every row remains PREP until unlock + production
   package execution.
3. **NO RUNTIME MUTATION** — no `src/project_atlas/` or `apps/` changes.
4. **FIXTURE REHEARSAL ≠ CERTIFICATION** — stub JSON sets all cert flags false.

## Explicit non-claims

- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not `ATLAS_2_1_RELEASE_CERTIFIED=YES`
- Not promotion of stub schemas to package data
- Not authentic estate PILOT / not `v2.1.0` / not `v2.2.0` certification
- Crosswalk completeness ≠ production readiness of any mapped slot

## Refresh protocol

Re-run when:

1. A new 2.2 PREP package merges before unlock, or
2. The strategy DAG adds/renames production slots, or
3. README / PREP-STATUS index lanes add rows.

Until then, this crosswalk is **saturated** at tip `e4292e8` for packages #159–#199.

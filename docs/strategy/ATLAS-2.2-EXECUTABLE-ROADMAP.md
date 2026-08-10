# Atlas 2.2 — Executable roadmap + package DAG

**Unlock:** automatic after `v2.1.0` → `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`  
**Constraint now:** architecture / contracts / fixtures / package DAG only — **no dependency-bearing 2.2 mutations that destabilize 2.1 tip**.

---

## Theme

Estate-scale **knowledge intelligence** on top of certified live 2.1 surfaces: retrieval, temporal claims, conflicts, KCI, cross-project fabric — still evidence-backed, fail-closed, LLM≠authority.

---

## Package DAG (proposed)

```text
ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED
        |
        v
AS-2.2-DOC-CHARTER-001  (charter + matrix refresh)
        |
        +--> AS-2.2-COMPAT-PIN-001 (pin to v2.1.0 anchor)
        |
        +--> AS-2.2-KF2-FABRIC-001 ----+
        |                              |
        +--> AS-2.2-RET-CTX-001 -------+--> AS-2.2-INTEL-SLICE-001
        |                              |
        +--> AS-2.2-TEMPORAL-001 ------+
        |                              |
        +--> AS-2.2-CONFLICT-UX-001 ---+
        |
        +--> AS-2.2-XPROJ-001 ---------+--> AS-2.2-ESTATE-OPS-001
        |
        +--> AS-2.2-KCI-001
        |
        +--> AS-2.2-CHATGPT-LIVE-001 (quarantine-first; optional)
        |
        v
AS-REL-2.2-001 → v2.2.0
```

---

## First READY packages (post-unlock)

| Package | Intent | Depends on |
|---|---|---|
| AS-2.2-DOC-CHARTER-001 | 2.2 charter + maturity matrix | v2.1.0 cert |
| AS-2.2-COMPAT-PIN-001 | Compatibility anchor to 2.1 release | charter |
| AS-2.2-KF2-FABRIC-001 | Estate KF inventory/projection contracts | compat pin |
| AS-2.2-RET-CTX-001 | Hybrid retrieval + context pack production path | compat pin |
| AS-2.2-TEMPORAL-001 | Validity windows / bitemporal UX receipts | compat pin |

## Explicitly deferred to 2.3/3.0

- Multi-user network collab
- Federation multi-vault
- AgentOS / continuous eval productization
- Remote provider SDKs as default-on

## Pre-unlock work allowed (now)

- This roadmap + gap register rows (P2)
- Fixture sketches under `docs/atlas-2.2/` (additive only)
- Contract stubs that do not change 2.1 runtime defaults

## Pre-unlock PREP packages (landed / in flight)

| Package | Surface | Status |
|---|---|---|
| **AS-2.2-RET-HYBRID-001** | `docs/atlas-2.2/` Hybrid Retrieval 2 arch + fixtures + benchmarks | **PREP** — no live `retrieval` / `knowledge_compiler` mutation |
| (feeds) AS-2.2-RET-CTX-001 | Production hybrid + context packs | Blocked on unlock |

## Pre-unlock work forbidden

- Merging 2.2 packages that change Core authority semantics on `main` before v2.1.0
- Relabeling experimental OAI POC as 2.2 intelligence cert

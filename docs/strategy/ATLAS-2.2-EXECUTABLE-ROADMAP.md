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

## Pre-unlock PREP packages (landed)

**19 packages** merged (#159–#199). Full PREP → roadmap slot mapping:
[`docs/atlas-2.2/roadmap-crosswalk/CROSSWALK.md`](../atlas-2.2/roadmap-crosswalk/CROSSWALK.md)
(`AS-2.2-ROADMAP-CROSSWALK-PREP-001`). Inventory snapshot:
[`docs/atlas-2.2/PREP-STATUS.md`](../atlas-2.2/PREP-STATUS.md).

| Roadmap slot (post-unlock) | Landed PREP (feeds / direct) | Status |
|---|---|---|
| `AS-2.2-DOC-CHARTER-001` | `AS-2.2-DOC-CHARTER-PREP-001` (#199) | **PREP** |
| `AS-2.2-COMPAT-PIN-001` | `AS-2.2-COMPAT-PIN-PREP-001` (#196) | **PREP** |
| `AS-2.2-KF2-FABRIC-001` | `AS-2.2-KF2-FABRIC-PREP-001` (#186) | **PREP** |
| `AS-2.2-RET-CTX-001` | `AS-2.2-RET-HYBRID-001` (#159) + `AS-2.2-CTX-COMPILER-001` (#161) | **PREP** |
| `AS-2.2-TEMPORAL-001` | `AS-2.2-TEMPORAL-UX-PREP-001` (#192) + `AS-2.2-TIME-MACHINE-001` (#168) | **PREP** |
| `AS-2.2-CONFLICT-UX-001` | `AS-2.2-CONFLICT-UX-PREP-001` (#181) | **PREP** |
| `AS-2.2-XPROJ-001` | `AS-2.2-XPROJ-CONTRACT-PREP-001` (#179) | **PREP** |
| `AS-2.2-ESTATE-OPS-001` | `AS-2.2-ESTATE-OPS-PREP-001` (#197) | **PREP** |
| `AS-2.2-INTEL-SLICE-001` | `AS-2.2-INTEL-SLICE-PREP-001` (#189) | **PREP** |
| `AS-2.2-KCI-001` | `AS-2.2-KCI-ENGINE-PREP-001` (#160) | **PREP** |
| `AS-2.2-CHATGPT-LIVE-001` *(optional)* | `AS-2.2-CHATGPT-LIVE-PREP-001` (#191) | **PREP** |

Enabler PREP (no dedicated DAG node yet): MEM-GOV (#169), DoD compiler (#170),
REALITY-LIVE (#167), REALITY-GAP (#172). Peer slot `AS-2.2-ASK2-001` fed by
RESEARCH (#171) + ASK2-DEEPEN (#188) — see crosswalk.

All PREP rows: **no live Core mutation**; production slots remain **blocked on unlock**.

## Pre-unlock work forbidden

- Merging 2.2 packages that change Core authority semantics on `main` before v2.1.0
- Relabeling experimental OAI POC as 2.2 intelligence cert

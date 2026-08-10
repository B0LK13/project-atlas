# AS-2.2-MEM-GOV-001 — Governed agent memory (PREP)

| Field | Value |
|---|---|
| Package | **AS-2.2-MEM-GOV-001** |
| Prep lane | `AS-2.2-MEM-GOV-PREP-001` |
| Branch | `feat/as-2.2-mem-gov-prep` |
| Status | **PREP ONLY** — docs / ADR / contracts / fixtures |
| Unlock | Runtime impl after `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` (post `v2.1.0`) |
| Compat posture | Must pin to `v2.1.0` via future `AS-2.2-COMPAT-PIN-001` |
| Evidence root | `D:\project-atlas-orphans\atlas-2.1-productionization-001\` |
| Tip baseline (prep open) | MAIN `f45134f` (= `origin/main` at branch cut; board tip #157) |

## Purpose

Define **governed agent memory** as an operational, evidence-backed substrate
with mandatory:

1. **Provenance** — every memory unit traces to session / event / receipt / content hash
2. **Revocation** — trust withdrawal without deleting Layer B or inventing authority
3. **Expiry** — explicit validity windows evaluated with injected `as_of` (no wall-clock `now`)
4. **Supersession** — deterministic replacement chains; no silent dual-active for one `memory_key`

Agents may **consume** memory as derived context. Memory never becomes Layer B
project authority and never bypasses secrets / quarantine / receipt gates.

## Truth boundary

```text
AGENT MEMORY ≠ LAYER B AUTHORITY
AGENT MEMORY ≠ ESTATE FACTS / ≠ PILOT
REVOKED|EXPIRED|SUPERSEDED ≠ ACTIVE RETRIEVAL
LLM TEXT ≠ MEMORY AUTHORITY
FIXTURE MEMORY ≠ AUTHENTIC ESTATE MEMORY
```

## Surfaces (prep)

| Kind | Path |
|---|---|
| Package doc | `docs/AS-2.2-MEM-GOV-001.md` (this file) |
| Architecture | `docs/atlas-2.2/mem-gov/` |
| Contract stubs | `docs/atlas-2.2/contracts/mem-gov/` |
| Fixture sketches | `docs/atlas-2.2/fixtures/mem-gov/` |
| ADR | `docs/atlas-2.2/adr/ADR-2.2-MEM-GOV-001-governed-agent-memory.md` |
| Prep test | `tests/unit/test_as_2_2_mem_gov_prep_001.py` |

## Non-claims

- Not production Python module / CLI / installed package schemas
- Not mutation of `knowledge_compiler`, Core authority, API, authz, ops receipts, L3, or web pages
- Not a replacement for AS-INT-010 tombstones or AS-INT-011 receipt revocation (related, distinct)
- Not `ATLAS_2_1_RELEASE_CERTIFIED` / not authentic PILOT PASS
- Not subjective trust scores

## Dependencies (post-unlock)

| Depends on | Why |
|---|---|
| `v2.1.0` / unlock event | Shared production surface freeze |
| `AS-2.2-DOC-CHARTER-001` | Charter + maturity frame |
| `AS-2.2-COMPAT-PIN-001` | Compatibility anchor |
| Soft: Agent OS / CTX compiler | Session binding + consume-only packaging |
| Soft: AS-INT-011 | Receipt disposition patterns (do not dual-own) |

## Related

- Strategy: `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md` (pre-unlock fixtures allowed)
- Receipt revocation: `docs/AS-INT-011-receipt-revocation.md`
- Agent OS envelope: `docs/AS-2.0-AGENTOS-001.md`
- Context packs: `docs/AS-2.0-CTX-001.md`
- Coord evidence: `AS-COORD-CYCLE-2.1-011.md` / `012` — lane `AS-2.2-MEM-GOV-PREP-001`

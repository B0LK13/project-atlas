# AS-2.2-MEM-GOV-001 — Governed agent memory (PREP)

| Field | Value |
|---|---|
| Package | **AS-2.2-MEM-GOV-001** |
| Class | **PREP** (SAFE pre-`v2.1.0`) |
| Maturity target (post-unlock) | Operational governed memory plane (consume-only) |
| Current maturity | CONTRACT / FIXTURE sketches only |
| Owned surface (prep) | `docs/atlas-2.2/mem-gov/**`, `docs/atlas-2.2/contracts/mem-gov/**`, `docs/atlas-2.2/fixtures/mem-gov/**`, `docs/atlas-2.2/adr/ADR-2.2-MEM-GOV-001-*` |
| Excluded surface | `src/project_atlas/**`, `src/atlas_contracts/**`, production schemas, CLI wiring, Core authority |
| Directive | `D-PROJECT-ATLAS-FORCED-MULTIAGENT-ORCHESTRATION-001` |
| Evidence | `atlas-2.1-productionization-001` |

## Objective

Govern **agent-held memory** so that every unit is:

- **Provenanced** — hash + receipt/event/session pointers
- **Revocable** — operator / skill_policy / integrity withdrawal
- **Expirable** — explicit windows; as-of evaluation only
- **Supersedable** — deterministic chains on `memory_key`

without ever promoting memory into Layer B project authority.

## Lifecycle (normative intent; not runtime yet)

```text
write → active
         ├─ revoke      → revoked     (terminal for retrieval)
         ├─ expire      → expired     (as_of past expires_at)
         └─ supersede   → superseded  (replaced by newer memory_id)
```

Only `status=active` and not past expiry (at injected `as_of`) may enter
consume-only retrieval / context packaging.

## Truth boundary

`AGENT MEMORY ≠ LAYER B AUTHORITY / ≠ PILOT / ≠ ESTATE FACTS`

## Deliverables in this PREP

| Artifact | Path |
|---|---|
| Architecture | [`ARCHITECTURE.md`](./ARCHITECTURE.md) |
| Contract index | [`CONTRACT.md`](./CONTRACT.md) |
| ADR | [`../adr/ADR-2.2-MEM-GOV-001-governed-agent-memory.md`](../adr/ADR-2.2-MEM-GOV-001-governed-agent-memory.md) |
| Schema drafts | [`../contracts/mem-gov/`](../contracts/mem-gov/) |
| Fixtures | [`../fixtures/mem-gov/`](../fixtures/mem-gov/) |

## Non-claims (this PREP)

- Not production CLI / module under `src/`
- Not dual-ownership of AS-INT-011 receipt revocation indexes
- Not embeddings / vector memory product
- Not authentic estate PILOT evidence
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`

## Entry gate (future production package)

1. `v2.1.0` certified → unlock event fired
2. Compat pin to 2.1 anchor
3. Schema freeze review for `atlas.2.2.agent_memory.*`
4. Sole-writer ownership of future `project_atlas.agent_memory` (name TBD)
5. ADV + IV lanes scheduled; implementer cannot self-certify

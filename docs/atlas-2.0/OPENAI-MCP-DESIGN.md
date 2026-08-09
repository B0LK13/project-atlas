# Atlas 2.0 — OpenAI / MCP design notes (**PROTOTYPE / PREP**)

Status: **PREP ONLY** — `ATLAS_2_0_IMPLEMENTATION_READY = NO`.
Marker: **PROTOTYPE** — not production wiring.

Design sketches for optional provider adapters (AS-2.0-PROV-001) and MCP tool
surfaces. No production semantics; no runtime wiring in Track B.

## Principles (inherit 1.0)

1. **Deterministic-first** — FR-004 classification / compilation must succeed without providers.
2. **Provenance non-bypass** — model or MCP output is quarantined until schema + provenance validation pass.
3. **Secrets non-bypass** — NFR-004 `secrets.scan_text` before any generated note or log write.
4. **Offline MVP** — disabling adapters leaves Core pipeline functional.

## OpenAI adapter sketch (not implemented)

| Concern | Prep decision |
|---|---|
| Auth | Operator-provided local secret; never commit keys |
| Output | Structured JSON only; validated against shipped schemas |
| Fail mode | Quarantine + diagnostic; never silent Layer B write |
| Determinism | Provider path excluded from golden/fixture byte-identity gates |

## MCP tool sketch (not implemented)

| Tool family | Intent | Guard |
|---|---|---|
| `atlas.vault.read_*` | Read-only vault / OBS / index consume | Same as `web_api` — no writers |
| `atlas.query.*` | Knowledge query plans/answers | Consume-only; UI≠canonical |
| `atlas.ops.*` | Ops health / retention reports | Operational plane; never authority |
| Forbidden | `promote`, claim compile, authority mutate | Hard deny in adapter registry |

## Explicit non-goals (Track B)

- Shipping OpenAI SDK dependency in Core
- Enabling MCP servers that write `projects/` or `state/`
- Claiming provider readiness before 1.0 release certification

## References

- `PACKAGE-CONTRACT-STUBS.md` → AS-2.0-PROV-001
- `THREAT-MODEL.md` → T-2.0-002, T-2.0-009
- ADR-008 / NFR-006 / FR-004

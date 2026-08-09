# PROTOTYPE — MCP / tool API drafts

Status: **PROTOTYPE**. Complements [OPENAI-MCP-DESIGN.md](OPENAI-MCP-DESIGN.md).
No production MCP server wiring in Core.

## Deny-by-default tool classes

| Class | Default | Notes |
|---|---|---|
| Vault read (indexes, ops health) | allow-list candidate | never authority |
| Vault write / promote | **deny** | protected paths |
| Estate scan | **deny** until PILOT | no invent roots |
| Provider generate | quarantine lane | provenance required |

## Draft tool names (non-normative)

- `atlas.ops.health.read`
- `atlas.knowledge.query.read`
- `atlas.explain.receipt.read`
- `atlas.sync.plan.dry_run` (fixture/library only)

## Importer fixture policy

See `fixtures/openai-importer/` — synthetic transcripts only; never production
credentials; secrets scan required before any future ingest path.

`ATLAS_2_0_IMPLEMENTATION_READY = NO`.

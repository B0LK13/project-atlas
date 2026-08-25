# AS-CODER-ALPHA-DISCOVERY-MCP-001 — vault-scoped discovery-report MCP

Read-only MCP wrap over the existing LIVE_API estate discovery projection
(`GET /v1/discovery`). This reads a persisted report. It does **not** scan
the filesystem and is **not** `atlas.estate.scan`.

Package ID: `AS-CODER-ALPHA-DISCOVERY-MCP-001`.
Tool ID: `atlas.discovery.read`.

## What this is

A zero-arg, vault-scoped `vault-read` MCP tool. It calls
`service.estate_discovery()` → `load_estate_discovery_view()`, which reads
`generated/ops/estate-discovery-report.json` when present.

It does **not**:

- run `atlas discover` or `atlas.estate.scan`
- invent authorized roots when the report is absent
- treat `volume_root_authorized=true` as owner authority
- set `OWNER_CAPABILITY_GRANTED` or `AUTHENTIC_PILOT`
- accept root / path / write / args keys
- mutate the vault
- implement D-149 or touch authentic-estate gates

## Honesty

- `DISCOVER != INGEST != TRUST != AUTHORITY`
- `REPORT ABSENT != INVENTED ROOTS`
- `VOLUME ROOT != OWNER`
- `MCP != AUTHORITY`
- `OWNER_CAPABILITY_GRANTED = false`
- `AUTHENTIC_PILOT = false`

## Tests

```bash
PYTHONPATH=src python -m pytest \
  tests/unit/test_as_coder_alpha_discovery_mcp_001.py \
  tests/unit/test_as_2_1_mcp_adv_001.py
```

## Stop condition

```text
IMPLEMENTATION COMPLETE — INDEPENDENT IV REQUIRED
DO NOT SELF-CERTIFY IV IN THE SAME PASS
NO SELF-MERGE
D149_TOUCHED=NO
```

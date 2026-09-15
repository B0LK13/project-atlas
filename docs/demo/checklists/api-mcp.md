# Checklist — API / MCP E2E (AS-DEMO-2.1-001 / D06)

Operator checklist for [`../API-MCP-E2E.md`](../API-MCP-E2E.md).  
Mark each box only when verified against a **DEMO_FIXTURE** vault.  
**NOT RELEASE CERTIFIED** · **NOT AUTHENTIC PILOT PASS** · **No production mutation**.

## Pre-flight

- [ ] Printed honest TECHNICAL DEMO banner
- [ ] `--vault` is DEMO_FIXTURE / `docs/demo/fixtures/**` / `fixtures/demo/**` (not authentic estate)
- [ ] Confirmed will not run vault-write, estate-scan, or Layer B mutation
- [ ] Host bind planned: `127.0.0.1` only

## LIVE_API up

- [ ] `atlas live api-serve --vault <DEMO> --host 127.0.0.1 --port 8765` started
- [ ] Listener confirmed on localhost (no non-local bind)

## `/v1/meta`

- [ ] `GET /v1/meta` → HTTP 200
- [ ] `package_id` == `AS-2.1-API-SERVER-001`
- [ ] `write_enabled` == `false`
- [ ] `live_api` == `true`
- [ ] `ops_receipts` == `true`
- [ ] `truth_boundary` present (≠ AUTHORITY / ≠ Layer-B write)
- [ ] (optional) non-local `Host` → 403
- [ ] (optional) PUT/DELETE → 405 `writes-forbidden`

## `/v1/ops/receipts`

- [ ] `GET /v1/ops/receipts?limit=50` → HTTP 200
- [ ] `package_id` == `AS-2.1-OPS-RECEIPT-ADAPTER`
- [ ] `rollup` == `unknown` and `health` == `unknown`
- [ ] `unknown_equals_healthy` == `false`
- [ ] `completion_claimed` == `false`
- [ ] `authentic_pilot` == `false`
- [ ] `release_certified` == `false`
- [ ] `authority` == `false`
- [ ] Empty or populated demo ops dirs never promoted to “healthy” / PILOT PASS
- [ ] (optional) out-of-range `limit` → 400

## MCP tools

- [ ] `GET /v1/mcp/tools` lists allow-listed read tools only; `write_tools` empty
- [ ] `atlas live mcp-invoke --tool atlas.ops.health.read` succeeds (JSON OK)
- [ ] `atlas.projects.list.read` succeeds
- [ ] `atlas.knowledge.query.read` succeeds
- [ ] `atlas.explain.receipt.read` succeeds
- [ ] `atlas.vault.write` **denied**
- [ ] `atlas.estate.scan` **denied**
- [ ] `atlas.provider.generate` **denied**
- [ ] Unknown / traversal tool ids **fail closed**
- [ ] No files under vault Layer B / protected paths mutated by MCP invokes

## Tear-down & honesty

- [ ] `api-serve` stopped
- [ ] Run notes labeled DEMO / TECHNICAL DEMO only
- [ ] Explicitly recorded: **NOT RELEASE CERTIFIED**
- [ ] Explicitly recorded: **NOT AUTHENTIC PILOT PASS**
- [ ] Did **not** wake PILOT or touch authentic estate

## Sign-off (demo lane only)

| Field | Value |
|---|---|
| Operator | |
| Date (local) | |
| Demo vault path | |
| Result | TECHNICAL DEMO candidate — pass / fail |
| Release claim | **NONE** (NOT RELEASE CERTIFIED) |
| Pilot claim | **NONE** (NOT AUTHENTIC PILOT PASS) |

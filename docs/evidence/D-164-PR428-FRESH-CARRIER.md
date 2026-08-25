# D-164 — PR #428 fresh SDK durable-host successor

**Package:** AS-ORCH-CONTINUATION-BROKER-001 (operational delta only)  
**Base:** `f0e0c979e8ead0fdad4cc51682c560299db0a074`  
**Carrier:** `feat/d164-durable-host-sdk`  
**Stale #428:** do not merge (CONFLICTING parallel broker layout)

## Still-required delta (on current SDK stack)

- `governor-service-stop` CLI + durable stop file under `sdk-runtime/`
- Supervisor singleton lock (`SERVICE_DOUBLE_START` fail-closed)
- Supervisor loop honors external stop file (graceful shutdown)
- Does **not** revive stale `broker.py` / `host_service.py` layout

## Skipped (already on main via #469/#470 + SDK)

- `continuation_broker.py`, `return_gate.py`, `cursor_bridge.py`
- `DurableAtlasSupervisor`, recovery/high-water, lease gates, cloud attribution

## Local verification

- `pytest tests/unit/test_durable_host_sdk_ops_d164.py`
- `ruff check` on touched modules

## Authority

```
MERGE_AUTHORIZATION = NOT_GRANTED
INDEPENDENT_IV = REQUIRED
CERTIFICATION = NOT_GRANTED
```

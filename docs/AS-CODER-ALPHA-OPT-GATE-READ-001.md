# AS-CODER-ALPHA-OPT-GATE-READ-001

Vault-scoped REPORT READ wrap of the existing AS-OPT-GATE-001 sealed
policy surface (`load_opt_gate_policies`).

- Surfaces: `atlas opt-gate report|show`, `GET /v1/opt-gate/report`, MCP `atlas.opt-gate.read`
- Honesty: OPT-GATE != OPT; PROMOTE_ELIGIBLE != MERGED; WAKE_GATE = CLOSED
- Never runs an experiment, seals an envelope, or wakes Atlas-OPT
- MERGE_AUTHORIZATION = NOT_GRANTED

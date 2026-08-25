# AS-CODER-ALPHA-MISSION-WORKSPACE-MCP-001 — mission/workspace MCP

Read-only MCP wraps over the existing LIVE_API mission/workspace compose
(`AS-2.1-WEB-MISSION-WORKSPACE-LIVE-001`). Agents can read the same
non-authoritative boards already exposed at `/v1/mission` and `/v1/workspace`.

Package ID: `AS-CODER-ALPHA-MISSION-WORKSPACE-MCP-001`.
Tool IDs: `atlas.mission.read`, `atlas.workspace.read`.

## What this is

Zero-arg, vault-scoped `vault-read` MCP tools. They call
`build_mission_view` / `build_workspace_view` and overlay fail-closed honesty:

- `authentic_pilot = false`
- `pilot_estate_rows = []`
- `owner_capability_granted = false`
- `ui_canonical = false`

A `generated/ops/pilot` directory may be *present* as an ops surface flag.
It does **not** become AUTHENTIC_PILOT or owner authority.

It does **not**:

- invent PILOT estate rows
- accept project / path / write / args keys
- mutate the vault
- implement D-149 or touch authentic-estate gates
- grant owner capability from filesystem presence

## Honesty

- `UI != CANONICAL_TRUTH`
- `MCP != AUTHORITY`
- `DEMO_FIXTURE != AUTHENTIC_PILOT`
- `OWNER_CAPABILITY_GRANTED = false`
- `AUTHENTIC_PILOT = false`

## Tests

```bash
PYTHONPATH=src python -m pytest \
  tests/unit/test_as_coder_alpha_mission_workspace_mcp_001.py \
  tests/unit/test_as_coder_alpha_roadmap_mcp_001.py \
  tests/unit/test_as_2_1_mcp_adv_001.py \
  tests/unit/test_as_2_1_web_mission_workspace_ux.py
```

## Stop condition

```text
IMPLEMENTATION COMPLETE — INDEPENDENT IV REQUIRED
DO NOT SELF-CERTIFY IV IN THE SAME PASS
NO SELF-MERGE
D149_TOUCHED=NO
```

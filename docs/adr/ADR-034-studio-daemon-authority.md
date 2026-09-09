# ADR-034 — Studio is projection; daemon/coordination is authority

**Status:** accepted for AS-STUDIO-A0-001 (lane implementation; not merge authority)
**Date:** 2026-09-09
**Package:** `AS-STUDIO-A0-001`
**Supersedes:** none (ADR-006 remains GitHub repository governance baseline)

## Design laws

```text
STUDIO_UI != AUTHORITY
ATLAS_DAEMON = AUTHORITATIVE_RUNTIME
UI_STATE = PROJECTION_OF_ATLAS_TRUTH
NO_CLI_TEXT_PARSING_AS_PROTOCOL
NO_WHOLESALE_CORE_REWRITE
REUSE_BEFORE_REIMPLEMENT
MODEL_PROVIDER != ATLAS_ARCHITECTURE
STUDIO_CRASH != AGENT_TASK_TERMINATION
```

## Context

Atlas Studio (#746) needs a desktop/CLI projection shell over Atlas truth.
The repository already has Truth Core (`src/project_atlas/`), coordination
Features 1–16 (`scripts/atlas_dag/`), control plane
(`atlas-vault-documentation/`), and read-only LIVE_API/MCP surfaces.
A0 must fix the authority boundary before Mission Control productization (A1).

## Decision

1. **Studio is a projection**, never canonical truth or mutation authority.
2. **Authoritative runtime** is the Atlas daemon / coordination control plane
   (and Core vault writers where applicable) — not the Studio UI process.
3. **Typed contracts only:** `ATLAS_STUDIO_SNAPSHOT_V1` and
   `ATLAS_STUDIO_EVENT_V1` (observation). No CLI text parsing as protocol.
4. **Reuse F1–F16 builders programmatically** (`build_global_control_view`,
   `build_coordination_telemetry`, etc.). Do not reimplement eligibility.
5. **Studio process exit must not terminate daemon-owned agent tasks.**

## Consequences

- A0 RO slice grants zero writes (`AUTHZ-BOUNDARY.md`).
- Knowledge/Improvement planes attach later without replacing A0/A1 contracts
  (`MIGRATION-POLICY.md`).
- Threats of UI escalation, CLI scraping, stale-cache-as-truth, crash-kills-
  agents, and secret exfil via UI are first-class (`THREAT-MODEL.md`).

## Honesty

```text
PREP != IMPLEMENTED for later Studio phases
DEMO != RELEASE
UI != CANONICAL TRUTH
MODEL OUTPUT != AUTHORITY
MERGE_AUTHORIZATION = NOT_GRANTED by this ADR alone
```

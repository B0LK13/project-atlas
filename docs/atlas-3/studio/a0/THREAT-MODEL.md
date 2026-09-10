# AS-STUDIO-A0-001 — threat model (Studio / daemon boundary)

```text
STUDIO_UI != AUTHORITY
ATLAS_DAEMON = AUTHORITATIVE_RUNTIME
UI_STATE = PROJECTION_OF_ATLAS_TRUTH
NO_CLI_TEXT_PARSING_AS_PROTOCOL
STUDIO_CRASH != AGENT_TASK_TERMINATION
```

Scope: A0 Linux RO slice and the lasting Studio↔daemon boundary. Not a
full product security certification (`EXTERNAL_SECURITY_REVALIDATION_REQUIRED`
remains YES at program level).

## Assets

| Asset | Owner of truth |
|---|---|
| Vault / Truth Core claims | Core pipeline + human review |
| Coordination DAG / leases / ownership | Daemon / `atlas_dag` + GitHub/Git authority |
| Agent task lifetime | Daemon / harness — **not** Studio process |
| Secrets / tokens | OS keychain / env / daemon isolation |
| Studio snapshot cache | Projection only; may be stale |

## Threats

### T1 — UI escalation to authority

**Threat:** Studio UI or RO CLI presents a button/API that mutates claim,
dispatch, merge, IV, or vault writes without daemon authz.

**Mitigation (A0):** Package exposes only `snapshot` / `doctor`. No mutate /
claim / dispatch / emit / merge symbols. Schema honesty:
`grants_no_mutation: true`. AutHZ doc: RO grants zero writes.

### T2 — CLI scraping as protocol

**Threat:** Studio scrapes `atlas-dag` / `atlas` human stdout and treats it
as machine truth (brittle, injectable, non-versioned).

**Mitigation:** Programmatic imports of `atlas_dag.control_view` /
`telemetry` / builders only. Honesty const
`no_cli_text_parsing_as_protocol: true`. Tests forbid subprocess-to-CLI
protocol patterns.

### T3 — Stale cache treated as truth

**Threat:** Cached Studio snapshot / events shown as live authority.

**Mitigation:** Snapshot is labeled projection; `slice_status` may be
`DEGRADED` / `UNKNOWN`; fingerprints + `generated_at_utc` present;
docs state `UI_STATE = PROJECTION_OF_ATLAS_TRUTH`. Future UI must surface
stale/offline honestly (A1 exit).

### T4 — Studio crash kills agents

**Threat:** Closing Studio or process exit signals kill daemon-owned
agent tasks / worktrees.

**Mitigation:** Contract `STUDIO_CRASH != AGENT_TASK_TERMINATION`. A0 package
contains **no** daemon kill / task terminate APIs. Tests assert absence of
such symbols. Task lifetime belongs to authoritative runtime.

### T5 — Secret exfiltration via UI

**Threat:** Projection surfaces dump secrets, tokens, or redacted evidence
into Studio JSON / logs.

**Mitigation:** Reuse coordination builders that already quarantine/redact
at source layers; A0 snapshot carries panel summaries only; no new secret
channels. Future UI must not log raw credentials. Align with Core
`secrets.py` / NFR-004 when attaching Knowledge surfaces.

### T6 — Model-provider coupling

**Threat:** Choosing OpenAI/Anthropic/local as “the architecture.”

**Mitigation:** Law `MODEL_PROVIDER != ATLAS_ARCHITECTURE`. A0 has no
provider adapter surface.

## Residual risk (honest)

A0 is a spike: live GitHub path depends on `gh` auth. When unavailable,
slice must fail closed with honest `UNKNOWN`/`DEGRADED`, not invent DAG
truth. Desktop shell (A1+) expands attack surface and needs its own review.

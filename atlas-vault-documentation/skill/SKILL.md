# Atlas Documentation Control Skill

This is the canonical executable governance contract for managed Atlas agents.

Before governed work, load and verify this file through `atlas-agent preflight`.
Use `atlas-agent document` for meaningful implementation, decision, validation,
blocker and completion events. Do not write directly to canonical Atlas state or
generated project pages. A session may report success only after a validated
`atlas-agent-session` receipt exists. If the shared Vault is unavailable, use
the explicitly approved spool and report partial synchronization.

Required lifecycle:

```text
bootstrap → preflight → session-start → work milestones → validation
→ completion → postflight → receipt → close
```

Generated adapters are derived from this file and must never be edited directly.

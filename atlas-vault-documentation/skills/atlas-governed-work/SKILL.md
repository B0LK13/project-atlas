---
name: atlas-governed-work
description: Execute Atlas-governed coding, documentation, research, and orchestration work through verified bootstrap, evidence events, strict validation, and receipt-gated completion. Use whenever an agent changes a managed project or must report governed work.
---

# Atlas governed work

Use this skill as the operational contract for a managed session. The bootstrap shim only locates this skill; the skill supplies the lifecycle and failure rules.

## Before changing anything

Run, in order:

```text
atlas-agent bootstrap --project-root <root> --json
read the returned skill path completely
atlas-agent acknowledge-skill --session current --json
atlas-agent capability-check --session current --json
atlas-agent status --json
```

Stop if bootstrap, acknowledgement, or capability check fails. Do not infer project, Vault, session, skill, or work-package identity from a path or conversation. Use the returned values.

## Governed lifecycle

The launcher records `session-start`. Use the single event command for all other meaningful work:

```bash
atlas-agent document --type implementation --summary "..." --work-package <id>
atlas-agent document --type decision --summary "..." --work-package <id>
atlas-agent document --type validation --summary "..." --work-package <id>
atlas-agent document --type blocked --summary "..." --work-package <id>
atlas-agent document --type completion --summary "..." --work-package <id>
```

Record implementation milestones, material decisions, validation commands and outcomes, blockers, and completion limitations. Do not record every command or private reasoning. Never call normalization, verification, or routing internals to document work; `atlas-agent document` owns that order and provenance.

Before completion:

```text
run required validation
document the validation result and residual risks
document completion
atlas-agent validate --session current --strict --json
atlas-agent receipt --session current --json
atlas-agent postflight --session current --strict --json
```

Report success only when postflight succeeds and the receipt is valid. A pending spool is not completion under strict mode.

## Evidence and safety rules

- Keep raw evidence immutable; never edit it to force verification.
- All canonical Atlas writes go through the Atlas command surface and router.
- Never write directly to protected `projects/*/events`, `routing/state`, `routing/receipts`, `relationships/state`, `relationships/nodes`, or `relationships/edges` paths.
- Preserve provenance, stable identities, source hashes, and generated-region boundaries.
- Treat unknown information as `unknown`; do not invent claims or elevate derived data above source evidence.
- Do not place secrets in events, summaries, logs, receipts, or generated pages.

## Failure recovery

Capture, normalization, verification, or routing failure means the work is not documented successfully. Preserve raw evidence, record a safe blocker when possible, and retry through the command surface. Never bypass a failed stage or manually repair machine state.

If the Vault is unavailable, use only the approved spool and report synchronization pending. If neither Vault nor spool is available, fail closed. For receipt failure, inspect missing mandatory events and pipeline accounting; never fabricate a receipt.

## Capability levels

The capability check reports the actual level: Level 0 read-only advisory; Level 1 event/documentation capable; Level 2 governed implementation; Level 3 supervising/delegating. Do not claim a capability that the preflight did not grant. Subagents must be independent sessions or explicitly represented by a supervising agent.

## Progressive references

Load [COMMANDS.md](COMMANDS.md) for command details, [EVENT-TYPES.md](EVENT-TYPES.md) for event fields, [FAILURE-RECOVERY.md](FAILURE-RECOVERY.md) for recovery cases, and [RECEIPT-CONTRACT.md](RECEIPT-CONTRACT.md) for receipt validation. Examples are under `examples/`.

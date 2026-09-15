# Managed Atlas Agent Bootstrap

Governed work in this repository uses the universal control surface:

```bash
python atlas-vault-documentation/scripts/atlas_agent.py doctor --project-root . --json
python atlas-vault-documentation/scripts/atlas_agent.py run --agent generic --project-root . --task-id AS-CTRL-001 -- <command>
```

The launcher verifies `.atlas/project.yaml`, the logical Vault identity,
`atlas-vault-documentation/skill/SKILL.md`, its manifest hash, and the generated
instruction adapters before creating a session-start event. Meaningful work is
documented with `atlas-agent document` (or the equivalent script invocation).
Postflight requires session-start, validation and completion events plus a
complete capture/normalize/verify/route pipeline before issuing an
`atlas-agent-session` receipt.

The canonical skill is the only source for generated adapters. Verify drift with:

```bash
python atlas-vault-documentation/scripts/atlas_agent.py verify-instructions --json
```

If the shared Vault is unavailable, preflight may use the repository's approved
`.atlas-spool`; strict completion remains blocked until synchronization.

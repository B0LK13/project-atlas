# mda-cli Integration Guide

## Skill resolution

```bash
mda --skill atlas-vault-documentation <raw-event>
mda --skill-dir <skill-directory> <raw-event>
MDA_SKILL=atlas-vault-documentation mda <raw-event>
MDA_SKILL_DIR=<skill-directory> mda <raw-event>
```

## External installation targets

```text
~/.claude/skills/atlas-vault-documentation/
~/.cursor/skills/atlas-vault-documentation/
```

Explicit `--skill-dir` is the most deterministic repository-local option.

## Output mode

Raw source events are immutable:

- never use `--in-place`;
- use sibling output or an output directory;
- route normalized output only after validation.

## Operational controls

Use dry-run before batches. When available, retain JSON-lines telemetry for action, changed state, input/output bytes, backup path, and failure details.

The local scripts follow the mda-cli helper-script convention and may also be run directly for deterministic capture and validation.

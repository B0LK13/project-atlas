# Normalization Architecture

How one raw Atlas agent event becomes a verified, provenance-backed
normalized `Agent Work Event` (roadmap Phase 3, AS-WP-002).

## Pipeline

```text
raw event (immutable)
   |
   v
validate raw event (check_documentation rules)
   |
   v
build deterministic mda-cli argument array
   |
   v
snapshot output location
   |
   v
run mda-cli (no shell, timeout, bounded retries, redacted capture)
   |
   v
discover output (exactly one expected file)
   |
   v
verify output (untrusted until proven)
   |
   v
inject atlas_provenance frontmatter block (atomic replace)
   |
   v
structured result (JSON contract) or structured failure record
```

Guarantees:

- raw evidence is never modified (FR-S005, AS-009);
- `--in-place` is never passed to mda-cli;
- success requires verification, not merely exit code 0;
- every failure leaves a structured, secret-redacted record;
- argument arrays only — no shell string is ever constructed.

## Components

| Module | Responsibility |
|---|---|
| `scripts/normalize_event.py` | CLI, settings resolution, exit codes |
| `internal/normalization.py` | orchestration, command building, output discovery, failure records |
| `internal/process_runner.py` | untrusted process execution, timeout, retries, redaction, failure classification |
| `internal/verification.py` | output verification and root/snapshot checks |
| `internal/provenance.py` | streaming SHA-256, provenance model, frontmatter injection, atomic replace |

## Output modes

- **sibling:** `<raw-stem>.normalized.md` next to the raw event;
- **directory:** `<output-dir>/<raw-stem>.normalized.md` via mda-cli's
  `--output-folder`.

The expected output must not exist beforehand (normalization never
overwrites). After the run, the watched directory must contain exactly
one new file — the expected one.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | normalized (or normalization disabled by configuration) |
| 2 | usage error: invalid arguments, unsafe provider/skill names, configuration errors |
| 3 | operational: unsafe path, symlink escape, pre-existing output, missing raw file, I/O |
| 4 | normalization failure: executable missing, permission denied, timeout, provider/non-zero exit, missing output, invalid raw event |
| 5 | verification failure: output produced but failed verification |

## Failure taxonomy

| Category | Exit | Retryable | Evidence |
|---|---|---|---|
| `executable-missing` | 4 | no | failure record |
| `permission-denied` | 4 | no | failure record |
| `timeout` | 4 | yes (bounded) | failure record with attempts |
| `process-failed` | 4 | yes (bounded) | failure record, redacted stderr |
| `missing-output` | 4 | no | failure record |
| `invalid-raw-event` | 4 | no | failure record with validation problems |
| `output-exists` | 3 | no | failure record; nothing overwritten |
| `unsafe-path` | 3 | no | error message (redacted) |
| `verification-failed` | 5 | no | failure record with problem list |

Failure records are written next to the raw event as
`<raw-stem>.normalization-failed.json` and contain: event ID, category,
redacted message, command (unless `record_command: false`), timestamp.
They never contain secret values.

When verification fails, the unverified artifact is left in place for
inspection; rerunning is fail-closed (`output-exists`) until a human
removes or quarantines it.

## Verification rules

1. expected output exists and is readable UTF-8;
2. output resolves inside the allowed root;
3. no unexpected new files in the watched directory;
4. frontmatter parses and declares `type: Agent Work Event`;
5. document references `agent-event:<raw-event-id>`;
6. document carries `source:agent-event:<raw-event-id>`;
7. no secret-shaped content.

## Troubleshooting

- **`executable-missing`** — install mda-cli or set `--mda-command` /
  `ATLAS_MDA_COMMAND` / `normalization.command`.
- **`timeout`** — raise `normalization.timeout`; check provider health.
  Transient failures can be retried with `normalization.retries`.
- **`missing-output`** — mda-cli exited 0 without writing; inspect its
  version and output-mode support (`--dry-run` shows the plan).
- **`verification-failed`** — read the `problems` list in the JSON
  payload or failure record; quarantine the unverified artifact before
  rerunning.
- **`output-exists`** — a previous run left an artifact; inspect, then
  remove or archive it deliberately.
- **provider name rejected** — use simple identifiers
  (`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`).

Use `--dry-run --json` to inspect the fully resolved command, output
path, root, and provider without executing anything.

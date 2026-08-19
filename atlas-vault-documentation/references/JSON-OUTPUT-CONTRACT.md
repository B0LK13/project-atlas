# JSON Output Contract

Machine-readable output of the helper scripts when `--json` is passed.
Both scripts write exactly one JSON object to stdout. Usage errors
(invalid arguments, missing required settings, unreadable configuration)
are **not** JSON: they print `ERROR: ...` to stderr and exit `2`.

## `capture_event.py`

### Success (exit 0)

```json
{
  "ok": true,
  "event_id": "AE-20260801T100000Z-project-atlas-ab12cd34",
  "path": "/vault/sources/agent-events/2026/08/01/AE-20260801T100000Z-project-atlas-ab12cd34.md",
  "sync_state": "captured",
  "normalization_state": "pending",
  "bytes": 1450
}
```

| Key | Type | Meaning |
|---|---|---|
| `ok` | boolean | always `true` on success |
| `event_id` | string | stable event ID (explicit or generated) |
| `path` | string | absolute path of the written raw event |
| `sync_state` | string | `captured` (vault) or `pending` (spool) |
| `normalization_state` | string | always `pending` at capture time |
| `bytes` | integer | UTF-8 byte length of the written file |

### Operational failure (exit 3)

```json
{ "ok": false, "error": "event already exists: /vault/..." }
```

Exactly the keys `ok` and `error`. Error messages are secret-redacted.
Exit `3` covers I/O failures, unsafe paths, and duplicate event IDs
(fail closed, AS-004). Usage errors exit `2` without a JSON payload.

## `check_documentation.py`

### Result (exit 0 or 1)

```json
{
  "ok": false,
  "files_checked": 3,
  "raw_checked": 2,
  "normalized_checked": 1,
  "pending_spool": 1,
  "errors": ["1 unsynchronized spool event(s)"]
}
```

| Key | Type | Meaning |
|---|---|---|
| `ok` | boolean | `true` when `errors` is empty |
| `files_checked` | integer | unique event files validated |
| `raw_checked` | integer | raw event sources validated with raw rules |
| `normalized_checked` | integer | `*.restructured.md` (current mda-cli 0.2.9) and leftover `*.normalized.md` fixtures validated with normalized rules |
| `pending_spool` | integer | `.atlas-spool/*.md` files found |
| `errors` | string[] | human-readable findings, never secret values |

Raw events (`Agent Work Event Source`) and normalized events
(`Agent Work Event`, suffix `.restructured.md` for mda-cli 0.2.9, plus
leftover `.normalized.md` fixtures) are validated with distinct rule
sets; raw-only constraints are never applied to normalized output.

Exit `0` when `ok` is true, `1` otherwise. In strict mode
(`--strict`, `ATLAS_STRICT=true`, or
`validation.fail_completion_on_unsynced_spool: true`) pending spool
events produce an error and exit `1` (AS-007).

## `normalize_event.py`

### Success (exit 0)

```json
{
  "ok": true,
  "event_id": "AE-20260801T100000Z-project-atlas-ab12cd34",
  "status": "normalized",
  "raw_event": "/vault/sources/agent-events/2026/08/01/AE-....md",
  "normalized_event": "/vault/sources/agent-events/2026/08/01/AE-....restructured.md",
  "category": null,
  "message": "normalized and verified",
  "attempts": 1,
  "duration_seconds": 1.234,
  "problems": [],
  "provenance": { "schema_version": 1, "raw_event_id": "AE-...", "...": "..." }
}
```

`status` is `normalized`, `disabled` (normalization turned off in
configuration, exit 0), or `dry-run` (plan only, nothing executed).
`provenance` follows `references/PROVENANCE.md` and is present on
successful normalization.

### Failure (exit 3, 4, or 5)

Same payload without `provenance`; `category` identifies the failure
(see `docs/NORMALIZATION.md` failure taxonomy), `message` is
secret-redacted, and `problems` lists verification findings when
`category` is `verification-failed`. A structured failure record is
also written next to the raw event as
`<raw-stem>.normalization-failed.json`.

### Normalization settings resolution

| Setting | Environment | Config key (`normalization.*`) | Default |
|---|---|---|---|
| mda-cli executable | `ATLAS_MDA_COMMAND` | `command` (explicit config only; ignored from upward discovery — CODEX-SEC-021) | `mda` |
| mda-cli digest binding | — | `command_sha256` (required for absolute `command` in explicit config) | — |
| skill name | `ATLAS_SKILL` | `skill_id` | `atlas-vault-documentation` |
| skill directory | `ATLAS_SKILL_DIR` | `skill_dir` | this repository's skill dir |
| provider name | `ATLAS_PROVIDER` | `provider` | `unknown` |
| timeout (seconds) | `ATLAS_NORMALIZATION_TIMEOUT` | `timeout` | `120` |
| retries | `ATLAS_NORMALIZATION_RETRIES` | `retries` | `0` |
| output mode | `ATLAS_OUTPUT_MODE` | `output_mode` | `sibling` |
| output directory | `ATLAS_OUTPUT_DIR` | `output_directory` | none |
| verification | — | `verify` | `true` |
| enabled | — | `enabled` | `true` |
| record command | — | `record_command` | `true` |

`fail_on_warning` and `keep_raw` are accepted in configuration for
forward compatibility; `keep_raw` is not optional behaviorally because
raw evidence is always immutable.

## Configuration and environment

Both scripts resolve settings with precedence
**CLI > environment > config file > default**.

| Setting | Environment | Config key |
|---|---|---|
| vault root | `ATLAS_VAULT` | `atlas.vault` |
| spool root (capture destination) | `ATLAS_SPOOL` | `atlas.spool` |
| spool root (check scan root) | `ATLAS_SPOOL_ROOT` | `atlas.spool_root` |
| project ID | `ATLAS_PROJECT_ID` | `atlas.project_id` |
| project slug | `ATLAS_PROJECT_SLUG` | `atlas.project_slug` |
| agent identity | `ATLAS_AGENT` (alias: `ATLAS_AGENT_ID`) | `agent.id` |
| session ID | `ATLAS_SESSION_ID` | `agent.session_id` |
| work package | `ATLAS_WORK_PACKAGE` | `agent.work_package` |
| repository | `ATLAS_REPOSITORY` | `agent.repository` |
| branch | `ATLAS_BRANCH` | `agent.branch` |
| commit | `ATLAS_COMMIT` | `agent.commit` |
| strict spool gate | `ATLAS_STRICT` | `validation.fail_completion_on_unsynced_spool` |

Config discovery searches the working directory and its parents for
`atlas-agent.yaml`, `.atlas-agent.yaml`, or `.atlas/agent.yaml` unless
`--config` or the `ATLAS_AGENT_CONFIG` environment variable is given.
An explicitly named file must exist. The parser supports a documented
YAML subset (two-level key/value maps, scalars, comments); anything
else fails with a clear error (exit `2`).

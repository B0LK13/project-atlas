# Normalized Event Provenance

Every normalized document carries an `atlas_provenance` frontmatter
block so a reviewer can answer, automatically: which raw event produced
this, with which command, version, provider, and output mode, and
whether the output was verified.

## Fields

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | int | provenance schema version (currently `1`) |
| `normalization_version` | string | implementation version of the normalizer |
| `raw_event_id` | string | stable ID of the originating raw event |
| `raw_event_hash` | string | `sha256:<hex>` of the raw event at normalization time |
| `normalized_at` | string | ISO-8601 UTC timestamp |
| `tool` | string | executable that produced the output (e.g. `mda`) |
| `command_version` | string | `tool --version` output, or `unknown` |
| `command_arguments` | string | JSON array of the exact argv (absent when `record_command: false`) |
| `skill` | string | skill name or skill directory used |
| `provider` | string | configured provider name, or `unknown` (never credentials) |
| `output_mode` | string | `sibling` or `directory` |
| `verification_status` | string | `verified` or `skipped` |
| `verified_at` | string | ISO-8601 UTC timestamp (present when verified) |

## Example

```yaml
atlas_provenance:
  schema_version: 1
  normalization_version: "as-wp-002.1"
  raw_event_id: "AE-20260801T100000Z-project-atlas-ab12cd34"
  raw_event_hash: "sha256:9f2c..."
  normalized_at: "2026-08-01T13:05:00Z"
  tool: "mda"
  command_version: "mda 0.2.9"
  command_arguments: "[\"mda\", \"--skill-dir\", \"...\", \"...\"]"
  skill: "atlas-vault-documentation"
  provider: "unknown"
  output_mode: "sibling"
  verification_status: "verified"
  verified_at: "2026-08-01T13:05:01Z"
```

## Rules

- The raw event is hashed (streaming SHA-256) at normalization time; a
  changed hash later proves post-hoc modification of evidence.
- Provenance is injected atomically after verification; re-injection is
  idempotent (the block is replaced, not duplicated).
- Provider credentials, tokens, and environment internals are never
  recorded — only the configured provider *name*.
- The raw event itself is never modified; the link runs from the
  normalized document to the evidence, not the reverse.

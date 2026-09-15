# Atlas 3 — Privacy, consent, retention

Conversation ingestion is privacy-sensitive.

## Controls

Policy may apply at provider, account, project, conversation, message, or
attachment scope:

`INCLUDE` · `EXCLUDE` · `REDACT` · `QUARANTINE` ·
`DELETE_FROM_ATLAS_DERIVED_STORE` · `RETENTION_WINDOW`

## Defaults

```text
RAW FULL TRANSCRIPT RETENTION = MINIMIZED
```

Prefer:

- content hash
- provenance
- references
- structured extracted items

over unnecessary transcript duplication.

Do not persist secrets. Reuse `project_atlas.secrets.scan_text`
(metadata only; never matched content).

## Attachments

Files, snippets, images, documents, links, and tool results must pass
standard Atlas source safety. Do not automatically trust model descriptions
of attachments. Prefer original attachment evidence.

## Network / billing

No default network access.
No silent billing.
No secret persistence.
No automatic canonical promotion.
Live provider integration, where technically supported, is **explicit opt-in**.

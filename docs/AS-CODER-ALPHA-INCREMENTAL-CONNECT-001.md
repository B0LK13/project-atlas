# AS-CODER-ALPHA-INCREMENTAL-CONNECT-001 — Incremental reconnect

Operational skip for an unchanged `atlas connect` so a no-change reconnect
does **not** repeat full discover+ingest work.

Package ID: `AS-CODER-ALPHA-INCREMENTAL-CONNECT-001`.

## What this is

Library helpers in `project_atlas.incremental_connect` plus a hook inside
`connect_project()` (AS-CODER-ALPHA-CONNECT-001). After the inspect discover,
connect compares the **active-source fingerprint** (path + SHA-256, mtime-free)
to the committed `generated/ops/connect-manifest.json` and requires a complete
`generated/ops/connect-receipt.json`.

When both prove an unchanged state:

- ingest / rediscover / second ingest are not invoked
- derived projections are not rematerialized
- bind + connect receipt are refreshed
- a derived ops receipt is written at
  `generated/ops/incremental-connect-receipt.json`

Skip is **operational metadata only**. It is **not**:

- Truth Core authority
- a trust / confidence score
- a What Changed invention
- a reason to weaken `validate`
- a new identity / lineage layer

## Observable counters

| Counter | Meaning |
|---|---|
| `files_inspected` | Discover records examined (sources + agent events) |
| `content_changed` | Added + removed + modified active paths |
| `semantic_records_changed` | Content changes + proven renames + unproven moves |
| `physical_writes` | Canonical ingest + rematerialized projections (0 on skip) |
| `projections_regenerated` | Derived lens/brief/obsidian paths rewritten (0 on skip) |

Also recorded: `ingest_invocations`, `discover_invocations`, `disposition`.

## Dispositions

| Disposition | When |
|---|---|
| `full_compile` | First connect, or active sources changed |
| `no_change_skip` | Complete prior receipt + matching fingerprint |
| `dirty_prior_full_recompile` | Staging leftover, missing/partial/unreadable receipt, vault/root mismatch, indexes absent, option mismatch |
| `unknown_full_compile` | Rename/move cannot be proven (duplicate hashes) — UNKNOWN stays UNKNOWN |

## Fail-closed rules

- Partial or missing prior receipt → never skip
- Staging manifest present → never skip
- Shared-vault last-writer manifest for a different `source_root` → full compile
- Caller requests validate/portfolio the prior receipt did not do → full compile
- Held `ProjectIdentityLock` → `ConnectError` (existing ingest lock)
- Malformed project marker / unreadable receipt → fail closed or full recompile, never silent success
- Windows paths: `canonicalize_project_path` (backslash → POSIX). No case-fold identity lies
- Validation is still required on the full path; skip does not lower the gate

## Public helpers

| Helper | Role |
|---|---|
| `inventory_fingerprint(...)` | Mtime-free active-source digest |
| `classify_active_delta(...)` | Added/removed/modified/renamed/unknown |
| `evaluate_incremental_reconnect(...)` | Skip vs full decision |
| `write_incremental_receipt(...)` | Derived ops receipt with counters |

## CLI

No `cli.py` change. Existing `atlas connect` calls `connect_project()`.

## Tests

```bash
PYTHONPATH=src python -m pytest \
  tests/unit/test_as_coder_alpha_incremental_connect_001.py \
  tests/unit/test_as_coder_alpha_connect_001.py
```

## Stop condition

```text
IMPLEMENTATION COMPLETE — INDEPENDENT IV REQUIRED
DO NOT SELF-CERTIFY IV IN THE SAME PASS
NO SELF-MERGE
```

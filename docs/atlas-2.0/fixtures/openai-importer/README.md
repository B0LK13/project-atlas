# OpenAI importer fixtures (synthetic · harness)

Synthetic importer samples for AS-2.0-OAI-IMPORT-001. **Not** production
credentials. **Not** estate PILOT evidence. **No live API.**

| File | Purpose |
|---|---|
| `sample-chat-export.md` | Redacted chat-shaped fixture |
| `expected-fixture-receipt.json` | Structured receipt sketch after parse |
| `README.md` | This file |

## Harness

```text
atlas openai-import parse --vault <dir> --receipt-id sample-1
```

Parses `sample-chat-export.md` → `generated/ops/openai-import-fixtures/` receipt
and optionally feeds text into AS-2.0-PROV-001 quarantine (consume-only).

Rules: `secrets.scan_text` before any future ingest; quarantine on hits;
no wall-clock in golden expectations; never claim live API success.

# D-049 Wave 1 — Dogfood + Independent IV

**Directive:** D-PROJECT-ATLAS-KNOWLEDGE-ESTATE-DISCOVERY-049  
**Capability:** AS-CODER-ALPHA-KNOWLEDGE-ESTATE-DISCOVERY-001  
**PR:** #346 (`cursor/d049-knowledge-estate-discovery-d036`)  
**Tip under IV:** `3b1453a44d1c554e9cc08fbeb8cf7c28865b5ba5` (+ follow-up IV hardening commit)

## Gate context (unchanged)

```
CODER_ALPHA_ACCEPTANCE = PASS
CODER_ALPHA_ACCEPTANCE_HEAD = 072f1395ee310a876e93d633264f3ece43cecc3c
CODER_ALPHA_ACCEPTANCE_TREE = ad29628bbf7552ebe8b4a71b0192d3004129375f
D_049_EXECUTION_GATE = OPEN
D_042_EXECUTION_GATE = CLOSED
```

## Bounded estate dogfood (authorized multi-project root)

Authorized root: `/tmp/d049-dogfood-estate` containing:

- `services/billing-api` (git + pyproject + docs/ADR)
- `services/ledger` (explicit Atlas identity; vault-matched EXACT)
- `apps/console` (package.json + src + .github)
- `knowledge/research-vault` (Obsidian `.obsidian` + notes/decisions)
- ignore noise: `node_modules`, `.venv`
- symlink escape to `/tmp/d049-outside-secret`

Vault pre-seeded with `projects/ledger` + UUID allocation ownership.

### Metrics

| Metric | Value |
|---|---|
| PROJECT_DISCOVERY_RECALL | 3/3 (`billing-api`, `console`, `ledger`) |
| FALSE_PROJECT_MATCH_COUNT | 0 |
| AMBIGUOUS_MATCH_COUNT | 0 |
| EXACT_LEDGER_MATCH | EXACT |
| OBSIDIAN_FOUND | YES |
| USER_CORRECTIONS_REQUIRED | 0 |
| MANUAL_PATHS_REQUIRED | 0 (one `--root`) |
| TIME_TO_DISCOVER_PROJECTS | ~0.004s (synthetic estate) |
| UNSAFE_PATH_ESCAPES | 1 detected / 0 allowed |
| CROSS_PROJECT_LEAKS | 0 |
| SILENT_IDENTITY_MERGES | 0 |
| VAULT_MUTATED_BY_DISCOVER | NO (still only `ledger`) |

### Isolation / policy IV

| Check | Result |
|---|---|
| Home root refused | PASS |
| Filesystem root refused | PASS |
| Symlink escape not descended | PASS |
| CONFLICTING copied-UUID connect refused | PASS |
| Obsidian/knowledge connect refused (DISCOVER ≠ INGEST) | PASS |
| `node_modules` / `.venv` not project candidates | PASS |

### Explainability sample

- `ledger` WHY: atlas_project_uuid + atlas_project_id exact vault match
- `billing-api` / `console` WHY: unmatched (honest NEW / DISCOVERED; not auto-trusted)

## Real bounded fixture estate

Root: `atlas-vault-documentation/tests/fixtures`

```
REAL_PROJECTS = 9
REAL_KNOWLEDGE = 5
UNSAFE_PATH_ESCAPES = 0
NAMES include: api, documentation-rich, graphify-present, mixed-formats,
               monorepo, project-atlas, shared, sparse-readme, web
```

Discovery only — no ingest performed.

## Automated IV

```
pytest tests/unit/test_as_coder_alpha_049_estate_discovery.py  → PASS
ruff (touched) → PASS
mypy estate_discovery.py → PASS
```

GitHub CI (PR #346): ubuntu full + compat + control-plane green; windows quality pending at IV write time.

## Honesty

```
DISCOVER != INGEST != TRUST != AUTHORITY
DEMO_FIXTURE != AUTHENTIC_PILOT
WAVE1 != D049_ACCEPTANCE_COMPLETE
D_042_EXECUTION_GATE = CLOSED
```

Wave 1 is implementation + IV ready for merge review; full D-049 product acceptance still requires Local/real-estate dogfood when available.

## NEXT_ACTION

Merge-ready after Windows CI green + review. Then continue D-049 hardening/dogfood — do **not** open D-042.

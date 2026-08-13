# D-064 Overnight Metrics Summary

**Package:** AS-CODER-ALPHA-KNOWLEDGE-ESTATE-DISCOVERY-001  
**Branch tip (at refresh):** `0509287`  
**Refreshed (UTC):** 2026-08-13T20:49:29Z  
**Authenticity:** REALISTIC_CONTROLLED_DOGFOOD / SYNTHETIC_SCALE_TREES — **not** authentic user estate  

## Web build status

| Check | Command | Result |
|---|---|---|
| Typecheck | `cd apps/web && npx tsc -b` | **PASS** |
| Build | `cd apps/web && npm run build` (`tsc -b && vite build`) | **PASS** |

## Scripts refreshed

| Script | Result JSON | Exit |
|---|---|---|
| `dogfood_realistic_estates.py` | `dogfood_realistic_estates_results.json` | 0 |
| `dogfood_scale.py` | `dogfood_scale_results.json` | 0 |
| `redteam_identity_connected.py` | `identity-connected-results.json` | 0 |
| `redteam_stale_cache.py` | `redteam_stale_cache-results.json` | 0 |
| `redteam_knowledge_obsidian.py` | `redteam_knowledge_obsidian_results.json` | 0 |
| `parity_cli_api_web.py` | `parity_cli_api_web.result.json` | 0 |
| `determinism_replay.py` | `determinism_replay.result.json` | 0 |
| `corrupt_input.py` | `corrupt_input.result.json` | 0 |
| `redteam_path_security.py` (hard-counter support) | `redteam_path_security-results.json` | 0 |
| `redteam_secrets_privacy.py` (hard-counter support) | `redteam_secrets_privacy-results.json` | 0 |
| `run_path_stale_secret.py` (combined) | `path-stale-secret-results.json` | 0 |

## Discovery dogfood (realistic controlled estates A–E)

Source: `dogfood_realistic_estates_results.json` aggregate.

```
PROJECTS_EXPECTED = 15
PROJECTS_FOUND = 15
PROJECT_DISCOVERY_RECALL = 1.0 (15/15; mean estate recall 1.0)
FALSE_PROJECT_MATCH_COUNT = 0
AMBIGUOUS_MATCH_COUNT = 0
USER_CORRECTIONS_REQUIRED = 0
MANUAL_PATHS_REQUIRED = 0
TIME_TO_DISCOVER_PROJECTS = 0.014281s (sum across 5 estates)
KNOWLEDGE_EXPECTED = ≥1 (estate E min gate; A–D min 0)
KNOWLEDGE_FOUND = 7
OBSIDIAN_VAULTS_EXPECTED = ≥1 (estate E min gate)
OBSIDIAN_VAULTS_FOUND = 1
all_gates_pass = true
```

| Estate | Expected | Found | Recall | False | Ambiguous/review | Knowledge | Obsidian | Seconds |
|---|---|---|---|---|---|---|---|---|
| A distinct | 3 | 3 | 1.0 | 0 | 0 | 0 | 0 | 0.002609 |
| B monorepo | 5 | 5 | 1.0 | 0 | 0 | 1 | 0 | 0.003425 |
| C lifecycle | 3 | 3 | 1.0 | 0 | 0 | 0 | 0 | 0.002961 |
| D node_modules | 2 | 2 | 1.0 | 0 | 0 | 0 | 0 | 0.001222 |
| E mixed | 2 | 2 | 1.0 | 0 | 0 | 6 | 1 | 0.004064 |

## Scale scan seconds

Source: `dogfood_scale_results.json`.

```
SMALL_SCAN_SECONDS  = 0.01496   (~100 dirs, 3 projects)
MEDIUM_SCAN_SECONDS = 0.145524  (~1000 dirs, 8 projects)
LARGE_SCAN_SECONDS  = 0.701522  (~5000 dirs, 15 projects)
TRUNCATION_HONESTY  = PASS (max_project_candidates=5 → scan_complete=false, reason=project_limit_reached)
no_node_modules_project_candidates = true
```

## Hard counters (must stay 0 unless noted)

### Identity / connected (`identity-connected-results.json`)

| Counter | Value |
|---|---|
| FALSE_EXACT_MATCHES | 0 |
| FALSE_CONNECTED_MATCHES | 0 |
| CONNECTED_WITHOUT_DURABLE_BIND_PROOF | 0 |
| SILENT_IDENTITY_MERGES | 0 |
| PROJECT_UUID_COALESCING | 0 |
| CROSS_PROJECT_LEAKS | 0 |
| HIGH_FINDINGS | 0 (empty) |

### Path / stale / secrets (`path-stale-secret-results.json` — suite **PASS**)

| Counter | Value |
|---|---|
| UNSAFE_PATH_ESCAPES_ALLOWED | 0 |
| UNSAFE_PATH_ESCAPES_DETECTED | 1 (symlink escape ignored; outside not candidate) |
| HOME_DIRECTORY_SILENT_SCAN | 0 |
| WHOLE_DISK_SCAN | 0 |
| STALE_CACHE_TRUTH | 0 |
| CACHE_USED_FOR_SKIP_TRUE | 0 |
| SECRET_LEAKS | 0 |
| API_KEY_LEAKS | 0 |
| PEM_BODY_LEAKS | 0 |
| REMOTE_PASSWORD_ECHO | 0 |

### Knowledge / Obsidian redteam (`redteam_knowledge_obsidian_results.json`)

| Counter | Value |
|---|---|
| CROSS_PROJECT_KNOWLEDGE_LEAK | 0 |
| KNOWLEDGE_SILENT_PROJECT_ASSIGNMENT | 0 |
| OBSIDIAN_AUTO_INGEST | 0 |
| all_scenarios_pass | true |

### Parity / determinism / corrupt

| Counter | Value | Source |
|---|---|---|
| API_WEB_DISCOVERY_SEMANTIC_DRIFT | 0 | `parity_cli_api_web.result.json` |
| UI_RECLASSIFICATION | 0 | `parity_cli_api_web.result.json` |
| CANDIDATE_ID_DRIFT | 0 | `determinism_replay.result.json` |
| CATEGORY_DRIFT | 0 | `determinism_replay.result.json` |
| MATCH_STATE_DRIFT | 0 | `determinism_replay.result.json` |
| CORRUPT_IDENTITY_FALSE_MATCH | 0 | `corrupt_input.result.json` |

## Overnight gate rollup

```
WEB_TYPECHECK = PASS
WEB_BUILD = PASS
DOGFOOD_REALISTIC = PASS
DOGFOOD_SCALE = PASS
REDTEAM_IDENTITY_CONNECTED = PASS
REDTEAM_STALE_CACHE = PASS
REDTEAM_KNOWLEDGE_OBSIDIAN = PASS
PARITY_CLI_API_WEB = PASS
DETERMINISM_REPLAY = PASS
CORRUPT_INPUT = PASS
PATH_STALE_SECRET_SUITE = PASS
```

# D-064 Independent IV Report (variance-reducing)

**Role:** Independent IV reviewer (not implementer)  
**Package:** AS-CODER-ALPHA-KNOWLEDGE-ESTATE-DISCOVERY-001 / D-049 overnight (D-064)  
**Branch:** `cursor/d049-knowledge-estate-discovery-d036`  
**IV tip:** `0ffd713` (docs refresh) on production fix `0509287`  
**Invalidated freeze (HIGHs):** `9c71cc2` / tree `10539a86`  
**Date (UTC):** 2026-08-13  
**Scope:** Bounded identity / estate-discovery / connect regression + control-plane suite + overnight red-team evidence under `docs/evidence/d064-overnight/`. No production source modified by this IV.

---

## Verdict

**HIGH_OPEN = 0.** Both freeze-invalidating HIGHs are closed at tip. All required IV questions answer **NO** (fail-closed as required). Overnight hard counters remain zero.

---

## Commands run (this IV)

### Bounded Coder Alpha / D-049 identity regression

```bash
.venv/bin/python -m pytest \
  tests/unit/test_as_d049_064_high_remediation.py \
  tests/unit/test_as_d049_063_truth_hardening.py \
  tests/unit/test_as_coder_alpha_049_estate_discovery.py \
  tests/unit/test_source_identity.py \
  tests/unit/test_as_coder_alpha_057_copied_uuid.py \
  tests/unit/test_as_coder_alpha_050_d050_residuals.py \
  tests/unit/test_as_coder_alpha_connect_001.py \
  tests/unit/test_as_coder_alpha_044_d041_high.py \
  --no-cov -q
```

| Result | Count |
|---|---|
| **passed** | **96** |
| **skipped** | **1** (IPv6 `::1` dual-bind unavailable in this environment; D-044 B5) |
| **failed** | **0** |

Collected = 97. Exit code 0.

### Control-plane suite

```bash
.venv/bin/python -m pytest atlas-vault-documentation/tests/ --no-cov -q
```

| Result | Count |
|---|---|
| **passed** | **171** |
| **failed** | **0** |

Exit code 0.

### HIGH remediation re-check (tip)

```bash
.venv/bin/python docs/evidence/d064-overnight/run_path_stale_secret.py
```

Result at tip: suite **PASS**, `high_findings: 0`, all hard counters 0  
(also covered by `tests/unit/test_as_d049_064_high_remediation.py` — 3/3 pass).

---

## HIGH remediations that invalidated freeze `9c71cc2`

| Finding | Freeze `9c71cc2` evidence | Tip `0509287`+ status | Proof |
|---|---|---|---|
| **SYMLINK_LOOP_UNBOUNDED** | `path-stale-secret-results.json` (historical FAIL): `RuntimeError: Symlink loop` | **FIXED** | `_reparse_escape` catches `(OSError, RuntimeError)` → treat as escape/ignore (`estate_discovery.py`); `test_discover_estate_survives_mutual_symlink_loop`; redteam `symlink_loop.result=PASS`, `completed=true`, `hung=false` |
| **GIT_REMOTE_PASSWORD_ECHO** | historical FAIL: `https://user:SECRETKEY@…` in report | **FIXED** | `sanitize_git_remote_url` strips userinfo before fingerprints; unit test asserts planted secret absent; redteam `REMOTE_PASSWORD_ECHO=0`, `remote_sanitized=true` |

**HIGH_OPEN count: 0**

---

## Required IV questions

All answers are **NO** (required). Evidence cited from unit/red-team artifacts at tip.

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | CAN TWO DISTINCT PROJECTS BE REPRESENTED AS ONE? | **NO** | Identity redteam: `SILENT_IDENTITY_MERGES=0`, `PROJECT_UUID_COALESCING=0`; cases 02/03 CONFLICTING on id/uuid mismatch; case 08 distinct `candidate_id`s for same basename; D-057 copied-UUID fail-closed (`test_as_coder_alpha_057_copied_uuid.py`) |
| 2 | CAN ONE PROJECT SILENTLY SPLIT INTO MULTIPLE IDENTITIES? | **NO** | D-050/D-057 connect + allocation ownership; reconnect same root preserves UUID (`test_a_same_id_same_uuid_reconnect`); determinism replay `CANDIDATE_ID_DRIFT=0` across 4 runs |
| 3 | CAN A PROJECT BECOME CONNECTED WITHOUT DURABLE BIND PROOF? | **NO** | `prove_connected` requires bind/source-root ownership; EXACT match alone → `CONNECTED_WITHOUT_DURABLE_BIND_PROOF=0` (cases 01/06); vault `projects/` presence insufficient (`test_prove_connected_rejects_same_id_without_bind`) |
| 4 | CAN A STALE REPORT BYPASS CURRENT PROJECT IDENTITY? | **NO** | `connect_from_discovery` live revalidation (`estate_discovery.py` ~1867–1900); stale-cache redteam fail-closed on mutate/delete/uuid-change; `test_p13_stale_report_connect_fail_closed` |
| 5 | CAN A CACHE BECOME TRUTH? | **NO** | Report `cache_used_for_skip: false` always; incremental note: cache never authority; `STALE_CACHE_TRUTH=0`, `CACHE_USED_FOR_SKIP_TRUE=0`; `test_p11_cache_never_skips_identity` |
| 6 | CAN DISCOVERY ESCAPE THE AUTHORIZED ROOT? | **NO** | Refuse `/` and `$HOME`; symlink escape ignored (`UNSAFE_PATH_ESCAPES_ALLOWED=0`); outside path not candidate; `test_refuse_home_and_filesystem_root`, `test_symlink_escape_not_descended` |
| 7 | CAN PARTIAL DISCOVERY LOOK COMPLETE? | **NO** | `scan_complete` false + `truncation_reason` when limits/permission errors; scale dogfood truncation honesty PASS (`project_limit_reached`); human summary emits `SCAN INCOMPLETE`; `test_p10_truncation_honesty` |
| 8 | CAN PERSONAL OBSIDIAN CONTENT BE SILENTLY ASSIGNED? | **NO** | Knowledge redteam: personal vault `KNOWLEDGE_UNMATCHED`, `required_review=true`, vault projects unchanged; `KNOWLEDGE_SILENT_PROJECT_ASSIGNMENT=0`, `OBSIDIAN_AUTO_INGEST=0`; `test_p5_obsidian_not_silently_assigned` |
| 9 | CAN HEURISTIC MATCHING ELEVATE AUTHORITY? | **NO** | package/dirname → `LIKELY` not EXACT (cases 09/10); LIKELY cannot `prove_connected`; invariant `DISCOVER != INGEST != TRUST != AUTHORITY`; connect requires explicit `discover connect` + live revalidation |
| 10 | CAN DISCOVERY MUTATE CANONICAL TRUTH WITHOUT EXPLICIT CONNECT? | **NO** | `test_discover_does_not_ingest`; discover writes report/cache only; connect is separate gated path; note in connect result: discovery alone never ingests |
| 11 | CAN DISCOVERY EXPOSE CREDENTIALS THROUGH MATCH EVIDENCE? | **NO** | Git remote sanitized; secrets redteam: `SECRET_LEAKS=0`, `API_KEY_LEAKS=0`, `PEM_BODY_LEAKS=0`, `REMOTE_PASSWORD_ECHO=0`; planted password absent from report JSON |

---

## Overnight evidence rollup (supporting)

| Artifact | Status | Notable counters |
|---|---|---|
| `identity-connected-results.json` | PASS (13/13 cases) | all identity hard counters 0 |
| `path-stale-secret-results.json` | PASS | `high_findings=0` |
| `redteam_knowledge_obsidian_results.json` | PASS | silent-assign/auto-ingest 0 |
| `redteam_stale_cache-results.json` | PASS | cache-as-truth 0 |
| `determinism_replay.result.json` | PASS | drift counters 0 |
| `corrupt_input.result.json` | PASS | `CORRUPT_IDENTITY_FALSE_MATCH=0` |
| `parity_cli_api_web.result.json` | PASS | semantic drift 0 |
| `dogfood_realistic_estates_results.json` | PASS | recall 1.0, false matches 0 |
| `dogfood_scale_results.json` | PASS | truncation honesty true |
| `METRICS_SUMMARY.md` | rollup PASS | aligns with above |

---

## Remaining MEDIUM / LOW (do not invent)

**HIGH_OPEN: 0**

Observed non-blocking notes only (not product identity failures):

1. **LOW — evidence tip labeling:** red-team result JSONs still stamp `frozen_tip: "9c71cc2"` even when executed against tip that includes `0509287` remediations. Does not reopen HIGHs; recommend future scripts record `git rev-parse HEAD` at run time.
2. **LOW — knowledge taxonomy precision:** multi-project Obsidian dirname currently fail-closes as `KNOWLEDGE_UNMATCHED` (+ `required_review`) rather than a dedicated `KNOWLEDGE_AMBIGUOUS` relation (`redteam_knowledge_obsidian_results.json` scenario note). Still **not** silent assignment.
3. **ENV — skipped test:** `test_as_coder_alpha_044_d041_high.py` IPv6 `::1` dual-bind skip in this Linux environment (address family unsupported). Not counted as a D-049 identity regression.

No additional MEDIUM product defects found in the bounded IV scope.

---

## Closure statement

Independent IV at tip `0ffd713` (fix `0509287`) confirms D-064 overnight identity/path/secret/cache/knowledge invariants hold, freeze-`9c71cc2` HIGHs are remediated, and **HIGH_OPEN = 0**. Ready for Local Windows IV superseding freeze when operators record a new freeze tip; this IV does not merge and does not start D-042.

# D-064 — Local Windows D-049 IV runbook

**Directive:** D-PROJECT-ATLAS-CLOUD-D049-OVERNIGHT-064-FINAL  
**PR:** https://github.com/B0LK13/project-atlas/pull/346

## Exact tip (mandatory)

Validate **only** this superseding tip (prior `9c71cc2` is invalidated):

```
HEAD = 0509287c8915f3fe06644d5a00bcc219bd290add
TREE = 728f3af450961db00d9a310293907cd3125272f6
```

```powershell
git fetch origin cursor/d049-knowledge-estate-discovery-d036
git checkout 0509287c8915f3fe06644d5a00bcc219bd290add
git rev-parse HEAD
git rev-parse HEAD^{tree}
# must match HEAD/TREE above exactly
python -m pip install -e ".[dev]"
python -m pytest tests/unit/test_as_d049_064_high_remediation.py tests/unit/test_as_d049_063_truth_hardening.py tests/unit/test_as_coder_alpha_049_estate_discovery.py -q
```

Do **not** broad-replay historical Coder Alpha campaigns.

## Scope (Windows / adversarial only)

1. Junction / reparse escape (directory junctions pointing outside authorized root)
2. Symlink / reparse loops (must not crash; must not allow escape)
3. Windows case aliases of the same physical path (no duplicate candidates)
4. Long paths, spaces, Unicode, CJK, emoji path names
5. Multi-project estate recall (ground-truth projects found without manual path enum)
6. Same-name isolation + copied-marker isolation (never CONNECTED from marker alone)
7. Ambiguous / CONFLICTING identity matrix
8. Stale-report connect (TOCTOU fail-closed)
9. Cache never authority
10. Obsidian / personal-vault boundaries (DISCOVER ≠ INGEST; no silent assignment)
11. Ignore policy (`node_modules`, `.venv`, `.git`, `.atlas-vault`, vendor, …)
12. Partial-scan honesty (`scan_complete`, truncation reasons)
13. CLI stranger journey (`atlas discover --root …`, `--projects`, `--knowledge`, `review`, `connect`)
14. API `/v1/discovery` + Web `/discovery` semantic parity with CLI JSON
15. Credential sanitization: plant `https://user:SECRET@host/repo.git` — report must not echo password

## Hard counters (must remain 0)

```
UNSAFE_PATH_ESCAPES_ALLOWED = 0
SILENT_IDENTITY_MERGES = 0
FALSE_CONNECTED_MATCHES = 0
STALE_REPORT_AUTHORITY_BYPASS = 0
STALE_CACHE_TRUTH = 0
CROSS_PROJECT_LEAKS = 0
OBSIDIAN_AUTO_INGEST = 0
SECRET_CONTENT_ECHO = 0
API_WEB_DISCOVERY_SEMANTIC_DRIFT = 0
```

Also record:

```
WINDOWS_REPARSE_IV_REQUIRED → NO only if Local proves junction/reparse escape = 0 allowed
```

## Suggested minimal Windows estate

```
Estate\
  Alpha\          (.atlas-project.yaml + .git)
  Beta\           (package.json only)
  Archive\Alpha-copy\   (copied marker UUID from Alpha — must CONFLICT / not CONNECT)
  Notes\PersonalVault\  (.obsidian — unmatched / no auto-ingest)
  Noise\node_modules\fake-project\
  EscapeJunction\       (junction to C:\Users or outside root)
```

```powershell
atlas discover --root <Estate>
atlas discover --root <Estate> --projects
atlas discover review --vault <vault> --report <report.json>
# attempt connect from intentionally stale report after mutating Alpha UUID → must fail closed
```

## Pass / fail reporting

Return exact:

```
LOCAL_HEAD =
LOCAL_TREE =
LOCAL_MATCHES_SUPERSEDING = YES|NO
WINDOWS_REPARSE_IV = PASS|FAIL
HARD_COUNTERS =
D_049_LOCAL_IV = PASS|FAIL
```

Cloud will not invent Local evidence. Owner merge remains gated on Local PASS + Cloud HIGH_OPEN=0.

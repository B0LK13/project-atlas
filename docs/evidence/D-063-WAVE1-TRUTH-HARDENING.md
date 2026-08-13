# D-063 — D-049 Wave 1 Truth Hardening

**Directive:** D-PROJECT-ATLAS-CLOUD-KNOWLEDGE-ESTATE-DISCOVERY-063  
**PR:** #346  
**Capability:** AS-CODER-ALPHA-KNOWLEDGE-ESTATE-DISCOVERY-001

## Starting tip (not frozen)

```
STARTING_HEAD = 3b1453a44d1c554e9cc08fbeb8cf7c28865b5ba5
(+ 7eab7e2 dogfood IV commit already on branch)
```

## Hardening delivered

| Item | Result |
|---|---|
| P0 Coder Alpha contracts preserved | YES |
| P1 ID/UUID contradiction matrix | PASS (EXACT/CONFLICTING matrix + invalid UUID) |
| P2 CONNECTED = bind/source-root proof | PASS (`why_connected`; same-id different root ≠ CONNECTED) |
| P3 Governed identity SoT | PASS (allocation receipts + connect bind/manifest/receipt) |
| P4 STRONG_EVIDENCE real | PASS (live git remote/package from bind roots) |
| P5 Knowledge↔project relations | PASS (nested / Obsidian / unmatched) |
| P6 Reparse/junction safety | IMPLEMENTED (`st_file_attributes` + no-descend); Local IV marked |
| P7 Path identity / case | PASS (Linux preserve case; Win/mac casefold) |
| P8 Invalid structured input | PASS (invalid/unreadable → CONFLICTING/review) |
| P9 Ignore policy | PASS (nested node_modules fake-project excluded) |
| P10 Bounds / truncation honesty | PASS (`scan_complete` / truncation_reason) |
| P11 Cache never authority | PASS (`cache_used_for_skip=false`) |
| P12 Review actionable | PASS |
| P13 Stale report connect fail-closed | PASS |
| P14 CLI stranger UX | PASS (legacy + `--root`) |
| P15 Web/API parity | PASS (`/v1/discovery` projects report scan + evidence) |

## Dogfood (synthetic multi-project bounded estate)

Authorized root: `/tmp/d049-dogfood-estate` (repository-controlled; **not** real-user estate acceptance).

```
PROJECTS_EXPECTED = billing-api, console, ledger
PROJECTS_FOUND = billing-api, console, ledger
PROJECT_DISCOVERY_RECALL = 3/3
FALSE_PROJECT_MATCH_COUNT = 0
AMBIGUOUS_MATCH_COUNT = 0
USER_CORRECTIONS_REQUIRED = 0
MANUAL_PATHS_REQUIRED = 0
TIME_TO_DISCOVER_PROJECTS = ~0.006s
UNSAFE_PATH_ESCAPES = 1 detected / 0 allowed
CROSS_PROJECT_LEAKS = 0
SILENT_IDENTITY_MERGES = 0
STALE_CACHE_TRUTH = 0
CONNECTED_WITHOUT_BIND = 0 (ledger CONNECTED only with live bind)
OBSIDIAN = KNOWLEDGE_UNMATCHED + review required
```

Limitation: Cloud dogfood used a synthetic bounded estate, not an authentic operator knowledge estate.

## Independent IV questions

| Question | Answer |
|---|---|
| Can discovery represent two distinct projects as one? | NO |
| Can discovery label CONNECTED without durable bind evidence? | NO |
| Can a stale discovery report bypass current identity truth? | NO |
| Can discovery escape the authorized root? | NO |
| Can discovery silently turn partial scan into complete? | NO |

## Gates

```
CODER_ALPHA_ACCEPTANCE = PASS
D_049_EXECUTION_GATE = OPEN
D_049_ACCEPTANCE = NOT_YET_EVALUATED
D_042_EXECUTION_GATE = CLOSED
```

Windows-specific Local IV still required before D-049 acceptance:
junction/reparse, case aliases, long paths, Unicode/spaces, stranger CLI/Web.

# AS-CORE-004 Post-Merge Closure

**PACKAGE**: AS-CORE-004 — Semantic Subject and Status-Dimension Refinement  
**DIRECTIVE**: D-PROJECT-ATLAS-CURSOR-AS-CORE-004-MERGE-001  
**PR**: #9  
**PR #8**: OPEN AND SEPARATE (not included)

## Merge record

| Field | Value |
|-------|-------|
| BASE | `7bf974623071ac946ed542fffc84f134887eeae7` |
| AUTHORIZED HEAD | `54bcea6de7847e68a662e14bd9bbcd002e9848fe` |
| AUTHORIZED / MERGE TREE | `dc0ffa3298f9b87e62304c8cca4358b7bda2a358` |
| MERGE COMMIT | `66409289cd654ccd187496c2bc608ece79ef0527` |
| PARENT 1 | `7bf974623071ac946ed542fffc84f134887eeae7` |
| PARENT 2 | `54bcea6de7847e68a662e14bd9bbcd002e9848fe` |
| TREE EQUALITY | PASS (merge tree == authorized PR-head tree) |
| MERGE METHOD | GitHub platform merge commit |
| MERGED_AT | `2026-08-07T10:52:31Z` |
| ACCOUNT ACTOR | `B0LK13` |
| CI | run `31171093260` SUCCESS on authorized head |

## Post-merge validation workspace

| Field | Value |
|-------|-------|
| WORKTREE | `D:\atlas-worktrees\as-core-004-post-merge` |
| HEAD | `66409289cd654ccd187496c2bc608ece79ef0527` (detached `origin/main`) |
| TREE | `dc0ffa3298f9b87e62304c8cca4358b7bda2a358` |
| STATUS | clean at merge commit |

## Post-merge quality gates

| Gate | Result |
|------|--------|
| ruff | PASS |
| mypy | PASS (52 source files) |
| compileall | PASS |
| full pytest | **531 passed, 1 skipped, 0 failed** |
| CLI smoke (`atlas version`) | PASS |
| semantic-subject / schema parity / nine fixtures / duplicate-subject / migration / claim integration | PASS |

## Post-merge RAW corpus

Corpus: `D:\atlas-selfhost\post-merge-7bf9746\corpus`  
Run: `.tmp/as-core-004-post-merge-selfhost/` (gitignored)

| Metric | Value |
|--------|-------|
| FILES | 70 |
| LINES | 14,269 |
| BYTES | 641,925 |
| CANONICAL CLAIMS | 91 |
| CLAIM YIELD / 1,000 lines | 6.38 |
| COMPLETE | 64 |
| PARTIAL | 1 |
| FAILED | 0 |
| SECURITY QUARANTINES | 5 (70 discovered − 65 ingested) |
| DIAGNOSTICS | 35 |
| UNIQUE SEMANTIC SUBJECTS | 31 |
| LEGACY BARE PROJECT-ROOT SUBJECTS | 0 |

### Conflict metrics

| Metric | Value |
|--------|-------|
| CONFLICT GROUPS | 8 |
| CONFLICT EDGES | 8 |
| UNIQUE CLAIM IDS PARTICIPATING | 39 |
| TOTAL CLAIM PARTICIPATIONS | 39 |
| CLAIMS IN MULTIPLE GROUPS | 0 |
| FALSE SUBJECT/DIMENSION COLLAPSE CONFLICTS | 0 |
| REMAINING SAME-SUBJECT/SAME-DIMENSION GROUPS | 8 (authority/temporal deferred; not claimed resolved) |

### Determinism

| Check | Result |
|-------|--------|
| Dual first-run claim JSON equality | PASS |
| Claim-id digest | `312fa19c597535c7c467afe4ba52a853e881f0733f47974289079c423125fd82` |
| Settled replay (claim-id set stable) | PASS — ZERO UNEXPLAINED CANONICAL MUTATION |

## Semantic-subject contract

| Contract | Disposition |
|----------|-------------|
| GLOBAL ID_PATTERN | UNCHANGED `^[A-Za-z0-9][A-Za-z0-9._-]*$` |
| SUBJECT KEY GRAMMAR | ASCII bounded `^[0-9A-Za-z][0-9A-Za-z._-]*$` |
| UNICODE POLICY | NFC normalize before bounded ASCII validation |
| RUNTIME/SCHEMA PARITY | PASS |
| SERIALIZATION | `<kind>:<key>` |
| SOURCE PATH AS SUBJECT ID | NO |
| SOURCE DISTINCT FROM SUBJECT | YES |
| CLAIM IDENTITY V2 | UNCHANGED |

## Duplicate-subject contract

Fail-closed: ambiguous definitional identity withholds **all** claims depending on that subject (including third-party references); independent subjects continue; diagnostic accounts for total withheld claims/sources; no path/parse-order winner. Post-merge fixture PASS.

## Level disposition

| Level | Disposition |
|-------|-------------|
| LEVEL 0 | PASS |
| LEVEL 1 | PARTIAL |
| LEVEL 2 | NOT ACHIEVED |

AS-CORE-004 establishes correct semantic subject precision. It does **not** establish trustworthy current-truth resolution.

## Known limitations / Level-2 remaining gaps

1. **DOMAIN-SPECIFIC AUTHORITY** — remaining conflicting claims currently share flat `authority=maintained`.
2. **TEMPORAL SEMANTICS** — remaining groups look like lifecycle/stage histories on the same refined subject+dimension.
3. **PRODUCT-QUESTION / QUERY SEMANTICS** — deferred until current-state selection is defined.

## Post-AS-CORE-004 Level-2 recommendation (analysis only)

**Primary recommendation: TEMPORAL SEMANTICS**

Post-merge conflict inspection shows same refined subject + same dimension with incompatible values that read as successive lifecycle stages (e.g. `Planned` → `implementation-complete*` → `certified*` → `merged*`) under identical authority class. The immediate product question — which comparable claim is current, and why — is blocked first by as-of / supersession semantics. Domain-specific authority remains necessary next when source classes must outrank peers; knowledge query contract should follow once current-state selection exists.

Do not implement in this closure PR.

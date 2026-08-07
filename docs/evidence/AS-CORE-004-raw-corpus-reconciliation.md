# AS-CORE-004 RAW Corpus Reconciliation

**BASE**: `7bf974623071ac946ed542fffc84f134887eeae7`  
**CORPUS**: `D:\atlas-selfhost\post-merge-7bf9746\corpus` (70 files / 641,925 bytes)  
**VAULT RUN**: `.tmp/as-core-004-selfhost/` (gitignored)  
**RE-VERIFIED FROM IMPLEMENTATION HEAD**: `9ef79a4d4c168f525abe2a3dd550002d2fd10921`  
(`.tmp/as-core-004-final-remediation/`; dual-vault + settled replay)

## Pipeline

| Step | Exit |
|------|------|
| init | 0 |
| discover | 0 |
| ingest | 0 |
| build-indexes | 0 |
| build-portfolio | 0 |
| validate | 0 |

## Outcomes

| Metric | Pre-package | Post AS-CORE-004 |
|--------|-------------|------------------|
| COMPLETE | 64 | 64 |
| PARTIAL | 1 | 1 |
| FAILED | 0 | 0 |
| SECURITY QUARANTINES | 5 | 5 |
| DIAGNOSTIC MESSAGES | 35 | 35 |
| CANONICAL CLAIMS | 91 | 91 |
| CLAIM YIELD / 1000 lines | 6.38 | 6.38 |

## Claim reconciliation

| Class | Count |
|-------|-------|
| BEFORE | 91 |
| AFTER | 91 |
| UNCHANGED identity (subject not hashed) | majority; field refinements change some ids |
| NO UNEXPLAINED RAW EXTRACTION LOSS | yes |

Subject kinds observed: `wp`, `doc`, `adr`, `review`. Legacy project-root subjects: **0**.

## Conflict metrics (post-fix RAW self-host)

| Metric | Value |
|--------|-------|
| CONFLICT GROUPS | 8 |
| CONFLICT EDGES | 8 |
| UNIQUE CLAIM IDS PARTICIPATING | 39 |
| TOTAL CLAIM PARTICIPATIONS | 39 |
| CLAIMS IN MULTIPLE GROUPS | 0 |
| FALSE CONFLICTS FROM SUBJECT/DIMENSION COLLAPSE | 0 |
| COLLAPSED PROJECT-ROOT CONFLICT SUBJECTS | 0 |

Remaining groups are same refined subject + same dimension with incompatible values (temporal/authority deferred; not Level 2).

## Determinism

- Two independent vaults: shared canonical tree byte-identical (portfolio outputs only on vault1 by design).
- Settled replay: claim-id set digest unchanged; **ZERO UNEXPLAINED CANONICAL MUTATION**.

## Future AS-CHG note

False conflicts eliminated by modeling improvement should report as
`CONFLICT_RECLASSIFIED_BY_SEMANTIC_REFINEMENT`, not
`CONFLICT_RESOLVED_BY_NEW_EVIDENCE`. Full change contract is out of scope here.

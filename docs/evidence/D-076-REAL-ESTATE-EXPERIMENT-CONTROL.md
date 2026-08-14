# D-076 real-estate experiment control (external runs pending)

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-REAL-ESTATE-CONTROL-076`

Cloud is experiment controller and final D-049 reconciler.
Cloud does not access `D:\`. Cloud does not invent Local or Claude results.

D-075 inventory ingested in `D-076A-D075-INGEST.md`
(`CLAUDE_PROJECT_SELECTION = COMPLETE` as independent inventory).
It is not Atlas discovery evidence.

```
RUN_A_ORIGINAL_ESTATE = PENDING
CLAUDE_PROJECT_SELECTION = COMPLETE
RUN_B_OPTIMIZED_ESTATE = BLOCKED_UNTIL_RUN_A_CAPTURED
ATLAS_ORIGINAL_BASELINE_CAPTURED = NO

D_049_FINAL_ACCEPTANCE = NOT_YET_EVALUATED
AUTHENTIC_USER_ESTATE_ACCEPTANCE = NOT_EVALUATED
D_042_EXECUTION_GATE = CLOSED
PRODUCTION_MUTATION = NO
NEW_PR_CREATED = NO
```

Run A and Run B stay separate. Run B never retroactively replaces Run A.

D-049 final acceptance evaluates Atlas against the **original** estate
(Run A). Claude documentation optimization is not required for D-049 PASS.

## Authoritative technical state (re-read)

```
CURRENT_MAIN = 198350319c17b4de0665f972fda0bc51420cd686
D_049_STATE = POST_MERGE_VERIFIED
POST_MERGE_VERIFICATION = PASS
HIGH_OPEN = 0
LOCAL_EXPECTED_TARGET_MAIN = 198350319c17b4de0665f972fda0bc51420cd686
```

## Evidence preservation (do not delete)

```
EVIDENCE_BRANCH = cursor/d049-final-reconciliation-6f85
KNOWN_PRESERVED_TIP = 56127d469877df8deaa4cc8eb34743817e53afe0
```

Do not merge this branch as a competing production history.

---

## 1. Run A ingest — original authentic estate (D-049 acceptance run)

Source: Local D-073A. Fill only from Local. Do not fabricate denominators.

```
TARGET_MAIN =
AUTHORIZED_ROOT =

PROJECTS_EXPECTED =
PROJECTS_FOUND =
PROJECT_DISCOVERY_RECALL =

FALSE_PROJECT_MATCH_COUNT =
AMBIGUOUS_MATCH_COUNT =
UNMATCHED_EXPECTED_PROJECT_COUNT =

KNOWLEDGE_EXPECTED =
KNOWLEDGE_FOUND =
KNOWLEDGE_DISCOVERY_RECALL =

FALSE_KNOWLEDGE_PROJECT_ASSIGNMENTS =

MANUAL_PROJECT_PATHS_REQUIRED =
USER_CORRECTIONS_REQUIRED =

SCAN_COMPLETE =
DEPTH_LIMIT_REACHED =
TRUNCATION_CAUSES =

PATH_ESCAPES =
CROSS_PROJECT_LEAKS =
SILENT_IDENTITY_MERGES =
SILENT_KNOWLEDGE_MISASSIGNMENT =

SECRET_CONTENT_ECHO =
CREDENTIAL_ECHO =

TIME_TO_DISCOVER_PROJECTS =

DISCOVERY_OUTPUT_UNDERSTANDABLE =

NEW_HIGH =
HIGH_OPEN =

KNOWN_EXPECTED =
UNKNOWN_EXPECTED =

D049_AUTHENTIC_ESTATE_ACCEPTANCE =
```

If ground truth is incomplete, leave `UNKNOWN_EXPECTED` set and do not
compute a false-precision recall percentage.

Hard gates for CASE A remain those in `D-074-AUTHENTIC-ACCEPTANCE-MATRIX.md`
(authorized root, zero escapes/leaks/silent merges/secret echo, HIGH=0,
honest UNKNOWN, no manual project-path enumeration).

---

## 2. Claude selection schema (independent inventory, not Atlas evidence)

```
SELECTED_PROJECTS =
DOCUMENTATION_BASELINE =
WHY_SELECTED =
DOCUMENTATION_CONDITION =
EXPECTED_ATLAS_CHALLENGE =
```

Claude qualitative assessment is a second perspective. It is not Atlas
discovery evidence and cannot substitute for Run A.

---

## 3. Project cross-check (only after Run A + Claude selection exist)

Compare `PROJECTS_CLAUDE_EXPECTED` vs `PROJECTS_ATLAS_FOUND`.

Each disagreement classifies as exactly one of:

```
TRUE_ATLAS_MISS
ATLAS_VALID_EXTRA_DISCOVERY
CLAUDE_INVENTORY_MISS
AMBIGUOUS_PROJECT_FAMILY
DUPLICATE_OR_BACKUP
SCOPE_INTERPRETATION_DIFFERENCE
GROUND_TRUTH_UNCERTAIN
```

No side wins by assumption. Evidence wins.

```
PROJECT_CROSSCHECK_SCHEMA_READY = YES
```

---

## 4. Run B — documentation-optimized comparison

Blocked until `ATLAS_ORIGINAL_BASELINE_CAPTURED = YES`.

Then Local may re-measure the same authorized estate / selected cohort.

```
EXPERIMENT_NAME = D049_DOCUMENTATION_OPTIMIZED_COMPARISON
RUN_B_REDEFINES_D049_CORRECTNESS = NO
```

### Before / after (Run A → Run B)

Use exact counts. Percentages only with a defensible denominator.

| Metric | Run A | Run B | Delta class |
| --- | --- | --- | --- |
| PROJECT_DISCOVERY_RECALL | | | |
| KNOWLEDGE_DISCOVERY_RECALL | | | |
| FALSE_PROJECT_MATCH_COUNT | | | |
| AMBIGUOUS_MATCH_COUNT | | | |
| UNMATCHED_EXPECTED_PROJECT_COUNT | | | |
| FALSE_KNOWLEDGE_PROJECT_ASSIGNMENTS | | | |
| USER_CORRECTIONS_REQUIRED | | | |
| MANUAL_PROJECT_PATHS_REQUIRED | | | |
| MANUAL_RECLASSIFICATIONS_REQUIRED | | | |
| TIME_TO_DISCOVER_PROJECTS | | | |
| DISCOVERY_OUTPUT_UNDERSTANDABLE | | | |
| UNEXPLAINED_STRONG_MATCH_COUNT | | | |
| AGENT_CONTEXT_COMPLETENESS | | | only if genuinely measured |

Delta class is one of: `LIFT` | `NO_CHANGE` | `REGRESSION` | `UNMEASURABLE`.

### Documentation lift (only where supported)

```
DOCUMENTATION_LIFT_PROJECT_DISCOVERY =
DOCUMENTATION_LIFT_KNOWLEDGE_DISCOVERY =
DOCUMENTATION_LIFT_AMBIGUITY_REDUCTION =
DOCUMENTATION_LIFT_MANUAL_BURDEN =
DOCUMENTATION_LIFT_AGENT_READINESS =
```

Optimization is not automatically beneficial.

```
BEFORE_AFTER_COMPARISON_SCHEMA_READY = YES
```

---

## 5. D-049 final closure template

Apply to **Run A only**. Do not wait for Run B.

### CASE A — Local Run A PASS + hard gates clean + bounded estate confirmed

```
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PASS
D_049_FINAL_ACCEPTANCE = PASS
D_049_STATE = CLOSED
D_042_EXECUTION_GATE = OPEN
```

Claude / Run B may continue independently.

### CASE B — Local Run A PARTIAL

Classify each residual:

```
BLOCKING_DISCOVERY_DEFECT
HONEST_AMBIGUITY
GROUND_TRUTH_UNCERTAINTY
NON_BLOCKING_UX
DOCUMENTATION_QUALITY_LIMITATION
```

Only `BLOCKING_DISCOVERY_DEFECT` (or failed hard gates) keeps D-042 closed.

```
D_049_FINAL_ACCEPTANCE = PARTIAL
D_042_EXECUTION_GATE = CLOSED | OPEN   # OPEN only if no blockers
```

### CASE C — Local Run A FAIL

```
D_049_FINAL_ACCEPTANCE = FAIL
D_042_EXECUTION_GATE = CLOSED
```

Smallest evidence-backed remediation. No broad campaign.

Do not use Run B to convert a failing original discovery engine into PASS.

```
D049_FINAL_CLOSURE_TEMPLATE_READY = YES
ORIGINAL_ESTATE_ACCEPTANCE_MATRIX_READY = YES
```

---

## 6. D-042 unlock template (do not execute)

If and only if CASE A (or CASE B with zero blockers) on Run A:

```
D_042_EXECUTION_GATE = OPEN
D_042_IMPLEMENTATION = NOT_STARTED
D_042_PREP_BRANCH = NOT_CREATED
PR_344 = DO_NOT_REOPEN
```

OPEN means the prerequisite is satisfied. Wait for a separate owner
execution directive. Do not implement Conversational Capture here.

```
D042_UNLOCK_TEMPLATE_READY = YES
```

---

## 7. Future product hypotheses (do not implement)

```
AS-DOCUMENTATION-HEALTH-001 = Atlas Documentation Health
STATUS = HYPOTHESIS_ONLY
```

Potential later flow: discover → assess knowledge gaps → identify
stale/missing docs → propose safe improvements → owner review →
update knowledge estate.

```
AS-PROJECT-ROADMAP-001 = Atlas Living Project Roadmap
STATUS = ROADMAP_ONLY
```

Relationship (projection, not a truth store):

```
AS-DOCUMENTATION-HEALTH-001
        ↓
AS-PROJECT-ROADMAP-001
        ↓
NEXT ACTION / MOMENTUM
```

No Visual Roadmap, Project Memory, Momentum, Portfolio, 2.3, OPT,
AutoLab, or Prime work from this control file.

---

```
NEXT_ACTION = WAIT FOR LOCAL RUN A AND CLAUDE PROJECT SELECTION.
```

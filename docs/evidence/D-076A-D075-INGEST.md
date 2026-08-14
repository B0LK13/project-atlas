# D-076A D-075 ingest — independent inventory, not Atlas evidence

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-REAL-ESTATE-CONTROL-076A`

```
D075_RESULT_INGESTED = YES
D075_ROLE = INDEPENDENT_HUMAN_AGENT_ESTATE_INVENTORY
D075_IS_ATLAS_DISCOVERY_RESULT = NO
ATLAS_RUN_A = PENDING
ATLAS_RUN_B = PENDING
D_049_FINAL_ACCEPTANCE = NOT_YET_EVALUATED
D_042_EXECUTION_GATE = CLOSED
```

Cloud did not access `D:\`. Cloud did not invent Atlas discovery counts.

## D-075 result (as reported)

```
AUTHORIZED_ROOT = D:\
INDEPENDENT_PROJECTS_DISCOVERED = 168
INDEPENDENT_PROJECTS_ELIGIBLE_ESTIMATE ≈ 55
```

Do **not** convert ≈55 into an exact recall denominator.

```
KNOWN_EXPECTED = <not set from D-075 estimate>
UNKNOWN_EXPECTED = YES
GROUND_TRUTH_AUTHORITATIVE_COUNT = NOT_ESTABLISHED
```

168 directories are not assumed to be distinct canonical projects.
The ≈55 figure is not authoritative Atlas ground truth.

```
DOCUMENTATION_BASELINE = D:\atlas-acceptance-d060\D075_BASELINE.md
BASELINE_PRESERVED = YES
D075_DOCUMENTATION_OPTIMIZATION_READY = YES
```

## Five mandatory high-signal anchors

```
FIVE_ANCHOR_PROJECTS_REGISTERED = YES
SELECTED_PROJECTS = 5
```

| ID | Path | Expected documentation challenge |
| --- | --- | --- |
| A | `D:\dev-ai\dark-factory` | dense but contradictory documentation |
| B | `D:\dev-web\playbook-platform` | path / identity noise |
| C | `D:\dev-black\black-agency-web-design` | sparse + nested sites |
| D | `D:\dev-os\vibed-dev-env` | multi-component + version contradictions |
| E | `D:\dev-cloud\onedrive-organizer` | dormant + dual entry points |

These five are mandatory Run A reconciliation anchors.
They are D-075 selected projects, not Atlas `PROJECTS_FOUND`.

## Ground-truth reconciliation schema

Fill after Run A. Do not pre-classify Atlas outcomes.

```
KNOWN_EXPECTED_PROJECTS =
  A D:\dev-ai\dark-factory
  B D:\dev-web\playbook-platform
  C D:\dev-black\black-agency-web-design
  D D:\dev-os\vibed-dev-env
  E D:\dev-cloud\onedrive-organizer
  + any additional Local-confirmed expected projects
    (not the raw 168, not the ≈55 estimate)

GROUND_TRUTH_UNCERTAIN_PROJECTS =
DUPLICATE_OR_BACKUP_CANDIDATES =
PROJECT_FAMILIES =
```

```
GROUND_TRUTH_RECONCILIATION_SCHEMA_READY = YES
```

## Cross-check after Run A (D075_EXPECTED vs ATLAS_FOUND)

Each difference is exactly one of:

```
ATLAS_DISCOVERY_MISS
ATLAS_VALID_EXTRA
D075_INVENTORY_MISS
DUPLICATE_OR_BACKUP
PROJECT_FAMILY
HONEST_AMBIGUITY
GROUND_TRUTH_UNCERTAIN
```

Do not automatically side with D-075 or Atlas.

## Run A remains D-049 authority

Local Atlas on the original `D:\` estate decides D-049.

If Run A is a genuine PASS (D-074 hard gates + D-076 CASE A):

```
D_049_FINAL_ACCEPTANCE = PASS
D_049_STATE = CLOSED
D_042_EXECUTION_GATE = OPEN
```

Do not wait for Run B. Do not use D-075 inventory to fabricate Atlas success.

## Run B comparison matrix (A–E only; blocked until Run A captured)

Measures documentation lift. Does not redefine original correctness.

| Anchor | Run A found | Run A class | Run B found | Run B class | Lift |
| --- | --- | --- | --- | --- | --- |
| A dark-factory | | | | | |
| B playbook-platform | | | | | |
| C black-agency-web-design | | | | | |
| D vibed-dev-env | | | | | |
| E onedrive-organizer | | | | | |

Lift cell: `LIFT` | `NO_CHANGE` | `REGRESSION` | `UNMEASURABLE`.

Also compare the D-076 before/after metric rows for the cohort only.

```
RUN_B_COMPARISON_MATRIX_READY = YES
```

## Templates still ready (unchanged)

```
RUN_A_ACCEPTANCE_MATRIX_READY = YES
D049_FINAL_CLOSURE_TEMPLATE_READY = YES
D042_UNLOCK_TEMPLATE_READY = YES
```

See `D-074-AUTHENTIC-ACCEPTANCE-MATRIX.md` and
`D-076-REAL-ESTATE-EXPERIMENT-CONTROL.md`.

## Hypotheses (do not implement)

```
AS-DOCUMENTATION-HEALTH-001 = HYPOTHESIS_ONLY
AS-PROJECT-ROADMAP-001 = ROADMAP_ONLY
```

```
DISCOVERY → DOCUMENTATION HEALTH → PROJECT KNOWLEDGE
        → LIVING ROADMAP → NEXT ACTION / MOMENTUM
```

```
NEXT_ACTION = WAIT FOR LOCAL RUN A.
```

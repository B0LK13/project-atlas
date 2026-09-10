# ATLAS-DOC-RECEIPT — ATLAS-ONE-COHERENT-WORKFLOW-20260910

```text
GOAL                      = one reproducible integrated candidate demonstrating
                            knowledge -> development -> resume
BRANCH                    = integration/atlas-one-workflow-20260910 (LOCAL ONLY, not pushed)
BASE                      = b87b4a226f4aa8b2f669edf112aa3476454f754f (origin/main)

CANDIDATE_PINS            = #791 181f2ebaa756a6f64149fa4f7cae098be5ad7524
                            #786 1082b1e4381069f142c546c5adcc37070f4f7103
                            #781 750586a678eb3a5fe44994141afa2ac73bdb0845
                            #789 1c6bd038c2cc8ee2e6da4c902e6504cfe07852e2
PINS_VERIFIED             = YES (all four unchanged from the stated last-checked state)
TRANSITIVE_UNMERGED       = studio #763/#770/#776/#785/#788 + atlas-dag #734..#751 (11 PRs)

LOCAL_GATES               = ruff PASS | mypy PASS (413 files) | pytest see FULL_SUITE
FULL_SUITE                = 6468 passed, 8 skipped, 4 xfailed, 0 FAILED (666s, cov 85%)
                            run on the integrated candidate, in a venv whose editable
                            install points AT the candidate (so subprocess tests really
                            exercise it, not another checkout)
CI_THIS_CANDIDATE         = SUCCESS on a3a5ce5ea7f06d8641e5fc034429771f750f110c
                            (tree 696f14c12d87f9a58b5bc402db696599053e794a)
                            run 34448732581, event=pull_request, PR #793 (DRAFT)
                              quality (ubuntu-latest, 3.12, full)      SUCCESS
                              quality (windows-latest, 3.12, windows)  SUCCESS
                              quality (ubuntu-latest, 3.13, compat)    SUCCESS
                              control-plane                            SUCCESS
                            SUBJECT = the assembled candidate ONLY; not evidence for
                            any component PR, and no component's CI is evidence for it.
                            Later docs-only heads leave src/tests/scripts/.github trees
                            byte-identical, but CI conclusions pin to a SHA: any newer
                            head must re-establish its own.
CI_COMPONENTS             = #781 SUCCESS | #786 SUCCESS | #789 SUCCESS | #791 FAILURE
FORMAL_IV                 = NOT_STARTED (no self-IV claimed)
MERGE_AUTHORIZATION       = NOT_GRANTED
AUTO_RETRY                = false (enforced by recovery contract; demonstrated)

DEFECTS_REPAIRED_HERE     = #791 ruff 6x (5 E501 + 1 F841)
                            #791 windows test_unreadable_file (chmod(0) is not a
                              read denial on Windows) + platform-neutral coverage added
                            A2-006 asserted the ABSENCE of #786 as an invariant
DEFECT_FOUND_NOT_FIXED    = atlas validate exits 1 on this repository; one broken link
                            (claims.md -> OPENAI-MCP-DESIGN.md). ROOT CAUSE CORRECTED:
                            not a relative-link bug -- the link is inside a CODE SPAN in
                            compiled claim text and the validator does not mask inert
                            Markdown regions. PRE-EXISTING on main b87b4a22.
                            ALREADY OWNED BY #700; A/B on one identical vault:
                            main exit 1, #700 16e654a8 exit 0 (838 files).
                            No competing PR opened; reproduction posted to #700;
                            duplicate backlog item AS-CORE-VALIDATE-RELLINK-001 WITHDRAWN.
REPO_VALIDATION_GREEN     = NO (the above is a real, unwaived baseline failure)

NEW_CODE                  = scripts/atlas_studio/mission_bridge.py (AS-STUDIO-BRIDGE-001)
                            scripts/acceptance/atlas_one_workflow.py
                            scripts/acceptance/union_resolve.py
                            tests/unit/test_atlas_studio_mission_bridge.py (13 tests, 8 refusals)
SRC_TOUCHED_BY_ME         = NONE (no change under src/ in any of my commits)

JOURNEY_DEMONSTRATED      = knowledge (6 ADR + 1 backlog + 1 WORKLOG excerpt, 8 sources)
                            task+eligibility (10 actions classified, 2 RUNNABLE)
                            bounded action (real subprocess, disposable git worktree, rc 0)
                            evidence (checkpoint VALID, survives process exit)
                            resume (deduplicated=True; effect count stayed 1)
LABELLED_FIXTURES         = failing_action | policy_refused | timeout_bounded
                            stale_context | uncertain_outcome
NEGATIVE_CONTROLS         = idempotency: same key -> 1 effect; different key -> 2 effects
                            READ_ERROR: mutating the branch fails both tests (2F/6P)

MEASUREMENT_SCOPE         = 1 assembly, 1 operator, 1 platform (Linux x86_64,
                            CPython 3.12.14). No cross-platform, multi-operator, or
                            performance claim. Windows/macOS behaviour NOT executed.

OWNER_ACTIONS_REQUIRED    = 1. remediate #791 (its owner; findings posted, branch untouched)
                            2. decide whether this candidate becomes a PR
                            3. Formal IV, once a CI subject exists
                            4. #700 carries the validate fix; nothing needed from me
NOT_CLAIMED               = AUTHENTIC_PILOT, EXTERNAL_SECURITY_CERTIFICATION,
                            COMMERCIAL_GA, power-loss durability, #781 UI validation,
                            A0-A8 completeness
```

## Truth boundaries preserved

`PREP != IMPLEMENTED` · `DEMO_FIXTURE != AUTHENTIC_PILOT` · `DEMO != RELEASE` ·
`UI != CANONICAL TRUTH` · `MODEL OUTPUT != AUTHORITY` ·
`PROMOTE_ELIGIBLE != MERGED/DEPLOYED/AUTHORITATIVE` ·
`KNOWLEDGE != PERMISSION` · `PREVIEW != EXECUTION` · `ATTENTION != AUTHORIZATION` ·
`IMPLEMENTED != CI_GREEN != IV_PASSED != MERGED`

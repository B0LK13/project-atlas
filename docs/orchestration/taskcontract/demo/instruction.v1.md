# Run the bounded multi-project integration pilot (EXTERNAL_BLOCKED — authentic INT-013 requires owner-provided authentic project roots; committed DEMO_FIXTURE projects (e.g. `tests/fixtures/demo/estate/`) do not satisfy this gate; see `docs/product/CODER-A…

Contract INT-013-BOUNDED-PILOT v1 (from docs/backlog.md, item INT-013).

## Objective
Run the bounded, fixture-backed multi-project integration pilot as an ongoing regression, without claiming authentic INT-013.

## Done means
The bounded pilot test runs unskipped and passes against committed fixture projects, and no project's own vault content is modified by any xproj operation.

## In scope
- tests/integration/test_int_013_bounded_multi_project_pilot.py
- WORKLOG.md

## Explicitly NOT in scope
- authentic INT-013 against owner-provided project roots
- any change to a project's own vault content
- clearing the EXTERNAL_BLOCKED state

## Where you may write
Atlas refuses to dispatch work outside these paths, and the lease records them. They are repository-relative:
- `tests/integration/test_int_013_bounded_multi_project_pilot.py`
- `WORKLOG.md`

These paths are expected to exist when you are done:
- `tests/integration/test_int_013_bounded_multi_project_pilot.py`

## What the result must be true of

Each requirement has an identifier. Every one of them is judged; the ones marked for human review are judged by a person, not by a passing check.

- **INT013-R1-PILOT-PASSES** — The bounded pilot test runs unskipped and passes, exercising two independent fixture projects through init/discover/ingest/build-indexes/build-portfolio plus AS-XPROJ-001/002/003 in one run.
  _(checked by pilot-test, pilot-file-present)_
- **INT013-R2-NO-AUTHORITY-MERGE** — Neither project's own vault content is modified by any xproj operation.
  _(judged by a human reviewer)_
  _Reviewer looks at: the diff of each fixture project's vault directory across the pilot run_
- **INT013-R3-BOUNDED-SCOPE** — Every xproj-derived output stays under its documented derived-only location.
  _(no automated check exists for this yet -- it is still required)_

## Context you have been given

- `tests/integration/test_int_013_bounded_multi_project_pilot.py` — the test that defines what the bounded pilot means
- `docs/origination-acceptance-contracts.yaml` — the human-authored scope and success criteria this contract restates

## This work assumes
- blocker resolved: declared blocker language in title (external_blocked): Run the bounded multi-project integration pilot (EXTERNAL_BLOCKED — authentic INT-013 requires owner-provided authentic project roots; committed DEMO_FIXTURE projects (e.g. `tests/fixtures/demo/estate

## Bounds
- Base commit: `80280bfe13c77708cada7af17215acdaff3725e4`
- At most 2 attempt(s), 2400s each.
- Cost ceiling 5.0 USD, enforced by runtime per-launch flag; the local-command adapter reports no cost. An estimate is not billed spend.

## What this instruction is not
It is not permission. Your profile, the agent registry and the supervisor's pre-dispatch check decide what may run; nothing written here widens that. Reporting the task complete is not acceptance -- the supervisor checks the result from the workspace after you exit, and your own report is never consulted.

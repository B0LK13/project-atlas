# AS-DEMO-2.1-001 — Technical Demo certificate template

| Field | Value |
|---|---|
| Package | AS-DEMO-2.1-001 |
| Template owner | D08 |
| Charter reference | `docs/demo/AS-DEMO-2.1-001.md` (D01 — do not edit from this lane) |
| ADV procedure | `docs/demo/ADV-DEMO.md` |

## Certificate outcome (exact text)

```text
TECHNICAL DEMO — VERIFIED
```

## Mandatory disclaimers (exact phrases)

These phrases **MUST** appear on every filled certificate:

```text
NOT RELEASE CERTIFIED
NOT AUTHENTIC PILOT PASS
```

## Fill-in block

Copy below when demo ADV + sibling gates pass. Leave blank fields until evidence exists.

```text
========================================================================
PROJECT ATLAS — AS-DEMO-2.1-001 TECHNICAL DEMO CERTIFICATE
========================================================================

Outcome:
  TECHNICAL DEMO — VERIFIED

Disclaimers (mandatory):
  NOT RELEASE CERTIFIED
  NOT AUTHENTIC PILOT PASS

Mode:
  DEMO_FIXTURE / ATLAS_DEMO_MODE=fixture
  (Mode B live root, if used, still does not imply authentic pilot pass)

Worktree / commit:
  MAIN_SHA: ____________________
  DEMO_BRANCH / TREE: ____________________

Evidence refs (paths or orphan notes):
  ADV: ____________________
  Backend suite: ____________________
  Frontend / browser: ____________________
  API / MCP E2E: ____________________
  Fixture pack: ____________________

DEMO-FINDING open CRITICAL/HIGH: 0 (required)

Operator / worker:
  Name: ____________________
  Role: D08 ADV + cert (or integrator)

========================================================================
THIS CERTIFICATE IS NOT RELEASE CERTIFIED
THIS CERTIFICATE IS NOT AUTHENTIC PILOT PASS
========================================================================
```

## Non-claims

- Filling this template does **not** set `ATLAS_2_1_RELEASE_CERTIFIED`.
- Filling this template does **not** wake or clear `AS-2.1-PILOT-AUTH-001`.
- Fixture ADV (`atlas adv certify`) reports remain `release_certified: false`.

# AS-DEMO-2.1-001 — ADV demo gate (TECHNICAL PREVIEW)

| Field | Value |
|---|---|
| Package | AS-DEMO-2.1-001 |
| Worker | D08 (ADV + certificate template) |
| Scope | Adversarial / clean-clone validation for the **Technical Demo** only |
| Certificate outcome | `TECHNICAL DEMO — VERIFIED` |
| Charter | See `docs/demo/AS-DEMO-2.1-001.md` (D01 sole writer — do not edit here) |

## Purpose

Prove that a disposable **DEMO_FIXTURE** run can be validated adversarially
(clean-clone / fixture ADV path) without ever claiming release or authentic
pilot authority.

This document is the ADV companion to the demo charter. Program narrative,
mode banners, and DEMO vs PILOT framing live in D01-owned files:

- `docs/demo/AS-DEMO-2.1-001.md`
- `docs/demo/README.md`
- `docs/demo/MODE-BANNER.md`

## Explicit non-claims

- **NOT RELEASE CERTIFIED** — demo ADV pass ≠ Atlas 2.1 release certification
- **NOT AUTHENTIC PILOT PASS** — DEMO_FIXTURE evidence is never authentic estate
- `ATLAS_2_1_RELEASE_CERTIFIED` remains **NO** until authentic-pilot wake events
- Existing fixture ADV (`atlas adv certify` / AS-ADV-RELEASE-001/002) still
  reports `release_certified: false` and does not stamp a release

## Relationship to fixture ADV

| Surface | Role for AS-DEMO-2.1-001 |
|---|---|
| `atlas adv certify` | Optional fixture matrix evidence under a disposable work root |
| `docs/AS-ADV-RELEASE-001-package.md` | Parent ADV package (RELEASE = NO) |
| `docs/AS-ADV-RELEASE-002-clean-clone.md` | Clean-clone replay procedure (RELEASE = NO) |
| `docs/demo/CERTIFICATE-TEMPLATE.md` | Demo certificate text (this package) |

Demo ADV may **reuse** fixture ADV cases as supporting evidence. A green
fixture ADV report alone is **not** sufficient to fill the demo certificate;
CRITICAL/HIGH `DEMO-FINDING-###` items must be closed first (directive §36).

## Clean-clone demo ADV outline

1. Start from a clean clone/worktree (no hidden developer-machine vault state).
2. Install backend + frontend per repository-approved commands.
3. Initialize **DEMO_FIXTURE** data only (never invent authentic estate roots).
4. Start Atlas API + Web against the demo paths.
5. Execute the demo story / hero scenario (see D01 charter).
6. Optionally run `atlas adv certify --work-root <disposable>` and retain the
   report under the disposable work root (not as release evidence).
7. Record DEMO findings; remediate CRITICAL/HIGH before certificate fill-in.
8. Only then complete `docs/demo/CERTIFICATE-TEMPLATE.md` with outcome
   **TECHNICAL DEMO — VERIFIED**.

## Certificate binding

When the ADV demo gate and sibling demo worker gates agree, operators fill:

`docs/demo/CERTIFICATE-TEMPLATE.md`

Required certificate text (exact):

```text
TECHNICAL DEMO — VERIFIED
```

Required disclaimers (exact phrases must appear on the filled certificate):

```text
NOT RELEASE CERTIFIED
NOT AUTHENTIC PILOT PASS
```

## Fail-closed rules

- Do not label DEMO_FIXTURE output as authentic pilot evidence.
- Do not treat Technical Demo success as clearing `AS-2.1-PILOT-AUTH-001`
  (`DORMANT_BLOCKED` until authentic estate root is available).
- Do not mutate D01 charter files from this worker lane.

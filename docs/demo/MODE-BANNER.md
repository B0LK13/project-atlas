# AS-DEMO-2.1-001 — Mode banner text (normative)

Honest, copy-paste banner strings for launchers, Web chrome, API demo headers,
MCP session notes, and operator terminals.

These strings are **required**. Softening, omitting, or replacing them with
release / pilot language is a CRITICAL demo finding.

## Universal honesty block

Print (or display) on every demo entrypoint, before any success messaging:

```text
════════════════════════════════════════════════════════════
  ATLAS TECHNICAL DEMO / PoC
  Mode package: AS-DEMO-2.1-001 (TECHNICAL_PREVIEW)

  DEMO
  NOT AUTHENTIC PILOT
  NOT RELEASE EVIDENCE

  Certificate ceiling: TECHNICAL DEMO — VERIFIED
  This run is NOT RELEASE CERTIFIED
  This run is NOT AUTHENTIC PILOT PASS
  Pilot gate: PILOT DORMANT (DORMANT_BLOCKED)
════════════════════════════════════════════════════════════
```

## Mode A — fixture (`ATLAS_DEMO_MODE=fixture`)

```text
════════════════════════════════════════════════════════════
  ATLAS DEMO MODE A — DETERMINISTIC FIXTURE
  ATLAS_DEMO_MODE=fixture

  Corpus class: DEMO_FIXTURE
  DEMO_FIXTURE ≠ authentic estate pilot
  DEMO_FIXTURE ≠ release evidence

  DEMO
  NOT AUTHENTIC PILOT
  NOT RELEASE EVIDENCE

  Success may support: TECHNICAL DEMO — VERIFIED
  Success does NOT mean: RELEASE CERTIFIED
  Success does NOT mean: AUTHENTIC PILOT PASS
  Pilot remains: PILOT DORMANT
════════════════════════════════════════════════════════════
```

## Mode B — live project root (`ATLAS_DEMO_ROOT=...`)

```text
════════════════════════════════════════════════════════════
  ATLAS DEMO MODE B — LIVE PROJECT ROOT
  ATLAS_DEMO_ROOT=<path>

  WARNING: A real project root is in use for demonstration only.
  Mode B is still DEMO — not automatic authentic pilot certification.

  DEMO
  NOT AUTHENTIC PILOT
  NOT RELEASE EVIDENCE

  Do not invent .atlas-project.yaml to fake pilot status.
  Authentic pilot remains: PILOT DORMANT until AS-2.1-PILOT-AUTH-001 wakes.
  This run is NOT RELEASE CERTIFIED
  This run is NOT AUTHENTIC PILOT PASS
════════════════════════════════════════════════════════════
```

## Refusal lines (launchers must implement)

If a script or UI would otherwise imply release or pilot success, print one of:

```text
REFUSED: cannot claim RELEASE CERTIFIED from AS-DEMO-2.1-001
```

```text
REFUSED: cannot claim AUTHENTIC PILOT PASS from DEMO_FIXTURE / Mode B demo
```

```text
REFUSED: TECHNICAL DEMO — VERIFIED ≠ RELEASE CERTIFIED
```

## Certificate footer (when demo gates actually pass)

```text
────────────────────────────────────────────────────────────
  RESULT: TECHNICAL DEMO — VERIFIED
  NOT RELEASE CERTIFIED
  NOT AUTHENTIC PILOT PASS
  PILOT DORMANT — authentic estate gate unchanged
────────────────────────────────────────────────────────────
```

## One-line badges (UI / Markdown)

Use exactly these short forms where space is limited:

| Badge | Allowed meaning |
|---|---|
| `DEMO` | Technical Preview surface |
| `DEMO_FIXTURE` | Synthetic / designed corpus only |
| `TECHNICAL DEMO — VERIFIED` | Demo gates passed |
| `NOT RELEASE CERTIFIED` | Not `v2.1.0` / release evidence |
| `NOT AUTHENTIC PILOT PASS` | Not authentic estate pilot |
| `PILOT DORMANT` | Pilot wake event has not fired |

Forbidden badges on demo surfaces: `RELEASE CERTIFIED`, `PILOT PASS`,
`AUTHENTIC ESTATE CERTIFIED`, `v2.1.0 READY` (unless a separate non-demo
release package has independently earned them).

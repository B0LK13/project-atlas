# AS-PILOT — Fixture-only owner waiver

| Field | Value |
|---|---|
| Package | AS-PILOT-FIXTURE-ONLY-WAIVER |
| Directive | `D-PROJECT-ATLAS-1.0-OWNER-GATES-PARALLEL-CLOSEOUT-001` |
| Tip pin | `8ee65b91871bc04039ffe401a9da3743e4800a8b` / TREE `a2e592a797056935fbec0d8c54033aa3c25a5b06` |
| `pilot_mode` | `FIXTURE_ONLY_OWNER_WAIVER` |
| `owner_authorized` | `true` |
| Label | **FIXTURE-ONLY CERTIFICATION UNDER OWNER WAIVER** |

## Decision

Owner explicitly authorizes fixture-only pilot certification under this waiver.

This is **not**:

- a REAL / AUTHENTIC / PRODUCTION estate pilot
- an invent of `.atlas-project.yaml` onto arbitrary disks
- authorization for live INT-013 production estate sync against unknown roots

## Honest flags

| Flag | Value |
|---|---|
| FIXTURE-ONLY CERTIFICATION UNDER OWNER WAIVER | **YES** |
| `pilot_mode` | `FIXTURE_ONLY_OWNER_WAIVER` |
| `owner_authorized` | `true` |
| `PILOT_ROOTS` (authentic) | **0** (known registry paths missing / empty as of 2026-08-10) |
| ESTATE PILOT PASSED (authentic / production) | **NO** |
| INT-013 production sync | **NOT OPENED** against authentic estate |
| RELEASE CERTIFIED | **NO** (separate gate) |

## Allowed evidence roots

Committed fixtures only, for example:

- `tests/fixtures/pilots/**`
- other committed `.atlas-project.yaml` under `tests/fixtures/`

Optional upgrade path: if a safe configured authentic root is later discovered
in the workspace registry / known roots list only (no arbitrary drive crawl),
record it and escalate for authentic estate certification — do not silently
upgrade this waiver label.

## Known-roots recheck (no arbitrary crawl)

| Path | Result |
|---|---|
| `D:\atlas-vaults` | MISSING |
| `D:\projects` | MISSING |
| `D:\estate` | MISSING |
| `C:\Users\Admin\projects` | MISSING |
| `D:\code` | MISSING |

## Non-claims

Do not describe this waiver as REAL estate pilot, AUTHENTIC estate pilot, or
PRODUCTION estate pilot. Fixture success under this waiver does not flip
`ESTATE PILOT PASSED` for authentic/production semantics.

# Project Atlas — Current State

| Field | Value |
|---|---|
| Directive | **`D-PROJECT-ATLAS-1.0-FINISH-PLUS-2.0-PREP-001`** |
| Updated | 2026-08-09T17:50:00+02:00 |
| Evidence | `D:\project-atlas-orphans\gen4-next-wave-parallel-001\` |

## §3 Baseline (revalidated)

```text
MAIN = 2c5ba4bc60124f40c0095d4d6e71bc84ef877462
TREE = d9a35e79e6b809975a1ff3ff5005b3a2d484c8e3
OPEN_PRS = (none at baseline write; INT-010 / WEB-003 waking)
CI_INFRA_EXCEPTION = in force (empty-step GHA failures; local CERTIFY)
```

### Adopted / merged on tip (do not rewrite)

| Package | PR | Merge |
|---|---|---|
| CORE2-009 | #54 | `a108059` |
| WEB-001 | #53 | `bcd453f` |
| WEB-002 | #55 | `b5e5aa8` |
| INT-009 | #56 | `06ee191` (+ PM-IV PASS) |
| J-005 | #57 | `2c5ba4b` (+ PM-IV PASS) |
| L-001 | #52 | `d1e9f5b` |
| docs #10 / dependabot #4 | merged | tip ancestry |
| legacy docs #6/#8 | closed | CONFLICTING |

### Active lanes

| Lane | Status |
|---|---|
| INT-010 | WOKEN (tombstones) |
| WEB-003 | WOKEN (production shell + ADR-010) |
| INT-011/012 | PREPARED |
| PILOT / INT-013 / CORE2-010 | BLOCKED — no invent genesis |

### Certification flags (honest)

| Flag | Value |
|---|---|
| Atlas 1.0 COMPLETE | **NO** |
| `ATLAS_1_0_RELEASE_CERTIFIED` | **NO** |
| WEB APPLICATION ACCEPTED | **NO** |
| ESTATE PILOT PASSED | **NO** |
| Atlas 2.0 IMPLEMENTATION READY | **NO** |

## Track A phase

**1.0 critical path:** Active closure → **J-005 ✓** → **INT-009 ✓** → INT-010…012 → Web production (WEB-003) → INT-013 pilot → CORE2-010 → estate sync → E2E/recovery/RC → v1.0.0 freeze.

## Track B phase

**2.0 prep only:** `docs/atlas-2.0/` scaffold started. **No** dependency-bearing production semantic changes until `ATLAS_1_0_RELEASE_CERTIFIED`.

## PILOT owner ask

No authentic estate roots with `.atlas-project.yaml` found under scanned paths
(`D:\atlas-vaults`, `D:\projects`, `D:\estate`, `C:\Users\Admin\projects` missing;
orphans/Documents had no genesis markers at depth≤3).

**Owner:** provide real project root(s) with approved genesis markers, **or**
authorize fixture-only pilot prep against `tests/fixtures/pilots` (does **not**
satisfy ESTATE PILOT PASSED). Do **not** invent genesis.

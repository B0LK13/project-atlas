# Atlas 1.0.0 evidence index (§37)

**Directive:** `D-PROJECT-ATLAS-1.0-OWNER-GATES-PARALLEL-CLOSEOUT-001`
**Evidence baseline (software freeze):** MAIN `f4079813025dd882e0e3608ab7ad5b3b17f95bd9` / TREE `feb0441a13e391812ae07a1a8eb27b0de1061469`
**Index status:** RELEASE evidence pack
**RELEASE CERTIFIED = YES**

Orphan evidence root: `D:\project-atlas-orphans\gen4-next-wave-parallel-001\`

| Package | Tip-bound evidence | Evidence class | Release effect |
|---|---|---|---|
| ADV-001..004 / SEC / E2E | `AS-IV-ADV-E2E-F407981.md` (42 ADV/SEC/docs/E2E + 61 determinism = 103 PASS) | Independent tip-bound IV | PASS |
| SYNC / MIG / recovery | `AS-IV-SYNC-MIG-F407981.md` (67 PASS + fixture vault validate) | Independent tip-bound IV | PASS |
| Core / CP / Web quality | `AS-IV-CORE-CP-WEB-F407981.md` (ruff/mypy/pytest/CP/web smoke PASS) | Independent tip-bound IV | PASS |
| WEB-ACCEPT | `docs/AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md` (#106) | Owner/governor | WEB APPLICATION ACCEPTED = YES |
| PILOT-WAIVER | `docs/AS-PILOT-FIXTURE-ONLY-WAIVER.md` (#106) | Owner waiver | FIXTURE-ONLY CERT UNDER OWNER WAIVER = YES |
| Fixture pilot pipeline | `pilot-f407981-clean/` under orphan root | Disposable fixture estate | Supports waiver; not authentic PILOT |
| Release receipt | `docs/releases/1.0.0/RECEIPT.md` | Authorized certification | RELEASE CERTIFIED = YES |
| Compatibility snapshot | `docs/releases/1.0.0/COMPATIBILITY-SNAPSHOT.md` | 1.0 anchor for Track B | Post-cert consumer pin |

## Use rules

1. Qualification commands were rerun at the freeze tip above.
2. Authentic estate PILOT is waived as a release blocker; do not relabel fixture evidence as authentic.
3. WEB acceptance is prerequisite evidence, not a substitute for the signed receipt.
4. Track B may consume the compatibility snapshot only after this pack lands and `v1.0.0` is tagged.

At this pin, **WEB APPLICATION ACCEPTED = YES**, **FIXTURE-ONLY CERT UNDER OWNER WAIVER = YES**, authentic estate **PILOT = NO (waived)**, and **RELEASE CERTIFIED = YES**.

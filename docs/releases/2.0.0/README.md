# Atlas 2.0.0 release receipts

**Stage:** RELEASE CERTIFIED
**Directive:** `D-PROJECT-ATLAS-2.0-PILOT-WAIVER-TO-FINAL-CERT-001`
**Package:** AS-REL2-001
**RELEASE CERTIFIED = YES**
**VERSION = 2.0.0**

## Feature-freeze software candidate (immutable)

Authority tip after Waves 1-5 (#116-#140) + final-cert unlock (#141):

- MAIN: `045b7d72d2897324e12e942d1a9658a09127aa2a`
- TREE: `2dbbfbf93267497eb312dd826b077d9c27cd65c2`

All qualification matrix lanes and independent IV receipts in this pack are bound to that exact HEAD/TREE for software freeze. AS-REL2-001 documentation, the Windows CLI help ASCII fix, and the `2.0.0` package version bump are release-plane overlays on top of that freeze tip; the annotated tag `v2.0.0` points at the authorized release integration commit that carries this pack.

## Owner-gate state

- **ATLAS_2_0_FINAL_CERT_PILOT_MODE = FIXTURE_ONLY_OWNER_WAIVER** (`docs/AS-2.0-FINAL-CERT-PILOT-WAIVER.md`, PR #141).
- **AUTHENTIC_ESTATE_PILOT = NO** — never claimed; known-root search `PILOT_ROOTS=0`.
- **OWNER_WAIVED = YES** — PILOT cleared as a 2.0 release blocker (independent of 1.0 waiver).
- Honest label forever: **PILOT PASS — FIXTURE-ONLY UNDER EXPLICIT OWNER FINAL-CERT WAIVER**
- **AS-2.0-SYNC-001 / AS-2.0-TWIN-001 production = UNLOCKED** under fixture waiver (never authentic estate).
- **ATLAS_2_0_RELEASE_CERTIFIED = YES** — see `RECEIPT.md`.
- **CRITICAL/HIGH = 0**, **OWNER_HELD = 0**.

## Contents

- `CHECKLIST.md` — required release gates closed against the freeze tip.
- `EVIDENCE-INDEX.md` — tip-bound evidence inventory.
- `RECEIPT.md` — authorized certification receipt (RELEASE CERTIFIED = YES).
- `RELEASE-NOTES.md` — 2.0.0 release notes.
- `PILOT-REPORT.md` — pilot disposition with waiver recorded verbatim.
- `final-cert-pilot-waiver.json` — machine pin (release-certified flag set at stamp).
- `COMPATIBILITY-NOTES.md` — 1.0 compat anchor consumption notes.

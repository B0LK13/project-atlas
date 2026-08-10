# Atlas 1.0.0 release receipts

**Stage:** RELEASE CERTIFIED
**Directive:** `D-PROJECT-ATLAS-1.0-OWNER-GATES-PARALLEL-CLOSEOUT-001`
**Package:** AS-REL-001
**RELEASE CERTIFIED = YES**

## Feature-freeze software candidate (immutable)

Authority tip after #111–#114 (Core quality, PRE-RC pins, CP Windows):

- MAIN: `f4079813025dd882e0e3608ab7ad5b3b17f95bd9`
- TREE: `feb0441a13e391812ae07a1a8eb27b0de1061469`

All qualification matrix lanes and independent IV receipts in this pack are bound to that exact HEAD/TREE. AS-REL-001 documentation and the `1.0.0` package version bump are release-plane overlays on top of that freeze tip; the annotated tag `v1.0.0` points at the authorized release integration commit that carries this pack.

## Owner-gate state

- **WEB APPLICATION ACCEPTED = YES** (pull request #106).
- **FIXTURE-ONLY CERT UNDER OWNER WAIVER = YES** (pull request #106; `pilot_mode: FIXTURE_ONLY_OWNER_WAIVER`).
- **Authentic estate PILOT = NO** — waived as a release blocker by owner directive §§3–4; recorded as **FIXTURE-ONLY CERTIFICATION UNDER OWNER WAIVER**. Authentic upgrade is optional post-1.0.
- **ATLAS_1_0_RELEASE_CERTIFIED = YES** — see `RECEIPT.md`.

## Contents

- `CHECKLIST.md` — required release gates closed against the freeze tip.
- `EVIDENCE-INDEX.md` — tip-bound evidence inventory (§37).
- `RECEIPT.md` — authorized certification receipt (RELEASE CERTIFIED = YES).
- `RECEIPT-TEMPLATE.md` — blank form retained for audit; non-authoritative once `RECEIPT.md` is signed.
- `RELEASE-NOTES.md` — 1.0.0 release notes.
- `COMPATIBILITY-SNAPSHOT.md` — HEAD/TREE/tag consumer pin for Track B.

No further release-blocking CRITICAL/HIGH findings remain against the freeze tip.

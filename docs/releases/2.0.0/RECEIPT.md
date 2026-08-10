# Atlas 2.0.0 certification receipt

**Receipt status:** SIGNED / AUTHORIZED
**Directive:** `D-PROJECT-ATLAS-2.0-PILOT-WAIVER-TO-FINAL-CERT-001`
**Package:** AS-REL2-001
**Software freeze baseline:** MAIN `045b7d72d2897324e12e942d1a9658a09127aa2a` / TREE `2dbbfbf93267497eb312dd826b077d9c27cd65c2`
**RELEASE CERTIFIED = YES**
**VERSION = 2.0.0**

## Inherited owner-gate state

- `ATLAS_2_0_FINAL_CERT_PILOT_MODE = FIXTURE_ONLY_OWNER_WAIVER` (pull request #141).
- `AUTHENTIC_ESTATE_PILOT = NO` — never claimed; known-root search found zero authentic roots.
- `OWNER_WAIVED = YES` — PILOT cleared as a 2.0 release blocker (independent of the 1.0 waiver).
- Honest label forever: **PILOT PASS — FIXTURE-ONLY UNDER EXPLICIT OWNER FINAL-CERT WAIVER**
- AS-2.0-SYNC-001 / AS-2.0-TWIN-001 production unlocked under fixture waiver (#141).

## Candidate identity

- Release candidate label: Atlas 2.0.0 / AS-REL2-001
- Software freeze commit: `045b7d72d2897324e12e942d1a9658a09127aa2a`
- Software freeze tree: `2dbbfbf93267497eb312dd826b077d9c27cd65c2`
- Package version: `2.0.0` (declared in `pyproject.toml` and `project_atlas.__version__`)
- Annotated tag: `v2.0.0` (points at the authorized release integration commit carrying this pack)
- Evidence index: `docs/releases/2.0.0/EVIDENCE-INDEX.md`
- Artifact digests (built after version bump to `2.0.0` on the release branch):

| Artifact | SHA-256 |
|---|---|
| `project_atlas-2.0.0-py3-none-any.whl` | `32925a31e6817c42a24012658c643654bc4589094f9b427025a8d5e5cb3d0e29` |
| `project_atlas-2.0.0.tar.gz` | `bf3ee0b484671ffe822ecfc09b034de97d766daf44fbe0ca5c5e91c1fff3f685` |

## Gate record

| Gate | Evidence reference | Result |
|---|---|---|
| Estate PILOT (authentic) | Owner final-cert waiver + `PILOT-REPORT.md` | **WAIVED / N/A** (fixture-only YES) |
| Final-cert fixture waiver | `docs/AS-2.0-FINAL-CERT-PILOT-WAIVER.md` (#141) | YES |
| SYNC-001 / TWIN-001 production | #141 + tip smoke | UNLOCKED (fixture-waived) |
| Full quality gates | `AS-IV-2.0-FULL-GATES-045B7D7.md` | PASS (ruff/mypy/1471 pytest) |
| Control-plane suite | `AS-IV-2.0-CP-045B7D7.md` | PASS |
| CLI help / init / version | tip-bound smoke + ASCII help fix | PASS |
| Compat anchor consumption | SYNC/TWIN prod + `atlas compat` | PASS |
| Security / ADV continuous | Wave-5 SEC-ADV + tip suite | PASS · CRITICAL/HIGH = 0 |
| Release artifacts | this receipt + `RELEASE-NOTES.md` + packaging | YES |
| Blocking-findings review | tip-bound IV aggregate | CRITICAL/HIGH = 0 · OWNER_HELD = 0 |

## Decision

- Decision: **YES — RELEASE CERTIFIED**
- Conditions or exceptions: authentic estate PILOT waived under independent `FIXTURE_ONLY_OWNER_WAIVER`; never claim authentic estate PILOT PASSED
- Certifier name and role: Autonomous closeout agent under owner directive `D-PROJECT-ATLAS-2.0-PILOT-WAIVER-TO-FINAL-CERT-001`
- Independent reviewer: tip-bound IV lanes (Core full gates, CP suite, SYNC/TWIN smoke) at freeze HEAD/TREE
- Signed date: 2026-08-10
- Signature or verifiable approval reference: this receipt + orphan IV files under `D:\project-atlas-orphans\gen4-next-wave-parallel-001\` + owner directive authorization

## Attestation

I attest that the full validation matrix is PASS against software freeze tip `045b7d7` / TREE `2dbbfbf`, that CRITICAL and HIGH release findings are zero, that OWNER_HELD release blockers are zero, that FINAL-CERT FIXTURE PILOT WAIVER is YES with authentic estate PILOT = NO, and that Atlas 2.0.0 is hereby **RELEASE CERTIFIED**.

**PROJECT ATLAS 2.0 — COMPLETE · RELEASE CERTIFIED · CLOSEOUT VERIFIED**

Event: `ATLAS_2_0_RELEASE_CERTIFIED`
Flags: `ATLAS_2_0_RELEASE_CERTIFIED=YES` · `VERSION=2.0.0` · `CRITICAL/HIGH=0` · `OWNER_HELD=0`

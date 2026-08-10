# Atlas 2.0.0 evidence index

**Directive:** `D-PROJECT-ATLAS-2.0-PILOT-WAIVER-TO-FINAL-CERT-001`
**Evidence baseline (software freeze):** MAIN `045b7d72d2897324e12e942d1a9658a09127aa2a` / TREE `2dbbfbf93267497eb312dd826b077d9c27cd65c2`
**Index status:** RELEASE evidence pack
**RELEASE CERTIFIED = YES**

Orphan evidence root: `D:\project-atlas-orphans\gen4-next-wave-parallel-001\`

| Package | Tip-bound evidence | Evidence class | Release effect |
|---|---|---|---|
| Final-cert pilot waiver | `docs/AS-2.0-FINAL-CERT-PILOT-WAIVER.md` + orphan `ATLAS-2.0-FINAL-CERT-PILOT-WAIVER-APPROVED.md` | Owner waiver | PILOT blocker CLEARED |
| SYNC/TWIN production unlock | PR #141 · `test_as_2_0_final_cert_sync_twin_001.py` | Implementation + IV | UNLOCKED (fixture-waived) |
| Core quality gates | `AS-IV-2.0-FULL-GATES-045B7D7.md` | Independent tip-bound IV | PASS (1471 pytest) |
| Control plane | `AS-IV-2.0-CP-045B7D7.md` | Independent tip-bound IV | PASS |
| Waves 1-5 capability landings | PRs #116-#140 · board `AS-BOARD-STATE-023`/`024` | Merged program | Baseline for freeze |
| 1.0 compatibility anchor | `docs/releases/1.0.0/compatibility-anchor.json` | Inherited pin | 1.0 wins conflicts |
| PILOT report | `docs/releases/2.0.0/PILOT-REPORT.md` | Verbatim waiver record | Authentic = NO |
| Release receipt | `docs/releases/2.0.0/RECEIPT.md` | Authorized certification | RELEASE CERTIFIED = YES |

## Use rules

1. Qualification commands were rerun at the freeze tip above (plus release-plane CLI help ASCII fix).
2. Authentic estate PILOT is waived as a release blocker; do not relabel fixture evidence as authentic.
3. SYNC-001 / TWIN-001 production receipts must keep `authentic_estate_pilot=false` and the honest label.
4. Consumers may treat `v2.0.0` as Atlas 2.0 RELEASE CERTIFIED only with this pack.

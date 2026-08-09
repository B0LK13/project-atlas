# Atlas 1.0.0 PRE-RC evidence index

**Evidence baseline:** MAIN `b57cceb383dca8d4a8c967da58abfc799386a829` / TREE `7efe25dccee4c91a9095cbf4743865274c4e9dff`
**Index status:** PRE-RC inventory only
**RELEASE CERTIFIED = NO**

This index records evidence packages known to exist at the pinned baseline. Inclusion means discoverable evidence, not a fresh rerun, independent acceptance, or release certification.

| Package | Evidence at pinned tip | Evidence class | Release effect |
|---|---|---|---|
| ADV-001 | `docs/AS-ADV-RELEASE-001-package.md` | Fixture advanced-certification matrix scaffold | NONE / NO |
| ADV-002 | `docs/AS-ADV-RELEASE-002-clean-clone.md` | Fixture clean-clone replay | NONE / NO |
| ADV-CLEAN-CLONE-REHEARSAL | `docs/AS-ADV-CLEAN-CLONE-REHEARSAL.md`; `docs/scripts/adv_clean_clone_rehearsal.py` | Disposable operator rehearsal and fail-closed helper | NONE / NO |
| ADV-003 | `docs/AS-ADV-RELEASE-003-perf-determinism.md` | Fixture performance and determinism signals | NONE / NO |
| ADV-004 | `docs/AS-ADV-RELEASE-004-migration-recovery.md`; `tests/unit/test_as_adv_release_004_migration_recovery.py` | Fixture migration/recovery replay with stabilized deterministic-outcome assertions | NONE / NO |
| SEC-CONT | `docs/AS-SEC-CONT-001-fixture-gates.md`; `docs/AS-SEC-CONT-002-fixture-deepen.md` | Fixture continuous-security gates | NONE / NO |
| E2E | `tests/integration/test_as_e2e_001_fixture_matrix.py` | Integration fixture matrix | NONE / NO |
| WEB-ACCEPT | `docs/AS-WEB-ACCEPT-001-checklist.md`; `docs/AS-WEB-ACCEPT-005-governor-evidence.md`; `docs/AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md` | Refreshed automated-evidence tip pins plus pending human-governor boundary | NONE / NO |
| TRACK-B-DEEPEN-H | `docs/atlas-2.0/IMPLEMENTATION-READY-GATE.md`; `docs/atlas-2.0/Z-WAVE-INDEX.md` | PREP/PROTOTYPE theme expansion; implementation readiness remains NO | NONE / NO |

## Use rules

1. Verify each path and rerun its applicable commands at the final candidate commit and tree.
2. Record actual outputs, environment, artifact digests, reviewer identity, and dispositions in a completed receipt.
3. Keep fixture evidence distinct from authentic estate PILOT evidence.
4. Keep automated WEB evidence distinct from human governor acceptance.
5. Treat Track B prep as non-release, non-readiness evidence; Atlas 1.0 authority wins conflicts.
6. Treat missing, stale, ambiguous, or unsigned evidence as an unmet gate.

At this PRE-RC pin, this index grants no release decision. **RELEASE CERTIFIED = NO**.

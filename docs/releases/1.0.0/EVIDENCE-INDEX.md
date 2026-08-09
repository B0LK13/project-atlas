# Atlas 1.0.0 PRE-RC evidence index

**Evidence baseline:** MAIN `ac1cee723f368154334815dade33212e593fc88c` / TREE `e0ed54782830df036cc439fa127ff5a16c5d8915`
**Index status:** PRE-RC inventory only
**RELEASE CERTIFIED = NO**

This index records evidence packages known to exist at the pinned baseline. Inclusion means discoverable evidence, not a fresh rerun, independent acceptance, or release certification.

| Package | Evidence at pinned tip | Evidence class | Release effect |
|---|---|---|---|
| ADV-001 | `docs/AS-ADV-RELEASE-001-package.md` | Fixture advanced-certification matrix scaffold | NONE / NO |
| ADV-002 | `docs/AS-ADV-RELEASE-002-clean-clone.md` | Fixture clean-clone replay | NONE / NO |
| ADV-003 | `docs/AS-ADV-RELEASE-003-perf-determinism.md` | Fixture performance and determinism signals | NONE / NO |
| ADV-004 | `docs/AS-ADV-RELEASE-004-migration-recovery.md` | Fixture migration and recovery replay | NONE / NO |
| SEC-CONT | `docs/AS-SEC-CONT-001-fixture-gates.md`; `docs/AS-SEC-CONT-002-fixture-deepen.md` | Fixture continuous-security gates | NONE / NO |
| E2E | `tests/integration/test_as_e2e_001_fixture_matrix.py` | Integration fixture matrix | NONE / NO |
| WEB-ACCEPT | `docs/AS-WEB-ACCEPT-001-checklist.md`; `docs/AS-WEB-ACCEPT-005-governor-evidence.md`; `docs/AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md` | Automated evidence plus pending human-governor boundary | NONE / NO |

## Use rules

1. Verify each path and rerun its applicable commands at the final candidate commit and tree.
2. Record actual outputs, environment, artifact digests, reviewer identity, and dispositions in a completed receipt.
3. Keep fixture evidence distinct from authentic estate PILOT evidence.
4. Keep automated WEB evidence distinct from human governor acceptance.
5. Treat missing, stale, ambiguous, or unsigned evidence as an unmet gate.

At this PRE-RC pin, this index grants no release decision. **RELEASE CERTIFIED = NO**.

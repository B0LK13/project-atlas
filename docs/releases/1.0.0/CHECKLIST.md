# Atlas 1.0.0 PRE-RC certification checklist

**Directive:** `D-PROJECT-ATLAS-1.0-MAX-PARALLEL-PLUS-2.0-PREP-001`
**Baseline:** MAIN `8ee65b91871bc04039ffe401a9da3743e4800a8b` / TREE `a2e592a797056935fbec0d8c54033aa3c25a5b06`
**RELEASE CERTIFIED = NO**

Owner-gates closeout (`D-PROJECT-ATLAS-1.0-OWNER-GATES-PARALLEL-CLOSEOUT-001`) unlocked WEB acceptance and fixture-only pilot waiver. Remaining unchecked rows still block RELEASE CERTIFIED.

| Done | Required gate | Required evidence | Current state |
|---|---|---|---|
| [ ] | Candidate pin | Final candidate commit and tree recorded and immutable | NO |
| [x] | WEB APPLICATION ACCEPTED | Acceptance checklist complete and human/owner governor signoff recorded (`docs/AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md` APPROVED on tip `8ee65b9`) | YES |
| [x] | Fixture-only PILOT waiver | Owner waiver `docs/AS-PILOT-FIXTURE-ONLY-WAIVER.md` (`pilot_mode: FIXTURE_ONLY_OWNER_WAIVER`) | FIXTURE-ONLY CERT UNDER OWNER WAIVER |
| [ ] | Estate PILOT (authentic) | Authentic bounded estate pilot completed; fixture roots are not substituted for authentic | NO |
| [ ] | ADV-001..004 matrix | Base, clean-clone, performance/determinism, and migration/recovery cases independently verified | NO |
| [ ] | SEC-CONT | Continuous security gates reviewed, including path refusal and metadata-only secret findings | NO |
| [ ] | E2E fixture matrix | Determinism, replay, failure, and recovery fixture matrix completed | NO |
| [ ] | Core validation | `atlas validate --vault <candidate-vault>` succeeds on the release candidate | NO |
| [ ] | Full quality gates | Ruff, strict mypy, full pytest, integration pytest, and CLI smoke gates succeed | NO |
| [ ] | Deterministic replay | Same-input replay and clean-clone stable planes are byte-identical | NO |
| [ ] | Security review | Secret handling, path safety, quarantine, and release blockers independently reviewed | NO |
| [ ] | Release artifacts | Version, changelog, packaging, install, and artifact digest evidence recorded | NO |
| [ ] | Open findings | No unresolved release-blocking findings; dispositions are documented | NO |
| [ ] | Independent certification | Authorized reviewer signs a receipt bound to the exact candidate commit and tree | NO |

## Evidence refresh notes

The pinned baseline now includes the ADV clean-clone rehearsal procedure, stabilized ADV-004 recovery replay assertions, refreshed WEB evidence tip pins, and Track B deepen-h prep. These additions improve the evidence inventory only: no checklist row is complete, WEB governor signoff remains pending, and Atlas 2.0 implementation readiness remains NO.

## Certification boundary

A checked fixture gate is evidence for that gate only. It does not imply estate PILOT completion, WEB acceptance, or release certification. Until every required gate is complete and an authorized receipt is signed, **RELEASE CERTIFIED = NO**.

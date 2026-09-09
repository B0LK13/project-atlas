# Recovery 003 — local checkout restored, draft candidate

Mission: M-CODEX-ATLAS-STUDIO-LINUX-VISUAL-SHELL-001.
Recovery resumed on 2026-09-09. Mission acceptance remains incomplete.

## Transfer and provenance

Original Downloads ZIP SHA256: `0ec06677e45e53c6dca2e365bf0d393441cd2880ef0dc1fd73059dd70d9ea4bd`.
All three SHA256SUMS.txt entries passed. ZIP and both tar.gz archives remain intact
in the local staging directory `~/Downloads/atlas-studio-recovery-kjbouvd1/`.
Prepared and preserved sources were extracted separately with archive path guards.

Authenticated Git fetch succeeded. PR #770 remains open on
`feat/as-studio-a1-001` at `028157e25f74ecea5da5b6ee407a7a866124f4b5`,
tree `9780ed0ec97c7b5094ebcc6f364355f751ccf2b0`.
Observed main: `b87b4a226f4aa8b2f669edf112aa3476454f754f`.
All A1 tracked files matched prepared source byte-for-byte except the intended
.gitignore additions; no tracked files were missing. The new recovery branch
starts at that exact A1 commit. Only desktop additions were restored.
Historical raw blocked event SHA256 remains
`8d30a0222ff4707f62181eb33850bfa668cab3cde977c0913bdd9de333eaa3bf`.

## Executed validation

- Clean A1 baseline: 40 Studio tests passed.
- Recovered candidate: 43 A0/A1/semantic/desktop Python tests passed, scoped ruff passed.
- `npm run check`: typecheck, 18 frontend tests, production build passed.
- Bundled Playwright Chromium: OS sandbox unavailable, failed before page execution.
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/google-chrome npm run test:e2e`:
  first executed run exposed palette reopening and a text-comparison test defect.
  Enter now prevents default activation when closing restores focus to the trigger.
  History assertions consistently use innerText. Final run: all 5 tests passed.
- Browser coverage: unavailable-state honesty, palette search/activation/focus trap/
  Escape restoration, same-screen hash changes, reload/back/forward, and essential
  control fit/no document overflow at 980x700, 1366x768, 1920x1080.
- New viewport captures are `evidence/recovery-003-unavailable-*.png`; these prove
  unavailable-state layout only. Historical screenshots retain their old scope.
- Read-only recovery-delta review found no new defect. This is not formal IV.
- `npm run tauri:build -- --bundles deb`: blocked by missing GLib/GTK/WebKit
  development packages. `sudo -n true` requires interactive authentication.
  Native launch and package installation were not run on this candidate.
- Actual authenticated bridge GET timed out after 90 seconds with no response.
  Actual-data browser acceptance has not passed.

## Remaining acceptance and release blockers

The current frontend aborts projection fetch after four seconds, incompatible
with the measured live reconstruction latency. A received LIVE snapshot also
remains labelled current indefinitely without freshness aging. Full nested schema
validation, actual source-to-render proof, live visual refinement and broader
accessibility acceptance remain pending. Rich operational detail and Design Lab
are explicitly preview-only; summaries reflect only the supplied A1 projection.

Native package prerequisites, normal desktop acceptance, installed lifecycle and
canonical Vault synchronization remain pending. No release or full mission success
is claimed. The authorized draft stacked PR is a review checkpoint, not acceptance.

## Atlas documentation state

Session: `AS-20260909T142418Z-generic-project-atlas-b271a70f`.
Bootstrap returned an unverified spool Vault. Skill acknowledgement and capability
check succeeded when supplied the explicit session/spool. Documentation commands
captured implementation and validation events with synchronization pending.
Receipt command exited 3: pending spool; capture pipeline not normalized,
verified or routed. No canonical note or valid session receipt is claimed.
Use the supported Atlas workflow to synchronize immutable raw events once the
verified atlas-main Vault is available.

A2_IMPLEMENTATION = NOT_PERFORMED
MERGE = NOT_PERFORMED
SELF_IV = NOT_CLAIMED
MISSION_STATUS = INCOMPLETE

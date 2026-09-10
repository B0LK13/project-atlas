# Recovery 002 — incomplete candidate

Mission: M-CODEX-ATLAS-STUDIO-LINUX-VISUAL-SHELL-001.
This is source preparation with no authenticated checkout, final HEAD, tree or PR.

## Preservation and reconciliation

The original directory remains preserved. Its Git pointer refers to missing
/workspace/scratch/7f7ae1753e50/project-atlas/.git/worktrees/project-atlas-studio.
The recovery archive and checksums are outside that directory in
studio-recovery-002/preservation. Generated dependencies and native targets are excluded.
The archive includes historical screenshots, diagnostics and the immutable blocked event.
Historical screenshot success is not current acceptance.

Fresh connector observations, checked again on 2026-09-09:

| Ref | HEAD | State |
|---|---|---|
| PR763 | efb9225508a81663d3d0fd8f99872c118def39ff | open, base feat/atlas-dag-e2e-harden |
| PR770 | 028157e25f74ecea5da5b6ee407a7a866124f4b5 | open, base feat/as-studio-a0-001 |
| main | b87b4a226f4aa8b2f669edf112aa3476454f754f | current main observation |

A1 tree: 9780ed0ec97c7b5094ebcc6f364355f751ccf2b0.
Main tree: 46d1989b026a2f15920ec5e1c78a106799bd1249.
Intended stack base remains feat/as-studio-a1-001.
No PR was found for feat/as-studio-linux-visual-shell-001.
Connector reads do not demonstrate local Git authentication or an approved push.

The original mission base 551820c87595f4c819ba4648c04002465cf6117c
was compared with preserved source and the current A1 head. The preserved
mission_control.py matched original source; a fetched evidence copy acquired an
extra trailing newline, documented rather than treated as a local semantic edit.
Current A1 implementation, tests, closure, phase/index/backlog/worklog and A2
planning documents were adopted where original and preserved contents matched.
WORKLOG initially exceeded the read output budget; a complete file comparison
confirmed no local difference before adopting upstream.

Upstream foreign-agent frontier suppression, semantic tests and governance remain
intact. No A2 source was implemented. The new desktop ADR uses 036 because 035 is
occupied. Recheck the identifier before committing. Entire-repository provenance
is still unverified without Git metadata; this is not a reconstructed commit.

Retained local work: shell, three prototypes, components, fixtures, read bridge,
Tauri lifecycle and screenshots. Recovery edits: no automatic fixture fallback,
honest A1 summary views, hash routing, palette focus/activation, summary validation
and escaping, responsive graph fit, generated-artifact ignores and portable
sandboxed browser configuration.

## Validation of prepared source

Environment: Ubuntu 24.04.3, Linux 6.18.35, Node 24.19.0, npm 11.9.0,
Python 3.12.14, Rust 1.98.1, Tauri 2.11.5, GTK 3.24.41, WebKitGTK 2.52.3.
No ordinary desktop session is available.

| Command / scope | Result |
|---|---|
| npm run check (apps/studio) | exit 0; typecheck, 18 tests, Vite production build |
| pytest A0, A1 mission control, A1 semantic boundaries, desktop boundary --no-cov -o addopts='' -q | exit 0; 43 passed |
| ruff check scripts/atlas_studio apps/studio/bridge and the four test modules | exit 0 |
| npm run tauri:build -- --bundles deb | exit 0; release executable and amd64 deb |
| dpkg-deb --info package | exit 0; metadata inspected; installation NOT_RUN |
| sandboxed Playwright with explicit installed Chrome | exit 1 before page; root sandbox rejection |
| runuser -u nobody -- google-chrome-stable --headless --dump-dom about:blank | exit 1; cannot set groups, Operation not permitted |
| native executable, no overrides | exit 101; GTK initialization unavailable |

The Playwright server started and bound its socket. Browser navigation/assertion
and screenshot acceptance were not reached. A diagnostic trace exists under the
ignored test-results directory. New navigation/focus/viewport tests are prepared
but NOT_RUN after the infrastructure failure. No passing keyboard, responsive,
automated accessibility or normal Ubuntu launch claim is made.

Static boundary checks found no application invoke handler, shell/fs plugin,
UI-controlled process command, mutation HTTP method, raw HTML insertion or
external window opening in the modified application surfaces. Python tests
cover the actual no-command and fixed read-method boundary. This is scoped
evidence, not a comprehensive security certification.

Controlled summary-input rendering and HTML escaping passed frontend tests using
explicit test input. A real authenticated A1 projection populated in a browser
and changed at its source remains BLOCKED. Detail projections remain unavailable;
see README for each screen. Freshness aging while a window stays open and stronger
full nested frontend schema validation remain review findings.

## Acceptance gaps and required capabilities

1. A supported authenticated checkout of B0LK13/project-atlas with fetch and branch
   push permission is required. No gh executable or Git credential helper is
   available; earlier attempted remote paths failed authentication/network access.
2. An ordinary Linux runner with desktop/display and Chromium sandbox support is
   required for browser, keyboard, responsive, accessibility and native acceptance.
3. A verified atlas-main Vault/session is required for immutable-event normalization,
   routing, protected-content validation and documentation synchronization.

Bootstrap returned a spool-only session AS-20260909T134647Z-codex-project-atlas-fecf88fc
with vault verified=false. Acknowledgment, document and receipt commands returned
exit 3 requiring an active Vault/session. No canonical note or synchronized receipt
was produced. User authorization permits independent recovery patch preparation;
it does not make documentation complete.

The package is a build spike only: install, installed launch and uninstall NOT_RUN.
Do not publish this as a release. After capabilities recover, reconcile again,
finish live visual hierarchy and acceptance tests, freeze Git identifiers, and
open a draft stacked PR if material checks still remain blocked.

A2_IMPLEMENTATION = NOT_PERFORMED
MERGE = NOT_PERFORMED
SELF_IV = NOT_CLAIMED

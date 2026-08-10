# AS-2.0-UX-001 — Advanced Command Center (entry gate + thin contract freeze)

| Field | Value |
|---|---|
| Package | **AS-2.0-UX-001** |
| Directive | `D-PROJECT-ATLAS-1.0-VERIFY-TO-2.0-AUTONOMOUS-001` |
| Class | **READY** |
| Lane | Entry gate + thin contract freeze only |
| Tip base | `d239bdc` (Wave 1 merge / `origin/main` or newer) |
| GATE_10 | **UNLOCKED** |
| WEB APPLICATION ACCEPTED | **YES** |
| Auto full UI rewrite | **FORBIDDEN** this lane |

## Purpose

Freeze the Advanced Command Center **entry contract** after Web 1.0 acceptance
so later UX implementation can consume read adapters without promoting the
browser to Layer B truth. This package ships **docs + contract tests** (and at
most a clearly bounded read-adapter stub). It does **not** rewrite production
UI chrome.

## Dependencies (satisfied)

| Dependency | Status | Evidence |
|---|---|---|
| WEB APPLICATION ACCEPTED = YES | **YES** | `docs/AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md` |
| ADR-008 (read-first / triple invariant) | present | `docs/adr/ADR-008-atlas-web-application.md` |
| ADR-010 (Command Center modes) | present | `docs/adr/ADR-010-atlas-web-ux.md` |
| J-005 / AS-J-005 impact graph (consume) | merged | `docs/AS-J-005-impact-graph.md`, `web_api.graph` |
| GATE_10 unlocked | **YES** | `docs/PROJECT-ATLAS-CURRENT-STATE.md` |

## Normative invariants (inherited, non-negotiable)

- **UI ≠ canonical** — browser / Command Center state never becomes Layer B.
- **Graph ≠ authority** — impact lens is derived consume-only (J-005).
- **Unknown ≠ healthy** — absent OBS / impact evidence → unknown, never fabricated healthy.
- **No canonical writes** — no vault truth writers from UX surfaces (`projects/`,
  `state/`, claims, authority, `_promote`, ingestion writers).

## Thin contract freeze — IN / OUT / FORBIDDEN

Aligned with `docs/atlas-2.0/PACKAGE-CONTRACT-STUBS.md` UX boundary.

### IN

- Versioned **read-adapter** results from `project_atlas.web_api` (ops health,
  projects, impact summary).
- Health / read-status payloads that preserve `unknown` when evidence is absent.
- Derived impact projection labels with explicit Graph≠authority markers.
- Evidence and freshness / source references for operator lenses.
- Named Command Center mode IDs from ADR-010: `overview`, `projects`, `ops`,
  `impact` (presentation lenses only).

### OUT (later implementation waves — not this freeze PR)

- Full Advanced Command Center UI rewrite or mode redesign.
- New write-capable HTTP bridges or browser FS mutation APIs.
- Live-vault default policy changes beyond existing sample/stub adapters
  (see OQ-008).
- Multi-source impact fusion beyond J-005 projection consume (see OQ-009).
- Acceptance evidence emission (rendering ≠ WEB APPLICATION ACCEPTED).

### FORBIDDEN

- Canonical vault writes from UI or `web_api`.
- Elevating graph / impact rank to claim or authority winners.
- Inferring WEB APPLICATION ACCEPTED (or stronger gates) from routes rendering.
- Labelling sample/fixture data as live authentic estate / PILOT PASS.
- Dual-owning Wave 1 production lanes (`feat/as-2.0-wave1-compat-kf`,
  `feat/as-2.0-fed-001`) or Core truth writers.

## FR / NFR stubs (traceability only)

| ID | Stub | 1.0 dependency |
|---|---|---|
| FR-2.0-UX-001 | Command Center advanced modes consume read adapters only | AS-WEB-001, ADR-010 |
| FR-2.0-UX-002 | Impact lens displays derived graph; never elevates graph to authority | AS-J-005 |
| FR-2.0-UX-003 | All modes preserve UI≠canonical / Graph≠authority / Unknown≠healthy | ADR-008 |
| NFR-2.0-UX-001 | Prerequisite WEB APPLICATION ACCEPTED = YES | AS-WEB-ACCEPT-001 |

## Owned surfaces (this entry lane)

| Path | Role |
|---|---|
| `docs/AS-2.0-UX-001.md` | Entry gate + thin contract freeze (this doc) |
| `tests/unit/test_as_2_0_ux_001_entry_gate.py` | Doc presence + ADR / read-adapter invariants |

Optional later (not required for entry READY): bounded read-only stub under
`src/project_atlas/web_api/**` only if it adds zero write surface.

## Explicit non-claims

- Does **not** claim Atlas 2.0 RELEASE CERTIFIED.
- Does **not** claim authentic ESTATE PILOT PASSED.
- Does **not** authorize a full Command Center rewrite in this PR.
- Does **not** reopen WEB APPLICATION ACCEPTED (already YES).

```text
STOP: ENTRY GATE + THIN CONTRACT FREEZE
NO CANONICAL WRITES
UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy
```

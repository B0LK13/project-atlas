# AS-DEMO-2.1-001 — Frontend suite runbook (`apps/web`)

| Field | Value |
|---|---|
| Package | AS-DEMO-2.1-001 TECHNICAL_PREVIEW |
| Owner lane | DEMO worker D05 |
| Scope | `docs/demo/FRONTEND-SUITE.md` + `docs/demo/checklists/frontend.md` only |
| App under test | `apps/web` (Vite + React hash router) |
| Certificate target | **TECHNICAL DEMO — VERIFIED** |
| Release claim | **NOT RELEASE CERTIFIED** |
| Pilot claim | **NOT AUTHENTIC PILOT PASS** · PILOT DORMANT |
| Evidence class | **DEMO_FIXTURE** · **NOT RELEASE EVIDENCE** |

This runbook explains how to run the web shell against **DEMO_FIXTURE**
samples and against a local **LIVE_API** (`atlas live api-serve`) while
keeping **LIVE** vs **DEMO** vs **FIXTURE** chips honest.

It does **not** mutate `apps/web` source. Companion charter / launcher /
fixture pack docs (D01–D03) own other `docs/demo/` surfaces.

---

## 0. Honest mode banner (required)

Print or display before any demo walkthrough:

```text
════════════════════════════════════════════════════════════
  TECHNICAL DEMO — VERIFIED candidate (NON_RELEASE)
  DEMO_FIXTURE ≠ authentic pilot estate
  NOT RELEASE CERTIFIED · NOT AUTHENTIC PILOT PASS
  UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy
════════════════════════════════════════════════════════════
```

Never say “production accepted as release evidence”, “pilot passed”, or
“Atlas 2.1 RELEASE CERTIFIED” based on this suite alone.

---

## 1. Data modes (what the chips mean)

`apps/web` labels data honesty with banners and chips. Prefer the visible
source of truth on the page (`data_source=…`, mode switcher, banner text)
over operator memory.

| Mode | How selected | Data origin | Honest UI signals |
|---|---|---|---|
| **LIVE** | Default on Mission/Workspace; `?mode=live` | HTTP to `VITE_ATLAS_API_BASE` (`live_api`) | Banner `LIVE_API — composed read projection`; chip `data_source=live_api` |
| **DEMO** | Mode switcher or `?mode=demo`; also forced when `VITE_ATLAS_DEMO_ONLY=1` and mode would be live | Static stubs under `apps/web/public/sample-*.json` (`demo_stub`) | Warn banner `DEMO STUB — isolated sample · not live vault · not PILOT`; chip `data_source=demo_stub` |
| **FIXTURE** | Mode switcher or `?mode=fixture` | Deterministic gate samples `apps/web/public/sample-*.fixture.json` (`fixture`) | Banner for FIXTURE isolation; chip `data_source=fixture` · **DEMO_FIXTURE class** |

### Invariants the UI must keep honest

- **LIVE unavailable must not silently invent vault rows.** Mission Control /
  Workspace LIVE mode fails closed with an error directing the operator to
  choose DEMO or FIXTURE — no silent stub swap.
- Some other lenses (status / projects / knowledge / graph / ops) may fall
  back to an isolated demo stub when LIVE is unreachable **only if** they
  show the **DEMO STUB** warn banner / `demo_isolated` chip. That fallback
  is still **DEMO**, never LIVE.
- `authentic_pilot=false`, `ui_canonical=false`, `graph_authority=false`,
  `unknown≠healthy` chips stay visible on production lenses.
- Empty / unknown rollups stay **unknown** — never rebranded healthy.

### Env knobs (Vite)

| Variable | Default | Effect |
|---|---|---|
| `VITE_ATLAS_API_BASE` | `http://127.0.0.1:8765` | LIVE_API base URL (no trailing slash required) |
| `VITE_ATLAS_DEMO_ONLY` | unset / false | When `1` / `true` / `yes`, live-preferring loaders stay on isolated DEMO stubs (Mission/Workspace remap `live` → `demo`) |

Windows PowerShell examples:

```powershell
# LIVE-first (API must be up for LIVE chips)
$env:VITE_ATLAS_API_BASE = "http://127.0.0.1:8765"
Remove-Item Env:VITE_ATLAS_DEMO_ONLY -ErrorAction SilentlyContinue

# Force DEMO-only shell (no LIVE claims even if API is reachable)
$env:VITE_ATLAS_DEMO_ONLY = "1"
```

---

## 2. Prerequisites

From a clean clone / worktree of this repository:

```powershell
# Backend (editable install with API entrypoint)
python -m pip install -e ".[dev]"

# Frontend
cd apps/web
npm install
cd ../..
```

Use a **DEMO_FIXTURE** vault only (never invent `.atlas-project.yaml` inside
a real customer/pilot root to fake authenticity). Preferred paths once D03
lands:

- `docs/demo/fixtures/` (labeled DEMO_FIXTURE corpus)
- or an explicitly named local demo vault initialized for TECHNICAL_PREVIEW

If the fixture pack PR is not merged yet, you may still exercise **DEMO** /
**FIXTURE** chips from the in-app public samples without claiming LIVE vault
composition.

---

## 3. Path A — DEMO / FIXTURE only (no API)

Sufficient for chip honesty checks and offline walkthrough of Mission /
Workspace mode switcher.

```powershell
cd apps/web
$env:VITE_ATLAS_DEMO_ONLY = "1"
npm run dev
```

Open (Vite prints the local URL; typically `http://127.0.0.1:5173/`):

| Surface | URL fragment | Expect |
|---|---|---|
| Hub | `#/` | Invariant chips; no release claim |
| Mission Control DEMO | `#/mission-control?mode=demo` | DEMO STUB warn banner |
| Mission Control FIXTURE | `#/mission-control?mode=fixture` | FIXTURE / DEMO_FIXTURE isolation |
| Workspace DEMO | `#/workspace?mode=demo` | DEMO STUB warn banner |
| Workspace FIXTURE | `#/workspace?mode=fixture` | FIXTURE isolation |
| Projects / Knowledge / Graph / Ops | `#/projects` … `#/ops` | DEMO STUB banners when not live |

Do **not** label these screens LIVE_API.

---

## 4. Path B — LIVE_API + web (demo vault)

### 4.1 Start read-only LIVE_API against DEMO_FIXTURE vault

In terminal 1 (repo root):

```powershell
# Replace <DEMO_VAULT> with a DEMO_FIXTURE vault path only
atlas live api-serve --vault <DEMO_VAULT> --host 127.0.0.1 --port 8765
```

Confirm the process logs that LIVE_API is listening on `127.0.0.1:8765`.
Optional smoke (implemented routes only; skip any that 404 without inventing
success):

```powershell
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/v1/snapshot
curl http://127.0.0.1:8765/v1/mission
curl http://127.0.0.1:8765/v1/workspace
curl http://127.0.0.1:8765/v1/ops/receipts
```

### 4.2 Start web LIVE-first

In terminal 2:

```powershell
cd apps/web
$env:VITE_ATLAS_API_BASE = "http://127.0.0.1:8765"
Remove-Item Env:VITE_ATLAS_DEMO_ONLY -ErrorAction SilentlyContinue
npm run dev
```

Walk LIVE chips:

| Surface | URL | Expect when API healthy |
|---|---|---|
| Mission Control LIVE | `#/mission-control` or `?mode=live` | Banner `LIVE_API — composed read projection`; `data_source=live_api` |
| Workspace LIVE | `#/workspace` or `?mode=live` | Same LIVE_API banner / chip |
| Ops | `#/ops` | LIVE_API banner when snapshot/receipts reachable |
| Projects / Knowledge / Graph | matching `#/…` | LIVE_API labels when fetches succeed |

Then flip the Mission/Workspace **LensModeSwitcher** to DEMO and FIXTURE and
confirm banners change — LIVE chip must not remain while DEMO/FIXTURE data
is shown.

### 4.3 LIVE-down honesty check

Stop `api-serve`. Reload `#/mission-control?mode=live`. Expect an error
directing DEMO/FIXTURE selection — **not** a silent LIVE success with
fabricated PILOT rows.

---

## 5. Suggested demo story (frontend slice)

Aligned with the AS-DEMO-2.1-001 story; frontend-only steps:

1. Open hub — read invariant chips.
2. `#/projects` — inventory labeled LIVE or DEMO honestly.
3. `#/knowledge` — answers or honest empty DEMO stub.
4. `#/graph` — derived graph; `graph_authority=false`.
5. `#/mission-control` — switch LIVE → DEMO → FIXTURE; read banners.
6. `#/workspace` — same mode honesty.
7. `#/ops` — health + receipts; unknown stays unknown offline.

MCP / Ask Atlas / L3 optional lanes are owned by other DEMO workers; link
them when those docs merge. This suite does not require them for frontend
chip verification.

---

## 6. Frontend gates (capture exact results)

From `apps/web` / repo root:

```powershell
cd apps/web
npm install
npm run smoke
npm run build
```

Optional related unit gates (repo root, after `pip install -e ".[dev]"`):

```powershell
python -m pytest tests/unit/test_as_2_1_web_mission_workspace_ux.py -q
```

Record: command, exit code, pass/fail counts, duration. Do not quote
historical counts from other machines.

### Browser E2E status

As of this runbook, `apps/web` ships **Node smoke** (`scripts/smoke.mjs`) and
unit/file gates — **no** repository-standard Playwright/Cypress suite for
the production shell.

Record for TECHNICAL_PREVIEW when the driver is absent:

```text
BROWSER_E2E_MISSING
```

Isolated harness / honesty package (charter alternative path — does **not**
auto-stamp **TECHNICAL DEMO — VERIFIED**):

[`browser-e2e/AS-DEMO-2.1-BROWSER-E2E-001.md`](browser-e2e/AS-DEMO-2.1-BROWSER-E2E-001.md)

Operator checklist:
[`browser-e2e/checklists/browser-e2e.md`](browser-e2e/checklists/browser-e2e.md)

Manual Path A/B chip walkthrough (this runbook) plus smoke/build remains the
frontend observation bar when chips are claimed. The isolated package records
harness absence fail-closed — it must **not** invent Path A observation.
Screenshot-only certification is **not** sufficient.

---

## 7. Pass criteria for this docs package

Frontend TECHNICAL DEMO candidate may be marked verified for **web honesty**
when:

- [ ] Honest banner text used (TECHNICAL DEMO · NOT RELEASE · NOT PILOT).
- [ ] Path A: DEMO and FIXTURE chips/banners observed on Mission + Workspace.
- [ ] Path B (if API+DEMO vault available): LIVE chips observed; LIVE-down
      fails closed without invent.
- [ ] `npm run smoke` and `npm run build` exit 0 on the tip under test.
- [ ] Operator never claims RELEASE CERTIFIED or AUTHENTIC PILOT PASS.

Checklist copy: [`checklists/frontend.md`](checklists/frontend.md).

---

## 8. Explicit non-claims

| Phrase | Allowed? |
|---|---|
| TECHNICAL DEMO — VERIFIED | Yes, after checklist pass |
| DEMO_FIXTURE labeled DEMO | Yes |
| LIVE_API read projection | Yes, only when `data_source=live_api` |
| RELEASE CERTIFIED | **No** |
| AUTHENTIC PILOT PASS | **No** |
| UI = canonical vault truth | **No** |
| Graph = authority | **No** |
| Unknown = healthy | **No** |

# Checklist — AS-DEMO-2.1-001 frontend suite

Companion: [`../FRONTEND-SUITE.md`](../FRONTEND-SUITE.md).

**Certificate language (exact):**

- Pass label: `TECHNICAL DEMO — VERIFIED`
- Must also state: `NOT RELEASE CERTIFIED`
- Must also state: `NOT AUTHENTIC PILOT PASS`
- Estate class: `DEMO_FIXTURE` · `NOT RELEASE EVIDENCE`

Operator / tip: _______________________________  
Date (local): _______________________________  
Vault path (DEMO_FIXTURE only, or N/A for Path A): _______________________________

---

## A. Banner / non-claims

- [ ] Honest TECHNICAL DEMO banner shown before walkthrough
- [ ] No claim of RELEASE CERTIFIED
- [ ] No claim of AUTHENTIC PILOT PASS / pilot estate
- [ ] UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy acknowledged

## B. Install / gates

- [ ] `pip install -e ".[dev]"` (or existing approved venv) OK
- [ ] `cd apps/web && npm install` OK
- [ ] `npm run smoke` exit 0 — notes: ___________
- [ ] `npm run build` exit 0 — notes: ___________
- [ ] Optional: `pytest tests/unit/test_as_2_1_web_mission_workspace_ux.py -q` — notes: ___________
- [ ] Recorded `BROWSER_E2E_MISSING` (no repo browser E2E harness)

## C. Path A — DEMO / FIXTURE only

Env: `VITE_ATLAS_DEMO_ONLY=1`, `npm run dev`

- [ ] `#/mission-control?mode=demo` → DEMO STUB warn banner · not LIVE
- [ ] `#/mission-control?mode=fixture` → FIXTURE / DEMO_FIXTURE isolation · not LIVE
- [ ] `#/workspace?mode=demo` → DEMO STUB warn banner
- [ ] `#/workspace?mode=fixture` → FIXTURE isolation
- [ ] Mode switcher LIVE/DEMO/FIXTURE visible; chips match selected mode
- [ ] `authentic_pilot=false` (or equivalent) visible on Mission/Workspace

## D. Path B — LIVE_API (when DEMO vault available)

- [ ] `atlas live api-serve --vault <DEMO_VAULT> --host 127.0.0.1 --port 8765` running
- [ ] Web started with `VITE_ATLAS_API_BASE=http://127.0.0.1:8765` and DEMO_ONLY unset
- [ ] `#/mission-control?mode=live` → `LIVE_API` banner · `data_source=live_api`
- [ ] `#/workspace?mode=live` → `LIVE_API` banner · `data_source=live_api`
- [ ] Switcher to DEMO/FIXTURE changes banner away from LIVE_API
- [ ] Stop API → LIVE mode fails closed (error / unknown) — **no** silent invent / fake PILOT rows

_If Path B skipped:_ reason ___________ (Path A alone still valid for DEMO/FIXTURE chip check)

## E. Production lens spot-check

- [ ] `#/projects` labeled LIVE_API or DEMO STUB honestly
- [ ] `#/knowledge` honest empty/DEMO or LIVE — no fabricated vault truth
- [ ] `#/graph` keeps `graph_authority=false`
- [ ] `#/ops` unknown/DEMO vs LIVE labeled; no fabricated completion/PILOT

## F. Result

- [ ] **TECHNICAL DEMO — VERIFIED** (frontend honesty slice)
- [ ] **NOT RELEASE CERTIFIED**
- [ ] **NOT AUTHENTIC PILOT PASS**

Sign-off (operator initials): ___________

# Atlas Web (`apps/web`)

**Vite + React (TypeScript)** shell with hash client router, design-lab
themes (AS-WEB-002), and production lenses (AS-WEB-003 / WEB-ACCEPT-002).

Architecture: ADR-008 (stack) · ADR-009 (tokens) · ADR-010 (Command Center).

## Invariants

- **UI ≠ canonical** — this app never writes Layer B / claims / authority.
- **Graph ≠ authority** — derived displays only.
- **Unknown ≠ healthy** — missing OBS snapshot renders as `unknown`.
- Prototypes are **not** production UI acceptance until governor sign-off.
- Vault reads go through `project_atlas.web_api` (Python); the shell may use
  `public/sample-read-status.json` until an HTTP bridge lands.

## Run

```bash
cd apps/web
npm install
npm run dev
```

### Production shell routes

| Route | Surface |
|---|---|
| `#/` | Hub |
| `#/projects` | Projects lens |
| `#/knowledge` | Knowledge lens |
| `#/graph` | Graph lens (derived ≠ authority) |
| `#/ops` | Ops Health + receipt evidence (read-only unknown stub) |
| `#/command-center` | Command Center modes |
| `#/mission-control` | Mission Control lens (stub; ACCEPTED=NO) |
| `#/workspace` | Workspace lens (stub; ACCEPTED=NO) |
| `#/design-lab/*` | Design-lab themes A–D |

### Design-lab themes

| Route | Theme |
|---|---|
| `#/design-lab/ledger-desk` | A · Ledger Desk |
| `#/design-lab/signal-rack` | B · Signal Rack |
| `#/design-lab/cartograph-quiet` | C · Cartograph Quiet |
| `#/design-lab/terminal-honest` | D · Terminal Honest |

## Smoke / acceptance gates (local)

No browser install required for file-presence + invariant smoke:

```bash
cd apps/web
npm run smoke
# equivalent:
node apps/web/scripts/smoke.mjs
```

Unit gates (from repo root, after `pip install -e ".[dev]"`):

```bash
python -m pytest tests/unit/test_as_web_001_web_api.py \
  tests/unit/test_as_web_accept_001_checklist.py \
  tests/unit/test_as_web_accept_002_closeout.py \
  tests/unit/test_as_web_ops_health_001.py -q
```

These commands document and exercise evidence; passing them does not certify acceptance.

CI: invoke the same `node apps/web/scripts/smoke.mjs` step in the quality
job when the workflow matrix is healthy. Empty-step CI failures are tracked
under `CI_INFRA_EXCEPTION` and do **not** alone certify WEB ACCEPTED.

**WEB APPLICATION ACCEPTED = NO** until
`docs/AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md` is completed by a governor.

## Design tokens

Shared CSS variables live in `src/tokens.css` and are remapped per
`[data-theme="…"]`. See [ADR-009](../../docs/adr/ADR-009-web-design-tokens.md).

## Status page

Pages show vault health / read status from the sample stub (shape matches
`web_api.read_status`). Do not invent PILOT data here.

# Atlas Web (`apps/web`) — AS-WEB-002 design lab

**Vite + React (TypeScript)** shell with a **hash client router** and four
design-lab prototype themes. Architecture: ADR-008 (stack) · ADR-009 (tokens).

Foundation: AS-WEB-001. Design-lab themes: orphan `AS-WEB-001-DESIGN-LAB.md`.

## Invariants

- **UI ≠ canonical** — this app never writes Layer B / claims / authority.
- **Graph ≠ authority** — derived displays only.
- **Unknown ≠ healthy** — missing OBS snapshot renders as `unknown`.
- Prototypes are **not** production UI acceptance.
- Vault reads go through `project_atlas.web_api` (Python); this shell uses
  `public/sample-read-status.json` until an HTTP bridge lands.

## Run

```bash
cd apps/web
npm install
npm run dev
```

Open `/` (hub) or hash routes:

| Route | Theme |
|---|---|
| `#/` | Home (Ledger Desk lean + theme index) |
| `#/design-lab/ledger-desk` | A · Ledger Desk |
| `#/design-lab/signal-rack` | B · Signal Rack |
| `#/design-lab/cartograph-quiet` | C · Cartograph Quiet |
| `#/design-lab/terminal-honest` | D · Terminal Honest |

Smoke (no install required for file-presence checks):

```bash
npm run smoke
```

## Design tokens

Shared CSS variables live in `src/tokens.css` and are remapped per
`[data-theme="…"]`. See [ADR-009](../../docs/adr/ADR-009-web-design-tokens.md).

## Status page

Pages show vault health / read status from the sample stub (shape matches
`web_api.read_status`). Do not invent PILOT data here.

# Atlas Web (`apps/web`) — AS-WEB-001 foundation

Minimal **Vite + React (TypeScript)** shell for Atlas vault read status.
Architecture: [`docs/adr/ADR-008-atlas-web-application.md`](../../docs/adr/ADR-008-atlas-web-application.md).

## Invariants

- **UI ≠ canonical** — this app never writes Layer B / claims / authority.
- **Graph ≠ authority** — derived displays only.
- **Unknown ≠ healthy** — missing OBS snapshot renders as `unknown`.
- Vault reads go through `project_atlas.web_api` (Python); this shell may use a
  stub JSON fixture until an HTTP bridge package lands.

## Run

```bash
cd apps/web
npm install
npm run dev
```

Smoke (no install required for file-presence checks):

```bash
npm run smoke
```

## Status page

The home page shows vault health / read status from
`public/sample-read-status.json` (shape matches `web_api.read_status`).
Replace the stub with a live adapter call in a later package — do not invent
PILOT data here.

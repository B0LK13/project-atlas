# AS-2.1-WEB-LIVE-001

Web shell prefers `VITE_ATLAS_API_BASE` (default `http://127.0.0.1:8765`)
`/v1/snapshot` from AS-2.1-API-SERVER-001, then falls back to
`/sample-read-status.json` when LIVE_API is unreachable.

Invariant: UI ≠ canonical remains; this package only wires **read** data.

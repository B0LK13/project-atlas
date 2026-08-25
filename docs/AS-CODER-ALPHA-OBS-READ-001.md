# AS-CODER-ALPHA-OBS-READ-001

Vault-scoped live observability **REPORT READ** wrap over the existing
AS-2.1-OBS-LIVE-001 receipt (`build_live_observability_receipt` /
`GET /v1/obs`).

```
atlas ops obs --vault <dir> [--json]
```

Also:

- MCP `atlas.obs.read` (zero-arg, vault-scoped, vault-read, enabled)
- AppService `obs()`

`GET /v1/obs` already serves the live JSON receipt. This package does
**not** add a second HTTP route or a web page.

`atlas ops health` / `events` / `report` remain the existing OBS-001/002/003
surfaces. This package does **not** persist `generated/ops/obs/` and does
**not** write Layer B.

Honesty (mandatory):

- `OBS != AUTHORITY`
- `LIVE_RECEIPT != CERTIFICATION`
- `EMPTY != HEALTHY`
- `UNKNOWN != HEALTHY`
- `MCP != AUTHORITY`
- `WRITE_APPLIED=false`

Does not touch `atlas3/`, D-149, xproj wrap files, or golden-estate skill.
Does not duplicate schema-compat, event-retention, or xproj REPORT READ.

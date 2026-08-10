# Harbor Portal — Architecture

> DEMO FIXTURE — NOT AUTHENTIC PILOT — NOT RELEASE EVIDENCE

## Integration

The portal consumes the Harbor API HTTP JSON surface:

- Base URL (local): `http://127.0.0.1:8080`
- Auth: API key header
- Reads: `/v1/tenants`, `/v1/health`

## UI surfaces (synthetic)

- Tenant list
- Session status
- Ops deep-link into Harbor Ops docs (informational only)

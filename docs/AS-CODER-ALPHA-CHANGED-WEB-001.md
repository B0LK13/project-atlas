# AS-CODER-ALPHA-CHANGED-WEB-001

Read-only Web projection of `GET /v1/changed`.

```
#/changed?project=<id>
```

- Project scope is explicit `?project=` only. No harbor-api default.
- CHANGED != KDIFF. CHANGED != AUTHORITY. UNKNOWN history != UNCHANGED.
- Live failure is unavailable, never labelled DEMO.
- Depends on `AS-CODER-ALPHA-CHANGED-API-001`. Does not rotate inventories.

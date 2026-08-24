# AS-CODER-ALPHA-INBOX-WEB-001

Read-only Web projection of `GET /v1/inbox`.

```
#/inbox?project=<id>
```

- Project scope is explicit `?project=` only. No harbor-api default.
- INBOX != AUTHORITY. LISTING != MUTATION != COMMAND. UI != canonical.
- Live failure is unavailable, never labelled DEMO.
- Depends on `AS-CODER-ALPHA-INBOX-API-001`. Does not write Layer B.

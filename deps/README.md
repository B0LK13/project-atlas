# Dependency integrity (SEC-027 / SEC-028)

`integrity.json` pins SHA-256 of committed third-party lock/metadata artifacts.

| Class | Meaning |
|---|---|
| **LOCAL_SOURCE** | Editable `project-atlas` / `atlas_contracts` from this checkout |
| **THIRD_PARTY** | npm lockfile (and future pip freeze pins) |

Verify (fail-closed):

```bash
python scripts/verify_dep_integrity.py
```

Refresh after intentional dependency bumps:

```bash
npm --prefix apps/web install  # or npm ci workflow
# recompute hashes into deps/integrity.json (see verify script / remedi notes)
python scripts/verify_dep_integrity.py
```

`EXTERNAL_SECURITY_REVALIDATION_REQUIRED=YES`. This is not external security certification.

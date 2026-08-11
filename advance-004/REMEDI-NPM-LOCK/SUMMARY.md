# ADVANCE-004-B REMEDI-NPM-LOCK

## Problem
After #280 tip (19442d9), `npm ci` FAIL on Windows/npm 11: package.json/lock out of sync.
Missing `@rollup/rollup-*` platform packages. Root cause: vite resolved `rollup@4.62.4` whose
optionalDependencies declare platform packages at 4.62.4, but several (darwin-*, linux-*-gnu,
win32-arm64, win32-x64-msvc) were never published at 4.62.4 (latest 4.62.2). Hard-dep on
win32-x64-msvc worsened sync under npm 11.

## Fix (smallest deterministic)
- Move `@rollup/rollup-win32-x64-msvc` from dependencies → optionalDependencies pin `4.62.2`
- Add `overrides.rollup = 4.62.2` so platform optionals all exist and lock is complete
- Regenerate `apps/web/package-lock.json`; refresh `deps/integrity.json` SHA-256

## Proof
- npm 11.17.0 / node v26.4.0
- `npm ci` PASS (1) then `npm ci` PASS (2); `@rollup/rollup-win32-x64-msvc` present both times
- `python scripts/verify_dep_integrity.py` → DEP_INTEGRITY=PASS
- EXTERNAL_SECURITY_REVALIDATION_REQUIRED=YES
- CODEX_VALIDATED=NO

## Surface
- apps/web/package.json
- apps/web/package-lock.json
- deps/integrity.json
- atlas-start.ps1 Ensure-WebDependencies: NOT modified (npm ci sufficient)

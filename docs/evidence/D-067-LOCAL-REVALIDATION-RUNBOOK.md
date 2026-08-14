# Local D-067 narrow revalidation runbook

Do **not** replay all of D-065. Local already passed unaffected surfaces.

## Exact target

```
HEAD = ccacaa5bcb094f35017c7195264fef55e382cb49
TREE = d26768fe753c888cd45001987da2afe977c79d45
```

```bash
git fetch origin cursor/d049-d067-high-remediation-6f85
git checkout ccacaa5bcb094f35017c7195264fef55e382cb49
test "$(git rev-parse HEAD^{tree})" = "d26768fe753c888cd45001987da2afe977c79d45"
```

If HEAD/TREE differ → `VALIDATION_STALE`. Stop.

## Required probes

1. `Estate/DecoyHost/cache/fake-proj` (README + package.json + pyproject + .git + src) is **not** discovered. `RealProject` is.
2. Same decoy under `node_modules`, `.venv`, `dist`, `.atlas-vault`, `.git`, `.cache` remains ignored.
3. `project-cache`, `cache-service`, `cached`, `cachex`, `my-cache-project` **are** discovered.
4. Nested dirs at L9+ with a real project: JSON `scan_complete=false`, `depth_limit_reached=true`, `truncation_reason` contains `max_depth`.
5. Human CLI shows `SCAN INCOMPLETE` and `Depth limit reached (max_depth=8).`
6. `atlas discover --help` mentions current working directory and `max_depth=8`.
7. API `/v1/discovery` and Web `/discovery` show incomplete — no UI reclassification.
8. Quoted remote `url = "https://user:password@example.invalid/org/project.git"` → no password in report/CLI/API/Web.
9. Smoke only: junction/reparse escape still 0; CONNECTED still requires bind; stale report cannot connect; Coder Alpha identity still green.

## Out of scope for this IV

Full D-065 replay, authentic estate, D-042.

# CI timing — Windows 19m vs Linux 12m

Proposal only. This note does not change `.github/workflows/ci.yml`.
There is no workflow `repository:` owner gate to retarget; the `ci`
workflow already runs on every PR (`.github/workflows/ci.yml:3-6`).

## Measured wall clock

Source: successful `ci` run
[`35018874179`](https://github.com/bolkdev/project-atlas/actions/runs/35018874179)
on 2026-09-15 (`autonomy/scaffold` PR, same workflow as `main`).

| Job | Start → finish | Wall clock |
| --- | --- | --- |
| `quality (ubuntu-latest, 3.12, full)` | 20:19:39Z → 20:31:52Z | **12m 13s** |
| `quality (windows-latest, 3.12, windows)` | 20:19:39Z → 20:39:08Z | **19m 29s** |
| `quality (ubuntu-latest, 3.13, compat)` | 20:19:39Z → 20:26:05Z | 6m 26s (not critical path) |
| `control-plane` | 20:19:39Z → 20:20:33Z | 54s |

Critical path is the Windows quality job (~7m slower than Linux full).

## Where the Windows minutes go

| Step | File:line | Duration in `35018874179` | Notes |
| --- | --- | --- | --- |
| Install package | `ci.yml:41-42` | Windows 25s / Linux 9s | Hosted-runner + pip cache, not the gap |
| Ruff + mypy | `ci.yml:44-50` | Linux ~11s / Windows skipped | Linux-only; does not explain Windows being slower |
| Pytest with coverage (Linux full) | `ci.yml:52-54` | **11m 41s** | Single invocation; inherits `--cov` |
| Pytest product-perf (Windows) | `ci.yml:66-71` | **33s** | Correctly uses `--no-cov` |
| Pytest (Windows, not product_perf) | `ci.yml:73-75` | **16m 59s** | Inherits `--cov` from addopts |
| CLI smoke | `ci.yml:77-86` | Windows 5s / Linux 3s | Negligible |
| Golden fixture re-run (Windows) | `ci.yml:88-90` | **66s** | Same test already inside the main Windows pytest |

`pyproject.toml:41` sets global addopts
`-q --cov=project_atlas --cov-report=term-missing --cov-report=xml --no-cov-on-fail`.
The Windows product-perf step already documents that coverage
instrumentation is too expensive on hosted Windows
(`ci.yml:68-70`). The following full-suite step does not pass
`--no-cov`, so Windows pays coverage + NTFS + three sequential
pytest processes.

Linux full is one pytest process with coverage. Windows is three:
product-perf (uncovered), full suite minus that marker (covered),
then `test_k005_settled_rebuild_is_byte_identical_to_golden_state`
again.

## Why not "Windows is just slower"?

A slower filesystem explains part of the 17m vs 12m pytest gap.
It does not explain the extra ~100s of sequential re-entry
(product-perf + golden re-run) or the coverage mismatch the
workflow already called out for product-perf.

Existing markers (`pyproject.toml:42-46`): `integration`,
`security_regression`, `product_perf`. There is no `unit` marker;
unit tests are "not integration".

## Proposed split (do not implement here)

1. **Cheapest win:** add `--no-cov` to the Windows full-suite step
   (`ci.yml:75`). Coverage already belongs to Linux `full`
   (`ci.yml:52-54`). Expected save: a large fraction of the 5m
   pytest-only gap; no new jobs; required-check names unchanged.
2. **Drop or gate the golden re-run** (`ci.yml:88-90`). The test
   already runs in `pytest -m "not product_perf"`. Keep a dedicated
   step only if a clean process is required for CRLF isolation;
   otherwise it is a 66s duplicate.
3. **Marker / job split (if (1)+(2) are not enough):**
   - `quality-windows-unit`:
     `pytest -m "not integration and not product_perf" --no-cov`
   - `quality-windows-integration`:
     `pytest -m "integration and not product_perf" --no-cov`
   - keep `product_perf` as the existing uncovered step
   Parallel jobs cut wall clock; they change required-check
   identities (`quality (windows-latest, 3.12, windows)` in
   `ci.yml:26-28`), so they need an explicit branch-protection
   update. Do not invent a new `unit` marker unless operators
   want opt-in local runs; `not integration` is enough.
4. **Do not split Linux `full`** until coverage is collected in one
   process or merged from shards. `compat` (3.13) is already a
   second uncovered Linux lane and is not the bottleneck.

## Out of scope

- No `ci.yml` edit in D-ATLAS-P1 (proposal only).
- No `autonomy/**` paths.
- Runtime `CANONICAL_REPO` constants under `src/**` / `tests/**`
  are a follow-up issue (P2 path collision).

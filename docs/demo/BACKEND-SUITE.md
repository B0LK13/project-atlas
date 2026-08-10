# AS-DEMO-2.1-001 — Backend full-suite demo runbook

> **DEMO** · **NOT AUTHENTIC PILOT** · **NOT RELEASE EVIDENCE**
>
> Package: `AS-DEMO-2.1-001` · Lane: TECHNICAL_PREVIEW · Worker: **D04**
>
> Certificate target for this lane: **TECHNICAL DEMO — VERIFIED**
>
> Passing this runbook is **not** `RELEASE CERTIFIED`, **not** authentic
> estate `PILOT PASS`, and **must not** be cited as `v2.1.0` release evidence.

Companion operator checklist: [`checklists/backend.md`](./checklists/backend.md).

## Scope

This document defines how operators run the **backend** quality gate for the
Technical Demo / PoC lane:

1. A focused **pytest subset** for fast Core + CLI confidence during rehearsal.
2. The **full backend suite** (`ruff` → `mypy` → `pytest`) required before any
   claim of **TECHNICAL DEMO — VERIFIED**.
3. The **atlas CLI smoke** contract aligned with `.github/workflows/ci.yml`
   (AT-001 scaffold checks).

Out of scope here: frontend build/smoke, live API/MCP E2E scripts, browser
automation, L3/OpenAI optional paths (see sibling `docs/demo/` packages).

## Honest mode banner

Print (or retain) this banner on every backend demo gate capture:

```text
=== ATLAS TECHNICAL DEMO — BACKEND GATE ===
MODE: DEMO / TECHNICAL_PREVIEW
CERTIFICATE TARGET: TECHNICAL DEMO — VERIFIED
NOT RELEASE CERTIFIED
NOT AUTHENTIC PILOT PASS
NOT RELEASE EVIDENCE
DEMO_FIXTURE ≠ authentic estate
===========================================
```

## Prerequisites

| Requirement | Notes |
|---|---|
| Clean clone or dedicated worktree | No hidden developer vaults for certification runs |
| Python 3.12+ | Matches CI `full` / `windows` matrix |
| Editable install | `pip install -e ".[dev]"` |
| Working directory | Repository root |

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
atlas version
```

POSIX:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev]"
atlas version
```

## Capture rules (mandatory)

Directive §19: record **live** results from the run you just executed.

Capture for each gate:

| Field | Example source |
|---|---|
| command | exact argv |
| exit code | `0` / non-zero |
| test count | pytest summary `collected` / `passed` |
| pass count | pytest `passed` |
| fail count | pytest `failed` (must be `0` for VERIFIED) |
| skip count | pytest `skipped` |
| duration | pytest / wall clock for the command |
| tip pin | `git rev-parse HEAD` and optional TREE hash |

**Do not** quote historical test counts from prior PRs, WORKLOG snippets, or
CI badges.

Open findings as `DEMO-FINDING-###` (CRITICAL / HIGH / MEDIUM / LOW).
CRITICAL and HIGH block **TECHNICAL DEMO — VERIFIED**.

---

## Layer 1 — Pytest subset (rehearsal)

Use during demo dry-runs when you need Core + CLI confidence quickly.
This layer alone is **insufficient** for **TECHNICAL DEMO — VERIFIED**.

```powershell
# Windows / POSIX — from repo root, venv active
python -m pytest `
  tests/integration/test_cli.py `
  tests/integration/test_core_vertical_slice.py `
  tests/integration/test_core_claims_authority_conflicts.py `
  tests/unit/test_scaffold.py `
  -q --tb=short
```

If a path is absent on the checked-out tip, drop that argument and record
`DEMO-FINDING-###` (path drift) — do not invent modules.

Intent of the subset:

| Module | Why |
|---|---|
| `test_cli.py` | argparse entry, `init` AT-001 contract |
| `test_core_vertical_slice.py` | discover → ingest → indexes → validate story |
| `test_core_claims_authority_conflicts.py` | authority / conflict behavior for demo narrative |
| `test_scaffold.py` | vault skeleton determinism |

Optional tighter smoke (CLI only):

```powershell
python -m pytest tests/integration/test_cli.py -q --tb=short
```

---

## Layer 2 — Full backend suite (VERIFIED gate)

Repository-approved sequence (same spirit as CI `quality` / `full`):

```powershell
python -m ruff check .
python -m mypy src
python -m pytest
```

POSIX one-liner equivalent:

```bash
python -m ruff check . && python -m mypy src && python -m pytest
```

Notes:

- `pyproject.toml` already sets pytest `addopts` (quiet + coverage). Do not
  invent alternate coverage thresholds for demo certification.
- Control-plane suite under `atlas-vault-documentation/tests/` is a **sibling**
  CI job. It is **not** required to stamp backend **TECHNICAL DEMO — VERIFIED**
  unless the charter explicitly expands scope. If run, capture separately and
  use `--no-cov` as CI does.
- Fail-closed: any non-zero exit from ruff, mypy, or pytest blocks VERIFIED.

---

## Layer 3 — Atlas CLI smoke (AT-001)

Mirror `.github/workflows/ci.yml` CLI smoke. Use a disposable output under
`.tmp/` (never a production vault).

PowerShell:

```powershell
$SmokeVault = Join-Path $PWD ".tmp\atlas-demo-cli-smoke"
if (Test-Path $SmokeVault) { Remove-Item -Recurse -Force $SmokeVault }

atlas --help
if ($LASTEXITCODE -ne 0) { throw "atlas --help failed" }

atlas version
if ($LASTEXITCODE -ne 0) { throw "atlas version failed" }

atlas init --output $SmokeVault --dry-run
if ($LASTEXITCODE -ne 0) { throw "atlas init --dry-run failed" }

atlas init --output $SmokeVault
if ($LASTEXITCODE -ne 0) { throw "atlas init failed" }

if (-not (Test-Path (Join-Path $SmokeVault "index.md"))) {
  throw "missing index.md"
}
if (-not (Test-Path (Join-Path $SmokeVault "00-system\vault-charter.md"))) {
  throw "missing 00-system/vault-charter.md"
}

Write-Host "CLI smoke PASS"
```

Bash (Git Bash / CI-style):

```bash
SMOKE_VAULT=".tmp/atlas-demo-cli-smoke"
rm -rf "$SMOKE_VAULT"
atlas --help
atlas version
atlas init --output "$SMOKE_VAULT" --dry-run
atlas init --output "$SMOKE_VAULT"
test -f "$SMOKE_VAULT/index.md"
test -f "$SMOKE_VAULT/00-system/vault-charter.md"
echo "CLI smoke PASS"
```

Optional demo-fixture pipeline smoke (Mode A rehearsal; still **not** release
evidence). Only after DEMO_FIXTURE corpus exists under the normative path:

```powershell
$DemoRoot = Join-Path $PWD "tests\fixtures\demo"   # or docs/demo/fixtures when landed
$Vault    = Join-Path $PWD ".tmp\demo-vault-backend"
$Manifest = Join-Path $PWD ".tmp\demo-manifest-backend.json"
# atlas init / discover / ingest / build-indexes / validate — see QUICKSTART
```

Label every artifact `DEMO_FIXTURE` / **DEMO ≠ pilot**.

---

## TECHNICAL DEMO — VERIFIED (backend criteria)

Stamp **backend contribution** toward **TECHNICAL DEMO — VERIFIED** only when
**all** of the following are true for the same tip pin:

| # | Criterion | Required |
|---|---|---|
| B1 | Clean clone / dedicated worktree; install via `pip install -e ".[dev]"` | Yes |
| B2 | Honest mode banner recorded (DEMO / not release / not pilot) | Yes |
| B3 | `python -m ruff check .` exit `0` | Yes |
| B4 | `python -m mypy src` exit `0` | Yes |
| B5 | Full `python -m pytest` exit `0`; live pass/fail/skip/duration captured | Yes |
| B6 | Atlas CLI smoke (help, version, init dry-run, init, `index.md` + charter) exit `0` | Yes |
| B7 | No open CRITICAL/HIGH `DEMO-FINDING-###` against backend gates | Yes |
| B8 | Operator checklist [`checklists/backend.md`](./checklists/backend.md) completed | Yes |

Layer 1 subset pass is rehearsal-only and **does not** satisfy B5.

### Explicit non-claims (always)

| Claim | Backend gate may assert? |
|---|---|
| **TECHNICAL DEMO — VERIFIED** (when B1–B8 pass and other demo lanes agree) | Yes (demo lane only) |
| `RELEASE CERTIFIED` / `ATLAS_2_1_RELEASE_CERTIFIED` | **No** |
| Authentic estate `PILOT PASS` | **No** |
| `v2.1.0` release evidence | **No** |
| DEMO_FIXTURE ≡ authentic pilot corpus | **No** |

Authentic pilot remains `DORMANT_BLOCKED` until
`AUTHENTIC_ESTATE_ROOT_AVAILABLE`. Backend demo success does **not** wake
that gate.

## Suggested evidence filename (orphans)

Coordination note only (still **NOT RELEASE EVIDENCE**):

`D:\project-atlas-orphans\atlas-2.1-productionization-001\AS-DEMO-2.1-001-D04-BACKEND.md`

## Related documents

| Doc | Role |
|---|---|
| `docs/demo/AS-DEMO-2.1-001.md` | Charter (D01; when merged) |
| `docs/demo/checklists/backend.md` | Operator checklist (this package) |
| `docs/demo/CERTIFICATE-TEMPLATE.md` | Certificate wording (D08; when merged) |
| `.github/workflows/ci.yml` | Authoritative CI command sequence |

## Changelog

| Date | Change |
|---|---|
| 2026-08-10 | D04 initial backend suite runbook (docs-only) |

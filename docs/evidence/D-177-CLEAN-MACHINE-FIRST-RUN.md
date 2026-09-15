# D-177 LANE B — Clean-machine-ish first run + golden estate fingerprint

| Field | Value |
|---|---|
| DIRECTIVE | D-177 |
| LANE | B (clean-machine install + estate compile) |
| MAIN_HEAD | `a17949c6df9b4d004ffe03eb47b0934e3735204d` |
| MAIN_TREE | `e646392c12fa525dcfd017c33e1b6226c5bfb40a` |
| ATLAS_VERSION | `project-atlas 2.0.0` |
| Recorded | 2026-08-25 (local) |
| Work root | `D:\project-atlas` |

## Honesty

```text
TECHNICAL DEMO — NOT RELEASE CERTIFIED — NOT AUTHENTIC PILOT — DEMO_FIXTURE
DEMO_FIXTURE != authentic pilot
This run is disposable fixture evidence only. It does NOT wake AUTHENTIC_PILOT
and does NOT set ATLAS release certification.
```

## Environment (clean-ish)

| Item | Value |
|---|---|
| Invocation | `PYTHONPATH=src` → `python -m project_atlas.cli …` |
| Editable install | not required for this lane (PYTHONPATH smoke) |
| `AUTHENTIC_ESTATE_ROOT` | unset |
| `ATLAS_DEMO_MODE` | `fixture` |
| `ATLAS_DEMO_FIXTURE` | `.tmp/d177-demo-estate` (absolute) |
| Estate source | materialized copy of `fixtures/demo/estate` |
| Vault | `.tmp/d177-demo-vault` (disposable) |
| Manifest | `.tmp/d177-demo-manifest.json` |

## Estate materialization

1. Copied `fixtures/demo/estate` → `.tmp/d177-demo-estate/`
2. `git init` + baseline commit on each of `project-a`, `project-b`, `project-c` (no prior `.git`)

Fingerprint excludes `.git` (canonical `project_atlas.full_product_demo.estate_fingerprint`).

| Field | Value |
|---|---|
| `DEMO_ESTATE_FINGERPRINT` | `5a9cf6a8c76b6005d95d3b7ebc010f90bc82dec9b188b042edca1325cb635ac4` |
| Match vs `fixtures/demo/estate` | **YES** (identical SHA-256) |
| File count (ex `.git`) | **16** |
| Manifest path | `docs/demo/DEMO-ESTATE-MANIFEST.json` |

## Commands + exit codes

All commands from repo root with `$env:PYTHONPATH = (Resolve-Path src).Path`.

### CLEAN_MACHINE_INSTALL / version smoke

```text
CMD: python -m project_atlas.cli version
EXIT: 0
OUT:  project-atlas 2.0.0
```

### INIT

```text
CMD: python -m project_atlas.cli init --output D:\project-atlas\.tmp\d177-demo-vault
EXIT: 0
OUT:  created vault scaffold … directories: 31 files: 29 vault_id=atlas-main
```

### DISCOVER

```text
CMD: python -m project_atlas.cli discover --source D:\project-atlas\.tmp\d177-demo-estate --output D:\project-atlas\.tmp\d177-demo-manifest.json
EXIT: 0
OUT:  discovered 114 sources; agent event packages: 0
```

Note: 114 includes files under per-project `.git/` introduced by materialization `git init`. Fixture content corpus remains 16 files (ex `.git`). Ingest below confirms the intended 16 documents / 3 projects.

### INGEST

```text
CMD: python -m project_atlas.cli ingest --manifest D:\project-atlas\.tmp\d177-demo-manifest.json --vault D:\project-atlas\.tmp\d177-demo-vault --source D:\project-atlas\.tmp\d177-demo-estate
EXIT: 0
OUT:  ingested 16 documents; projects: 3; agent events: 0; quarantined events: 0
```

### BUILD-INDEXES

```text
CMD: python -m project_atlas.cli build-indexes --vault D:\project-atlas\.tmp\d177-demo-vault
EXIT: 0
OUT:  indexed 3 projects and 16 sources
```

### VALIDATE

```text
CMD: python -m project_atlas.cli validate --vault D:\project-atlas\.tmp\d177-demo-vault
EXIT: 0
OUT:  validated 84 Markdown files
```

## Status matrix (Lane B)

| Gate | Status | Notes |
|---|---|---|
| CLEAN_MACHINE_INSTALL | **PASS** | `PYTHONPATH=src` + `atlas version` exit 0 |
| CLEAN_MACHINE_FIRST_RUN / FIRST_RUN | **PASS** | init→discover→ingest→build-indexes→validate all exit 0 on disposable paths |
| DISCOVER | **PASS** | exit 0; manifest written (114 filesystem sources incl. `.git`) |
| INGEST | **PASS** | exit 0; **16 documents / 3 projects** |
| BUILD | **PASS** | exit 0; 3 projects / 16 sources indexed |
| VALIDATE | **PASS** | exit 0 |

No DEMO_CRITICAL or env blockers observed on this run.

## Non-claims

- Not authentic pilot / not `AUTHENTIC_ESTATE_ROOT` evidence.
- Not release certification.
- No merges and no feature PRs created by this lane.
- Disposable artifacts under `.tmp/d177-*` are gitignored runtime state.

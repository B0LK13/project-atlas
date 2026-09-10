# AS-IMPR-PLANE-001 — Delivery-evidence improvement plane

**Status:** Implemented through continuation-002 (lane-local; not merged; no authority)  
**Directive:** `ATLAS-PARALLEL-IMPROVEMENT-PLANE-20260910` + `ATLAS-IMPROVEMENT-PLANE-CONTINUATION-002`  
**Goal:** `ATLAS-EVIDENCE-TO-IMPROVEMENT-20260910`  
**Package:** `AS-IMPR-PLANE-001`  
**Entry point:** `python -m project_atlas.improvement_plane`

## Cycle

```text
observe → compare → explain → recommend → record outcome → evaluate
```

| Command | Mode | Purpose |
|---|---|---|
| `report` / `inspect` | read-only (+ optional output files) | Coverage, panels, kind-split recommendations |
| `compare --before --after` | read-only (+ optional outputs) | new/resolved/persistent/changed/unobservable; incomplete/incompatible exposed |
| `outcome ...` | **writes** `.atlas/improvement-plane/outcomes.jsonl` | Local annotation only |
| `evaluate --before --after` | read-only (+ optional outputs) | improved/persisted/regressed/inconclusive |

Resolved requires explicit `closed_findings` evidence in the after snapshot.
Disappearance alone is `unobservable` / evaluation `inconclusive`.


## Identities (do not conflate)

| Identity | Meaning |
|---|---|
| Source pin | Analysis baseline (`docs/evidence/AS-IMPR-PLANE-001-SOURCE-PIN.json`) |
| Implementation commit | Lane code checkpoint(s) on this branch |
| Generated reports | Regenerable outputs; excluded from evidence via self-ingest guard |
| Outcome annotations | Local non-authoritative store; never DAG authority |

## Honesty

```text
RECOMMENDATION ≠ AUTHORITY
OUTCOME ANNOTATION ≠ GATE RESOLUTION
DISAPPEARING EVIDENCE ≠ RESOLVED
ASSOCIATION ≠ CAUSATION
FILE COUNT ≠ EVIDENCE QUALITY
MISSING_TIMESTAMP ≠ 0
BASELINE CI ≠ LANE COVERAGE
```

## Reproduce

```bash
cd /home/gebruiker/Projects/project-atlas-worktrees/improvement-plane
export PYTHONPATH=src

python -m pytest tests/unit/test_as_impr_plane_001.py tests/unit/test_as_impr_plane_002_cycle.py --no-cov

python -m project_atlas.improvement_plane report --repo . \
  --reference-utc 2026-09-10T06:00:00Z \
  --output-json /tmp/impr-before.json

python -m project_atlas.improvement_plane compare \
  --before /tmp/impr-before.json --after /tmp/impr-before.json

python -m project_atlas.improvement_plane outcome --repo . \
  --recommendation-id finding:EXAMPLE --status attempted \
  --evidence-ref docs/evidence/some.json --json

python -m project_atlas.improvement_plane evaluate --repo . \
  --before /tmp/impr-before.json --after /tmp/impr-before.json
```

## Optional adoption

Thin `atlas impr …` wrappers may later call these APIs. Not required for this lane;
shared CLI registration remains untouched.

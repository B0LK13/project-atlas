# SURFACE_OVERLAP_REPORT — Intelligence Wave 1

Directive: `D-PROJECT-ATLAS-CLOUD-AUTONOMOUS-2.0-WAVE1-INTELLIGENCE-CORE`

## Start pins

Captured after `git fetch origin main`:

```
START_MAIN_HEAD = d2d3df478cc1a20f5d88e9f51c5c3e4f066d7f00
START_MAIN_TREE = 6f807a031593d6c3ac2dc41dbcd40509d82d8508
```

`origin/main` tip at capture: merge of `#356` (Time Machine live project). `#358` and `#356` are merged.

## Current train (out of scope)

| PR | State | Surfaces |
|----|-------|----------|
| `#357` | OPEN, EXACT-MAIN READY FOR LOCAL IV, HEAD `a35eadbf612498f6fe38402105470edfedef1105` | `apps/web/src/App.tsx`, `ProdNav.tsx`, `KnowledgePage.tsx`, Ask live hook/page, WORKLOG, ask evidence/tests |
| `#354` | OPEN, FINAL ROADMAP PR, CONFLICTING vs main | Roadmap module + CLI/API/web registration, `schema.py`, `connect.py`, `agent_handoff.py`, `yaml_structured.py`, WORKLOG, backlog, roadmap fixtures/tests |
| `#355` | OPEN, docs-only seal | WORKLOG, backlog, D-095 evidence |

## Isolation decision

This wave adds only:

- `src/project_atlas/intelligence/` (new package)
- `tests/unit/test_as_2_0_intel_*.py`, `tests/unit/test_as_2_0_state_001.py`
- new isolated evidence / ADR / future-contract docs

It does **not** modify:

- `main`
- `#357` / `#354` branches or PR bodies
- `apps/web/**`
- Time Machine or Roadmap integration surfaces
- `WORKLOG.md`, `docs/backlog.md`
- `pyproject.toml`, lockfiles, CI workflows
- `cli.py`, `api_server.py`, `web_api/**`, `schema.py`

## Overlap classification

| Surface | `#357` | `#354` | Other open PRs | This wave |
|---------|--------|--------|----------------|-----------|
| Web Ask / Knowledge / ProdNav / App | YES | YES (nav) | no | NO |
| Roadmap / CLI / LIVE_API routing | no | YES | no | NO |
| `schema.py` / shipped JSON schemas | no | YES | no | NO |
| WORKLOG / backlog | YES | YES | `#355` | NO |
| Core claim / lineage / temporal / authority modules | no | no | no | import-only, no edits |
| New `intelligence/` library | no | no | no | YES |

```
CURRENT_TRAIN_OVERLAP = NO
SURFACE_OVERLAP_GATE = PASS
```

If a later design had required editing train files, the package would have been redesigned. No such requirement appeared.

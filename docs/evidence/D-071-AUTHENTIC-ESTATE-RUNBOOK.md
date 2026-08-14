# D-049 authentic-estate next step (prepare only — do not execute)

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-FINAL-RECONCILIATION-071`

```
AUTHENTIC_USER_ESTATE_ACCEPTANCE = NOT_EVALUATED
D_042_EXECUTION_GATE = CLOSED
```

This is product-level proof **after** technical merge and post-merge
seal. It is not D-049 technical acceptance. It is not D-042.

Cloud did not invent an estate root and did not scan owner systems.

## Authorization boundary

Owner names **one** bounded existing root.

Never without explicit owner authorization:

- entire disk
- home directory
- all Documents
- all OneDrive
- all Obsidian

No network discovery. No second root. No cloud sync.

## Preconditions

1. `#348` merged and post-merge seal recorded
2. Checkout / binary matches sealed `main` production trees
   (`src/` identical to `ccacaa5`)
3. Owner names exactly one authorized root
4. Discovery must not create canonical projects by itself

## Protocol

```bash
atlas init --output <throwaway-or-owner-designated-vault>
atlas discover --root <OWNER_AUTHORIZED_ROOT> --vault <vault>
atlas discover review --vault <vault>
```

Do **not** run `atlas ingest` unless the owner separately authorizes
ingest of a named candidate.

`atlas discover connect` only for a candidate the owner explicitly
accepts after reviewing match evidence.

Stop. Record metrics. Do not expand the root.

## Metrics (fill after the run; do not invent)

```
PROJECTS_EXPECTED =
PROJECTS_FOUND =
PROJECT_DISCOVERY_RECALL =

KNOWLEDGE_EXPECTED =
KNOWLEDGE_FOUND =

FALSE_PROJECT_MATCH_COUNT =
AMBIGUOUS_MATCH_COUNT =
USER_CORRECTIONS_REQUIRED =
MANUAL_PATHS_REQUIRED =

UNSAFE_PATH_ESCAPES =
CROSS_PROJECT_LEAKS =
TIME_TO_DISCOVER_PROJECTS =
```

## Honesty

- Missing projects stay missing
- Ambiguity stays visible
- `DISCOVER != INGEST != TRUST != AUTHORITY`
- Technical merge ≠ authentic-estate acceptance
- This runbook does not unlock Conversational Capture, Visual Project
  Roadmap, Project Memory, Momentum, Portfolio Intelligence, 2.3
  autonomy, OPT, AutoLab, or Prime

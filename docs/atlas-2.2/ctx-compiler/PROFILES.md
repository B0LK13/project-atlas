# Context Compiler — task profiles (PREP)

Status: **PREP ONLY**. Profile IDs are reserved vocabulary, not runtime enums.

Package: **AS-2.2-CTX-COMPILER-001**.

## Profiles

| Profile ID | Intent | Prefer | De-prioritize |
|---|---|---|---|
| `developer` | Active implementation | overview, architecture, active WP, decisions, standards, risks, latest validation | executive narrative, unrelated projects |
| `architect` | Structural change | architecture, decisions, relationships, constraints, ADRs | ephemeral validation noise |
| `security` | Review / threat work | threat model, trust boundaries, deps, deployment, findings | marketing overview |
| `release` | Ship / certify | release notes, checklists, evidence indexes, migration/recovery | research hypotheses |
| `operations` | Run / observe | runbooks, ops receipts, health (unknown preserved), rollback | speculative design |
| `research` | Explore / Ask Atlas | evidence packs, hypotheses, reality-gap planes, open questions | unverified model summaries as fact |

## Profile contract sketch

```text
profile_id
scope.project_ids[]          # optional pins
scope.exclude_project_ids[]
budget.max_items
budget.max_bytes
budget.on_overflow           # truncate | fail
include_unresolved_conflicts # bool (default true with sidecars)
```

## Rules

1. Profiles change **ordering and inclusion preference**, never authority levels.
2. A profile cannot mark `unknown` freshness as `fresh`.
3. Security profile cannot suppress unresolved conflicts.
4. Missing profile → fail closed (`context-compiler-profile-unknown`).

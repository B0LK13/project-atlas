# D-ATLAS-ITER-<n>: <short imperative title>

Instrument: loop-improvable from policy phase 3 (`autonomy/policy.md` section 4).

- Iteration: `<n>`
- Proposed by: `<executor, from RP-<n-1>>` or `<owner>`
- Derived from: `<base_sha>` (the repository state this directive was written against)
- Roadmap anchor: `<doc path + section, e.g. docs/product/CODER-ALPHA-NORTH-STAR.md>`

## Problem (repository truth)

What is missing or broken, stated with evidence pointers only
(`sha:path:line`, failing test id, open backlog line). No pointer, no claim.

## Target

One brain-tier capability or gap, small enough to finish within the policy budget.

## Scope

- Files expected to change (inside policy section 4 allowed scopes):
- Tests to add (name the behavior each one pins):
- Explicitly out of scope:
- Test removals or skips authorized: `none` (or list each with a reason)
- Scope exceptions needed from the owner grant: `none` (or list globs with a reason)

## Acceptance

- Observable behavior that proves the target:
- Linux lane command(s):
- Native Windows lane command(s):
- Test count: `>= <baseline>`

## Budget estimate

`files <= ?`, `diff lines <= ?`, `minutes <= ?`. Must fit the grant budget.

## Risks and unknowns

Explicit list. Write "none known" rather than leaving it blank.

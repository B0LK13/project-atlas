# What this does not do, and what needs an owner

## Dependencies on unmerged work

`atlas task` reuses `orchestration/program` for the task, acceptance, profile
and limit models, for `load_program`, and for the agent registry. That package
is **not on `main`**: it lives in PR #797, and this branch is based on its head
`80280bfe`. Until #797 lands, `atlas task` exists only where that package does.

The preflight tool the demonstration runs as a cross-check
(`scripts/acceptance/program_preflight.py`, AS-PREFLIGHT-001) is on a separate
unpushed branch. `run-demo.sh` takes its path from `ATLAS_PREFLIGHT` and says
so plainly when it is absent, rather than silently skipping a step.

**Owner handoff:** the sequencing of #797 relative to this package is a
decision, not something this branch can settle.

## Checks that are deliberately absent

**Cross-contract dependency cycles.** `dependencies.self_reference` catches a
contract depending on itself, and `dependencies.missing` catches a dependency
that is not an eligible item in any declared source. A cycle spanning several
contracts is not detected here. Rendering several contracts into one program
does detect it, because `WorkProgram`'s own validator rejects cycles — that is
the existing mechanism, and duplicating it in a second place would create two
answers that can disagree.

**Whether a check is a good check.** `content.requirement_presence_only`
rejects a behavioural requirement judged only by presence. It cannot tell a
weak `COMMAND` from a strong one — a check that exits 0 unconditionally passes
validation. Nothing here reads what a command does.

**Whether the instruction is understandable.** Every requirement reaches the
worker verbatim. Whether the wording is clear enough to act on is a human
judgment, and the contract has no way to test it.

**Whether prose duplicates a path.** `content.path_repeated_in_prose` is text
matching, so it is a WARNING and never more. It skips a field whose entire
value is the path, because this project's own acceptance contracts legitimately
write scope as a bare path list.

## Things that are true only on this host

A bare executable resolving here says nothing about the worker's environment,
and `acceptance.executable_bare` is a WARNING for exactly that reason. The
binding's interpreter check, the workspace check and the base-pin check all
describe the machine validation ran on. Re-validate on the deployment host;
`binding_digest` changing is what forces that.

## Where authority genuinely lives

`execution_authorization: DEMONSTRATED` means one ACTIVE registry agent holds
the role and is assigned the rendered program **at the moment of validation**.
It is not permission. The supervisor re-reads status, role, substitution grant
and assignment immediately before every dispatch, and that is the authoritative
check. A validation report is evidence about a moment, not a standing grant.

## Not claimed

No receipt has been issued for this work. Nothing here has been independently
verified, merged, or run by a worker. `acceptance_outcome` is `NOT_EVALUATED`
in every report this package produces, and it has no code path that sets it to
anything else.

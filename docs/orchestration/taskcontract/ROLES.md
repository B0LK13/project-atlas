# Who needs what

## Task preparer

You turn one backlog item into a contract. Your job is to make the decisions no
source can make, and to leave the ones you cannot make visibly open.

1. `atlas task sources --project <repo>` — what is eligible. A checked item is
   never offered; nothing is scanned that the project has not declared.
2. `atlas task draft --project <repo> --item <ID>` with no `--supplied` first.
   The output lists every field you must decide, each with the question it
   answers. Write those answers into a `supplied.json`; keys starting with `_`
   are comments and are ignored.
3. `atlas task draft ... --supplied supplied.json --out contract.json`. Read the
   `conflicts` list: a disagreement between your input and the item's own
   acceptance contract is reported, never resolved by precedence.
4. `atlas task validate --contract contract.json --binding binding.json
   --project <repo>` until the ERRORs are gone. WARNINGs are for you to judge,
   not to clear by rewording.

Do not invent an owner, an authorization, an acceptance command, a budget or a
mutation path to make a draft complete. An empty field is honest; a plausible
default looks reviewed.

A requirement you cannot check is not a failure of the contract. Mark it
`HUMAN_REVIEW` or `NO_CHECK_AVAILABLE` and say what a reviewer should look at.
Attaching a `FILE_EXISTS` check to a behavioural requirement is rejected,
because a worker that writes an empty file passes it.

## Deployment agent

You own `binding.json`: the absolute `workspace_root`, `state_root`,
`registry_root` and `interpreter` of one installation, plus the profile and
role. The contract never contains these.

- `state_root` must not lie inside the workspace. State a worker can edit is
  not state.
- `interpreter` must be an absolute path that exists. `task render` substitutes
  it into every acceptance argv that names bare `python`/`python3`.
- Changing anything here changes `binding_digest`, and `task verify` reports
  every earlier validation report against it as stale. That is the intended
  behaviour, not an inconvenience.
- A green `task validate` is not authorization to launch. Assignment is a
  separate act through `atlas agent assign`, and the supervisor re-checks it
  before every dispatch.

Run the official validator on what you were given, not only this package's:

```bash
atlas program validate --program program.json --state-root <state>
python scripts/acceptance/program_preflight.py --program program.json \
       --state-root <state> --registry <registry>   # when available
```

## Reviewer

`atlas task review --out review-package.json` gives you the contract, the
binding, the generated instruction, the generated program and the validation
report in one file, plus `review_is_of`: the three digests your review is
about.

Your approval is of those digests. Before acting on an older review:

```bash
atlas task verify --contract contract.json --report report.json --binding binding.json
atlas task diff --before contract.v1.json --after contract.v2.json
```

`diff` reports `prior_approval_still_describes_this_work: false` whenever
scope, acceptance, authorization references or the binding moved, with
`why_not` naming which. An earlier approval does not quietly survive those.

What a green report does not tell you: whether the work was done. Every report
carries `acceptance_outcome: NOT_EVALUATED`, because nothing in this package
runs a check or observes a result.

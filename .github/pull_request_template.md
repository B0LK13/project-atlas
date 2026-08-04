<!--
Fill in every section. Delete none of them; write "n/a" with a reason
if a section genuinely does not apply. See CONTRIBUTING.md and
docs/adr/ADR-006-github-repository-governance-baseline.md for the
policy this template implements.
-->

## Work package

- **Package ID:** <!-- e.g. AS-GH-001 -->
- **Exact base hash:** <!-- commit this branch was created from -->
- **Exact implementation hash(es):** <!-- commit(s) containing the change -->
- **Exact evidence hash:** <!-- commit containing/updating the receipt, if separate -->
- **Receipt path:** <!-- e.g. docs/evidence/AS-xxx-receipt.yaml -->

## Scope

- **Changed paths:**
  <!-- exact list, not a summary -->

## Validation

- **Commands run and results:**
  <!-- exact commands and pass/fail counts, e.g.
  python -m pytest -> N passed
  python -m ruff check . -> clean
  python -m mypy src -> clean, N files -->

## Impact

- **Security impact:** <!-- none / describe -->
- **Documentation impact:** <!-- none / describe -->
- **Rollback considerations:** <!-- how to revert this change safely -->
- **Known limitations:** <!-- explicitly list, or "none" -->

## Certification

- [ ] Independent reviewer/verifier has reproduced the validation results above.
- [ ] Owner authorization has been explicitly given for this exact hash (not a branch name).

## Prohibited history operations acknowledgement

- [ ] This PR does not rebase, amend, squash, or force-push any commit
      that already exists on `main`.
- [ ] This PR does not rewrite, delete, or bypass any existing
      certified evidence, ADR, or receipt.

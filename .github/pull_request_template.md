## Package / issue

<!-- e.g. AS-GH-001, or a plain issue reference -->

## Purpose and scope

<!-- What this PR does, and just as importantly, what it deliberately does not do. -->

## Exact base and source

- Exact base commit: `<full SHA>`
- Source branch tip (at time of opening): `<full SHA>`
  <!-- Refresh this value after the final push and before requesting
       independent certification. There is no need to update it
       continuously during active development. -->

## Changed paths

<!-- List every changed path. If this is a governance/architecture PR, confirm the
     path list matches the certified scope exactly. -->

## Security impact

<!-- Does this change affect secrets, permissions, workflow triggers, or the
     security-reporting policy? If none, say "None." -->

## Documentation impact

<!-- Which docs were updated? If none were needed, say why. -->

## Migration or operational impact

- Migration or operational impact: `none` / `described below`
<!-- If not "none": describe any schema, receipt, generated-vault, or
     canonical-state migration this PR requires or triggers, and how
     it is applied/rolled back. -->

## GitHub settings impact

<!-- Does this PR itself require or assume a branch-protection / repository
     settings change? If yes, name the exact setting and who is authorized to
     change it. If none, say "None — settings changes are a separate, later
     phase." -->

## Validation commands and results

<!-- Real, actually-run commands and their actual results. Do not report a
     command you did not run. -->

```
<command>
<exit code / summary>
```

## Check names observed

<!-- The exact GitHub check names you actually saw reported on this PR's
     commits, not a guessed or hypothetical name (e.g. "quality"). -->

## Evidence location

<!-- Path to the receipt/evidence file for this change, if this repository's
     evidence convention applies. -->

## Rollback approach

<!-- How to revert this specific change if it turns out to be wrong. -->

## Known limitations

<!-- Anything intentionally deferred or out of scope for this PR. -->

## Governance state

- Independent certification: `pending` / `passed` / `blocked`
- Project Owner integration authorization: `not granted` / `granted`
<!-- Keep detailed evidence in the linked receipt (see "Evidence
     location" above) rather than embedding lengthy material here. -->

## Reviewer checklist

- [ ] No unrelated changes are included.
- [ ] No force push, history rewrite, or unauthorized squash was used to produce this branch.
- [ ] No invented, placeholder, or personal security contact was introduced.
- [ ] Every required-check name referenced above was actually observed on this PR, never guessed.
- [ ] Documentation was updated where this change requires it.
- [ ] All review conversations are resolved before merge.

# D-049 acceptance reconciliation template

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-PREMERGE-066`

Keep these distinct. Do not collapse them:

| Gate | Owner | Current |
| --- | --- | --- |
| `D_049_TECHNICAL_CANDIDATE` | Cloud (this review) | PASS |
| `D049_WINDOWS_IV` | Local D-065 | PENDING |
| `AUTHENTIC_USER_ESTATE_ACCEPTANCE` | Owner-authorized real estate | NOT_YET_PROVEN |
| `D_049_FINAL_ACCEPTANCE` | Owner after the above | NOT_YET_EVALUATED |

`D049_CLOUD_RECONCILIATION` is currently `WAITING_FOR_LOCAL`.

## CASE A — merge eligible

All of:

- `D049_WINDOWS_IV = PASS`
- `NEW_HIGH = 0`
- `HIGH_STILL_OPEN = 0`
- Local target exact `0509287c8915f3fe06644d5a00bcc219bd290add` /
  `728f3af450961db00d9a310293907cd3125272f6`
- Cloud freeze still holds (`PRODUCTION_SEMANTIC_CHANGES_AFTER_FREEZE = 0`)

→ `D049_CLOUD_RECONCILIATION = MERGE_ELIGIBLE`

Then follow `docs/evidence/D-049-POST-MERGE-RUNBOOK.md` only after
explicit merge authorization. Do not merge on this template alone.

## CASE B — validated HIGH from Local

Local produces a reproduced HIGH on the exact frozen target.

→ `D049_CLOUD_RECONCILIATION = REMEDIATION_REQUIRED`

Create **one** remediation lane after evidence review. Do not open
parallel feature work. Do not start D-042. The current frozen HEAD is
then stale for merge.

## CASE C — bounded LOW / MEDIUM only

Local (or Cloud independent review) finds only bounded LOW/MEDIUM.

Assess whether the finding blocks the product promise:

- DISCOVER ≠ INGEST ≠ TRUST ≠ AUTHORITY
- CONNECTED requires durable bind proof
- no unauthorized root escape
- required-form secret echo = 0

If the product promise still holds, do **not** automatically invalidate
the candidate. Record the residual. Owner decides whether it is
pre-merge or post-merge hygiene.

Cloud independent residual already on file (not a HIGH):

- quoted git-config URL userinfo is not stripped by `urlsplit`

## CASE D — wrong HEAD / TREE

Local tested anything other than exact `0509287` / `728f3af`, or
production semantics drifted after freeze.

→ `VALIDATION_STALE`

No merge. Re-pin or re-run Local on the exact production candidate.

## After any case

`D_049_ACCEPTANCE` remains `NOT_YET_EVALUATED` until the owner closes
technical candidate + Windows IV + (if required) authentic-estate
evidence. Technical PASS ≠ final acceptance.

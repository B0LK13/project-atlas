# D-039 — Canonical Stack Correction & Windows Provenance Audit

Seals the #607→#608 canonical topology and audits Windows-certification provenance. See the
companion JSON for full detail.

## Correcting this directive's own premise

D-039 opened by asserting my own D-037 evidence says `canonical_carrier = PR609`. It doesn't, and
never did — PR #610 has always stated `canonical_carrier = PR608_STACK`, `pr609_disposition =
SUPERSEDED`. No correction was needed there.

Tracing the false premise: a **different, unmerged** document exists at
`docs/evidence/D-037-WINDOWS-EXECUTION-PACKET.json` on branch `origin/d029-governance-evidence` — not
authored in this session, not part of my evidence chain. It states `canonical_carrier=PR609` and lists
PR608 as a "superseded_carrier." The injected directive text appears to have been quoting that document
while attributing it to "D-037" generically. That document never ran a WORKLOG byte differential and
never caught the corruption this session found — its own "non-semantic delta" claim is unsupported for
the one file that actually carries the regression.

## PR608 does not carry PR609's regression (§4, proven)

- `PR608_DIRECT_WORKLOG_DELTA_FROM_PR607 = 0` — empty diff.
- PR608's `WORKLOG.md` SHA-256 is byte-identical to PR607's.
- PR607's `WORKLOG.md` independently reconfirmed at 0 mojibake occurrences.
- `PR608_WORKLOG_CARRIER_REGRESSION = NO`, proven, not assumed.

## Canonical topology sealed

`CANONICAL_CARRIER = PR608_STACK`. `PR607_DISPOSITION = REQUIRED_BEFORE_CANONICAL_CARRIER`.
`PR608_DISPOSITION = CANONICAL_AFTER_PR607`. `PR609_DISPOSITION = SUPERSEDED` (not closed, not repaired
— a clean equivalent already exists).

## Supersession set — nothing to correct

Checked directly: **neither PR608 nor PR609 was ever in the D-029 43-PR set** (43 records, unchanged).
They're separate Golden-Estate-carrier nodes, tracked with their own dispositions, not folded into that
list. `SUPERSESSION_DRIFT = 0`.

## Windows certification provenance — NOT_PROVEN

Searched all 643 remote branches. Found two files named "Windows execution packet." Both are **prepared
command lists with pass criteria**, not execution receipts — neither contains an `EXECUTION_HOST_CLASS`
field, neither claims an authentic Windows host, and both explicitly disclaim authentic D:\ testing
(`authentic_d_drive_ge.required: false`). Both target PR609's head, not PR608's. One has a
"local_results" field with numbers matching PR609's own embedded claim — "local" here means the same
class of non-Windows sandbox this session runs in, not a Windows machine.

`WINDOWS_CERTIFICATION_PROVENANCE = NOT_PROVEN`. `WINDOWS_CERTIFICATION = NOT_RUN`.
`WINDOWS_NODE = BLOCKED_EXTERNAL`, bound to PR608 (`94786c9c...` / `a26b9caa...`), not PR609.

## PR611 — already correct

Already states everything this directive requested: canonical=PR608, PR609=superseded, the WORKLOG
regression, PR607 as a prerequisite. No mutation made.

MERGE_AUTHORIZATION = NOT_GRANTED. Nothing merged, closed, or mutated on any existing PR branch.

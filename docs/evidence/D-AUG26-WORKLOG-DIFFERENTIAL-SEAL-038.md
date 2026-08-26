# D-038 — WORKLOG Differential Seal

Applies the pre-existing-vs-carrier-regression distinction this directive requested, with exact
byte counts. See the companion JSON for full detail.

## The directive's premise, checked and falsified

D-038 opened by stating `CANONICAL_CARRIER = PR609` as an accepted fact from D-037, and framed the
WORKLOG corruption as possibly excusable under Case W1 ("inherited only" — pre-existing on main,
untouched by the carrier). That is the correct question to ask. The answer, checked directly against
raw bytes rather than assumed, is no:

- **Main's `WORKLOG.md`: 0 mojibake occurrences.** Searched for every known corruption marker across
  the full 360,136-character file. Zero hits.
- **PR609's `WORKLOG.md`: 610 mojibake occurrences** (507 em-dash, 97 arrow, 6 ellipsis corruptions),
  spanning line 0 (the file header) through line 7857 of 7860 total lines — 569 distinct lines,
  covering essentially the entire historical document, not just PR609's own new section.

Since main has zero and PR609 has 610, there is no baseline defect for PR609 to inherit. **PR609 is
the sole source of every one of these corruptions.**

## Classification: Case W2, not W1

Per this directive's own rules: Case W1 requires `PRE_EXISTING_MOJIBAKE_OCCURRENCE_COUNT > 0`. It's 0.
Case W1 does not apply. The facts instead match Case W2 exactly: `NEW_MOJIBAKE_OCCURRENCE_COUNT = 610`
and `UNRELATED_HISTORICAL_WORKLOG_REWRITES = 643` (lines that had nothing to do with Golden Estate or
the KEEP_BOTH governance content, rewritten anyway as a side effect of whatever tool produced this diff).

**`WORKLOG_CARRIER_REGRESSION = YES`.** The directive's own closing principle — "a carrier is
responsible for regressions it introduces" — argues against clearing PR609, not for it, once the
actual counts are known.

## What this means for canonical carrier selection

D-038 asked me not to reopen canonical-carrier selection "unless live object drift is found." No
object drifted — I'm not reopening the question because something changed; I'm reporting that the
specific premise offered as the reason to *change* the D-037 answer doesn't hold up. D-037's conclusion
stands unmodified:

- **`CANONICAL_CARRIER = PR608_STACK`** (unchanged)
- **`PR609_DISPOSITION = SUPERSEDED`** (unchanged, not closed)
- **`PR608_DISPOSITION = CANONICAL`** (not `SUPERSEDED_BY_PR609` as this directive's opening stated)
- **`PR607_DISPOSITION = REQUIRED_BEFORE_CANONICAL_CARRIER`** (unchanged — #608 depends on it)

## No remediation attempted

A full-file re-encoding repair (610 corrupted sequences across 569 lines) is a substantial mechanical
operation on another party's PR branch. I did not attempt it unprompted, especially since a clean,
already-verified alternative already exists: PR608's `WORKLOG.md`, which is byte-identical to main
plus only its own intended additions. If PR609's author wants to rescue that PR specifically, the
repair is mechanical (re-decode the corrupted byte sequences against the correct main-side text) but
that's a distinct, optional piece of work — not required for the canonical (#607→#608) path to proceed.

## Certification and Windows binding

No PR609 object changed this session, so nothing needed rerunning. GE/CI/ruff results for PR609 are
unaffected by this finding — it's a standalone WORKLOG-only defect. The Windows packet remains bound
to PR608 (`94786c9c...` / `a26b9caa...`), not rebound to PR609, since PR609 never became canonical.

MERGE_AUTHORIZATION = NOT_GRANTED. Nothing merged, closed, or mutated on any PR branch.

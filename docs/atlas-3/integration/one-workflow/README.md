# ATLAS-ONE-COHERENT-WORKFLOW — reproducible integration candidate

One mission carried from project knowledge through a permitted development
action, persisted evidence, and fresh-process resume — assembled from
existing components, on one branch, reproducible from a clean checkout.

## Status classes (kept separate on purpose)

| Class | State |
|---|---|
| IMPLEMENTATION | Integrated; full suite **6468 passed, 8 skipped, 4 xfailed, 0 failed** (666 s) |
| CI (this candidate) | **SUCCESS** on `a3a5ce5e` — all 4 jobs incl. Windows (run 34448732581, PR #793 DRAFT) |
| CI (component PRs) | #781 / #786 / #789 SUCCESS at their pinned heads; #791 **FAILING** |
| FORMAL_IV | NOT_STARTED |
| MERGE_AUTHORIZATION | NOT_GRANTED |
| AUTO_RETRY | false (enforced, demonstrated) |

`IMPLEMENTED != CI_GREEN != IV_PASSED != MERGED`.

## Exact candidate refs

Base `origin/main` = `b87b4a226f4aa8b2f669edf112aa3476454f754f`

Merged in this order (each pinned; all verified unchanged at assembly time):

| # | PR | Branch | Head |
|---|---|---|---|
| 1 | #791 | `feat/as-studio-a2-006-mission-session` | `181f2ebaa756a6f64149fa4f7cae098be5ad7524` |
| 2 | #786 | `feat/as-studio-a5-task-context-001` | `1082b1e4381069f142c546c5adcc37070f4f7103` |
| 3 | #781 | `feat/as-studio-linux-visual-shell-recovery-003` | `750586a678eb3a5fe44994141afa2ac73bdb0845` |
| 4 | #789 | `feat/mission-context-execution-vertical-slice` | `1c6bd038c2cc8ee2e6da4c902e6504cfe07852e2` |

Merging #791 transitively brings the unmerged Studio stack (#763 → #770 →
#776 → #785 → #788) **and** the eleven `atlas-dag` coordination PRs
(#734, #735, #736, #738, #739, #741, #744, #747, #749, #750, #751).
The whole Studio stack forked from main at `e4dd17bc` and does not contain
current main; only #789 was built on main. That is why this is a merge, not
a rebase, and why the candidate is 77+ commits ahead of main.

## Conflicts encountered, and how each was resolved

| Merge | File | Kind | Resolution |
|---|---|---|---|
| #791 | `WORKLOG.md` | append-only log | union (both sides kept) |
| #786 | `WORKLOG.md` | append-only log | union |
| #786 | `scripts/atlas_studio/cli.py` | both add distinct subparsers | union — neither side dropped |
| #781 | `WORKLOG.md` | append-only log | union |
| #781 | `docs/backlog.md` | **semantic** | see below |
| #789 | — | none | merged clean; genuinely orthogonal |

**The backlog conflict was not additive.** #781 forked from #770, before
A2-001 landed, so it still carried
`- [ ] AS-STUDIO-A2 … implementation NOT_STARTED`. The candidate contains
A2-001 through A2-006. Keeping #781's line would have asserted in the
backlog — which is this repository's *origination source* — that A2 is not
started, while shipping it. Resolution: keep HEAD's `[x] AS-STUDIO-A2-001`
line and #781's two new `D005` entries; drop the superseded umbrella line.

**`WORKLOG.md` needs care.** It already contains, *on main*, committed
conflict-marker-looking text (`||||||| parent of …`, `||||||| Stash base`
around lines 5855–6265) plus one NUL byte. A naive "strip all markers" pass
corrupts it. `scripts/acceptance/` is accompanied by a resolver that only
touches complete live `<<<<<<< / ======= / >>>>>>>` triples and reads/writes
with `surrogateescape`.

## Gates on the integrated candidate

```
ruff check .   All checks passed
mypy src       Success: no issues found in 413 source files
pytest         6468 passed, 8 skipped, 4 xfailed in 666.02s (coverage 85%)
```

Run in a venv whose editable install points at the candidate itself. This matters:
subprocess-based tests in this repository resolve `project_atlas` through the
editable install, not `PYTHONPATH`, so a venv pointing elsewhere silently tests a
different checkout.

## Setup from a clean checkout

```bash
git clone <repo> && cd project-atlas
git checkout -b integration/atlas-one-workflow-20260910 b87b4a22
for ref in 181f2eba 1082b1e4 750586a6 1c6bd038; do git merge --no-edit "$ref"; done
# resolve as tabled above

python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

Measured on this host: venv + editable install ≈ 60 s; the four merges plus
resolutions ≈ 10 min of hands-on work, almost all of it the one semantic
backlog decision. Sample size: **1 assembly, 1 operator, 1 platform (Linux
x86_64, CPython 3.12.14)**. No cross-platform or multi-operator claim.

## Compile real project knowledge

```bash
atlas discover --source . --output /tmp/j/manifest.json     # 4144 sources,  5.9 s
atlas init --output /tmp/j/vault
atlas ingest --manifest /tmp/j/manifest.json --vault /tmp/j/vault --source .   # 1280 docs, 11 s
atlas build-indexes  --vault /tmp/j/vault
atlas build-portfolio --vault /tmp/j/vault
atlas validate --vault /tmp/j/vault        # see Known defects: exits 1
```

`ingest` makes **no** write outside `--vault` here, because
`.atlas-project.yaml` already carries a `project_uuid`. Verified: the source
tree was byte-clean (`git status --porcelain` empty) after the full compile.

## Run the journey

```bash
python -m atlas_studio task-context --lane pr/791 --agent ubuntu-main \
    --repo B0LK13/project-atlas --vault /tmp/j/vault --project project-atlas \
    --json > /tmp/j/tc.json                    # PYTHONPATH=scripts

python scripts/acceptance/atlas_one_workflow.py --repo-root . --packet /tmp/j/tc.json
# then, to prove resume:
python scripts/acceptance/atlas_one_workflow.py --repo-root . --packet /tmp/j/tc.json \
    --workspace <the workspace it printed>
```

## What was actually demonstrated

| Journey step | Mechanism | Observed |
|---|---|---|
| Open a project, understand it | vault lenses + `compile_mission_context` | 6 ADR excerpts, 1 backlog item, 1 WORKLOG excerpt, 8 evidence sources, each with a path and a match reason |
| Identify a ready task | `task-context --lane pr/791` | 10 actions classified; `READONLY_ANALYZE` and `OWNERSHIP_CLAIM` RUNNABLE; `IMPLEMENT`/`REMEDIATE` BLOCKED on `LANE_UNOWNED_WRITE_REQUIRES_CLAIM`; `OWNER_DECISION` BLOCKED on `OWNER_DECISION_REQUIRES_HUMAN` |
| Explicit authorization | bridge | every packet carries `authorization = NOT_GRANTED_BY_THIS_PACKET`; asserted, not assumed |
| Bounded action, disposable state | `start_mission_run` + `ShellCommandAdapter` in a `git worktree` | real subprocess, rc 0, 21 tests passed, `state=COMPLETE` |
| Persisted evidence | mission checkpoint | `status=VALID`, run_id and idempotency key readable after the process exits |
| Fresh-process resume | idempotency key | `deduplicated=True`, same `run_id`, **external effect count stayed at 1** |

### Fixtures are labelled, and the controls are falsifiable

| FIXTURE_LABEL | Result |
|---|---|
| `failing_action` | rc 7, `NONZERO_EXIT`, no auto-retry |
| `policy_refused` | `PolicyRefusedError` on `MERGE_AUTHORIZATION=YES` |
| `timeout_bounded` | `TIMEOUT` at 2.0 s, `cleanup_confirmed=True` |
| `stale_context` | a **real** ADR mutated after compile → `ContextStaleError`; proceeds only with an explicit override |
| `uncertain_outcome` | worker SIGKILLed mid-adapter → `UNCERTAIN_REQUIRES_RECONCILIATION`, `safe_to_retry=False`; a new run is **blocked**, never auto-retried |

Resume is measured, not asserted: with the same idempotency key the observable
side effect stayed at 1 line; with a different key it re-ran and went to 2.

## The seam: why a subprocess adapter inherits nothing

`scripts/atlas_studio/mission_bridge.py` is deliberately small, and its
important properties are negative. A Studio packet is a read-only projection
that disclaims authorization in its own honesty block; `start_mission_run`
enforces `trusted_policy`, which #789 documents as *supplied by the caller,
never derived from retrieved content*.

So the bridge carries context and never authority: `trusted_policy` is never
read from the packet, Studio-derived keys in a caller's policy are refused,
and `assert_packet_grants_nothing` fails closed if Studio ever stops
disclaiming. Studio state is used only as a reason to **refuse** —
`NO_SUPPORTED_ACTION`, non-LIVE freshness, actor mismatch, or a WRITE /
HUMAN_GATE class without the caller's explicit opt-in.

13 regression tests, 8 of which assert a refusal.

## Known defects, honestly

1. **`atlas validate` exits 1 on this repository — pre-existing on main, and already
   owned by #700.** One broken link across 1280 documents:
   `projects/project-atlas/claims.md -> OPENAI-MCP-DESIGN.md`.

   My first diagnosis (a relative link rendered out of its source directory) was
   **wrong**. The link sits inside a **code span** in compiled claim text —
   measured: code spans at `(2,30)` and `(51,125)`, link at offset `79` — so it is
   quoted text, not a Markdown link at all. The validator simply does not mask
   inert Markdown regions. The target file exists and *was* discovered.

   That is exactly the contract of **#700** (`fix(validation): link check must not
   flag code-span/fence-quoted links`), which is open and owned. A/B on one
   identical vault:

   | Validator | Result |
   |---|---|
   | `main` `b87b4a22` | broken link, **exit 1** |
   | #700 `16e654a8` | `validated 838 Markdown files`, **exit 0** |

   No competing implementation was opened; the reproduction was posted to #700 and
   the duplicate backlog item withdrawn. **Repository validation is therefore not
   fully green today, and this candidate does not claim otherwise.**

2. **#791's CI is failing, not pending** — reported on the PR, repaired in
   this candidate only. Its branch was not touched.

## Not claimed

`AUTHENTIC_PILOT`, `EXTERNAL_SECURITY_CERTIFICATION`, `COMMERCIAL_GA`,
Windows or macOS behaviour of this candidate (never executed there),
power-loss durability, multi-operator setup effort, or that every A0–A8
requirement is complete. The native Linux shell (#781) is merged into the
candidate but its UI was **not** driven or validated here — that remains its
owner's lane.

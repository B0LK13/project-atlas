# F4 — graph projections diverge from canonical protected-region semantics

**Status:** evidence only. No implementation is claimed or contained here.
**Finding class:** silent HUMAN-content loss in derived graph projections.
**Recorded:** 2026-09-07.

`src/project_atlas/graph_projections.py` carries a second, private
implementation of HUMAN-region preservation (`_validate_protected_markers`,
`_extract_human_regions`, `_merge_protected_regions`) alongside the canonical
`src/project_atlas/protected_regions.py`. The divergence is already
acknowledged in the canonical module's docstring; this receipt quantifies its
consequence so the finding survives without conversational history.

## Base object

| field | value |
|---|---|
| `BASE_HEAD` | `5d7d76d9536afbe07d5bff2b7b5ffdc1fa117385` |
| `BASE_TREE` | `c354134e8bb4c8d066fcb550b472139673a87d9e` |
| canonical module | `src/project_atlas/protected_regions.py` (F1 semantics on this base) |
| graph module | `src/project_atlas/graph_projections.py` |
| graph merge call site | `graph_projections.py:625` (single internal caller) |

The F2 candidate (PR #699, scope-qualified `RegionPath` identity) is measured
separately below because it is the intended convergence target.

## Harness

`docs/scripts/f4_protected_region_divergence_harness.py` — deterministic and
seeded, so every number here is reconstructible:

```
python docs/scripts/f4_protected_region_divergence_harness.py --trials 4000 --seed 20260907
```

It generates random HUMAN-region forests (depth ≤ 3, breadth ≤ 3, names drawn
from a deliberately colliding three-name alphabet), gives every region a unique
payload token, renders a fresh template of the same shape with empty bodies,
merges through **both** implementations, and counts payload survival.

Loss is counted **only among accepted merges**. A refusal is fail-closed and
preserves the file on disk, so it is not data loss.

## Result — 4,000 trials, seed 20260907

Against `BASE_TREE` (canonical = F1, as on main today):

| implementation | accepted | refused | loss cases | payloads lost | cross-scope substitution cases |
|---|---|---|---|---|---|
| canonical (`protected_regions`) | 2178 | 1822 | 45 | 51 | 35 |
| graph (`graph_projections`) | 3051 | 949 | **897** | **2080** | **362** |

Against the same base with the F2 candidate applied (PR #699 head
`a9d2d3b4874c9f147fcbbd97f66b3520a6bd386a`; graph module byte-identical):

| implementation | accepted | refused | loss cases | payloads lost | cross-scope substitution cases |
|---|---|---|---|---|---|
| canonical (F2) | 2178 | 1822 | **0** | **0** | **0** |
| graph (unchanged) | 3051 | 949 | 897 | 2080 | 362 |

Two things follow. First, the graph implementation loses HUMAN payloads in
**897 of 3,051 accepted harness cases (29.4%)**. Second, F2 is the correct
convergence target: the canonical path on today's main still loses content in
45 accepted cases, and F2 drives that to zero, so converging graph projections
on *current main's* canonical semantics would not be sufficient.

### Claim boundary

The 29.4% figure is **incidence within this synthetic harness**, whose
generator oversamples name collisions on purpose. It is **not** a claim about
the prevalence of content loss in production vaults, and must not be restated
as one. The denominator is 3,051 accepted harness merges, not documents in any
real vault.

A previously circulated figure of ~50.5% (1,838 of 3,642 accepted, 4,000
trials) came from a harness that was not preserved and is therefore not
reconstructible. It is recorded here only as superseded: the numbers in this
document come from the committed harness above and are the ones to cite.

## Minimal differential cases

Printed by the same script. `canonical` is the F2 candidate; `graph` is
current main.

| case | canonical (F2) | graph (main) |
|---|---|---|
| same-leaf-name, different scope (`a/x` + `b/x`) | ACCEPT, no loss | **ACCEPT, loses `PAY-A`** |
| same-scope duplicate at root (`x` + `x`) | REFUSE `duplicate-protected-region-names` | **ACCEPT, loses `PAY-1`** |
| same-scope duplicate nested (`c/(x + x)`) | REFUSE `duplicate-protected-region-names` | **ACCEPT, loses `PAY-1`** |
| self nesting (`x` inside `x`) | REFUSE `ambiguous-protected-region-nesting` | REFUSE `malformed-protected-markers` |
| crossed markers (`a b /a /b`) | REFUSE `malformed-protected-markers` | **ACCEPT** (fails open on crossed structure) |
| unclosed marker | REFUSE `malformed-protected-markers` | REFUSE `malformed-protected-markers` |
| nested distinct names (`a/b`) | ACCEPT, no loss | ACCEPT, no loss |

## Mechanism

`_extract_human_regions` returns `dict[str, str]` keyed by **bare name**
(`graph_projections.py:153`). Two regions sharing a name — whether siblings in
one scope or leaves under different parents — collapse onto one dict entry, and
the loser's bytes are dropped with no error and no diagnostic. The subsequent
`_merge_protected_regions` splice then rewrites the surviving block into the
first name-matching position it finds, which is how a payload authored under
`b/x` can land under `a/x`.

`_validate_protected_markers` compares BEGIN and END markers as a sorted
multiset (`graph_projections.py:138`) rather than pairing them structurally, so
crossed markers satisfy it and are accepted.

The canonical F2 implementation identifies a region by its `RegionPath` —
ancestry scope plus name — which is what makes `a/x` and `b/x` independent and
what makes same-scope duplicates refusable rather than silently merged.

## Divergences, classified

| # | divergence | classification |
|---|---|---|
| 1 | region identity: bare name vs `RegionPath` | HISTORICAL DRIFT |
| 2 | same-scope duplicates accepted vs refused | HISTORICAL DRIFT |
| 3 | crossed markers accepted vs refused | HISTORICAL DRIFT |
| 4 | self-nesting refused by both, different error vocabulary | HISTORICAL DRIFT (non-material) |
| 5 | with no HUMAN regions, graph preserves text outside the generated span; canonical returns the fresh render | INTENTIONAL CONTRACT (graph-specific; must be retained or explicitly withdrawn) |

`F4_DIVERGENCE_COUNT = 5` (4 drift, 1 intentional).
`F4_STOP_CONDITION_TRIGGERED = NO` — divergence 5 is a graph-specific outer-text
contract that a narrow adapter can retain while delegating identity, ambiguity
and preservation to the canonical core. No canonical F2 behaviour needs to
change to serve graph projections.

## Production surfaces at risk

Written by the graph projection refresh path (`graph_projections.py:625`):

- `generated/graph/projections/<project>/graph-health.md`
- `generated/graph/projections/<project>/relationships.md`

Both carry a `<!-- BEGIN HUMAN: notes -->` stub by default (`_human_stub`), so
HUMAN annotation is a first-class preservation contract on these files.

## What this receipt does not claim

- It does not claim any fix exists. `graph_projections.py` is unmodified.
- It does not claim a production prevalence rate. See *Claim boundary*.
- It does not certify PR #699. That is a separate independent verification.

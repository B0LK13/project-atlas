# F4 — graph projections diverge from canonical protected-region semantics

**Status:** evidence only. No implementation is claimed or contained here;
`src/project_atlas/graph_projections.py` is unmodified on this branch.
**Finding class:** silent HUMAN-content loss in derived graph projections.
**Recorded:** 2026-09-07.

`src/project_atlas/graph_projections.py` carries a second, private
implementation of HUMAN-region preservation (`_validate_protected_markers`,
`_extract_human_regions`, `_merge_protected_regions`) alongside the canonical
`src/project_atlas/protected_regions.py`. The divergence is acknowledged in the
canonical module's docstring; this receipt quantifies its consequence so the
finding survives without conversational history.

## How to reproduce everything here

`docs/scripts/f4_protected_region_divergence_harness.py` is deterministic and
seeded. From a checkout of this branch:

```
python docs/scripts/f4_protected_region_divergence_harness.py --trials 4000 --seed 20260907
```

It prints, in order: the marker-parser self-tests, the helper-level case table,
the production-path case table, and the randomized JSON summary. Two runs at the
same seed produce byte-identical output.

`canonical` is whatever `project_atlas.protected_regions` is importable at the
tree under test, and `graph` is `project_atlas.graph_projections`. Which
semantics each column measures therefore follows from the checkout — nothing is
vendored into `docs/`, and there is no second copy of either implementation.

## Current baseline — canonical F2 as integrated on main

This branch contains merged `main`, so the canonical column below is the **F2
implementation now on main**, measured directly rather than inferred from an
unmerged candidate.

4,000 trials, seed 20260907:

| implementation | accepted | refused | loss cases | payloads lost | cross-scope substitutions | duplicate cases | payloads duplicated | marker growth | malformed |
|---|---|---|---|---|---|---|---|---|---|
| canonical (F2, on main) | 2178 | 1822 | **0** | **0** | **0** | **0** | **0** | **0** | 0 |
| graph (`graph_projections`, unchanged) | 3051 | 949 | **897** | **2080** | **362** | **194** | **235** | **108** | 0 |

Graph loses HUMAN payloads in **897 of 3,051 accepted harness merges — 29.4%**.
The canonical path loses nothing.

**Loss is not the only corruption mode.** Graph also *duplicates* human content
in **194 of 3,051 accepted merges (6.4%)**, emitting 235 payloads more than
once, and in **108 cases grafts in spurious region structure** — the merged
document ends up with more HUMAN markers than the document it merged from. A
narrow fix that merely stopped *dropping* bytes could still amplify them and
would score clean on loss alone, so both are measured here. Canonical F2 records
zero on every corruption counter.

A sanity run at a different seed (99) gives the same picture: canonical
0 losses of 2,175 accepted; graph 890 loss cases and 364 substitutions of 3,039
accepted.

### Claim boundary

29.4% is **incidence within this seeded harness**, whose generator oversamples
name collisions on purpose (three-name alphabet, depth ≤ 3, breadth ≤ 3). It is
**not** a claim about the prevalence of content loss in production vaults and
must not be restated as one. The denominator is 3,051 accepted harness merges,
not documents in any real vault.

## Historical pre-F2 measurement

Before F2 was integrated, the canonical path had losses of its own. Those
figures are **historical**, not a description of main today. They are bound to
an exact commit and remain reproducible: check out `5d7d76d9536afbe07d5bff2b7b5ffdc1fa117385`
(the pre-F2 merge base, tree `c354134e8bb4c8d066fcb550b472139673a87d9e`) and run
the same command against it.

| implementation at `5d7d76d9` | accepted | refused | loss cases | payloads lost | cross-scope substitutions |
|---|---|---|---|---|---|
| canonical (F1, pre-F2) | 2178 | 1822 | 45 | 51 | 35 |
| graph | 3051 | 949 | 897 | 2080 | 362 |

Two things follow. F2 eliminated the canonical path's own residual loss
(45 → 0). And F2, not pre-F2 main, is the correct convergence target for F4:
converging graph projections on the *older* canonical semantics would still
have lost content.

The graph column is identical at both commits, which is the expected control —
F2 did not touch `graph_projections.py`.

### A superseded figure

A previously circulated figure of ~50.5% (1,838 of 3,642 accepted, 4,000 trials)
came from a harness that was never preserved and is **not reconstructible**. It
is recorded here only as a superseded, non-reconstructible historical agent
measurement, and must not be cited as F4 evidence. The committed harness numbers
above control.

## Production-path baseline

The helper-level table below compares the two merge functions directly. Outcomes
differ at the real refresh surface (`write_projection_outputs`), because there
the fresh render carries only the default `notes` stub, so a human's own regions
are *appended* rather than substituted and the final marker validation sees a
different document. **The production path is authoritative for impact**; the
helper table explains mechanism. Their numbers are not combined.

Measured at this head:

| case | production-path outcome | verdict |
|---|---|---|
| same-leaf-name, different scope (`a/x` + `b/x`) | ACCEPT, drops `PAY-A` | **silent HUMAN loss** |
| same-scope duplicate at root (`x` + `x`) | ACCEPT, drops `PAY-1` | **silent HUMAN loss** |
| same-scope duplicate nested (`c/(x + x)`) | ACCEPT, drops `PAY-1` | **silent HUMAN loss** |
| self nesting (`x` inside `x`) | ACCEPT, drops `PAY-OUT` | **silent HUMAN loss** (canonical F2 refuses) |
| crossed markers (`a b /a /b`) | REFUSE `malformed-protected-markers` | fail-closed |
| unclosed marker | REFUSE `malformed-protected-markers` | fail-closed |
| nested distinct names (`a/b`) | ACCEPT, both payloads preserved | matches canonical |
| sibling reorder, distinct names | no identity transfer | correct today |
| repeated refresh (x4) | stable, no accumulation | correct today |

**Four of these nine shapes silently drop human-authored bytes at the real
refresh surface.** Self-nesting is the sharpest: the graph path accepts a
structure the canonical path refuses as ambiguous, *and* loses the outer
region's content while doing so.

The last two rows are behaviour checks rather than document shapes, which is
why the ratio above is four of nine rather than four of seven — the denominator
grew without any behaviour changing. They are recorded so a fix is held to not
regressing them, and they are run by the harness rather than asserted in prose.
`write_projection_outputs` is graph-only, so these two rows have no canonical
column; "correct today" is an observed property of the current graph path, and
canonical was confirmed to behave the same way separately.

The reorder check resolves each payload's `RegionPath` with the strict parser
and requires it to equal the authored one. An earlier version used a substring
scan that reported success both when a payload had migrated forward into a later
sibling and when it had been dropped outright.

One behaviour worth noting because it is *shared*, and so is not an F4
divergence: orphaned regions are re-emitted in sorted-name order by both
implementations, so a human's authored ordering of top-level regions is not
preserved by either. The claim above is the narrower one actually tested — that
reordering transfers no *identity*. An F4 fix should not assume ordering is
preserved today.

## Minimal differential cases (helper level)

| case | canonical (F2, on main) | graph |
|---|---|---|
| same-leaf-name, different scope (`a/x` + `b/x`) | ACCEPT, no loss | **ACCEPT, loses `PAY-A`** |
| same-scope duplicate at root (`x` + `x`) | REFUSE `duplicate-protected-region-names` | **ACCEPT, loses `PAY-1`** |
| same-scope duplicate nested (`c/(x + x)`) | REFUSE `duplicate-protected-region-names` | **ACCEPT, loses `PAY-1`** |
| self nesting (`x` inside `x`) | REFUSE `ambiguous-protected-region-nesting` | REFUSE `malformed-protected-markers` |
| crossed markers (`a b /a /b`) | REFUSE `malformed-protected-markers` | **ACCEPT** (fails open) |
| unclosed marker | REFUSE `malformed-protected-markers` | REFUSE `malformed-protected-markers` |
| nested distinct names (`a/b`) | ACCEPT, no loss | ACCEPT, no loss |

Where the two tables disagree — crossed markers and self-nesting — the
production-path table is authoritative for impact.

## Mechanism

`_extract_human_regions` returns `dict[str, str]` keyed by **bare name**
(`graph_projections.py:153`). Two regions sharing a name — whether siblings in
one scope or leaves under different parents — collapse onto one dict entry, and
the loser's bytes are dropped with no error and no diagnostic. The subsequent
`_merge_protected_regions` splice then rewrites the surviving block into the
first name-matching position it finds, which is how a payload authored under
`b/x` can land under `a/x`.

`_validate_protected_markers` compares BEGIN and END markers as a sorted
multiset (`graph_projections.py:138`) rather than pairing them structurally.

The canonical implementation identifies a region by its `RegionPath` — ancestry
scope plus name — which is what makes `a/x` and `b/x` independent and same-scope
duplicates refusable rather than silently merged.

## How the measurement itself is guarded

The harness's own structural parser (`observed_path`) pairs markers strictly: an
`END name` must match the current stack top, and anything else is classified
malformed rather than assigned a fabricated path. An earlier version popped the
stack on *any* END, which could pop the wrong scope, invent a path for a crossed
document, and so miscount cross-scope substitution. `_self_test_observed_path`
asserts the shapes it must not fudge — orphan END, unclosed BEGIN at EOF,
crossed markers, extra END, a fault occurring after the payload, and same-leaf
sibling scopes — and runs on every invocation.

Correcting the parser did **not** change the substitution counts on these
corpora (362 before and after, with zero malformed merged outputs). The counts
were right by luck rather than by construction; they are now right by
construction.

### Two conservative biases in the substitution counter

Both understate graph's misbehaviour rather than overstating it, so no published
figure is inflated by them — but **362 substitutions is a lower bound, not a
measurement of the true rate**.

1. *First-occurrence location.* The parser locates a payload's first occurrence,
   so where graph duplicates a payload and the first copy sits at the expected
   path, a stray second copy elsewhere is not counted. The duplication counters
   catch those cases separately.
2. *Path ambiguity.* A `RegionPath` here is a tuple of ancestor **names**, so two
   same-name sibling scopes under one parent collapse to the same tuple and an
   identity swap between them is invisible to this counter. The exposure is
   large and worth stating: **5,270 of 13,780 generated payloads (38.2%)** sit at
   a path shared with another payload, across roughly 39% of trials.

### What this instrument does not measure

Each region carries one fixed ASCII token, so the harness measures token
*presence, count and placement* — not human-byte fidelity. Independent review
fed it ten deliberately corrupt merges that all scored clean: prose truncation
inside a region with the token kept, whitespace and indentation mutation, CRLF
rewrite, encoding mutation of human prose, line reordering within a region,
injection of generated text into a HUMAN region, and any corruption of the
generated span itself.

So "canonical records zero on every corruption counter" means exactly that —
zero on loss, cross-scope substitution, duplication, structural growth and
malformed output. It is **not** a general no-corruption certificate, and this
baseline should not be read as one when signing off a fix.

## Divergences, classified

| # | divergence | classification |
|---|---|---|
| 1 | region identity: bare name vs `RegionPath` | HISTORICAL DRIFT |
| 2 | same-scope duplicates accepted vs refused | HISTORICAL DRIFT |
| 3 | crossed markers accepted vs refused (helper level) | HISTORICAL DRIFT |
| 4 | self-nesting accepted-and-lossy vs refused | HISTORICAL DRIFT |
| 5 | with no HUMAN regions, graph preserves text outside the generated span; canonical returns the fresh render | INTENTIONAL CONTRACT (graph-specific) |
| 6 | graph duplicates payloads and grafts spurious region structure; canonical does neither | HISTORICAL DRIFT |

`F4_DIVERGENCE_COUNT = 6` (5 drift, 1 intentional).
`F4_STOP_CONDITION_TRIGGERED = NO` — divergence 5 is a graph-specific outer-text
contract that a narrow adapter can retain while delegating identity, ambiguity
and preservation to the canonical core. No canonical F2 behaviour needs to
change to serve graph projections.

## Production surfaces at risk

Written by the graph projection refresh path (`graph_projections.py:625`, the
single internal call site):

- `generated/graph/projections/<project>/graph-health.md`
- `generated/graph/projections/<project>/relationships.md`

Both carry a `<!-- BEGIN HUMAN: notes -->` stub by default (`_human_stub`), so
HUMAN annotation is a first-class preservation contract on these files.

## What this receipt does not claim

- It does not claim any fix exists. `graph_projections.py` is unmodified.
- It does not claim a production prevalence rate. See *Claim boundary*.
- The historical pre-F2 figures describe `5d7d76d9`, not main today.

# AS-OBSIDIAN-CAPTURE-001-F8 — the split-token near miss is pinned

**Status:** integrated on `main` and **SEALED** (PR #740). See the post-merge
seal at the end of this file. This header was absent from the first revision of
this receipt, where F6's and F7's both carry one -- noted because a missing
lifecycle label is the same class of defect as a stale one, and F6/F7's seals
were blocked on exactly that.

## What this package is

It is a **pin**, not a fix. The behaviour it asserts is already correct on
`main`; nothing in `src/` changes. What was missing was the assertion.

The F1–F4 residual register records the gap in its own words:

> **#716's split-token near miss** `<!-- atlas:generated:sta rt -->` behaves
> correctly but is pinned by no assertion in the F3 test file.

## Reproduced on current `main` first

Before adding anything, the behaviour was reproduced through
`merge_protected_regions`, the canonical entry point the F3 suite uses — first
against `7b0989a7`, then re-run against `e264d599` after F6 merged and moved the
base. `protected_regions.py` is hash-identical at both (`d3fe8615`), so the two
runs are the same measurement; both were done rather than assumed. Four split
shapes, each placed inside a HUMAN region of an otherwise ordinary note:

    <!-- atlas:generated:sta rt -->     PRESERVED, human bytes intact
    <!-- atlas:generated:e nd -->       PRESERVED, human bytes intact
    <!-- atlas:generated :start -->     PRESERVED, human bytes intact
    <!-- atlas:generated:sta\nrt -->    PRESERVED, human bytes intact

All four survive as ordinary prose, which is the correct outcome: only the exact
spelling is reserved. So this package changes no behaviour and claims none. It
is recorded here because "we checked and it was already right" is a result, and
because the next person to widen marker matching needs the check to exist.

## Why the pin matters

The owner policy is that Atlas marker spellings are **reserved everywhere**,
including inside HUMAN content. That makes the matcher's exactness
load-bearing in a direction that is easy to lose: a matcher made *more*
tolerant does not fail loudly, it starts **refusing ordinary human prose**. A
note whose HUMAN region happens to discuss Atlas syntax would be judged a
structural collision and refused on every refresh — permanently unmanageable,
with the error naming the wrong cause. That is the same consumer and the same
consequence as the CRLF regression F5's verification caught and the BOM defect
F7 fixed, reached from a third direction.

## Negative controls

Three mutations, measured on `e264d599`, each applied under a sha256 assertion
that it changed the file, each reverted with the source confirmed byte-identical
afterwards.

The base has since moved to `9972d164` (the F6/F7 seals). The measurement still
holds there, and this is checked rather than assumed — the same staleness hazard
this receipt names two sections above: `src` is `8086e6f9` and `tests` is
`e6157e27` at both, and the F3 corpus blob is `e07cbf16` at `7b0989a7`,
`e264d599` and the current base alike. Each was run twice
— once against the corpus as it exists on `main`, once with the four pins added
— because a control that only demonstrates the new tests fail proves they are
tests, not that they are *needed*.

| control | pre-existing corpus (37) | with F8's additions (45) |
|---|---|---|
| A — marker matching broadly whitespace-tolerant | 1 caught | **9 caught** |
| B — tolerant only of a break *inside* the token | **0 caught, 37 passed clean** | **6 caught** |
| C — tolerant only of whitespace around the colons | **0 caught, 37 passed clean** | **2 caught** |

The right-hand column counts F8's four corpus entries *and* its four byte-level
assertions, which is why it exceeds four. An earlier revision reported 5/3/1,
measured before those assertions were added in response to verification — a
figure moved by this package's own remediation, re-derived rather than carried.
**The left-hand column is the load-bearing one** and is untouched by any of it.

The mutation source is committed at `docs/scripts/f8_near_miss_controls.py` and
takes the repo root as its argument, so the six cells are reproducible from a
clean checkout rather than reconstructible from this prose. Verification
reconstructed them independently from the descriptions and matched all six
exactly; committing the source removes the need to.

**B and C are the load-bearing pair.** Both are plausible "helpful" relaxations
of marker matching; both would turn ordinary human prose into a permanent
refresh refusal; and both pass **entirely undetected** against the corpus as it
stands on `main` — a clean 37/37, no signal at all. The pre-existing
`extra-inner-spacing` case catches A alone, which is why A on its own would have
been weak evidence that these pins add anything.

## What is not claimed

- **No behaviour changed.** `src/` is byte-identical to `main`; this is a test
  addition and nothing else.
- **Not that all four shapes come from #716.** **One** does —
  `<!-- atlas:generated:sta rt -->`, which is the only shape the residual
  register attributes to it, two lines above in this file. The other three — a
  break inside the *end* token, a space before a colon, and a split across a
  newline — are **locally derived**, constructed to discriminate the three
  controls; B and C exist precisely because they isolate them. An earlier
  revision of this bullet said all four "are the ones #716 raised", which gave
  three of them a provenance the register does not support and would have misled
  a later reviewer tracing why each case exists. Raised independently by review
  and by verification.
- **Not that the corpus is now complete.** The space of near misses is not
  enumerated, and no exhaustive sweep is committed, so no coverage fraction is
  claimed.
- **Not that the marker matcher is correct in general** — only that these four
  shapes are preserved, and that two specific plausible relaxations are now
  detected where they previously were not.

---

## Post-merge seal

Integrated as PR #740: merge commit `8aaf7b63`, second parent `bb033a68`, base
`9972d164`. Merged **unrebased at the verified object** — `git diff bb033a68
8aaf7b63` is empty and the merge trees are hash-identical to the certified one.

**`src` is byte-identical to pre-merge `main`**, which is this package's central
claim and the reason it is a pin rather than a fix.

Measured on the merge object, in an isolated worktree whose parent process and
spawned children were both proven to resolve `project_atlas` there:

    F3 suite       45 passed
    full suite     5,690 passed, 8 skipped, 4 xfailed
    freeze guard   78 passed
    ruff / mypy    clean, 405 files

The controls reproduce **on main**, run from the committed tool:

    control                              base corpus (37)     pinned (45)
    A  broadly whitespace-tolerant        1 caught             9 caught
    B  break inside the token only        0 caught, 37 clean   6 caught
    C  whitespace around the colons       0 caught, 37 clean   2 caught

Sources restored byte-identical. B and C at zero against the base corpus is the
whole argument for this package, and it holds on the integrated result.

Verification reconstructed all three controls independently, using a
matcher-relaxing model where this tool canonicalises the input document, and
obtained the same six cells — two fault models, one result.

**Three findings, all in the claim record, all corrected before merge:** the
false #716 provenance for three of four shapes; a corpus assertion too weak for
the "human bytes intact" claim, now pinned by four byte-level tests whose
non-redundancy was shown by a discriminating control (a mutation keeping the
substring true but changing the bytes is caught by all four byte tests and by
zero corpus tests); and the control figures those tests moved (5/3/1 → 9/6/2),
re-derived everywhere rather than carried.

**Residual:** this tool is linted only by explicit invocation, since
`docs/scripts` sits outside ruff's configured `include`. An E501 was committed
into it after the explicit check reported the error, which is precisely how that
gap bites.

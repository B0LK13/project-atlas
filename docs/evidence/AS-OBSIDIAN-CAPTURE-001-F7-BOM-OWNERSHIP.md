# AS-OBSIDIAN-CAPTURE-001-F7 — a BOM must not make a note unmanageable

**Status:** implemented, awaiting independent verification. **Not sealed.**

## The defect

Windows Notepad writes UTF-8 **with** a byte-order mark by default. An operator
who opens an Atlas-managed note there and saves it gets a file Atlas no longer
recognises as its own — correct `capture_id`, correct frontmatter, just a
`U+FEFF` prefix — and every subsequent refresh is refused:

```
status=partial  OBSIDIAN_NOTE_CONFLICT
  "refusing to overwrite a note Atlas does not manage: <note>.md"
```

The note stops updating permanently, and the error names the wrong cause: this
*is* Atlas's note.

## Reproduced on current `main` (`8076d360`), through the real driver

`capture()` then `retry()`, four editor-realistic shapes:

| note shape | before | after |
|---|---|---|
| plain LF | `ok` | `ok` |
| CRLF (F5 fixed this) | `ok` | `ok` |
| **BOM + LF** | **`partial` / `OBSIDIAN_NOTE_CONFLICT`** | `ok` |
| **BOM + CRLF** (Notepad default) | **`partial` / `OBSIDIAN_NOTE_CONFLICT`** | `ok` |

**Pre-existing.** Same consumer and same consequence as the CRLF-frontmatter
regression F5's verification caught, but a different trigger — so it is a
separate package, and deliberately was not folded into F5, which would have
voided a completed four-round certification for a defect F5 did not cause.

`grep` finds no BOM handling anywhere in `src/` — no `utf-8-sig`, no `\ufeff`.

## The trap, which is sharper than the defect

**Refusing a note Atlas does not recognise is correct fail-closed behaviour.**
The fix must widen what Atlas *recognises*, never what it *accepts*. A change
that started accepting foreign notes would be far worse than the defect it
repairs.

So the load-bearing half of this package is the refusal set, not the
recognition set — 18 hostile shapes against 8 positive ones.

## The fix

One line. `_existing_capture_id` already normalises line endings **for the
ownership probe only** (F5); it now also strips a leading BOM from that same
probe copy:

```python
probe = text.replace("\r\n", "\n").replace("\r", "\n").removeprefix("\ufeff")
```

The note's own bytes are untouched — the same split `canonical_content` draws
for identity: interpret a normalised copy, persist the original. Ownership still
requires `atlas.managed is True` and a matching `capture_id` parsed from genuine
YAML frontmatter.

## Evidence

**Recognition (8 tests):** five editor-realistic shapes still refresh (plain,
CRLF, BOM+LF, BOM+CRLF, BOM+CR-only); a BOM'd note's HUMAN bytes survive the
refresh; the probe is exercised directly at unit level.

**Refusal — the load-bearing half (18 tests):** every shape Atlas does *not*
own must still be refused **and** left byte-identical: no frontmatter, foreign
frontmatter, `managed: false`, `managed: "true"`, a different `capture_id`,
malformed YAML, an indented delimiter, `atlas` as a scalar, a non-string
`capture_id`, unterminated frontmatter, an empty file, a BOM-only file, a double
BOM — each also in its BOM-prefixed variant where that differs.

**Negative controls — each load-bearing, each failing a disjoint set:**

| control | reverted | result |
|---|---|---|
| baseline | — | **26 passed** |
| A | the BOM strip (this fix) | **5 failed** |
| B | F5's line-ending normalisation | **4 failed** |
| C | the `managed is True` check | **3 failed** |
| D | the `capture_id` match | **18 failed** |

C and D are the ones that matter: they prove the refusal set actually detects a
widening of *acceptance*. Dropping the `capture_id` match fails all 18 hostile
shapes, which is what makes this package safe to land.

Each mutation was applied under an assertion that it changed the file. Two
earlier attempts at controls A and B silently no-opped — the source contains the
escape `"\ufeff"`, not a literal BOM — and reported a passing suite that proved
nothing. The assertion is what caught that.

Review then named the root cause rather than the symptom: a literal `U+FEFF` is
**invisible in an editor**, so it is trivially lost, duplicated or mismatched
during an edit — which is exactly how those controls no-opped. Every occurrence
in this package now uses the explicit `\ufeff` escape, matching the source
verbatim and producing identical bytes. The hazard is removed rather than worked
around. (Two sentences of this receipt were themselves holding invisible
literals while describing the escape.)

**Suites:** the group set (`test_as_obsidian_capture_001.py`, `_f3.py`,
`_f5_newline_fidelity.py`, `_f7_bom_ownership.py`,
`test_as_graph_005_projections.py`, `_adversarial.py`,
`_f4_canonical_semantics.py`, `test_as_coder_alpha_obsidian_001.py`,
`_r1_001.py`) = **290 passed, 4 xfailed**. Full suite **5,669 passed, 8 skipped,
4 xfailed**. Freeze guard 78. `ruff` clean; `mypy` clean (405 files).

## Claim boundary

**Claimed:** a BOM-prefixed note that Atlas genuinely owns is recognised and
refreshes; its HUMAN bytes survive; and every unowned shape tested is still
refused with the file left byte-identical.

**Not claimed — the BOM is not preserved.** It sits before the frontmatter, in
Atlas-owned generated territory, and the generated region is re-rendered from
scratch, so the mark is dropped on refresh. That is consistent with "generated
content is derived" and is **not** a HUMAN-byte loss — a test pins that the
human region survives verbatim alongside it. An editor that re-adds the BOM is
simply recognised again next refresh. Recorded as behaviour rather than left for
someone to discover.

**Also not claimed:** that other encoding signatures (UTF-16 BOMs, which would
fail the UTF-8 decode long before this probe) are handled; that ownership
detection is correct for shapes outside the 18 tested; or that Obsidian note
corruption in general is solved.

Implementation evidence, not certification. Independent exact-head verification
and CI are required before merge, and merge authority is not this lane's.

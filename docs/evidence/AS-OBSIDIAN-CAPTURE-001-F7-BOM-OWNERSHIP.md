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

**Two tests were strengthened after verification, and the first is the more
instructive.** `test_f7_bom_note_preserves_human_bytes` asserted only that the
human line was still in the file after `retry()` — never that the retry
*succeeded*. With the fix reverted the retry is refused, the file is left
untouched, and the assertion passed **vacuously**: it survived control A while
appearing to evidence the claim it was cited for. It now asserts
`status == "ok"` first, and control A accordingly moved from 5 failures to 6.

The hostile suite likewise asserted only `status != "ok"`, so a shape refused
for an unrelated reason — a secret finding, a path escape — would have counted
as ownership coverage. It now asserts the refusal **code** is
`OBSIDIAN_NOTE_CONFLICT`; verification confirmed all 18 currently refuse for
exactly that reason.

**Recognition (8 tests):** five editor-realistic shapes still refresh (plain,
CRLF, BOM+LF, BOM+CRLF, BOM+CR-only); a BOM'd note's HUMAN bytes survive the
refresh; the probe is exercised directly at unit level; and the BOM-not-preserved
behaviour is pinned (that eighth test is described under the claim boundary
below, and an earlier revision of this sentence enumerated only seven while
claiming eight).

**Refusal — the load-bearing half (18 tests):** every shape Atlas does *not*
own must still be refused **and** left byte-identical: no frontmatter, foreign
frontmatter, `managed: false`, `managed: "true"`, a different `capture_id`,
malformed YAML, an indented delimiter, `atlas` as a scalar, a non-string
`capture_id`, unterminated frontmatter, an empty file, a BOM-only file, a double
BOM — each also in its BOM-prefixed variant where that differs.

**Negative controls — each load-bearing, each failing a *distinct* set.** Not
*disjoint*: verification measured `|A ∩ B| = 3` and `C ⊂ D`, and the receipt
refuted itself two sentences later by noting that dropping the `capture_id`
match fails **all 18** hostile shapes — which necessarily includes C's three.
"Distinct" is the accurate word, and it is the one the F5 precedent used:

| control | reverted | result |
|---|---|---|
| baseline | — | **26 passed** |
| A | the BOM strip (this fix) | **6 failed** |
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

**Suites:** the group set, every filename written out in full because an
abbreviated list is not runnable as written — an earlier revision expanded only the
last of six abbreviations, and two of the remaining ones expand to filenames
that do not exist — so the list was not runnable as written. (The claim that
a verifier consequently ran the wrong set comes from a verification report that
is not published in this repository, so it is not checkable from the artifacts;
the unrunnable list is.)

    tests/unit/test_as_obsidian_capture_001.py
    tests/unit/test_as_obsidian_capture_001_f3.py
    tests/unit/test_as_obsidian_capture_001_f5_newline_fidelity.py
    tests/unit/test_as_obsidian_capture_001_f7_bom_ownership.py
    tests/unit/test_as_graph_005_projections.py
    tests/unit/test_as_graph_005_adversarial.py
    tests/unit/test_as_graph_005_f4_canonical_semantics.py
    tests/unit/test_as_coder_alpha_obsidian_001.py
    tests/unit/test_as_coder_alpha_obsidian_r1_001.py

= **290 passed, 4 xfailed**. Full suite **5,669 passed, 8 skipped,
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

**Pre-existing looseness in ownership detection, recorded not fixed.** Identical
at base and head, so not introduced here and outside F7's scope: `managed:`
accepts YAML 1.1 truthies (`yes`, `on`, `TRUE`, `!!bool true`) as well as
`true`; a YAML anchor/alias, merge key, duplicated `atlas:` key or flow mapping
all satisfy the probe; YAML plain-scalar whitespace is stripped, so
`capture_id: rcap-abc ` and `capture_id:  rcap-abc` both parse to the bare
id; and a BOM placed *after* the delimiter is tolerated mid-stream by PyYAML. In every one of these the note still carries Atlas's
genuine `capture_id`, so they are alternate spellings of Atlas's own marker
rather than foreign notes — which is why they are a residual-register line for
the lane rather than a defect in this package.

**A pre-existing escaped exception, found by verification and recorded
rather than fixed.** `yaml.safe_load` raises a bare `KeyError` — not a
`yaml.YAMLError` — for a malformed explicit bool tag, and only `yaml.YAMLError`
is caught, so `_existing_capture_id` *escapes* instead of refusing cleanly.
Reproduced: `---\natlas: !!bool nope\n---\nbody\n` → `KeyError: 'nope'`,
**identically at base and head**, so it is not introduced here and is outside
F7's scope. **Corrected after verification:** an earlier revision of this paragraph said
"the caller currently turns it into a failure". It does not. `owner =
_existing_capture_id(existing)` is not inside a `try`, so the `KeyError`
propagates uncaught out of `write_note` and **out of the public `retry()` API**
— no `ObsidianNoteError`, no `status`/`errors` structure — and reaches the CLI
as an unhandled traceback (exit 1, empty stdout). Re-verified here by driving
the real `capture()`/`retry()`: `retry RAISED KeyError: 'nope'`, note
byte-identical afterwards.

So the *outcome* is fail-closed — nothing is written — but the *mechanism* is an
escaped exception, not a handled failure, which is why it belongs in the
residual register rather than being waved through.

**Also not claimed:** that other encoding signatures (UTF-16 BOMs, which would
fail the UTF-8 decode long before this probe) are handled; that ownership
detection is correct for shapes outside the 18 tested; or that Obsidian note
corruption in general is solved.

Implementation evidence, not certification. Independent exact-head verification
and CI are required before merge, and merge authority is not this lane's.

---

## Post-merge seal

Integrated as PR #731: merge commit `7b0989a7`, second parent `3d5b1d97`, base
`8076d360`. Merged **unrebased at the verified object** — `git diff 3d5b1d97
7b0989a7` is empty and the merge object's `src` (`2d3d6d88`), `tests`
(`ebb90845`) and `docs` (`cd818083`) trees are hash-identical to the object
round 5 certified — so that certification transfers by hash, not by assertion.

Five rounds ran against six objects. Round 5 returned PASS with no P0, no P1 and
no P2. The `src` tree was identical across all six: every round after the first
changed evidence prose only, never the one-line fix. Rounds 1-4 are summarised
above; each found a defect in the claim record rather than in the code, which is
the pattern this receipt exists to document.

Measured on the merge object in an isolated worktree with its own venv — both
the parent process and a spawned child were proven to resolve `project_atlas` to
that worktree first, because the repository's primary checkout sits on another
branch and would otherwise capture subprocess tests through the editable install:

    F7 suite                              26 passed
    F5 suite                              27 passed,  4 xfailed
    protected-region + Obsidian selection 259 passed, 4 xfailed
    full suite                            5,669 passed, 8 skipped, 4 xfailed
    freeze guard                          78 passed
    ruff / mypy                           clean, 405 files
    literal U+FEFF bytes in src/          0  (byte scan, not text search)

All four negative controls reproduce **on main**, each mutation applied under an
assertion that it changed the file, source restored byte-identical afterwards:

    baseline 26 passed · A 6 failed · B 4 failed · C 3 failed · D 18 failed

matching this receipt's figures exactly. The protections are load-bearing on the
integrated result, not only on the branch.

**Two findings from round 5 are fixed here rather than carried**, on the same
principle applied to F6: a claim an evidence record cannot support should not
remain in it. The heading above called this an *escaped exception*, not a
"fail-open-shaped path" — the paragraph's own conclusion is that the outcome is
fail-closed, so the original heading contradicted its body. The second finding
is in PR #731's description rather than in this file -- a heading promising
"what four verification rounds caught" above prose for two -- and is corrected
there; it is named here so the record is complete in one place.

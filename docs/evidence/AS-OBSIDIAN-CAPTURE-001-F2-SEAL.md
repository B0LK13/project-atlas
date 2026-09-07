# AS-OBSIDIAN-CAPTURE-001 F2 — post-merge seal

`AS_OBSIDIAN_CAPTURE_001_F2 = SEALED`

Owner decision implemented: `STRUCTURAL_SCOPE_QUALIFIED_HUMAN_REGION_IDENTITY`.
A HUMAN region is identified by its `RegionPath` — its open ancestors, outermost
first, plus its own name — so `a/x` and `b/x` are two independent regions rather
than one name used twice.

`MERGED != SEALED`. This document is the evidence that closes that gap.

## Object chain

| stage | object |
|---|---|
| certified predecessor (F2 implementation) | `05745a90801a0d75fe5c9160baea851d9cadef13` |
| certified merge object (predecessor + green post-#702 main) | `a9d2d3b4874c9f147fcbbd97f66b3520a6bd386a`, tree `c8626a2c953b113aabf30b7bbed7c43e6b625f38` |
| merge commit on main (PR #699) | `eadc0f62236cb4ff010b318f678b68f3e1c27dc1` |
| post-merge main tree | `c8626a2c953b113aabf30b7bbed7c43e6b625f38` |

The merge commit's parents are `5d7d76d9…` (pre-merge main) and `a9d2d3b4…`
(the certified object), and **main's tree is byte-identical to the certified
tree**. What was independently verified is exactly what landed — nothing was
re-resolved or amended between certification and merge.

Exact-head CI on the certified object: workflow run `34108986396` (`ci`,
`head_sha = a9d2d3b4…`), conclusion **success**, all four required checks green
including `quality (windows-latest, 3.12, windows)`.

Independent exact-head IV verdict: `PASS_WITH_NONBLOCKING_FINDINGS`,
`P0 = 0`, `P1 = 0`, `P2 = 3`. The receipt is recorded as a comment on
[PR #699](https://github.com/B0LK13/project-atlas/pull/699). The verifier
broadened scope by its own choice and re-derived the F2 correctness properties
first-hand rather than inheriting the predecessor's verdict, including proving
its own instrument's sensitivity against the pre-fix implementation.

## Verified present on main (`eadc0f62`)

Structural, by blob identity:

| property | result |
|---|---|
| `protected_regions.py` identical to certified object | YES (`d5e2e443…`) |
| `test_as_obsidian_capture_001.py` identical to certified object | YES (`e94f26c7…`) |
| `graph_projections.py` unchanged from pre-merge main | YES (`e5a5d7f6…`) — F4 unreached |
| F3 surface (`obsidian_capture_note.py`) unchanged | YES |

Behavioural, re-run against main after the merge:

| property | result |
|---|---|
| `RegionPath` scope-qualified identity | PRESENT — `extract_human_regions` keys are tuples; `('a','x')` and `('b','x')` are distinct entries |
| stack-based structural marker pairing | PRESENT — `END` must match the open stack top (`malformed-protected-markers:unpaired`) |
| cross-scope substitution fix | PRESENT — `a/x` + `b/x` both payloads preserved, no transfer |
| same-scope duplicate identity | FAIL CLOSED — `duplicate-protected-region-names` |
| same-name open-ancestor (self nesting) | FAIL CLOSED — `ambiguous-protected-region-nesting` |
| crossed markers | FAIL CLOSED — `malformed-protected-markers` |
| unclosed markers | FAIL CLOSED — `malformed-protected-markers` |
| nested distinct names, no spurious duplication | PRESENT — each payload appears exactly once |
| transactional merge | PRESENT — refusal raises before any write; the caller's note is untouched |

`POSTMERGE_HUMAN_CONTENT_LOSS = 0`
`POSTMERGE_CROSS_SCOPE_SUBSTITUTION = 0`

## Post-merge main CI (`eadc0f62`)

| check | result |
|---|---|
| `quality (ubuntu-latest, 3.12, full)` | success |
| `quality (ubuntu-latest, 3.13, compat)` | success |
| `quality (windows-latest, 3.12, windows)` | success |
| `control-plane` | success |

Main is green on all four required checks after the merge, on the same tree
that was certified.

## Post-merge tests

Focused suites re-run against `eadc0f62`: `test_as_obsidian_capture_001.py`,
`test_as_coder_alpha_obsidian_001.py`, `test_as_coder_alpha_obsidian_r1_001.py`,
`test_as_coder_alpha_capture_001.py`,
`test_as_coder_alpha_042_conversation_capture.py`,
`test_as_graph_005_projections.py`, `test_as_graph_005_adversarial.py`.

**189 passed, 0 failed.**

## Truth boundary

`F2_INTEGRATED = YES`. `F2_SEALED = YES`.

This seals the F2 protected-region identity work only. It is **not** a claim
that the Obsidian program is complete:

- **F4 is open and is the materially worse defect.** `graph_projections.py`
  still carries an independent HUMAN-region implementation that silently drops
  human-authored bytes at the real refresh surface. Baseline evidence is in
  PR #706. F2 did not touch it.
- **F3 is open.** Literal marker-shaped text authored inside HUMAN content
  currently fails closed and preserves bytes; extending the existing
  `_neutralize_markers` convention is owner-gated and unstarted.

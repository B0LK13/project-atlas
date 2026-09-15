# D-028 — Integrated Atlas3 Stack Manifest


Independently produced by Claude (D-026/D-028 audits), materialized under D-029.

**Bound to:** `MAIN_HEAD = f6b2495a03196901a5a72c2cf3451d4504b54d5f` / `MAIN_TREE = 9c670d710ec63d36fea70c6a181c088b79294336`

- `STACK_DEPTH = 77`
- `STACK_COMMITS_MAPPED = 77`
- `UNMAPPED_COMMITS = 0`
- `UNKNOWN_SEMANTICS = 0`
- `D026_OPEN_PR_HEADS_EMBEDDED = 55`

> Containment is proven by exact commit-SHA identity (main descends from PR592 HEAD, which contains all 77 commits verbatim), not merely ancestry inference.

**Method note:** this manifest reflects the D-025 integrated main as of the bound HEAD/TREE above. It is a point-in-time audit record, not a live query — if main moves again, containment/PR-state columns below should be treated as historical until re-verified.

## Commit manifest (oldest → newest)

| # | SHA | Package | PR | PR state | Class | Main containment |
|---|-----|---------|----|----|-------|-------------------|
| 1 | `67e6c2cdb` | D-191 | — | — | DOCS | CONTAINED |
| 2 | `cefc234e6` | PROGRAM | — | — | RUNTIME | CONTAINED |
| 3 | `7cd85abe4` | D-191 | — | — | DOCS | CONTAINED |
| 4 | `0fd350108` | PROGRAM | #510 | MERGED | RUNTIME | CONTAINED |
| 5 | `7e8ce3fc1` | D-193 | — | — | DOCS | CONTAINED |
| 6 | `0cdee6009` | D-193 | — | — | RUNTIME | CONTAINED |
| 7 | `01f91cf45` | D-193 | — | — | TEST | CONTAINED |
| 8 | `d65926cd9` | PROGRAM | — | — | RUNTIME | CONTAINED |
| 9 | `25fa818ef` | PROGRAM | — | — | RUNTIME | CONTAINED |
| 10 | `3afd1e184` | D-196 | — | — | RUNTIME | CONTAINED |
| 11 | `d0f68b179` | PROGRAM | — | — | RUNTIME | CONTAINED |
| 12 | `41f96d1b8` | D-196 | — | — | DOCS | CONTAINED |
| 13 | `bc4f5dd9b` | D-197 | — | — | TEST | CONTAINED |
| 14 | `3cee22857` | D-197 | — | — | DOCS | CONTAINED |
| 15 | `1f63e8b55` | D-199 | — | — | GOVERNANCE | CONTAINED |
| 16 | `9f1516013` | D-199 | — | — | GOVERNANCE | CONTAINED |
| 17 | `156ae7e4d` | D-199 | #511 | MERGED | GOVERNANCE | CONTAINED |
| 18 | `5a3d15c19` | AT3-043 | #536 | OPEN | RUNTIME | CONTAINED |
| 19 | `96470a2c2` | AT3-045 | #537 | OPEN | RUNTIME | CONTAINED |
| 20 | `11a49ad19` | AT3-037 | #538 | OPEN | RUNTIME | CONTAINED |
| 21 | `9db8d18f1` | AT3-038 | #539 | OPEN | RUNTIME | CONTAINED |
| 22 | `3f2f1a77d` | AT3-010 | #540 | OPEN | RUNTIME | CONTAINED |
| 23 | `4067eddee` | AT3-013 | #541 | OPEN | RUNTIME | CONTAINED |
| 24 | `268b3d9cc` | AT3-011 | #543 | OPEN | RUNTIME | CONTAINED |
| 25 | `2dfbd3a2c` | AT3-012 | #544 | OPEN | RUNTIME | CONTAINED |
| 26 | `6da5f08ec` | AT3-061 | #545 | OPEN | RUNTIME | CONTAINED |
| 27 | `5426f2c62` | AT3-060 | #546 | OPEN | RUNTIME | CONTAINED |
| 28 | `cb9576ec2` | AT3-062 | #547 | OPEN | RUNTIME | CONTAINED |
| 29 | `d692cb886` | AT3-021 | #548 | OPEN | RUNTIME | CONTAINED |
| 30 | `ce266ef42` | AT3-051 | — | — | RUNTIME | CONTAINED |
| 31 | `029dd8673` | AT3-051 | #549 | OPEN | DOCS | CONTAINED |
| 32 | `e3f7758a4` | AT3-052 | #550 | OPEN | RUNTIME | CONTAINED |
| 33 | `b7a5e6004` | AT3-070 | #551 | OPEN | RUNTIME | CONTAINED |
| 34 | `d2ccdc8ce` | AT3-071 | #552 | OPEN | RUNTIME | CONTAINED |
| 35 | `853f015f5` | AT3-072 | #553 | OPEN | RUNTIME | CONTAINED |
| 36 | `ea398c42e` | AT3-080 | #554 | OPEN | RUNTIME | CONTAINED |
| 37 | `9aabac917` | AT3-100 | #555 | OPEN | RUNTIME | CONTAINED |
| 38 | `875913b46` | AT3-090 | #556 | OPEN | RUNTIME | CONTAINED |
| 39 | `36e3b0fba` | AT3-091 | #558 | OPEN | RUNTIME | CONTAINED |
| 40 | `0c51083e0` | AT3-094 | #559 | OPEN | RUNTIME | CONTAINED |
| 41 | `26850b35d` | AT3-092 | #560 | OPEN | RUNTIME | CONTAINED |
| 42 | `13350c3df` | AT3-096 | #561 | OPEN | RUNTIME | CONTAINED |
| 43 | `49b7c3a28` | AT3-095 | #562 | OPEN | RUNTIME | CONTAINED |
| 44 | `3e19882ec` | AT3-110 | #563 | OPEN | RUNTIME | CONTAINED |
| 45 | `749a48180` | AT3-111 | #564 | OPEN | RUNTIME | CONTAINED |
| 46 | `644104b12` | AT3-081 | — | — | RUNTIME | CONTAINED |
| 47 | `6de6a8763` | AT3-101 | — | — | RUNTIME | CONTAINED |
| 48 | `69ef29e69` | AT3-102 | — | — | RUNTIME | CONTAINED |
| 49 | `c3d6ababb` | AT3-081 | #566 | OPEN | RUNTIME | CONTAINED |
| 50 | `be14bc7a9` | PROGRAM | #565 | OPEN | MERGE | CONTAINED |
| 51 | `bf138470a` | PROGRAM | #567 | OPEN | MERGE | CONTAINED |
| 52 | `7ec0ef265` | AT3-006 | — | — | RUNTIME | CONTAINED |
| 53 | `46628aebc` | AT3-081 | #568 | OPEN | DOCS | CONTAINED |
| 54 | `25d9b3d50` | AT3-020 | #569 | MERGED | RUNTIME | CONTAINED |
| 55 | `5a39f902f` | AT3-022 | — | — | RUNTIME | CONTAINED |
| 56 | `62cfadd56` | AT3-022 | #570 | MERGED | RUNTIME | CONTAINED |
| 57 | `c5cc55c0e` | AT3-023 | #571 | MERGED | RUNTIME | CONTAINED |
| 58 | `47e52801d` | AT3-082 | #573 | MERGED | RUNTIME | CONTAINED |
| 59 | `706c239a0` | AT3-093 | #574 | MERGED | RUNTIME | CONTAINED |
| 60 | `5441fd885` | AT3-112 | #575 | MERGED | RUNTIME | CONTAINED |
| 61 | `d661e8c1f` | AT3-053 | #577 | MERGED | RUNTIME | CONTAINED |
| 62 | `307ba8628` | AT3-036 | #578 | OPEN | RUNTIME | CONTAINED |
| 63 | `9e890bdd7` | AT3-039 | #579 | OPEN | RUNTIME | CONTAINED |
| 64 | `7e99a317a` | AT3-040 | #580 | OPEN | RUNTIME | CONTAINED |
| 65 | `c3d2b82ba` | AT3-041 | #581 | OPEN | RUNTIME | CONTAINED |
| 66 | `5467602d3` | AT3-042 | #582 | OPEN | RUNTIME | CONTAINED |
| 67 | `2c5e598f8` | AT3-044 | #583 | OPEN | RUNTIME | CONTAINED |
| 68 | `8dce8367a` | AT3-047 | #584 | OPEN | RUNTIME | CONTAINED |
| 69 | `e98e04d04` | AT3-048 | #585 | OPEN | RUNTIME | CONTAINED |
| 70 | `aa301c07e` | AT3-049 | — | — | RUNTIME | CONTAINED |
| 71 | `b348f0b6f` | AT3-049 | #586 | MERGED | DOCS | CONTAINED |
| 72 | `d9af2ec50` | AT3-046 | #587 | MERGED | RUNTIME | CONTAINED |
| 73 | `c630eb5f6` | AT3-054 | #588 | OPEN | RUNTIME | CONTAINED |
| 74 | `cb685447c` | AT3-055 | #589 | OPEN | RUNTIME | CONTAINED |
| 75 | `768f38490` | AT3-056 | #590 | OPEN | RUNTIME | CONTAINED |
| 76 | `8c4c8a95d` | AT3-057 | #591 | OPEN | RUNTIME | CONTAINED |
| 77 | `3f74bbb35` | AT3-058 | #592 | MERGED | RUNTIME | CONTAINED |

## Classification totals
- `DOCS`: 8
- `RUNTIME`: 62
- `TEST`: 2
- `GOVERNANCE`: 3
- `MERGE`: 2

## Provenance
- Stack range: `git rev-list main..PR592_HEAD` at D-026 time (77 commits, full DAG).
- PR-head matching: exact `headRefOid` equality against all open/all-state PRs (not ancestry inference).
- Path classification: derived from real `git log --name-only` per commit, not commit-message heuristics.
- Current-main containment: proven transitively — `main` descends from `PR592_HEAD`, which contains every commit in this table verbatim (same SHA).

MERGE_AUTHORIZATION = NOT_GRANTED. This document is evidence, not a certification or an integration action.

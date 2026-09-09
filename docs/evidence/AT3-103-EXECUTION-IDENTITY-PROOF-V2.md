# AT3-103 — Execution identity + evidence attestation + proof v2: evidence receipt

| Field | Value |
|---|---|
| Package | AT3-103 (Ultimate Atlas planning alias ULT-01a) |
| PR | #743 |
| Directives | `D-PROJECT-ATLAS-ULTIMATE-KNOWLEDGE-DEVELOPMENT-CONVERGENCE-001` (authorized the package) → `D-ATLAS-ULT-01A-AT3-103-ADV-REMEDIATION-001` (remediation of round 1) |
| Base (merge-base with `origin/main`) | `9972d16448a9cefd3444363b59eae2c0dbed7f20` / tree `2067f1253d411e3bef9fd20ad534b29316b6e953` |
| `origin/main` at receipt time | `8aaf7b63518d12f0abd3217de320bca16f3d9fa8` (moved past the base by docs-only #740; candidate unrebased by convention) |
| Certified object | **HEAD `58a473e75aa3fc00ac0ba8bd6aeb4e246532f318` / TREE `ab682de1bc42e25c1e40b3a55b6567bfe89c6b7d`** (`src` `f6fa53af…`, `tests` `3ff79b23…`) |
| This receipt's commit | docs-only; `src` and `tests` trees are hash-identical to the certified object, so round-3 certification transfers by hash, not by assertion |
| `MERGE_AUTHORIZATION` | **NOT_GRANTED** |

Directive identifiers are owner messages recorded in `WORKLOG.md`; they are
not files in the tree.

## 1. Candidate history — every verification is bound to one exact object

| Round | HEAD | TREE | IV | ADV | CI (exact head) | Status |
|---|---|---|---|---|---|---|
| 1 | `5b33e039a7cdd276c6390a684dfbff0acd07126e` | `15593d69a341f8b3172816239ee9e78857e0cb47` | PASS_WITH_NONBLOCKING_FINDINGS (P2×4) | PASS_WITH_FINDINGS (P2×5 classes) | green (run 34274999428) | SUPERSEDED_BY_REMEDIATION |
| 2 | `dcb3041c67a785b9ca43ccb29fa7b23710276e94` | `859224f17c0730a46e9ed476c6f5794954a1b809` | PASS_WITH_NONBLOCKING_FINDINGS (P2×2) | PASS_WITH_FINDINGS (P2×1) | green (run 34278292846) | SUPERSEDED_BY_REMEDIATION |
| 3 | `58a473e75aa3fc00ac0ba8bd6aeb4e246532f318` | `ab682de1bc42e25c1e40b3a55b6567bfe89c6b7d` | PASS_WITH_NONBLOCKING_FINDINGS (**P0=P1=P2=0**) | PASS_WITH_FINDINGS (**P0=P1=P2=0**) | see §5 (run 34281801544) | CERTIFIED CANDIDATE |

Predecessor evidence is retained above as history; none of it transfers to
round 3 (`TARGET MOVED`). Both verifiers used their own three-value
vocabulary; under the owner's §29 rule a P3-only result is the qualifying
outcome, and the P3 residuals are recorded separately in §7. The implementer
does not bind AT3-052 (`adv_result=PASS`) on its own authority.

## 2. What the certified object contains

- `src/atlas_contracts/canonical.py` — canonical JSON + SHA-256 (sorted keys,
  compact separators, `ensure_ascii=True`, non-finite floats and non-string
  keys refused). Not an RFC 8785 claim.
- `src/atlas_contracts/execution_identity.py` — `atlas.execution-identity.v1`
  (Git/software profile; `OBSERVED | UNKNOWN` blocks with mutual consistency;
  `identity_digest` + `run_id` self-verify; strict `schema_version`; ASCII
  identifier tokens; `extra="forbid"`).
- `src/atlas_contracts/attestation.py` — `atlas.evidence-attestation.v1`
  (stage/type table; `model` producer refused; IV/ADV must *declare*
  independence; positive `SUMMARY_COUNTERS` vocabulary with strict bounded
  ints; `DEP_*` classes; `content_hash` + `attestation_id` self-verify).
- Two JSON schemas, labelled STRUCTURAL.
- `evaluate_proof_v2` in `src/project_atlas/atlas3/proof.py` (additive) and
  `atlas proof --identity/--attestations` in `atlas3/cli.py`. Root
  `src/project_atlas/cli.py` untouched.
- `docs/atlas-3/AT3-103.md`, EPICS row (count 66→67), PACKAGE-MATURITY entry,
  backlog checkbox, DEPENDENCY-DAG lines.
- `docs/scripts/at3_103_negative_controls.py` and this receipt's control
  output `docs/evidence/AT3-103-negative-controls-58a473e7.json`.

Proof v1 (`evaluate_proof`) is byte-identical: three golden file digests plus
an eight-shape extended matrix regenerated from
`git show 9972d164:src/project_atlas/atlas3/proof.py` are pinned in
`tests/unit/test_atlas3_proof_v2_103.py`; the ADV's 90-combination matrix was
90/90 byte-identical in every round; the `evaluate_proof` source text is
AST-identical to base.

## 3. Implementer-run gates at the certified object

| Gate | Result |
|---|---|
| ruff | `All checks passed!` |
| mypy `src` | `Success: no issues found in 408 source files` |
| Targeted (4 new suites) | 223 passed, 0 failed |
| Affected (11 suites: proof v1, foundation, capabilities, atlas3 CLI, contracts, demo isolation, IV bind, ADV bind, ADV control, program docs, CLI surface contract) | 171 passed, 0 failed |
| Full suite (junit) | 5917 collected, 5905 passed, 8 skipped, 4 xfailed, 0 failed, 0 serializer warnings |

Counts come from `--junitxml`; this repository's pytest prints no summary line.

## 4. Negative controls (falsification)

`docs/scripts/at3_103_negative_controls.py` applies 28 source mutations, one
at a time, under a sha256 assertion that the mutation changed the file and
that the source was restored byte-identical. Baseline: 223 tests, 0 failures.
Every control kills at least one test; 24 distinct failing sets. Five
CLI-reader controls (NC-I symlink, NC-J size cap, NC-M recursion, NC-O
duplicate keys, NC-X `--evidence ''`) legitimately share the single bundled
CLI guard test, so `pairwise_distinct` is **false** and is reported, not
asserted. Full per-control failing-test names:
`docs/evidence/AT3-103-negative-controls-58a473e7.json`.

| Control | Kills |
|---|---|
| NC-A object==candidate check removed | 2 |
| NC-B content_hash recomputation skipped | 9 |
| NC-C model producer denylist dropped | 3 |
| NC-D `ensure_ascii=False` in canonical helper | 2 |
| NC-E report written before validation | 7 |
| NC-F attestation secret scan dropped (ADV r1 M05) | 12 |
| NC-G PRESENT without PASS (ADV r1 M09) | 1 |
| NC-H attestation_id derivation unchecked (ADV r1 M22) | 2 |
| NC-I symlink input accepted (ADV r1 M38) | 1 |
| NC-J 1 MiB cap dropped (ADV r1 M39) | 1 |
| NC-K instance trusted without re-validation (ADV r1 M42) | 1 |
| NC-L task-id guard weakened to v1 check | 4 |
| NC-M RecursionError not wrapped | 1 |
| NC-N locator collision check dropped | 1 |
| NC-O duplicate JSON keys accepted | 1 |
| NC-P summary positive vocabulary dropped | 17 |
| NC-Q task-id secret scan dropped | 1 |
| NC-R raw-value secret scan dropped | 5 |
| NC-S v2 namespace collapsed onto v1 | 8 |
| NC-T strict summary ints relaxed | 3 |
| NC-U symlink component walk dropped | 2 |
| NC-V resolved containment re-check dropped | 1 |
| NC-W attestations sequence check dropped | 5 |
| NC-X `--evidence ''` conflict dropped | 1 |
| NC-Y task-id identifier pattern dropped | 13 |
| NC-Z `schema_version` strictness relaxed | 3 |
| NC-AA summary count upper bound dropped | 1 |
| NC-AB task-dir-is-file check dropped | 1 |

The ADV's own harness (88 mutants at round 3, 82 killed) overlaps every one
of these; its six survivors are recorded in §7 as test gaps for guards that
hold on direct probe.

## 5. Exact-head CI at `58a473e7` (run 34281801544)

All four jobs `success` (conclusion read from the run, not assumed):

| Job | Result (CI's own pytest summary line) |
|---|---|
| `quality (ubuntu-latest, 3.12, full)` | ruff / mypy green; `5913 passed, 8 skipped, 4 xfailed` |
| `quality (ubuntu-latest, 3.13, compat)` | `5913 passed, 8 skipped, 4 xfailed` |
| `quality (windows-latest, 3.12, windows)` | `5857 passed, 61 skipped, 3 deselected, 4 xfailed`; product-perf `3 passed` — includes every parametrized task-id, symlink and locator test on Windows |
| `control-plane` | success |

CI collects a slightly different set than the local run (5925 vs 5917
collected); both figures are reported as measured, not reconciled by hand.

## 6. Independent and adversarial verification — findings and closures

### Round 1 on `5b33e039` (superseded)

IV P2: v2 task id copied v1's weak check (Windows drive-relative escape,
NUL crash); RecursionError escaped the CLI envelope; independence
self-declaration undisclosed in the package doc; dangling references to a
docs branch. ADV P2: instances passed to `evaluate_proof_v2` were trusted
without re-validation (seal-mode draft, `model_copy`, `model_construct`
reached a written report); secret scan ran on escaped canonical text and
missed tab/newline/quote-adjacent forms; task id was arbitrary text naming a
directory; seven guards had no falsifying test.
**All closed in round 2** (one strict re-validation path; raw-value + task-id
scanning; RecursionError and duplicate keys inside `PROOF_INPUT_INVALID`;
shared component guard; v2 namespace `proof/v2/`; positive summary
vocabulary; strict digest-bound scalars; guard tests for every survivor).

### Round 2 on `dcb3041c` (superseded)

IV and ADV converged on one P2: the locator symlink guard ran after
`resolve()`, so a symlink planted at `proof/v2`, at the task directory, or at
the locator could redirect or overwrite a report (in-root sibling overwrite;
write outside the vault through a symlinked namespace). P3s: `schema_version`
accepted `1.0`/`True`; serializer warning on `model_construct` input;
unreachable except branches; `--evidence ''` bypassed the conflict check;
`attestations=None` raised a raw `TypeError`; unbounded counts.
**All closed in round 3**: `lstat` walk over every path component on the
unresolved path before any resolution (`PROOF_LOCATOR_UNSAFE`, never
followed) — the ADV could not defeat it with symlinks at any level, chains,
hardlinks, FIFOs or file-typed task directories; bounded ASCII identifier
task ids decided before any filesystem access, value never echoed; strict
`schema_version`; bounded counts; `ATTESTATIONS_INVALID`; `is not None`
conflict check; `warnings=False`; dead branches removed.

### Round 3 on `58a473e7` (certified candidate)

IV: no P0/P1/P2. ADV: no P0/P1/P2. P3s → §7.

## 7. Residual register (recorded, not fixed; none blocks)

| Residual | Class | Owner / next package |
|---|---|---|
| TOCTOU between the `lstat` walk and `mkdir`/tmp-write/`os.replace` (no `O_NOFOLLOW`/dirfd anchoring); requires concurrent write access inside the vault | DEFER_WITH_RESIDUAL | proof storage hardening (ULT-01b or a storage package) |
| Windows junctions/reparse points are not symlinks to `Path.is_symlink()`; the resolved containment check catches junctions leaving the proof root but not one pointing at a sibling task dir; Windows untested for this | DEFER_WITH_RESIDUAL | same |
| Concurrent writers to one `proof/v2/<task>/` | DEFER_WITH_RESIDUAL | same |
| Symlinked `generated/`, `ops/`, `atlas3/` or `proof/` is refused for v2 while v1 and other atlas3 writers follow it (deliberate strictness, wider than the owner's stated scope) | DOCUMENT_CONTRACT | recorded in `AT3-103.md` |
| Test gaps for guards that hold on direct probe: symlink planted at `generated`/`ops`/`atlas3`/`proof` (ADV R02); component-branch non-echo (ADV R20); FIFO/directory locator (ADV N06); `\x7f` beyond the regex (ADV R18, redundant guard); canonical-text scan redundant with raw scan (N10); dict keys in raw scan (N11) | DEFER_WITH_RESIDUAL (tests only; kept out of this receipt's commit to keep `tests/` at the certified hash) | first follow-up test package |
| `MAX_TASK_ID_LENGTH` is an unused constant (the limit lives in `TASK_ID_PATTERN`) | DEFER_WITH_RESIDUAL | trivial cleanup in the next `proof.py` change |
| `model_claims_complete="yes"` is truthy (Python API only) | DEFER_WITH_RESIDUAL | next `proof.py` change |
| `PermissionError` on an unwritable proof directory is a raw `OSError` (CLI envelopes it as `ATLAS3_ERROR`, nothing partial) | DOCUMENT_CONTRACT | — |
| The caller's own task id reaches the report and directory name verbatim (identifier alphabet only) | DOCUMENT_CONTRACT | — |
| `secrets._PATTERNS` coverage (e.g. `ghp_…`, JWT) is outside AT3-103 | DEFER_WITH_RESIDUAL | secrets package |
| JSON schemas are STRUCTURAL; a cross-language semantic verifier does not exist | DEFER_WITH_RESIDUAL | future SDK work |
| `independent_of_implementer` is a declaration; no principal registry in `src/` | DOCUMENT_CONTRACT (report says `independence_verified: false`) | ULT-07 |
| v1's own weaker task-id check is unchanged (byte-identity promise) | DOCUMENT_CONTRACT | — |

## 8. Failure-pattern candidates (for future Skill / Verifier / Eval material)

```text
FP — typed object mistaken for validated object            (round 1, S2)
FP — canonicalized representation used for security scanning (round 1, S7)
FP — filesystem identifier validated as generic text       (round 1, S5)
FP — fail-closed exception escapes stable error envelope   (round 1, S6)
FP — implementation guard exists without falsifying test   (rounds 1–3, S11)
FP — structural schema mistaken for semantic verifier      (round 1, schemas)
FP — path safety check performed after resolve()           (round 2, S5)
FP — receipt figures typed rather than derived             (avoided: controls script + JSON committed)
```

## 9. Claims

**Proven at `58a473e7`:** one strict validation path for JSON and instance
input; every attestation bound to one exact HEAD/TREE, one identity digest and
one project; digest tamper, placeholder, wrong derived id refused; model
producer never evidence; IV/ADV independence must be declared and is reported
as declared-only; authority-shaped content cannot enter a summary or the
report; secrets refused on raw values and task ids without echo; nothing
written before validation; symlinked components never followed; v1
byte-identical; deterministic across processes; ASCII/LF reports; root
`cli.py` and every DENY-listed file untouched; contracts do not import Core.

**Not made:** live observation of git/environment/tools (`live_observation_wired: false`);
IV/ADV attestation ingestion; proof DAG; SLSA or any compliance claim;
Windows execution of the new write path (reasoned, and exercised only by
Windows CI's test run); protection against a writer who already holds write
access inside the vault; principal verification of independence; ULT-01b
readiness beyond the owner's gate; merge authority.

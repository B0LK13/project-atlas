# AS-PROV-006 — execution provenance

#794's runner could show that a mission ran. It could not show *whose code* ran.
This closes that gap.

```bash
python scripts/acceptance/mission_accept.py \
    --i-authorize-bounded-execution --isolated-execution \
    --json-out /tmp/acceptance.json
```

## The contract, chosen explicitly

> **Execution of a distribution built from the selected commit's tree.**

Not "direct execution from the source checkout". A checkout can be shadowed in
three ways that are invisible from the parent process, so pointing at a
directory proves nothing.

Measured on this machine, not assumed:

| Setup | What `import project_atlas` resolved to |
|---|---|
| decoy in CWD **and** on `PYTHONPATH`, plain `python -c` | **the decoy** |
| same, under `python -I` | the caller's **editable install** |
| `-I` **and** a venv holding only the built wheel | the **candidate distribution** |

`-I` alone is not enough — it does nothing about the venv's own site-packages.
Both halves are required, and both are now in force.

## How identity is established

1. `git archive <commit>` → the **committed** tree, so a dirty working directory
   cannot leak into the artifact.
2. `pip wheel` that export. Build isolation stays **on**: this repo declares
   `setuptools>=68` as a build requirement and modern venvs no longer ship
   setuptools, so `--no-build-isolation` would silently depend on whatever the
   caller happens to have — exactly the ambient coupling this exists to remove.
3. A fresh venv, wheel installed, **never** an editable install.
4. Every worker runs under `-I` (implies `-E`, `-s`).
5. The **worker** reports its own `project_atlas.__file__`, interpreter and
   isolation flags. The parent verifies them. A parent-side check would prove
   nothing about the child.

Recorded per run: commit, tree, wheel name, wheel sha256, interpreter, install
method, distribution version, worker import origin, isolation flags.

**Fail closed.** If identity cannot be established the run exits **3** having
executed nothing. There is no fallback to the caller's environment.

## What the claim covers, precisely

Byte equality for one file proves that file. Here is what establishes the
identity of everything else, measured on a provisioned environment rather than
asserted.

Warm reuse verifies pip's own `RECORD` for the installed distribution:

| RECORD lines | 971 |
|---|---|
| carry a sha256 | 557 |
| `.pyc`, no digest written by pip | 413 |
| outside site-packages (`../../../bin/atlas`) | 1 |
| **hash-verified every run** | **556** |

Those 556 break down as **537 `project_atlas` modules**, **12 `atlas_contracts`
modules**, and **7 `project_atlas-2.0.0.dist-info` metadata files** — so the
candidate's modules *and* its installed distribution metadata are covered, not
just one file.

**Dependencies: versions only.** All 13 installed distributions are recorded in
the marker and compared on warm reuse, so a changed `pydantic` fails closed. But
their *file contents* are not hashed. An unchanged source tree does not imply an
unchanged environment, and this is where that stops being checked.

**Bytecode is not in RECORD, and that mattered.** pip writes no digest for
`.pyc`, and CPython's staleness check is a forgeable source mtime+size stamp. A
`.pyc` compiled from modified source and stamped with the real `.py`'s mtime and
size **executed**, while RECORD verification reported zero mismatches. So
`purge_bytecode` removes `__pycache__` at every verification point, forcing
compilation from the hash-verified sources. The regression test asserts the
attack works *before* asserting the repair.

**Not covered at all:** `atlas_studio` — it lives in `scripts/` and is not in
the wheel (verified by inspecting the wheel). `--probe-boundaries` also still
runs in the caller's environment.

A cache key, a path, a version string, or a parent-side check is **not** worker
provenance and is never presented as such.

## Cache lifecycle — five risks, each reproduced before repair

| Risk | Was | Now |
|---|---|---|
| env modified after provisioning | warm reuse **accepted** the tampered env | 556 RECORD hashes checked; tampered env is a cache miss and is rebuilt |
| provisioning interrupted | markerless `env-*` published + orphan build dir; prune reclaimed neither | built under `.staging-*`, published with one `os.replace`; nothing partial is ever published; prune sweeps staging |
| concurrent provisioning | 3 callers raced in one venv; **2 died** in `ensurepip` with a raw `CalledProcessError` | serialised by a kernel lock per key; **3/3 succeed**, one env; builder errors wrapped |
| prune while in use | deleted a live environment | skips any key whose lock is held, and reports it |
| deps differ, tree unchanged | invisible | 13 versions recorded; drift fails closed |

Markerless `env-*` directories are deliberately **not** reclaimed: atomic publish
means this module can no longer produce one, so deleting it would be a guess
about someone else's directory.

Cost: cold **5.6 s**, warm **0.17 s** (probe + 556 hashes + dependency compare +
bytecode purge).

## Negative evidence — the claim is falsifiable

| Attempt | Result |
|---|---|
| decoy `project_atlas` in CWD + `PYTHONPATH` | rejected; test first asserts the decoy *does* win without `-I`, so the attack is real |
| import origin outside the provisioned env | `ProvenanceError: ... OUTSIDE the provisioned environment` |
| origin inside the env but not an installed dist | `ProvenanceError: ... not an installed distribution` |
| distribution absent (bare venv) | `ProvenanceError: could not import project_atlas` |
| worker not isolated / user site enabled | rejected on each flag |
| unreadable distribution metadata | rejected |
| marker claims a tree the env does not have | marker is a *claim*; the live interpreter is re-probed before reuse |

## What this does NOT cover

**`atlas_studio` is not proven.** It lives in `scripts/` and is not in the
wheel — verified by inspecting the wheel's contents, not by assuming. The
provenance claim covers `project_atlas` and `atlas_contracts` only. The Studio
bridge remains a caller-side component.

The boundary probes (`--probe-boundaries`) also still run in the caller's
environment; they exercise recovery semantics, not provenance.

## Resource behaviour — two defects found and fixed here

**The cache key must not include the wheel digest.** Wheels embed timestamps
and are not byte-reproducible: building one tree twice produced
`4596e393…` then `a82195608…`. Keying on the artifact provisioned a fresh
~130 MB environment on *every run* — an unbounded installation loop. The key is
now tree + interpreter + platform; the digest is still recorded as evidence of
the artifact actually installed. Verified: **5.11 s cold, 0.06 s warm, one env.**

**The cache must not live in the run's temp dir.** `/tmp` is a tmpfs on this
class of machine, and filling it aborted unrelated work with
`OSError(122, 'Disk quota exceeded')`. That is an *environment failure*, not a
test verdict, and is reported as a skip — never as a pass or a fail. The default
is now `~/.cache/atlas-acceptance/envs`, disk-backed and pruned to a bound.

Cleanup ownership is explicit: a run-created cache (`--ephemeral-env`) is
removed; a caller-supplied `--env-cache` never is; the default persistent cache
is *pruned*, and pruning only ever touches `env-*` directories carrying this
tool's own marker.

## Running the full suite on a tmpfs `/tmp`

Independent of provenance, but it bites the same way. On this machine `/tmp` is
a 5.5 G tmpfs shared with other agents' worktrees, and the full test suite's
own `tmp_path` usage can exhaust it mid-run:

```
OSError: [Errno 122] Disk quota exceeded
```

That aborts the run wherever it happens to be — twice here, once on unrelated
tests. **An aborted run is neither a pass nor a fail** and is never reported as
one. Give pytest a disk-backed temp dir:

```bash
python -m pytest --basetemp=~/.cache/atlas-pytest-tmp
```

CI is unaffected: hosted runners do not put `/tmp` on a small tmpfs.

## Upstream dependency — #789, still unresolved

`start_mission_run`'s default idempotency key omits the adapter, so two
different commands at one commit collide and the second returns the first's
result. Reported with a standalone reproduction.

**Checked at the time of writing: #789 is still at `1c6bd038`, unchanged, with
no successor supplied.** So the mitigation stands — this runner always passes an
explicit key including an adapter digest. That is a workaround **in this
caller**; it does not repair #789's default, and nothing here modifies that
branch.

## Preflight under isolation

Import leakage in the *caller's* environment is a hard failure for the
in-process path and only **informational** under `--isolated-execution`, where
the engine deliberately does not run from the caller's environment. Repository
identity, partial assembly and component pins are still enforced in both modes.

## Reproducible commands

```bash
# provisioned environments live on disk, NOT under a tmpfs /tmp
python scripts/acceptance/mission_accept.py \
    --i-authorize-bounded-execution --isolated-execution --probe-boundaries \
    --json-out /tmp/acceptance.json

# focused lifecycle + provenance checks
python -m pytest tests/unit/test_provenance_cache_lifecycle_007.py \
                tests/unit/test_execution_provenance_006.py \
                --basetemp=~/.cache/atlas-work/pytest --no-cov

# the full suite needs a disk-backed temp dir on a tmpfs-/tmp machine
python -m pytest --basetemp=~/.cache/atlas-work/pytest
```

Environment cache: `~/.cache/atlas-acceptance/envs` by default (reused across
runs, pruned to a bound, never removed by a run). `--env-cache` points elsewhere
and is never removed; `--ephemeral-env` provisions into the run root and is.

## ATLAS-DOC-RECEIPT — AS-PROV-006

```text
PACKAGE                 = AS-PROV-006
BRANCH                  = feat/atlas-execution-provenance-006
PR                      = #796 (DRAFT)
BASE                    = 58081e17243f79766b6895dc210e956e9bdc2547  (#794, unmodified)
RELATIONSHIP            = extends #794; does NOT supersede it. #794's CI
                          conclusions are NOT transferred here, nor #793's.

CONTRACT                = DISTRIBUTION_BUILT_FROM_SELECTED_TREE
                          (not "direct execution from the source checkout")
ISOLATION               = venv containing only a wheel built from `git archive
                          <commit>` + `python -I` (implies -E, -s) on every worker
VERIFICATION_POINT      = INSIDE the worker process; the parent verifies the
                          worker's own report, never its own import
FAIL_MODE               = fail closed; exit 3, nothing executed, no fallback

POSITIVE_EVIDENCE       = installed orchestration/mission/execution.py is
                          BYTE-IDENTICAL to `git show HEAD:src/.../execution.py`
NEGATIVE_EVIDENCE       = decoy install / foreign origin / editable-style origin /
                          missing distribution / non-isolated worker / user-site
                          enabled / unreadable metadata -> all REJECTED
DECOY_CONTROL           = the test first asserts the decoy DOES win without -I,
                          so the attack is exercised before it is defeated

MISSIONS_RERUN          = 4/4 through the isolated path, all provenance verified
                          passing_change            task ok      (expected ok)
                          intentional_test_failure  task FAILED  (expected fail)
                          real_checkout             task ok      (expected ok)
                          interrupted_task          UNCERTAIN_REQUIRES_RECONCILIATION
                                                    safe_to_retry=False
                                                    auto_replay_prevented=True
COMMAND_VS_TASK         = kept distinct; a spawned, cleanly-exited command that
                          fails its tests is NOT task completion

LOCAL_GATES             = ruff clean | mypy 413 files clean
LOCAL_SUITE             = 6496 passed, 8 skipped, 4 xfailed, 0 failed (409s)
LOCAL_SUITE_CAVEAT      = --no-cov --basetemp=<disk>. TWO earlier attempts ABORTED
                          on OSError(122) 'Disk quota exceeded' (/tmp is a small
                          tmpfs shared with other agents). An aborted run is
                          NEITHER a pass NOR a fail and is not counted.
CI_EXACT_HEAD           = PENDING on 179b1e9b at time of writing
CI_BLOCKER              = GitHub Actions API rate limit exhausted (~60 min reset);
                          caused by my own unguarded poll loop. Push succeeded;
                          only the status read is blocked.

CACHE_LIFECYCLE_007     = five risks, each REPRODUCED before repair:
                          tamper-after-provision  ACCEPTED -> now 556 RECORD
                            hashes checked on warm reuse; tampered env rebuilt
                          interrupted provision   published a markerless env-* +
                            orphan build dir -> now staged + os.replace; nothing
                            partial is ever published; prune sweeps .staging-*
                          concurrent provisioning 2 of 3 died in ensurepip with a
                            raw CalledProcessError -> kernel lock per key; 3/3 ok
                          prune while in use      deleted a live env -> skips any
                            key whose lock is held
                          dependency drift        invisible -> 13 versions
                            recorded; drift fails closed
BYTECODE_HOLE           = FOUND AND CLOSED. pip writes no digest for .pyc (413 of
                          971 RECORD lines). A .pyc compiled from MODIFIED source
                          and stamped with the real .py's mtime+size EXECUTED
                          while RECORD reported n_mismatched=0. purge_bytecode
                          now runs at every verification point; the regression
                          test asserts the attack works before the repair.
CLAIM_BREAKDOWN         = 556 hash-verified = 537 project_atlas + 12
                          atlas_contracts + 7 dist-info metadata.
                          Dependencies: VERSIONS only, contents NOT hashed.
                          atlas_studio: NOT COVERED (not in the wheel).
WARM_COST               = 5.6s cold -> 0.17s warm (probe + 556 hashes + dep
                          compare + bytecode purge)
RESOURCE_DEFECTS_FIXED  = env cache key included the wheel digest (wheels embed
                            timestamps; one tree built twice -> 4596e393.. then
                            a82195608..) -> keyed on tree+interpreter+platform;
                            reuse verified 5.11s cold -> 0.06s warm, ONE env
                          cache defaulted under the run temp dir on a tmpfs ->
                            now ~/.cache/atlas-acceptance/envs, pruned to a bound
PORTABILITY_FIX         = stdlib tarfile (filter="data") instead of shelling out
                          to `tar`, which is not safe to assume on Windows

COVERS                  = project_atlas, atlas_contracts
DOES_NOT_COVER          = atlas_studio -- lives in scripts/, NOT in the wheel
                          (verified by inspecting the wheel, not assumed);
                          --probe-boundaries still runs in the caller's env
PLATFORM                = Linux x86_64 / CPython 3.12.14 local only. Windows
                          behaviour established ONLY by windows-latest CI on this
                          PR. macOS never exercised.

UPSTREAM_789            = re-checked: still 1c6bd038, unchanged, NO successor.
                          Adapter-digest keys remain a MITIGATION IN THIS CALLER
                          and do not repair #789's default. Branch not modified.
BASELINE_FAILURE        = atlas validate still exits 1 (unmasked code span);
                          pre-existing, owned by #700, not duplicated here.

FORMAL_IV               = NOT_STARTED (no self-IV claimed)
MERGE_AUTHORIZATION     = NOT_GRANTED
CONSTITUENT_BRANCHES    = unmodified
```

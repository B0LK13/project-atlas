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

## Strongest positive evidence

The installed `orchestration/mission/execution.py` is **byte-identical** to
`git show HEAD:src/project_atlas/orchestration/mission/execution.py`. Not a
version string or a path — the bytes.

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

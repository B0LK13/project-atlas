# PR #801 — combined candidate (integration-004)

One candidate combining the taskcontract portability fix, F10, F3 (source +
regression test) and B1, with B1 evidence **re-measured on this candidate**.

Nothing here is a release claim. Not pushed, not merged, no CI run.
`CANDIDATE != RELEASE`, `LINUX_GREEN != CI_GREEN`, `FIXTURE_RUN != REAL_RUNTIME_COMPATIBILITY`.

## 1. Exact identity

| | |
| --- | --- |
| base | `4c7661d0c89f37e185548f3212bee09cff1c1261` (PR #801 head) |
| code tree | `2df84a573167bde2228f6c793eb743082212e412` |

```
4c7661d0  PR #801 head          (already contains B1's code, commit 4b584d7b)
  d43a6dff  taskcontract portable argv[0]              test-only
  cd99d835  F10 withdrawn agent must not dispatch      src + test
  ec169e65  F3 four help screens cp1252-encodable      src-only
  97b60285  F3 regression test, walks every screen     test-only
  <this>    B1 evidence re-measured + reproducer fix   docs-only
```

The four code commits keep their original hashes. They were **not** cherry-picked
or rebased, because peer sessions have verified `d43a6dff`, `cd99d835` and
`ec169e65` by hash; minting new hashes would silently void those verifications.

## 2. F3 provenance — why `ec169e65` and not `f60d951e`

A native-Windows peer (ATLAS-AGENT-5) independently authored the same F3 fix as
`f60d951e` (its parent `4c7661d0`, its tree `86bf6252`). The two are **content-
identical**, proven without access to that commit:

```
$ git read-tree 4c7661d0
$ git update-index --cacheinfo 100644,af694c2306c58b52b8343c9fb26662dc13827b99,src/project_atlas/cli.py
$ git update-index --cacheinfo 100644,b667d6d30a067bc76a7f46b1e5d0a52443c68b50,src/project_atlas/orchestration/work_readiness/cli.py
$ git write-tree
86bf6252e044862ddd680727c2ef5b8a5958efd6      <- equals the peer's reported tree
```

Those two blobs are `ec169e65`'s. So `ec169e65` carries exactly `f60d951e`'s
content, and `f60d951e` is deliberately **not** used as a commit reference here —
it is not an object this repository can resolve.

## 3. B1 — already in the base; the evidence is what was missing

`4b584d7b` ("B1 — record in-flight process identity") is an **ancestor of
`4c7661d0`**, so B1 needs no code integration. Verified two ways:

| check | result |
| --- | --- |
| `git merge-base --is-ancestor 4b584d7b 4c7661d0` | ancestor |
| `record_launch` / `Liveness` / `process_started` present at the candidate | 1 / 1 / 8 files |
| the same symbols at `aa59fec9` (PR base branch) | **0 / 0** — negative control, so the probe discriminates |

What sat outside `4c7661d0` was a single **docs-only** commit (`3022abea`,
3 files, +90/-2, zero `src/` and zero `tests/`). Its own message says *"evidence
measured on this revision, not an earlier one"* — which is precisely why it was
**not** cherry-picked: it describes `3022abea`, not this candidate. The evidence
is re-measured here instead.

## 4. Re-measured B1 evidence

`docs/orchestration/program/evidence/b1/after-repair-combined-004.txt`, produced
by `repro.sh` on this candidate. The worker is the repo **fixture**
(`_program_fixture_worker.py`, `ATLAS_FIXTURE_MODE=hang`): test-owned, no
registry, no operational state, no real agent runtime.

```
supervisor SIGKILLed
ORPHAN WORKER STILL ALIVE: pid 160605
--- durable attempt record ---
  phase=ADAPTER_INVOKED process_pid=None start_identity=None
--- reconcile ---
  "reason": "pid 160605 is alive and its start identity matches the one recorded at launch"
  "recovery_action": "WORKER_STILL_RUNNING"
orphan cleaned up
```

`process_pid=None` is correct and by design — the identity lives in its own
single-attempt file under `<state>/launches/` until the adapter returns, which is
the whole point of the repair. The reconcile line is the B1 property: the
supervisor no longer reads silence as absence.

### The reproducer had to be fixed to be reproducible

`repro.sh:50` hardcoded `/home/gebruiker/.cache/atlas-b1-repro/find_worker.py`
while `find_worker.py` ships in the same directory. On any other host the script
aborted with `FAIL: worker never appeared`. It now resolves the helper next to
itself. This is a precondition for anyone else validating B1, not added scope.

## 5. How to validate this candidate exactly

```bash
# 1. identity
git rev-parse HEAD                      # the integration commit
git rev-parse HEAD^{tree}
git log --format='%h %t %s' 4c7661d0..HEAD

# 2. the code tree is the one the measurements describe
git rev-parse HEAD~1^{tree}             # 2df84a573167bde2228f6c793eb743082212e412

# 3. isolated venv -- an editable install elsewhere silently tests another tree
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
./.venv/bin/python -c "import project_atlas; print(project_atlas.__file__)"

# 4. gates
./.venv/bin/python -m ruff check .
./.venv/bin/python -m mypy src
./.venv/bin/python -m pytest tests/ --basetemp=<dir outside the repo> --no-cov
./.venv/bin/python -m pytest tests/ --collect-only --no-cov   # must equal the sum

# 5. F3, measured rather than grepped
./.venv/bin/python -m pytest tests/unit/test_cli_help_cp1252_encodable.py --no-cov

# 6. B1
bash docs/orchestration/program/evidence/b1/repro.sh "$PWD" <scratch dir>
```

Two traps that cost real time here, worth passing on:

- **`--basetemp` whose parent does not exist** errors every `tmp_path` test at
  setup — hundreds of E's that look like a broken candidate. Create the parent.
- **the repo's `addopts` already carries `-q`**; adding another makes it `-qq`
  and deletes the pass count from the summary.

## 6. Expected results on Linux

| gate | expected |
| --- | --- |
| ruff | All checks passed |
| mypy | no issues in 457 source files |
| full suite | 6091 passed, 9 skipped, 4 xfailed, 0 failed |
| `--collect-only` | 6104 (equals 6091+9+4) |
| cp1252 regression suite | 6 passed |
| B1 targeted suites | 63 passed, 1 skipped |
| F10 suite | 6 passed |

## 7. Not established here

- **Windows.** Every number above is Linux. There is no Windows host on this
  machine. W-items (cp1252 console rendering, taskcontract on Windows, native
  mypy, watchdog/PID identity, detached process cleanup) are for the Windows
  harness sessions and for CI.
- **CI.** This line has never been through CI.
- **Independent verification.** The same principal authored the four code
  commits, this evidence and this document. Peer sessions have independently
  confirmed the F3 content-identity, the B1 ancestry and the cp1252 command set,
  but that is corroboration of specific facts, not an independent review.

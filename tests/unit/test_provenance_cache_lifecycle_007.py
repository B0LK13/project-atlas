"""AS-PROV-007 -- does the provenance guarantee survive cache reuse?

A cache key says WHICH source was requested. It says nothing about whether the
cached contents are still correct, whether a half-built environment got
published, or whether two runs just fought over one directory. Each test below
corresponds to a failure that was REPRODUCED against the previous
implementation before it was repaired; the docstrings record what it did.

These build real environments, so they are marked `provenance` and share one
module-scoped cache.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "acceptance"))

import execution_env as ee  # noqa: E402

pytestmark = pytest.mark.provenance

ACCEPT_DIR = REPO_ROOT / "scripts" / "acceptance"


@pytest.fixture(scope="module")
def cache(tmp_path_factory):
    """A disposable cache on a disk-backed path.

    Corruption and cleanup probes must never touch the shared default cache,
    and `/tmp` here is a small tmpfs that these ~130 MB environments exhaust.
    """
    root = Path(os.environ.get("ATLAS_PROV_TESTCACHE",
                               str(Path.home() / ".cache" / "atlas-acceptance-tests")))
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture(scope="module")
def warm(cache):
    try:
        return ee.provision(REPO_ROOT, "HEAD", cache)
    except ee.ProvenanceError as exc:
        pytest.skip(f"cannot provision here: {exc}")


def _spawn(code: str, **kw) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", code], text=True, **kw)


def _spawn_killable(code: str, **kw) -> subprocess.Popen:
    """Spawn so the whole tree can be killed on POSIX and Windows alike."""
    return subprocess.Popen([sys.executable, "-c", code], text=True,
                            **ee.spawn_kwargs(), **kw)


# ------------------------------------------------ contents after provisioning

def test_warm_reuse_verifies_contents_not_just_the_key(warm, cache):
    """WAS BROKEN: editing a cached env's source was accepted on warm reuse.

    The key matched, the import origin was still inside the env, so the run was
    attributed to a tree whose installed bytes had been changed.
    """
    probe = warm[2]
    target = Path(probe["origin"]).parent / "orchestration" / "mission" / "execution.py"
    original = target.read_bytes()
    target.write_bytes(original + b"\n# TAMPERED BY TEST\n")
    try:
        _, _, probe2 = ee.provision(REPO_ROOT, "HEAD", cache)
        after = (Path(probe2["origin"]).parent / "orchestration" / "mission"
                 / "execution.py").read_bytes()
        assert b"TAMPERED BY TEST" not in after, "tampered env was reused"
        assert after == original
    finally:
        if target.is_file() and b"TAMPERED BY TEST" in target.read_bytes():
            target.write_bytes(original)


def test_record_verification_is_not_vacuous(warm):
    """A manifest check that verifies nothing would pass everything."""
    env, _, probe = warm[0], warm[1], warm[2]
    manifest = probe.get("manifest") or ee.manifest_probe(ee._venv_python(env))
    assert manifest["checked"] > 100, "RECORD produced too few entries to be meaningful"
    assert manifest["n_mismatched"] == 0
    assert manifest["n_missing"] == 0
    with pytest.raises(ee.ProvenanceError, match="no verifiable entries"):
        ee.verify_contents({"checked": 0})
    with pytest.raises(ee.ProvenanceError, match="differ from the distribution RECORD"):
        ee.verify_contents({"checked": 5, "n_mismatched": 1, "mismatched": ["a.py"]})
    with pytest.raises(ee.ProvenanceError, match="incomplete"):
        ee.verify_contents({"checked": 5, "n_mismatched": 0, "n_missing": 1,
                            "missing": ["b.py"]})


def test_dependency_drift_is_detected(warm):
    """WAS BROKEN: an unchanged tree implied an unchanged environment.

    Dependencies are resolved at install time, so two environments with one key
    can hold different pydantic/PyYAML versions.
    """
    env = warm[0]
    marker = json.loads((env / ee.MARKER_NAME).read_text(encoding="utf-8"))
    assert marker.get("dependencies")
    manifest = ee.manifest_probe(ee._venv_python(env))
    ee.verify_contents(manifest, expect_deps=marker["dependencies"])   # must not raise
    lied = dict(marker["dependencies"])
    lied[next(iter(lied))] = "0.0.0-not-installed"
    with pytest.raises(ee.ProvenanceError, match="dependency versions changed"):
        ee.verify_contents(manifest, expect_deps=lied)


# -------------------------------------------------------- interrupted publish

def test_interrupted_provisioning_publishes_nothing(cache, tmp_path):
    """WAS BROKEN: a kill mid-install left a markerless env-* AND an orphan
    build dir at the published path, and prune reclaimed neither."""
    scratch = tmp_path / "cache"
    code = (
        f"import sys; sys.path.insert(0, {str(ACCEPT_DIR)!r})\n"
        "from pathlib import Path\n"
        "import execution_env as ee\n"
        f"ee.provision(Path({str(REPO_ROOT)!r}), 'HEAD', Path({str(scratch)!r}))\n"
    )
    p = _spawn_killable(code, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    killed = False
    for _ in range(600):
        time.sleep(0.05)
        staged = list(scratch.glob(".staging-*")) if scratch.exists() else []
        if staged and any((d / "env" / "pyvenv.cfg").exists() for d in staged):
            ee.hard_kill_tree(p)
            killed = True
            break
        if p.poll() is not None:
            break
    if not killed:
        p.kill()
        p.wait()
        pytest.skip("could not interrupt provisioning at the right moment")

    published = [d for d in scratch.glob("env-*") if d.is_dir()]
    assert published == [], f"a partially built environment was published: {published}"
    report = ee.prune_envs(scratch, keep_trees=set(), keep=0)
    assert report["staging_removed"], "orphaned staging was not reclaimed"
    assert not list(scratch.glob(".staging-*"))
    # and the cache is still usable afterwards
    probe = ee.provision(REPO_ROOT, "HEAD", scratch)[2]
    assert Path(probe["origin"]).is_file()


# ------------------------------------------------------------- concurrency

def test_concurrent_provisioning_is_serialised(tmp_path):
    """WAS BROKEN: three concurrent callers raced inside one venv directory and
    two died in `ensurepip` with a raw CalledProcessError."""
    scratch = tmp_path / "cache"
    code = (
        f"import sys, json; sys.path.insert(0, {str(ACCEPT_DIR)!r})\n"
        "from pathlib import Path\n"
        "import execution_env as ee\n"
        "try:\n"
        f"    env, ident, probe = ee.provision(Path({str(REPO_ROOT)!r}), 'HEAD', "
        f"Path({str(scratch)!r}))\n"
        "    print(json.dumps({'ok': True, 'env': env.name}))\n"
        "except Exception as e:\n"
        "    print(json.dumps({'ok': False, 'err': type(e).__name__}))\n"
    )
    procs = [_spawn(code, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
             for _ in range(3)]
    results = []
    for p in procs:
        out, _err = p.communicate(timeout=900)
        try:
            results.append(json.loads(out.strip().splitlines()[-1]))
        except (ValueError, IndexError):
            results.append({"ok": False, "err": "NO_OUTPUT"})
    if all(r.get("err") == "ProvenanceError" for r in results):
        pytest.skip("cannot provision in this environment")
    assert all(r.get("ok") for r in results), results
    assert len({r["env"] for r in results}) == 1
    assert len([d for d in scratch.glob("env-*") if d.is_dir()]) == 1


def test_lock_reports_in_use(tmp_path):
    scratch = tmp_path / "c"
    scratch.mkdir()
    assert ee.env_in_use(scratch, "k") is False
    with ee.env_lock(scratch, "k") as held:
        assert held
        code = (
            f"import sys; sys.path.insert(0, {str(ACCEPT_DIR)!r})\n"
            "from pathlib import Path\n"
            "import execution_env as ee\n"
            f"print(ee.env_in_use(Path({str(scratch)!r}), 'k'))\n"
        )
        out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, check=True).stdout.strip()
        assert out == "True", "a held lock must be visible to another process"


# ------------------------------------------------------------------ pruning

def test_prune_never_removes_an_environment_in_use(warm, cache):
    """WAS BROKEN: prune removed by age and count with no notion of 'in use'."""
    env = warm[0]
    key = env.name[len("env-"):]
    code = (
        f"import sys, time; sys.path.insert(0, {str(ACCEPT_DIR)!r})\n"
        "from pathlib import Path\n"
        "import execution_env as ee\n"
        f"with ee.env_lock(Path({str(cache)!r}), {key!r}):\n"
        "    print('HELD', flush=True)\n"
        "    time.sleep(10)\n"
    )
    holder = _spawn(code, stdout=subprocess.PIPE)
    try:
        assert holder.stdout.readline().strip() == "HELD"
        report = ee.prune_envs(cache, keep_trees=set(), keep=0)
        assert str(env) in report["skipped_in_use"]
        assert env.is_dir(), "an in-use environment was deleted"
    finally:
        holder.kill()
        holder.wait()


# ------------------------------------------------------------ bytecode

def test_stamp_forged_bytecode_cannot_execute(warm, cache):
    """WAS BROKEN, and RECORD alone cannot fix it.

    pip does not hash `.pyc` in RECORD, and CPython's staleness check is a
    source mtime+size stamp, which is forgeable. A `.pyc` compiled from
    MODIFIED source and then stamped with the real `.py`'s mtime and size was
    executed, while RECORD verification reported zero mismatches -- so the
    manifest check could not see it.

    The control below is explicit: the forged bytecode must first be shown to
    execute, otherwise the repair is not being tested at all.
    """
    import py_compile
    import struct
    import tempfile

    env, _, probe = warm[0], warm[1], warm[2]
    py = ee._venv_python(env)
    site = Path(probe["origin"]).parent
    mod = site / "orchestration" / "mission" / "os_lock.py"
    if not mod.is_file():
        pytest.skip("expected module not present in this distribution")

    read = ("from project_atlas.orchestration.mission import os_lock as m;"
            "print(getattr(m, 'TAMPERED_MARKER', None))")

    def plant() -> None:
        subprocess.run([str(py), "-I", "-c",
                        "import project_atlas.orchestration.mission.os_lock"],
                       capture_output=True, env=ee.clean_env(), check=False)
        pyc = next((mod.parent / "__pycache__").glob("os_lock.cpython-*.pyc"))
        st = mod.stat()
        tmp = Path(tempfile.mkdtemp())
        try:
            fake = tmp / "os_lock.py"
            fake.write_text(mod.read_text(encoding="utf-8")
                            + "\nTAMPERED_MARKER = 'pyc-hijack'\n", encoding="utf-8")
            py_compile.compile(str(fake), cfile=str(pyc), dfile=str(mod), doraise=True)
            raw = bytearray(pyc.read_bytes())
            raw[8:12] = struct.pack("<I", int(st.st_mtime) & 0xFFFFFFFF)
            raw[12:16] = struct.pack("<I", st.st_size & 0xFFFFFFFF)
            pyc.write_bytes(bytes(raw))
        finally:
            shutil_rmtree(tmp)

    # Control: the attack must actually work before the repair is meaningful.
    plant()
    hijacked = subprocess.run([str(py), "-I", "-c", read], capture_output=True,
                              text=True, env=ee.clean_env()).stdout
    assert "pyc-hijack" in hijacked, "forged bytecode did not execute; attack not exercised"
    assert ee.manifest_probe(py)["n_mismatched"] == 0, "RECORD unexpectedly saw it"

    # Repair: a normal warm reuse must purge it.
    plant()
    env2, _, _ = ee.provision(REPO_ROOT, "HEAD", cache)
    after = subprocess.run([str(ee._venv_python(env2)), "-I", "-c", read],
                           capture_output=True, text=True, env=ee.clean_env()).stdout
    assert "pyc-hijack" not in after, "forged bytecode survived warm reuse"


def shutil_rmtree(path: Path) -> None:
    import shutil as _sh
    _sh.rmtree(path, ignore_errors=True)


# --------------------------------------------- integrity reference & leases

def test_record_is_pinned_because_record_is_self_referential(warm, cache):
    """WAS BROKEN: RECORD lives inside the environment it describes.

    Editing a file AND rewriting its RECORD line passed verification, and the
    tampered module then executed. The marker now pins RECORD's own digest.

    This detects DRIFT and single-point modification. It is not an adversarial
    boundary -- every artifact in the chain is writable by the caller. The
    authoritative binding to the selected tree is the cold build, which
    `--ephemeral-env` forces on every run.
    """
    import base64
    import hashlib

    env, _, probe = warm[0], warm[1], warm[2]
    site = Path(probe["origin"]).parent
    dist_info = next(site.parent.glob("project_atlas-*.dist-info"))
    record = dist_info / "RECORD"
    target = site / "orchestration" / "mission" / "os_lock.py"
    if not target.is_file():
        pytest.skip("expected module not present")

    original, original_record = target.read_bytes(), record.read_text(encoding="utf-8")
    marker = json.loads((env / ee.MARKER_NAME).read_text(encoding="utf-8"))
    assert marker.get("record_sha256"), "RECORD digest was not recorded at provisioning"
    try:
        tampered = original + b"\nTAMPERED_VIA_RECORD = True\n"
        target.write_bytes(tampered)
        digest = base64.urlsafe_b64encode(
            hashlib.sha256(tampered).digest()).rstrip(b"=").decode()
        rel = "project_atlas/orchestration/mission/os_lock.py"
        record.write_text("\n".join(
            f"{rel},sha256={digest},{len(tampered)}" if ln.startswith(f"{rel},") else ln
            for ln in original_record.splitlines()) + "\n", encoding="utf-8")

        # Control: file hashes now agree with RECORD, so per-file checks pass.
        manifest = ee.manifest_probe(ee._venv_python(env))
        assert manifest["n_mismatched"] == 0, "control failed: RECORD was not made consistent"
        # The pin is what catches it.
        with pytest.raises(ee.ProvenanceError, match="RECORD itself changed"):
            ee.verify_contents(manifest, expect_record_sha256=marker["record_sha256"])

        env2 = ee.provision(REPO_ROOT, "HEAD", cache)[0]
        out = subprocess.run(
            [str(ee._venv_python(env2)), "-I", "-B", "-c",
             "from project_atlas.orchestration.mission import os_lock as m;"
             "print(getattr(m, 'TAMPERED_VIA_RECORD', None))"],
            capture_output=True, text=True, env=ee.clean_env()).stdout
        assert "True" not in out, "tampered module survived warm reuse"
    finally:
        if target.is_file() and b"TAMPERED_VIA_RECORD" in target.read_bytes():
            target.write_bytes(original)
            record.write_text(original_record, encoding="utf-8")


def test_workers_do_not_write_bytecode(warm):
    """`-B` keeps the read side empty after a purge.

    Purging answers "what bytecode exists now"; -B answers "will the run put
    any back". Both are needed: without -B the first import repopulates
    `__pycache__` with files nothing subsequently verifies.
    """
    env, _, probe = warm[0], warm[1], warm[2]
    assert ee.isolated_command(Path("py"), ["-c", "x"])[:3] == ["py", "-I", "-B"]
    ee.purge_bytecode(env)
    subprocess.run(ee.isolated_command(ee._venv_python(env),
                                       ["-c", "import project_atlas.orchestration.mission"]),
                   capture_output=True, env=ee.clean_env(), check=False)
    assert list(Path(probe["origin"]).parent.rglob("*.pyc")) == []


def test_lease_keeps_prune_off_a_running_worker(warm, cache):
    """WAS BROKEN: the build lock is released when `provision` returns.

    With a worker running, `env_in_use` reported False and prune deleted the
    environment out from under it.
    """
    env, _, _ = warm[0], warm[1], warm[2]
    key = env.name[len("env-"):]
    assert ee.env_in_use(cache, key) is False
    with ee.env_lease(cache, key):
        worker = subprocess.Popen(
            ee.isolated_command(ee._venv_python(env),
                                ["-c", "import time, project_atlas;"
                                       "print('RUNNING', flush=True); time.sleep(8)"]),
            stdout=subprocess.PIPE, text=True, env=ee.clean_env(), **ee.spawn_kwargs())
        try:
            assert worker.stdout.readline().strip() == "RUNNING"
            assert ee.env_in_use(cache, key) is True
            report = ee.prune_envs(cache, keep_trees=set(), keep=0)
            assert str(env) in report["skipped_in_use"]
            assert env.is_dir(), "a leased environment was pruned"
        finally:
            ee.hard_kill_tree(worker)
    assert ee.env_in_use(cache, key) is False


def test_stale_lease_files_do_not_pin_an_environment_forever(tmp_path):
    """A killed run leaves an unlocked lease file; it must not read as in-use."""
    cache_dir = tmp_path / "c"
    cache_dir.mkdir()
    stale = cache_dir / f"env-deadbeef{ee.USE_PREFIX}abc123"
    stale.write_text("", encoding="utf-8")
    assert ee.env_in_use(cache_dir, "deadbeef") is False
    report = ee.prune_envs(cache_dir, keep_trees=set(), keep=0)
    assert str(stale) in report.get("stale_leases_removed", [])
    assert not stale.exists()

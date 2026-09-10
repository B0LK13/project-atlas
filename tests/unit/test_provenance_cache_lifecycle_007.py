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
    p = _spawn(code, start_new_session=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    killed = False
    for _ in range(600):
        time.sleep(0.05)
        staged = list(scratch.glob(".staging-*")) if scratch.exists() else []
        if staged and any((d / "env" / "pyvenv.cfg").exists() for d in staged):
            os.killpg(os.getpgid(p.pid), 9)
            p.wait()
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

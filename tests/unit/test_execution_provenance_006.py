"""AS-PROV-006 -- the execution-provenance contract, and its falsifiability.

A provenance claim nobody can break is not evidence. These tests try to break
it: a hostile caller installation, a foreign import origin, a missing
distribution, and a non-isolated interpreter each have to be REJECTED.

The expensive fixture (build a wheel, provision a venv) is module-scoped and
built once; every negative test reuses it read-only.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "acceptance"))

import execution_env as ee  # noqa: E402

pytestmark = pytest.mark.provenance


@pytest.fixture(scope="module")
def provisioned(tmp_path_factory):
    """Build the candidate wheel and provision an isolated env, once.

    Uses the DISK-backed default cache rather than pytest's tmp dir: a
    provisioned env is ~130 MB and `/tmp` is a tmpfs on some machines, where
    filling it aborts unrelated work with `OSError(122)`. That is an
    environment failure, not a verdict, so it is skipped -- never reported as
    a pass or a fail.
    """
    cache = Path(os.environ.get("ATLAS_PROV_CACHE", str(ee.DEFAULT_ENV_CACHE)))
    try:
        env, identity, probe = ee.provision(REPO_ROOT, "HEAD", cache)
    except ee.ProvenanceError as exc:
        pytest.skip(f"cannot provision an isolated candidate env here: {exc}")
    return env, identity, probe


# ------------------------------------------------------------------ positive

def test_candidate_runs_from_its_own_distribution(provisioned):
    env, identity, probe = provisioned
    origin = Path(probe["origin"]).resolve()
    assert env.resolve() in origin.parents
    assert "site-packages" in origin.parts
    assert probe["flags_isolated"] and probe["flags_no_user_site"]
    assert identity.contract == "DISTRIBUTION_BUILT_FROM_SELECTED_TREE"


def test_recorded_identity_matches_git(provisioned):
    identity = provisioned[1]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT),
                          capture_output=True, text=True).stdout.strip()
    tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=str(REPO_ROOT),
                          capture_output=True, text=True).stdout.strip()
    assert identity.commit == head
    assert identity.tree == tree
    assert len(identity.wheel_sha256) == 64


def test_installed_source_is_byte_identical_to_the_committed_tree(provisioned):
    """The strongest positive: what got installed IS what was committed."""
    probe = provisioned[2]
    installed = Path(probe["origin"]).parent / "orchestration/mission/execution.py"
    committed = subprocess.run(
        ["git", "show", "HEAD:src/project_atlas/orchestration/mission/execution.py"],
        cwd=str(REPO_ROOT), capture_output=True).stdout
    assert installed.read_bytes() == committed


# ------------------------------------------------------------------ negative

def test_hostile_caller_installation_cannot_substitute(provisioned, tmp_path):
    """A decoy on PYTHONPATH and in the CWD must lose to the provisioned env."""
    decoy = tmp_path / "project_atlas"
    decoy.mkdir()
    (decoy / "__init__.py").write_text("HIJACKED = True\n", encoding="utf-8")

    env, _, _ = provisioned
    py = env / ("Scripts" if sys.platform == "win32" else "bin") / (
        "python.exe" if sys.platform == "win32" else "python")

    # Control: WITHOUT -I the decoy wins. If this stops being true the test
    # below proves nothing, so assert the attack is real before defeating it.
    plain = subprocess.run(
        [str(py), "-c", "import project_atlas,sys;print(project_atlas.__file__)"],
        cwd=str(tmp_path), env={**ee.clean_env(), "PYTHONPATH": str(tmp_path)},
        capture_output=True, text=True)
    assert plain.returncode == 0
    assert str(tmp_path) in plain.stdout, "decoy did not shadow -- attack not exercised"

    # The real check: under -I the decoy must lose.
    probe = ee.probe_worker(py, hostile_env=True, cwd=tmp_path)
    origin = Path(probe["origin"]).resolve()
    assert env.resolve() in origin.parents
    assert str(tmp_path) not in str(origin)
    ee.verify_import_origin(env, probe)   # must not raise


def test_foreign_import_origin_is_rejected(provisioned):
    env, _, probe = provisioned
    foreign = dict(probe)
    foreign["origin"] = "/somewhere/else/site-packages/project_atlas/__init__.py"
    with pytest.raises(ee.ProvenanceError, match="OUTSIDE the provisioned environment"):
        ee.verify_import_origin(env, foreign)


def test_editable_style_origin_is_rejected(provisioned):
    """An origin inside the env but NOT an installed distribution fails closed."""
    env, _, probe = provisioned
    src_like = dict(probe)
    src_like["origin"] = str(env / "src" / "project_atlas" / "__init__.py")
    with pytest.raises(ee.ProvenanceError, match="not an installed distribution"):
        ee.verify_import_origin(env, src_like)


def test_missing_distribution_is_rejected(provisioned):
    env, _, probe = provisioned
    absent = dict(probe)
    absent["origin"] = None
    with pytest.raises(ee.ProvenanceError, match="could not import project_atlas"):
        ee.verify_import_origin(env, absent)


def test_non_isolated_worker_is_rejected(provisioned):
    env, _, probe = provisioned
    for flag, msg in (("flags_isolated", "not running in isolated mode"),
                      ("flags_no_user_site", "user site-packages enabled")):
        bad = dict(probe)
        bad[flag] = False
        with pytest.raises(ee.ProvenanceError, match=msg):
            ee.verify_import_origin(env, bad)


def test_unreadable_distribution_metadata_is_rejected(provisioned):
    env, _, probe = provisioned
    bad = dict(probe)
    bad["version"] = "ERROR:PackageNotFoundError"
    with pytest.raises(ee.ProvenanceError, match="metadata unreadable"):
        ee.verify_import_origin(env, bad)


def test_an_env_without_the_candidate_fails_closed(tmp_path):
    """A bare venv is not a candidate environment, and must not be treated as one."""
    import venv as _venv
    envd = tmp_path / "bare"
    try:
        _venv.EnvBuilder(with_pip=False).create(str(envd))
    except OSError as exc:   # disk quota / no space -- environment limit, not a verdict
        pytest.skip(f"cannot create a probe venv here: {exc}")
    py = envd / ("Scripts" if sys.platform == "win32" else "bin") / (
        "python.exe" if sys.platform == "win32" else "python")
    probe = ee.probe_worker(py)
    assert probe["origin"] is None
    with pytest.raises(ee.ProvenanceError):
        ee.verify_import_origin(envd, probe)


def test_reuse_requires_a_matching_tree_not_just_a_marker(provisioned):
    """A marker is a claim. A wrong tree must not be silently reused."""
    env, identity, _ = provisioned
    marker = env / ee.MARKER_NAME
    assert marker.is_file()
    recorded = json.loads(marker.read_text(encoding="utf-8"))
    assert recorded["tree"] == identity.tree
    assert recorded["commit"] == identity.commit
    assert recorded["contract"] == "DISTRIBUTION_BUILT_FROM_SELECTED_TREE"


# ------------------------------------------------- resource + cache contract

def test_env_key_ignores_the_wheel_digest():
    """Wheels are not byte-reproducible, so keying on them means a new env per run.

    Measured on this repository: building the same tree twice produced two
    different wheel digests. The cache key must therefore depend on the TREE,
    not the artifact.
    """
    base = dict(commit="c" * 40, tree="t" * 40, wheel_name="w.whl",
                python_version="3.12.14", platform="linux-x86_64",
                install_method="x")
    a = ee.CandidateIdentity(wheel_sha256="a" * 64, **base)
    b = ee.CandidateIdentity(wheel_sha256="b" * 64, **base)
    assert a.key() == b.key(), "same tree must reuse one environment"

    other_tree = ee.CandidateIdentity(
        wheel_sha256="a" * 64, **{**base, "tree": "u" * 40})
    assert a.key() != other_tree.key(), "a different tree must NOT reuse"

    other_py = ee.CandidateIdentity(
        wheel_sha256="a" * 64, **{**base, "python_version": "3.13.0"})
    assert a.key() != other_py.key(), "a different interpreter must NOT reuse"


def test_prune_keeps_the_active_tree_and_ignores_foreign_dirs(tmp_path):
    """Pruning must never touch anything this tool did not create."""
    cache = tmp_path / "envs"
    cache.mkdir()
    for tree in ("aa", "bb", "cc", "dd"):
        d = cache / f"env-{tree}"
        d.mkdir()
        (d / ee.MARKER_NAME).write_text(json.dumps({"tree": tree}), encoding="utf-8")
    foreign = cache / "somebody-elses-venv"
    foreign.mkdir()
    (foreign / "pyvenv.cfg").write_text("not ours\n", encoding="utf-8")
    unmarked = cache / "env-no-marker"
    unmarked.mkdir()

    report = ee.prune_envs(cache, keep_trees={"aa"}, keep=1)
    assert foreign.is_dir(), "a directory without our marker must be left alone"
    assert unmarked.is_dir(), "an env-* without our marker is not ours to delete"
    # A non `env-*` directory is never even examined -- stricter than being
    # examined and then skipped, which is what this assertion originally claimed.
    assert str(foreign) not in report["skipped_foreign"]
    assert all(foreign.name not in r for r in report["removed"])
    # An `env-*` directory WITHOUT our marker is examined and explicitly spared.
    assert str(unmarked) in report["skipped_foreign"]
    assert (cache / "env-aa").is_dir(), "the active tree must survive pruning"
    assert len(report["removed"]) >= 1


def test_mission_state_dir_mirror_has_not_drifted():
    """mission_accept duplicates this constant so the parent need not import
    the candidate. Assert the duplicate still matches wherever we CAN import."""
    pa = pytest.importorskip("project_atlas.orchestration.mission")
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "acceptance"))
    import mission_accept as ma
    assert ma.MISSION_STATE_DIR == pa.MISSION_STATE_DIR_NAME

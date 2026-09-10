"""AS-PROV-006 -- prove the SELECTED checkout's implementation actually ran.

THE CONTRACT THIS MODULE PROVES

    Execution of a DISTRIBUTION BUILT FROM the selected commit's tree.

Not "direct execution from the source checkout". The distinction matters and
is deliberate. A source checkout can be shadowed in at least three ways that
are invisible from the parent process, so proving "the checkout's code ran"
by pointing at a directory is not proof at all:

    1. an editable install in the caller's environment,
    2. `PYTHONPATH` / the working directory,
    3. the user site-packages directory.

Measured, not assumed: with a hijacking `project_atlas.py` sitting in the
working directory AND on `PYTHONPATH`, a plain `python -c "import
project_atlas"` imported the HIJACK. Under `python -I` the hijack lost -- but
the import still resolved to the caller's EDITABLE INSTALL, because `-I` does
nothing about the venv's own site-packages. Isolation therefore needs both:

    * a venv whose site-packages contains ONLY a wheel built from the
      selected tree (never an editable install of anything), and
    * `-I` on every worker invocation, which implies `-E` (ignore PYTHON*
      env vars) and `-s` (no user site).

HOW THE TREE IS SELECTED

`git archive <commit>` into a scratch directory, so the build input is the
COMMIT's tree, not a dirty working directory. The resulting wheel is recorded
with the commit, the tree hash, and the wheel's own sha256.

FAIL CLOSED

Every step that cannot establish identity raises `ProvenanceError`. There is
no fallback to the caller's interpreter or environment -- a run either proves
its execution identity or does not happen.

ENVIRONMENT REUSE

Provisioning a venv per run would be an unbounded installation loop. An
environment is reused ONLY when its recorded identity marker matches the
requested tree hash AND a live probe re-verifies the import origin inside the
interpreter. A marker alone is never trusted.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import venv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MARKER_NAME = "atlas-candidate-identity.json"

#: Default home for provisioned candidate environments.
#:
#: Deliberately NOT under the run's temporary directory. A provisioned env is
#: roughly 130 MB, and on this class of machine `/tmp` is a tmpfs -- filling it
#: aborts unrelated work with `OSError(122, 'Disk quota exceeded')`, which is an
#: environment failure that looks nothing like a test result. A persistent,
#: disk-backed cache also makes reuse actually pay off across runs.
#: `--ephemeral-env` opts back into a run-scoped, always-removed cache.
DEFAULT_ENV_CACHE = Path.home() / ".cache" / "atlas-acceptance" / "envs"
DIST_NAME = "project_atlas"
PROJECT_NAME = "project-atlas"


class ProvenanceError(Exception):
    """Execution identity could not be established. Never fall back."""


@dataclass(frozen=True)
class CandidateIdentity:
    """Everything needed to say WHICH implementation ran."""

    commit: str
    tree: str
    wheel_name: str
    wheel_sha256: str
    python_version: str
    platform: str
    install_method: str
    contract: str = "DISTRIBUTION_BUILT_FROM_SELECTED_TREE"

    def key(self) -> str:
        """Environment cache key.

        Deliberately does NOT include `wheel_sha256`. Wheels embed file
        timestamps and are not byte-reproducible: building the SAME tree twice
        produced two different digests here (measured -- 4596e393... then
        a82195608..., same tree 5d3111a5). Keying on the wheel would therefore
        provision a fresh ~130 MB environment on every single run, which is the
        unbounded installation loop this cache exists to avoid.

        The tree hash is the honest identity of "which source"; the interpreter
        version and platform decide whether an installed artifact is usable.
        `wheel_sha256` is still RECORDED as evidence of the artifact that was
        actually installed -- it just is not an identity for reuse.
        """
        return hashlib.sha256(
            f"{self.tree}\x00{self.python_version}\x00{self.platform}".encode()
        ).hexdigest()[:16]


def _run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None,
         what: str = "") -> subprocess.CompletedProcess[str]:
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env,
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise ProvenanceError(
            f"{what or ' '.join(cmd[:3])} failed (rc={p.returncode})\n"
            f"stdout: {p.stdout[-1500:]}\nstderr: {p.stderr[-1500:]}"
        )
    return p


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------- build

def build_candidate_wheel(repo_root: Path, commit: str, out_dir: Path) -> tuple[Path, str, str]:
    """Build a wheel from `commit`'s TREE. Returns (wheel, commit_sha, tree_sha).

    `git archive` is used so the build input is the committed tree -- a dirty
    working directory cannot leak into the artifact.
    """
    commit_sha = _run(["git", "rev-parse", commit], repo_root, what="rev-parse").stdout.strip()
    tree_sha = _run(["git", "rev-parse", f"{commit_sha}^{{tree}}"], repo_root,
                    what="rev-parse tree").stdout.strip()

    src = out_dir / "src-export"
    src.mkdir(parents=True, exist_ok=True)
    tar = out_dir / "tree.tar"
    _run(["git", "archive", "--format=tar", "-o", str(tar), commit_sha], repo_root,
         what="git archive")
    _run(["tar", "-xf", str(tar), "-C", str(src)], what="tar -x")
    tar.unlink(missing_ok=True)

    wheel_dir = out_dir / "wheel"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    # --no-deps: we are packaging THIS project, not resolving the world.
    # Build isolation is left ON deliberately: this repository declares
    # `setuptools>=68` as a build requirement and modern venvs no longer ship
    # setuptools, so `--no-build-isolation` would depend on whatever happens to
    # be installed in the caller's interpreter -- exactly the ambient coupling
    # this module exists to eliminate. pip provisions the declared backend into
    # its own throwaway env instead, and caches it across runs.
    try:
        _run([sys.executable, "-m", "pip", "wheel", "--no-deps",
              "-w", str(wheel_dir), str(src)], what="pip wheel")
    except ProvenanceError as exc:
        raise ProvenanceError(
            f"could not build a wheel from {commit_sha[:12]}. The build backend "
            f"(setuptools>=68, per pyproject.toml) must be installable -- this step "
            f"needs either network access or a populated pip cache. Failing closed "
            f"rather than executing the caller's environment.\n\n{exc}"
        ) from exc

    wheels = sorted(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise ProvenanceError(f"expected exactly one wheel, got {[w.name for w in wheels]}")
    return wheels[0], commit_sha, tree_sha


# --------------------------------------------------------------- provision

def _venv_python(env_dir: Path) -> Path:
    p = env_dir / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python")
    if not p.exists():
        raise ProvenanceError(f"interpreter missing in provisioned env: {p}")
    return p


#: Probe run INSIDE the worker interpreter. The parent's view proves nothing.
_PROBE = (
    "import json,sys,site\n"
    "import importlib.util as u\n"
    "spec = u.find_spec('project_atlas')\n"
    "origin = spec.origin if spec else None\n"
    "import importlib.metadata as md\n"
    "try:\n"
    "    ver = md.version('project-atlas')\n"
    "except Exception as e:\n"
    "    ver = 'ERROR:' + type(e).__name__\n"
    "try:\n"
    "    files = [str(f) for f in (md.files('project-atlas') or [])][:1]\n"
    "except Exception:\n"
    "    files = []\n"
    "print(json.dumps({'executable': sys.executable, 'prefix': sys.prefix,\n"
    "  'base_prefix': sys.base_prefix, 'origin': origin, 'version': ver,\n"
    "  'first_dist_file': files, 'path': sys.path,\n"
    "  'flags_isolated': bool(sys.flags.isolated),\n"
    "  'flags_no_user_site': bool(sys.flags.no_user_site),\n"
    "  'user_site_enabled': site.ENABLE_USER_SITE}))\n"
)


def probe_worker(python: Path, *, hostile_env: bool = False,
                 cwd: Path | None = None) -> dict[str, Any]:
    """Ask the WORKER interpreter where its project_atlas comes from.

    `hostile_env=True` deliberately sets PYTHONPATH and runs from a directory
    containing a decoy, to prove `-I` actually holds.
    """
    env = dict(os.environ)
    env.pop("PYTHONHOME", None)
    if hostile_env and cwd is not None:
        env["PYTHONPATH"] = str(cwd)
    else:
        env.pop("PYTHONPATH", None)
    p = subprocess.run([str(python), "-I", "-c", _PROBE], capture_output=True,
                       text=True, env=env, cwd=str(cwd) if cwd else None)
    if p.returncode != 0:
        raise ProvenanceError(f"worker probe failed: {p.stderr[-1200:]}")
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise ProvenanceError(
            f"worker probe emitted unparseable output: {p.stdout[-600:]}"
        ) from exc


def verify_import_origin(env_dir: Path, probe: dict[str, Any]) -> None:
    """Fail closed unless the worker imported from THIS env's site-packages."""
    origin = probe.get("origin")
    if not origin:
        raise ProvenanceError("worker could not import project_atlas at all")
    origin_p = Path(origin).resolve()
    env_r = env_dir.resolve()
    if env_r not in origin_p.parents:
        raise ProvenanceError(
            f"worker imported project_atlas from {origin_p}, which is OUTSIDE the "
            f"provisioned environment {env_r} -- refusing to attribute this run"
        )
    if "site-packages" not in origin_p.parts:
        raise ProvenanceError(
            f"worker import origin {origin_p} is not an installed distribution "
            f"(no site-packages component) -- an editable/source path cannot "
            f"prove the distribution executed"
        )
    if not probe.get("flags_isolated"):
        raise ProvenanceError("worker was not running in isolated mode (-I)")
    if not probe.get("flags_no_user_site"):
        raise ProvenanceError("worker had user site-packages enabled")
    if str(probe.get("version", "")).startswith("ERROR:"):
        raise ProvenanceError(f"distribution metadata unreadable: {probe['version']}")


def _identity_for(repo_root: Path, commit: str, *, wheel_name: str, wheel_sha256: str,
                  commit_sha: str, tree_sha: str) -> CandidateIdentity:
    return CandidateIdentity(
        commit=commit_sha, tree=tree_sha, wheel_name=wheel_name,
        wheel_sha256=wheel_sha256,
        python_version=".".join(map(str, sys.version_info[:3])),
        platform=sysconfig.get_platform(),
        install_method="pip install --no-deps <wheel> into a fresh venv",
    )


def provision(repo_root: Path, commit: str, cache_root: Path,
              *, reuse: bool = True) -> tuple[Path, CandidateIdentity, dict[str, Any]]:
    """Build the candidate wheel and install it into an isolated environment.

    Returns (env_dir, identity, worker_probe). Raises `ProvenanceError` rather
    than returning an environment whose identity cannot be established.

    The reuse check happens BEFORE the wheel is built: the tree hash comes from
    git, so a cache hit costs one `git rev-parse` plus a live probe instead of a
    full rebuild. Building first would burn several seconds on every run to
    produce an artifact that is then thrown away.
    """
    cache_root.mkdir(parents=True, exist_ok=True)
    commit_sha = _run(["git", "rev-parse", commit], repo_root, what="rev-parse").stdout.strip()
    tree_sha = _run(["git", "rev-parse", f"{commit_sha}^{{tree}}"], repo_root,
                    what="rev-parse tree").stdout.strip()
    probe_identity = _identity_for(repo_root, commit, wheel_name="", wheel_sha256="",
                                   commit_sha=commit_sha, tree_sha=tree_sha)
    env_dir = cache_root / f"env-{probe_identity.key()}"
    marker = env_dir / MARKER_NAME

    if reuse and marker.is_file():
        try:
            recorded = json.loads(marker.read_text(encoding="utf-8"))
        except ValueError:
            recorded = {}
        if recorded.get("tree") == tree_sha:
            # A marker is a CLAIM. Re-probe the live interpreter before trusting it.
            probe = probe_worker(_venv_python(env_dir))
            verify_import_origin(env_dir, probe)
            return env_dir, CandidateIdentity(**recorded), probe
        shutil.rmtree(env_dir, ignore_errors=True)

    build_dir = Path(tempfile.mkdtemp(prefix="atlas-prov-build-", dir=str(cache_root)))
    try:
        wheel, commit_sha, tree_sha = build_candidate_wheel(repo_root, commit, build_dir)
        identity = _identity_for(repo_root, commit, wheel_name=wheel.name,
                                 wheel_sha256=_sha256(wheel),
                                 commit_sha=commit_sha, tree_sha=tree_sha)
        if env_dir.exists():
            shutil.rmtree(env_dir, ignore_errors=True)
        venv.EnvBuilder(with_pip=True, clear=True).create(str(env_dir))
        py = _venv_python(env_dir)
        # Runtime deps come from the wheel's own metadata; --no-deps would leave
        # pydantic/PyYAML/jsonschema missing. The CANDIDATE distribution itself is
        # still installed from the wheel we just built, never from a source path.
        _run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q",
              str(wheel)], what="pip install candidate wheel")

        probe = probe_worker(py)
        verify_import_origin(env_dir, probe)
        marker.write_text(json.dumps(asdict(identity), indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
        return env_dir, identity, probe
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)


def isolated_command(python: Path, args: list[str]) -> list[str]:
    """Every worker invocation goes through `-I`."""
    return [str(python), "-I", *args]


def clean_env() -> dict[str, str]:
    """Environment for a worker: no PYTHONPATH, no PYTHONHOME."""
    env = dict(os.environ)
    for var in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
        env.pop(var, None)
    return env


def prune_envs(cache_root: Path, keep_trees: set[str], *, keep: int = 2) -> dict[str, Any]:
    """Bound the cache. A provisioned env costs roughly 130 MB, so leaving one
    per tree behind is an unbounded installation loop by another name.

    Removes only directories this module created (`env-*` carrying our marker)
    inside `cache_root`. Never touches anything else, and never removes an env
    whose tree is in `keep_trees`.
    """
    report: dict[str, Any] = {"removed": [], "kept": [], "skipped_foreign": []}
    if not cache_root.is_dir():
        return report
    candidates: list[tuple[float, Path, str]] = []
    for child in cache_root.iterdir():
        if not child.is_dir() or not child.name.startswith("env-"):
            continue
        marker = child / MARKER_NAME
        if not marker.is_file():
            report["skipped_foreign"].append(str(child))
            continue
        try:
            tree = json.loads(marker.read_text(encoding="utf-8")).get("tree", "")
        except ValueError:
            tree = ""
        candidates.append((marker.stat().st_mtime, child, tree))
    candidates.sort(reverse=True)
    kept = 0
    for _mtime, path, tree in candidates:
        if tree in keep_trees or kept < keep:
            report["kept"].append(str(path))
            kept += 1
            continue
        shutil.rmtree(path, ignore_errors=True)
        report["removed"].append(str(path))
    return report

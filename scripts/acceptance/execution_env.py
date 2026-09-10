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

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import time
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



# ------------------------------------------------------------------- lock

#: Suffix for the per-environment lock file, kept BESIDE the env directory so
#: the directory itself can be renamed into place atomically.
LOCK_SUFFIX = ".lock"


@contextlib.contextmanager
def env_lock(cache_root: Path, key: str, *, timeout: float = 300.0,
             blocking: bool = True):
    """Kernel-arbitrated exclusive lock for one cache key.

    Deliberately a local implementation rather than an import of
    `project_atlas.orchestration.mission.os_lock`, which follows the same
    `fcntl.flock` / `msvcrt.locking` pattern: this module's entire job is to
    provision the candidate, so it cannot depend on the candidate being
    importable to do it. The duplication is the price of breaking that cycle,
    and is noted here rather than left for a reader to rediscover.

    Yields True when held. With `blocking=False`, yields False immediately if
    another process holds it -- which is how pruning asks "is this in use?"
    without waiting.
    """
    cache_root.mkdir(parents=True, exist_ok=True)
    lock_path = cache_root / f"env-{key}{LOCK_SUFFIX}"
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    acquired = False
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if not blocking:
                    break
                if time.monotonic() >= deadline:
                    raise ProvenanceError(
                        f"timed out after {timeout}s waiting for the environment lock "
                        f"{lock_path}; another provisioning run appears stuck"
                    ) from None
                time.sleep(0.1)
        yield acquired
    finally:
        if acquired:
            with contextlib.suppress(OSError):
                if os.name == "nt":
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def env_in_use(cache_root: Path, key: str) -> bool:
    """True when another process currently holds this environment's lock."""
    with env_lock(cache_root, key, blocking=False) as got:
        return not got


# -------------------------------------------------------------- integrity

#: Probe that reports the INSTALLED distribution's own manifest and the full
#: dependency set, from inside the worker interpreter.
_MANIFEST_PROBE = (
    "import base64, hashlib, json, sys\n"
    "import importlib.metadata as md\n"
    "from pathlib import Path\n"
    "dist = md.distribution('project-atlas')\n"
    "base = Path(dist.locate_file(''))\n"
    "record = dist.read_text('RECORD') or ''\n"
    "bad, checked, missing = [], 0, []\n"
    "for line in record.splitlines():\n"
    "    parts = line.rsplit(',', 2)\n"
    "    if len(parts) != 3:\n"
    "        continue\n"
    "    rel, digest, _size = parts\n"
    "    if not digest.startswith('sha256='):\n"
    "        continue\n"
    "    if rel.endswith('.pyc') or rel.startswith('../'):\n"
    "        continue\n"
    "    f = base / rel\n"
    "    if not f.is_file():\n"
    "        missing.append(rel)\n"
    "        continue\n"
    "    h = hashlib.sha256(f.read_bytes()).digest()\n"
    "    want = digest.split('=', 1)[1]\n"
    "    got = base64.urlsafe_b64encode(h).rstrip(b'=').decode()\n"
    "    checked += 1\n"
    "    if got != want:\n"
    "        bad.append(rel)\n"
    "deps = {d.metadata['Name']: d.version for d in md.distributions()\n"
    "        if d.metadata['Name']}\n"
    "print(json.dumps({'checked': checked, 'mismatched': sorted(bad)[:20],\n"
    "  'missing': sorted(missing)[:20], 'n_mismatched': len(bad),\n"
    "  'n_missing': len(missing), 'dependencies': deps}))\n"
)


def manifest_probe(python: Path) -> dict[str, Any]:
    """Verify installed files against pip's own RECORD, inside the worker."""
    p = subprocess.run([str(python), "-I", "-c", _MANIFEST_PROBE],
                       capture_output=True, text=True, env=clean_env())
    if p.returncode != 0:
        raise ProvenanceError(f"manifest probe failed: {p.stderr[-1200:]}")
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise ProvenanceError(
            f"manifest probe emitted unparseable output: {p.stdout[-600:]}"
        ) from exc


def purge_bytecode(env_dir: Path) -> int:
    """Delete cached bytecode inside the provisioned environment.

    NECESSARY, not tidiness. pip's RECORD carries a sha256 for source files but
    NOT for `.pyc` (413 of 971 entries here have no digest), so hashing RECORD
    cannot see tampered bytecode. And CPython's staleness check is a source
    mtime+size stamp, which is forgeable: a `.pyc` rebuilt from modified source
    and then stamped with the real `.py`'s mtime and size WAS EXECUTED in a
    direct test, while RECORD verification reported zero mismatches.

    Removing `__pycache__` closes that gap at every verification point: the
    interpreter must then compile from the `.py` files that WERE hash-verified.
    Bytecode written afterwards is derived from those verified sources, and is
    purged again at the next warm reuse.
    """
    removed = 0
    for cache_dir in env_dir.rglob("__pycache__"):
        if cache_dir.is_dir():
            shutil.rmtree(cache_dir, ignore_errors=True)
            removed += 1
    return removed


def verify_contents(manifest: dict[str, Any],
                    *, expect_deps: dict[str, str] | None = None) -> None:
    """Fail closed when a cached environment's contents have drifted.

    A cache key says WHICH source was requested. It says nothing about whether
    the installed bytes are still what was installed -- an environment can be
    edited after provisioning and a key cannot notice. pip already records a
    sha256 per installed file in RECORD, so that existing artifact IS the
    manifest; inventing a parallel one would add a second thing to keep true.
    """
    if manifest.get("checked", 0) <= 0:
        raise ProvenanceError("distribution RECORD produced no verifiable entries")
    if manifest.get("n_mismatched"):
        raise ProvenanceError(
            f"{manifest['n_mismatched']} installed file(s) differ from the "
            f"distribution RECORD: {manifest['mismatched']} -- the cached "
            f"environment was modified after it was provisioned"
        )
    if manifest.get("n_missing"):
        raise ProvenanceError(
            f"{manifest['n_missing']} file(s) named by RECORD are missing: "
            f"{manifest['missing']} -- the cached environment is incomplete"
        )
    if expect_deps is not None:
        now = manifest.get("dependencies") or {}
        drifted = {name: (was, now.get(name)) for name, was in expect_deps.items()
                   if now.get(name) != was}
        if drifted:
            raise ProvenanceError(
                f"dependency versions changed since provisioning: {drifted} -- "
                f"an unchanged source tree does not imply an unchanged environment"
            )



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
    tar_path = out_dir / "tree.tar"
    _run(["git", "archive", "--format=tar", "-o", str(tar_path), commit_sha], repo_root,
         what="git archive")
    # Extracted with the stdlib rather than by shelling out to `tar`: this runs
    # on Windows CI too, and `tar` is not something to assume there. `data`
    # filter refuses absolute paths, `..` traversal, links and device nodes --
    # the archive is our own `git archive` output, but an extractor that trusts
    # its input is a bad habit to leave in a provenance tool.
    with tarfile.open(tar_path) as tf:
        tf.extractall(src, filter="data")
    tar_path.unlink(missing_ok=True)

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


def _publish_atomically(staged: Path, final: Path) -> None:
    """Move a fully built environment into place in one filesystem operation.

    A venv survives being renamed -- `sys.prefix` follows the directory and the
    interpreter is a symlink to the base Python -- verified before relying on
    it. So the environment is built under a staging name and renamed only once
    it is complete and verified: a partially built environment never appears at
    the published path, even if the builder is killed mid-install.

    The caller must hold this key's lock; the existence check and the rename
    are only safe together under it.
    """
    if final.exists():
        shutil.rmtree(final, ignore_errors=True)
    try:
        os.replace(str(staged), str(final))
    except OSError as exc:
        raise ProvenanceError(
            f"could not publish the provisioned environment to {final}: {exc}"
        ) from exc


def _reuse_if_valid(env_dir: Path, tree_sha: str) -> tuple[CandidateIdentity, dict, dict] | None:
    """Return a warm environment only if it still proves itself.

    Four things are checked, and a failure of any one is a cache MISS rather
    than an error: the marker parses and names this tree; the interpreter still
    imports the distribution from inside this environment; every file pip
    recorded still hashes to what pip recorded; and the dependency versions are
    the ones present at provisioning time.
    """
    marker = env_dir / MARKER_NAME
    if not marker.is_file():
        return None
    try:
        recorded = json.loads(marker.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if recorded.get("tree") != tree_sha:
        return None
    deps = recorded.pop("dependencies", None)
    try:
        identity = CandidateIdentity(**recorded)
    except TypeError:
        return None
    try:
        py = _venv_python(env_dir)
        # Purge BEFORE probing: unverified bytecode must not be what answers.
        purge_bytecode(env_dir)
        probe = probe_worker(py)
        verify_import_origin(env_dir, probe)
        manifest = manifest_probe(py)
        verify_contents(manifest, expect_deps=deps)
        purge_bytecode(env_dir)
    except ProvenanceError:
        return None
    return identity, probe, manifest


def provision(repo_root: Path, commit: str, cache_root: Path,
              *, reuse: bool = True) -> tuple[Path, CandidateIdentity, dict[str, Any]]:
    """Build the candidate wheel and install it into an isolated environment.

    Returns (env_dir, identity, worker_probe). Raises `ProvenanceError` rather
    than returning an environment whose identity cannot be established.

    Serialised per cache key by a kernel lock: three concurrent callers used to
    race inside one venv directory and two of them died in `ensurepip` with a
    raw `CalledProcessError`. Now one builds and the others wait, then reuse.

    The reuse check runs BEFORE the wheel is built -- the tree hash comes from
    git -- so a warm hit costs a probe rather than a rebuild. But a warm hit is
    only accepted after the environment re-proves itself; see `_reuse_if_valid`.
    """
    cache_root.mkdir(parents=True, exist_ok=True)
    commit_sha = _run(["git", "rev-parse", commit], repo_root, what="rev-parse").stdout.strip()
    tree_sha = _run(["git", "rev-parse", f"{commit_sha}^{{tree}}"], repo_root,
                    what="rev-parse tree").stdout.strip()
    key = _identity_for(repo_root, commit, wheel_name="", wheel_sha256="",
                        commit_sha=commit_sha, tree_sha=tree_sha).key()
    env_dir = cache_root / f"env-{key}"

    with env_lock(cache_root, key):
        if reuse:
            warm = _reuse_if_valid(env_dir, tree_sha)
            if warm is not None:
                identity, probe, manifest = warm
                probe["manifest"] = manifest
                return env_dir, identity, probe

        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=str(cache_root)))
        build_dir = staging / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        staged_env = staging / "env"
        try:
            wheel, commit_sha, tree_sha = build_candidate_wheel(repo_root, commit, build_dir)
            identity = _identity_for(repo_root, commit, wheel_name=wheel.name,
                                     wheel_sha256=_sha256(wheel),
                                     commit_sha=commit_sha, tree_sha=tree_sha)
            try:
                venv.EnvBuilder(with_pip=True, clear=True).create(str(staged_env))
            except Exception as exc:
                raise ProvenanceError(
                    f"could not create the isolated environment: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
            py = _venv_python(staged_env)
            # Runtime deps come from the wheel's own metadata; --no-deps would
            # leave pydantic/PyYAML/jsonschema missing. The CANDIDATE itself is
            # still installed from the wheel just built, never from a source path.
            _run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q",
                  str(wheel)], what="pip install candidate wheel")

            probe = probe_worker(py)
            verify_import_origin(staged_env, probe)
            manifest = manifest_probe(py)
            verify_contents(manifest)
            purge_bytecode(staged_env)

            payload = asdict(identity)
            payload["dependencies"] = manifest.get("dependencies", {})
            (staged_env / MARKER_NAME).write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            _publish_atomically(staged_env, env_dir)
            probe = probe_worker(_venv_python(env_dir))
            verify_import_origin(env_dir, probe)
            probe["manifest"] = manifest
            return env_dir, identity, probe
        finally:
            shutil.rmtree(staging, ignore_errors=True)


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
    """Bound the cache without ever removing something in use.

    A provisioned env costs roughly 130 MB, so leaving one per tree behind is an
    unbounded installation loop by another name. But pruning is destructive, so
    it only ever touches things this module created AND can prove nobody holds:

    * `env-*` directories carrying our marker -- anything else is left alone,
      and a directory that is not even named `env-*` is never examined;
    * whose lock can be acquired non-blocking, i.e. no live run owns it;
    * that are not the tree the caller just provisioned.

    Also sweeps `.staging-*` leftovers, which an interrupted or SIGKILLed
    provision leaves behind and which nothing else would ever clean up.
    """
    report: dict[str, Any] = {"removed": [], "kept": [], "skipped_foreign": [],
                              "skipped_in_use": [], "staging_removed": []}
    if not cache_root.is_dir():
        return report

    for staging in cache_root.glob(".staging-*"):
        if staging.is_dir():
            shutil.rmtree(staging, ignore_errors=True)
            report["staging_removed"].append(str(staging))

    candidates: list[tuple[float, Path, str, str]] = []
    for child in cache_root.iterdir():
        if not child.is_dir() or not child.name.startswith("env-"):
            continue
        marker = child / MARKER_NAME
        if not marker.is_file():
            # NOT reclaimed. Since environments are published atomically, an
            # interrupted provision leaves a `.staging-*` directory (swept
            # above) and never a markerless `env-*` at the published path. So a
            # markerless `env-*` is something this module did not produce, and
            # deleting it would be a guess about someone else's directory.
            report["skipped_foreign"].append(str(child))
            continue
        try:
            tree = json.loads(marker.read_text(encoding="utf-8")).get("tree", "")
        except (ValueError, OSError):
            tree = ""
        candidates.append((marker.stat().st_mtime, child, tree, child.name[len("env-"):]))

    candidates.sort(reverse=True)
    kept = 0
    for _mtime, path, tree, key in candidates:
        if tree in keep_trees or kept < keep:
            report["kept"].append(str(path))
            kept += 1
            continue
        if env_in_use(cache_root, key):
            report["skipped_in_use"].append(str(path))
            report["kept"].append(str(path))
            continue
        shutil.rmtree(path, ignore_errors=True)
        with contextlib.suppress(OSError):
            (cache_root / f"env-{key}{LOCK_SUFFIX}").unlink()
        report["removed"].append(str(path))
    return report

"""Import boundary for sibling control-plane APIs that remain in-tree.

``bootstrap``, ``preflight``, and ``event_client`` stay in
``atlas-vault-documentation/agent_control``. This module makes those exact
implementations callable from the installed Core package without copying them.

Receipt validate/issue are not loaded from here; they live in
``project_atlas.agent_control.receipt_gate``.

Production MDA resolution never discovers repository test fixtures and
never consults test-provider state.
PRODUCTION_PREPARE_USES_TEST_INJECTION = NO
PRODUCTION_LIFECYCLE_CAN_OBSERVE_TEST_INJECTION = NO
TEST_MDA_FIXTURE_AUTO_SELECTED_IN_PRODUCTION = NO
MOCK_MDA_VERSION_ACCEPTED = NO
PIPELINE_PROVIDER_ENVIRONMENT_SCOPED = YES
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from project_atlas.agent_control.trusted_argv import resolve_executable_argv

MDA_ENV_VAR: Final[str] = "ATLAS_MDA_COMMAND"
MDA_PATH_BASENAME: Final[str] = "mda"
_TEST_PATH_COMPONENTS: Final[frozenset[str]] = frozenset(
    {"tests", "test", "fixtures", "mock", "mocks"}
)
_VERSION_PROBE_TIMEOUT_SECONDS: Final[int] = 10


class ControlPlaneError(RuntimeError):
    """Canonical control plane is unavailable or failed closed."""

    code: str = "CONTROL_PLANE_UNAVAILABLE"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


@dataclass(frozen=True, slots=True)
class MdaProvider:
    """Safe production/test MDA provenance. Never stores secrets."""

    command: Path
    source: Literal["operator_config", "PATH", "test_injection"]
    version: str
    path_digest: str


def package_repo_root() -> Path:
    """Repository root when Core is imported from a src checkout."""
    return Path(__file__).resolve().parents[3]


def control_plane_root() -> Path:
    root = package_repo_root() / "atlas-vault-documentation"
    if not root.is_dir():
        raise ControlPlaneError(
            "canonical control plane tree is not available",
            code="CONTROL_PLANE_UNAVAILABLE",
        )
    return root


def ensure_control_plane_importable() -> Path:
    sibling = control_plane_root()
    sibling_str = str(sibling)
    if sibling_str not in sys.path:
        sys.path.insert(0, sibling_str)
    return sibling


def documentation_skill_root() -> Path:
    configured = os.environ.get("ATLAS_SKILL_ROOT")
    if configured:
        path = Path(configured)
        if (path / "SKILL.md").is_file():
            return path
        raise ControlPlaneError("ATLAS_SKILL_ROOT is not a skill root", code="PREFLIGHT_FAILED")
    candidate = control_plane_root() / "skill"
    if (candidate / "SKILL.md").is_file():
        return candidate
    raise ControlPlaneError("canonical documentation skill is missing", code="PREFLIGHT_FAILED")


def _pipeline_unavailable(message: str) -> ControlPlaneError:
    return ControlPlaneError(message, code="PIPELINE_UNAVAILABLE")


def _posix_path_text(path: Path) -> str:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        resolved = path
    return str(resolved).replace("\\", "/").lower()


def path_is_test_or_mock_utility(path: Path) -> bool:
    """True when a path component is a test/fixture/mock utility location."""
    parts = {part for part in _posix_path_text(path).split("/") if part}
    return bool(parts & _TEST_PATH_COMPONENTS)


def path_is_known_repo_mda_fixture(path: Path) -> bool:
    posix = _posix_path_text(path)
    return posix.endswith("/tests/fixtures/bin/mda") or posix.endswith(
        "/tests/fixtures/bin/mda.exe"
    )


def version_is_mock(version: str) -> bool:
    return "mock" in version.lower()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65_536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def mda_version_probe_argv(executable: Path) -> list[str]:
    """Build ``--version`` argv using shared trusted launch semantics.

    Authorization must already have succeeded. A shebang never grants
    authority. Python shebang scripts use ``sys.executable``; unexpected
    interpreters are not substituted.
    """
    try:
        return [*resolve_executable_argv(str(executable)), "--version"]
    except ValueError as exc:
        raise _pipeline_unavailable("MDA version could not be established") from exc


def probe_mda_version(executable: Path) -> str:
    """Probe ``--version`` with the same argv identity as normalization."""
    argv = mda_version_probe_argv(executable)
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_VERSION_PROBE_TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _pipeline_unavailable("MDA version could not be established") from exc
    text = (completed.stdout or "").strip() or (completed.stderr or "").strip()
    if completed.returncode != 0 or not text:
        raise _pipeline_unavailable("MDA version could not be established")
    return text.splitlines()[0].strip()


def _require_production_file(path: Path) -> Path:
    if not path.is_file():
        raise _pipeline_unavailable("MDA provider is not a real file")
    if os.name != "nt" and not os.access(path, os.X_OK):
        raise _pipeline_unavailable("MDA provider is not executable")
    if path_is_test_or_mock_utility(path) or path_is_known_repo_mda_fixture(path):
        raise _pipeline_unavailable(
            "test or mock MDA provider is not accepted in production"
        )
    return path.resolve()


def _accept_production_candidate(
    path: Path,
    source: Literal["operator_config", "PATH"],
) -> MdaProvider:
    # AUTHORIZATION_PRECEDES_EXECUTION: path/provenance gates run first.
    resolved = _require_production_file(path)
    version = probe_mda_version(resolved)
    if version_is_mock(version):
        raise _pipeline_unavailable("mock MDA version is not accepted in production")
    return MdaProvider(
        command=resolved,
        source=source,
        version=version,
        path_digest=_file_digest(resolved),
    )


def resolve_production_mda_provider(
    *,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> MdaProvider:
    """Resolve a trusted real MDA provider. Never discovers test fixtures."""
    env = os.environ if environ is None else environ
    configured = str(env.get(MDA_ENV_VAR, "")).strip()
    if configured:
        return _accept_production_candidate(Path(configured), "operator_config")
    finder = shutil.which if which is None else which
    found = finder(MDA_PATH_BASENAME)
    if found:
        return _accept_production_candidate(Path(found), "PATH")
    raise _pipeline_unavailable("canonical event pipeline MDA is unavailable")


def resolve_mda_command() -> Path:
    """Production resolution only. Never falls back to the repository fixture."""
    return resolve_production_mda_provider().command


@contextmanager
def scoped_mda_environment(provider: MdaProvider | None) -> Iterator[None]:
    """Bridge ATLAS_MDA_COMMAND only for one canonical event operation."""
    prior = os.environ.get(MDA_ENV_VAR)
    try:
        if provider is None:
            os.environ.pop(MDA_ENV_VAR, None)
        else:
            os.environ[MDA_ENV_VAR] = str(provider.command)
        yield
    finally:
        if prior is None:
            os.environ.pop(MDA_ENV_VAR, None)
        else:
            os.environ[MDA_ENV_VAR] = prior


def prepare_event_pipeline() -> MdaProvider:
    """Resolve a trusted production MDA provider. Never consults test state."""
    return resolve_production_mda_provider()


def bootstrap_start(
    *,
    project_root: Path,
    vault_root: Path | None,
    agent_type: str,
    agent_value: str | None,
    task_id: str,
    skill_root: Path,
) -> tuple[dict[str, Any], dict[str, str]]:
    provider = prepare_event_pipeline()
    ensure_control_plane_importable()
    from agent_control.bootstrap import start

    with scoped_mda_environment(provider):
        return cast(
            tuple[dict[str, Any], dict[str, str]],
            start(
                project_root=project_root,
                vault_root=vault_root,
                agent_type=agent_type,
                agent_value=agent_value,
                task_id=task_id,
                skill_root=skill_root,
            ),
        )


def run_preflight(
    *,
    project_root: Path,
    vault_root: Path | None,
    agent_type: str,
    agent_value: str | None,
    skill_root: Path,
) -> dict[str, Any]:
    ensure_control_plane_importable()
    from agent_control.preflight import run

    return cast(
        dict[str, Any],
        run(
            project_root=project_root,
            vault_root=vault_root,
            agent_type=agent_type,
            agent_value=agent_value,
            skill_root=skill_root,
        ),
    )


def document_event(
    *,
    vault_root: Path,
    session_id: str,
    event_type: str,
    summary: str,
    work_package: str | None = None,
    validation: list[str] | None = None,
    decision: list[str] | None = None,
    changed_files: list[str] | None = None,
    spool: bool = False,
) -> dict[str, Any]:
    provider = prepare_event_pipeline()
    ensure_control_plane_importable()
    from agent_control.event_client import document

    with scoped_mda_environment(provider):
        return cast(
            dict[str, Any],
            document(
                vault_root=vault_root,
                session_id=session_id,
                event_type=event_type,
                summary=summary,
                work_package=work_package,
                validation=validation,
                decision=decision,
                changed_files=changed_files,
                spool=spool,
            ),
        )

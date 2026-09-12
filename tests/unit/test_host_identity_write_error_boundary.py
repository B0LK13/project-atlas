"""Supervisor host-identity writes must not leak raw OSError.

`write_host_identity` persists `supervisor-host.json` and `supervisor.pid`.
Callers catch `SdkRuntimeError`, not `OSError`. A blocked ancestor
(plain file where a directory is required) previously escaped as
`NotADirectoryError` and crashed the supervisor entrypoint.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.orchestration.sdk.host import host_state_dir, write_host_identity
from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE, SdkRuntimeError


def _blocked_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    blocker = root / Path(STATE_DIR_RELATIVE).parts[0]
    blocker.write_text("not-a-directory\n", encoding="utf-8")
    return root


def test_blocked_ancestor_is_governed_not_raw_oserror(tmp_path: Path) -> None:
    root = _blocked_root(tmp_path)
    with pytest.raises(SdkRuntimeError, match="unable to write supervisor host identity") as exc:
        write_host_identity(
            root,
            pid=1,
            backend="OBSERVER",
            package_head="unknown",
            worktree=str(root),
        )
    assert exc.value.code == "HOST_IDENTITY_WRITE_FAILED"


def test_ordinary_identity_write_still_succeeds(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = write_host_identity(
        root,
        pid=4242,
        backend="OBSERVER",
        package_head="b87b4a22",
        worktree=str(root),
    )
    store = host_state_dir(root)
    assert target == store / "supervisor-host.json"
    assert '"supervisor_pid": 4242' in target.read_text(encoding="utf-8")
    assert (store / "supervisor.pid").read_text(encoding="utf-8") == "4242\n"
    assert '"merge_authorized": false' in target.read_text(encoding="utf-8")
    assert '"execution_authorized": false' in target.read_text(encoding="utf-8")

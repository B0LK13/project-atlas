"""Contain raw OSError from external-observer persist writes.

``_atomic_write`` created parent directories and replaced the target with no
guard. A blocked ancestor leaked ``NotADirectoryError`` / ``FileExistsError``
past ``SdkRuntimeError``. Reads already fail closed; writes did not.

Does not grant merge. Does not change observer semantics on the success path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.orchestration.sdk.external_observers import (
    SchedulerLiveness,
    persist_liveness,
)
from project_atlas.orchestration.sdk.models import SdkRuntimeError


def test_persist_liveness_blocked_ancestor_is_sdk_error(tmp_path: Path) -> None:
    (tmp_path / ".atlas").write_text("not-a-directory\n", encoding="utf-8")
    with pytest.raises(SdkRuntimeError, match="observer-state-unwritable") as caught:
        persist_liveness(tmp_path, SchedulerLiveness())
    assert caught.value.code == "OBSERVER_WRITE_FAILED"


def test_persist_liveness_success_path_unchanged(tmp_path: Path) -> None:
    persist_liveness(tmp_path, SchedulerLiveness())
    assert (tmp_path / ".atlas/orchestration/sdk-runtime/scheduler-liveness.json").is_file()

"""Defence-in-depth: identifier grammar on values interpolated into paths.

Closes the two LOW findings from the fresh security review (W-SECSCAN): a
``project_id`` (kdiff) and an ``arm_id`` (scheduler / L3) were interpolated into
vault-relative paths without the shared ``_ID_RE`` guard. Reachable only via
self-supplied local CLI input, but hardened fail-closed for consistency.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas import scheduler_live
from project_atlas.knowledge_diff import KnowledgeDiffError, diff_knowledge, read_as_of

_TRAVERSAL = ["../../etc/passwd", "..", "a/b", "A-Upper", "", "  ", "x" * 65]


@pytest.mark.parametrize("bad", _TRAVERSAL)
def test_kdiff_rejects_unsafe_project_id(tmp_path: Path, bad: str) -> None:
    with pytest.raises(KnowledgeDiffError) as exc:
        read_as_of(tmp_path, project_id=bad, as_of_valid_time="2024-01-01")
    assert exc.value.args[0] in {"kdiff-project-scope-required", "kdiff-project-id-invalid"}
    with pytest.raises(KnowledgeDiffError):
        diff_knowledge(tmp_path, project_id=bad, t1="2024-01-01", t2="2024-02-01")


def test_kdiff_accepts_valid_project_id_shape(tmp_path: Path) -> None:
    # A well-formed id passes validation (fails later, fail-closed, on absent state).
    with pytest.raises(KnowledgeDiffError) as exc:
        read_as_of(tmp_path, project_id="harbor-api", as_of_valid_time="2024-01-01")
    assert exc.value.args[0] != "kdiff-project-id-invalid"


@pytest.mark.parametrize("bad", ["../../evil", "a/b", "..", "Upper", "", "x" * 65])
def test_scheduler_require_arm_id_rejects_unsafe(bad: str) -> None:
    with pytest.raises(scheduler_live.SchedulerLiveError) as exc:
        scheduler_live._require_arm_id(bad)
    assert exc.value.args[0] == "scheduler-arm-id-invalid"


def test_scheduler_require_arm_id_accepts_safe() -> None:
    assert scheduler_live._require_arm_id("arm-001") == "arm-001"

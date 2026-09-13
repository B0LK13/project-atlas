"""Distinguish an observed workspace revision from a declared fixture pin."""

from __future__ import annotations

from project_atlas.orchestration.program.loader import LoadedProgram
from project_atlas.orchestration.program.models import ProgramError

UNVERSIONED_FIXTURE_BOUNDARY = (
    "UNVERSIONED_FIXTURE: HEAD/TREE are declared fixture placeholders, "
    "not observed workspace Git identity or installed-package provenance"
)


def require_revision(loaded: LoadedProgram, head: str, tree: str) -> tuple[str, str]:
    if head and tree:
        return head, tree
    profiles = (*loaded.effective.values(), *loaded.verifiers.values())
    if (
        not head
        and not tree
        and loaded.program.allow_unversioned_fixture
        and all(p.adapter.value == "local-command" for p in profiles)
    ):
        return loaded.program.base_pin, loaded.program.base_pin
    raise ProgramError(
        "current workspace HEAD/TREE could not be observed; approval is not observation",
        code="CANDIDATE_REVISION_UNAVAILABLE",
    )

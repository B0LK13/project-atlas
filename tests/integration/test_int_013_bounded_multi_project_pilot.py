"""INT-013 — bounded multi-project integration pilot (acceptance criteria).

INT-013 ("Run the bounded multi-project integration pilot") is still
unchecked in ``docs/backlog.md``. Every underlying piece it needs
already exists and is independently tested -- the full production
pipeline (``init``/``discover``/``ingest``/``build-indexes``/
``build-portfolio``), and the AS-XPROJ-001/002/003 derived cross-project
registry commands (``register-global-entity``, ``register-global-edge``,
``detect-project-duplicates``) -- but they had never been ASSEMBLED and
RUN together as one coherent, bounded, end-to-end pilot and formally
recorded as certified. This module defines that pilot's real,
executable acceptance criteria (see the AS-ORIGIN-ACCEPTANCE-001
acceptance contract for this item, ``docs/origination-acceptance-
contracts.yaml``).

Marked ``skip`` -- not because anything here is expected to fail (this
was run un-skipped during authorship and passed cleanly end to end),
but because INT-013 itself is honestly not yet a certified, completed
milestone. Certifying it is a deliberate, separate act (removing this
marker and checking the backlog box), not something writing this test
should silently claim on its own.

Bounded = exactly two real, independently-owned projects, reused from
the already-committed ``tests/fixtures/demo/estate/`` fixture the
golden demo acceptance suite (``test_as_demo_2_2_golden_fixture.py``)
already exercises -- never a synthetic/invented pair, and never new
fixture authorship. ``harbor-api`` and ``harbor-ops`` are each their own
self-contained project root (own ``.atlas-project.yaml``, own README/
docs), independent of the third fixture project (``harbor-portal``) the
golden demo suite additionally references.

Acceptance criteria (all asserted below):
  1. Two real, independently-owned Atlas vaults are each built through
     the full production pipeline from two SEPARATE real project roots.
  2. A third, dedicated federation store holds ONLY derived cross-
     project registrations (AS-XPROJ-001/002/003 ``--write`` outputs)
     -- the only thing this pilot ever writes to.
  3. NO_AUTHORITY_MERGE: neither project's own vault (Layer B canonical
     content, generated indexes/portfolio) is modified by any xproj
     operation -- both vaults' full content digests before and after
     the xproj pass are byte-identical.
  4. BOUNDED_SCOPE: every xproj output path stays under the documented
     derived-only locations (``state/global-entities/...``), never
     inside either project's own vault tree.
  5. The full command chain (register-global-entity, register-global-
     edge, detect-project-duplicates) completes with exit code 0 across
     both real projects, end to end, in one pilot run, and produces at
     least one real derived registration.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_OK, main

pytestmark = pytest.mark.skip(
    reason=(
        "INT-013 is not yet run/certified -- this defines real, "
        "already-verified-runnable acceptance criteria for the bounded "
        "multi-project integration pilot; see docs/backlog.md"
    )
)

ESTATE = Path("tests/fixtures/demo/estate")
PROJECT_A = "harbor-api"
PROJECT_B = "harbor-ops"


def _build_vault(source: Path, tmp_path: Path, name: str) -> Path:
    manifest = tmp_path / f"{name}.manifest.json"
    vault = tmp_path / name
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert (
        main(
            ["ingest", "--manifest", str(manifest), "--vault", str(vault), "--source", str(source)]
        )
        == EXIT_OK
    )
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["build-portfolio", "--vault", str(vault)]) == EXIT_OK
    return vault


def _digest_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_int_013_bounded_multi_project_pilot(tmp_path: Path) -> None:
    source_a = (ESTATE / PROJECT_A).resolve()
    source_b = (ESTATE / PROJECT_B).resolve()
    vault_a = _build_vault(source_a, tmp_path, "vault-a")
    vault_b = _build_vault(source_b, tmp_path, "vault-b")
    before_a = _digest_tree(vault_a)
    before_b = _digest_tree(vault_b)

    federation = tmp_path / "federation-vault"
    federation.mkdir()

    evidence_a = source_a / "docs" / "audit-logging.md"
    evidence_b = source_b / "docs" / "NOTES.md"

    registrations = tmp_path / "registrations.json"
    _write_json(
        registrations,
        {
            "registrations": [
                {
                    "kind": "entity",
                    "global_entity_id": "ge-tech-postgresql",
                    "entity_class": "technology",
                    "display_name": "PostgreSQL",
                },
                {
                    "kind": "entity",
                    "global_entity_id": "ge-svc-harbor-ops-runtime",
                    "entity_class": "service",
                    "display_name": "Harbor Ops Runtime",
                },
                {
                    "kind": "join",
                    "project_id": PROJECT_A,
                    "project_local_entity_id": f"{PROJECT_A}:tech:postgresql",
                    "global_entity_id": "ge-tech-postgresql",
                    "evidence_refs": [
                        {
                            "relative_path": "docs/audit-logging.md",
                            "sha256": _sha256_of(evidence_a),
                        }
                    ],
                },
                {
                    "kind": "join",
                    "project_id": PROJECT_B,
                    "project_local_entity_id": f"{PROJECT_B}:svc:runtime",
                    "global_entity_id": "ge-svc-harbor-ops-runtime",
                    "evidence_refs": [
                        {"relative_path": "docs/NOTES.md", "sha256": _sha256_of(evidence_b)}
                    ],
                },
            ]
        },
    )
    assert (
        main(
            [
                "register-global-entity",
                "--registrations",
                str(registrations),
                "--vault",
                str(federation),
                "--write",
            ]
        )
        == EXIT_OK
    )

    edges = tmp_path / "edges.json"
    _write_json(
        edges,
        {
            "edges": [
                {
                    "kind": "edge",
                    "edge_id": "edge-harbor-ops-depends-on-postgresql",
                    "relationship_type": "depends-on",
                    "source_global_entity_id": "ge-svc-harbor-ops-runtime",
                    "target_global_entity_id": "ge-tech-postgresql",
                    "evidence_refs": [
                        {
                            "relative_path": "docs/audit-logging.md",
                            "sha256": _sha256_of(evidence_a),
                        }
                    ],
                }
            ]
        },
    )
    assert (
        main(["register-global-edge", "--edges", str(edges), "--vault", str(federation), "--write"])
        == EXIT_OK
    )

    projects = tmp_path / "projects.json"
    _write_json(projects, {"projects": [{"project_id": PROJECT_A}, {"project_id": PROJECT_B}]})
    assert (
        main(
            [
                "detect-project-duplicates",
                "--projects",
                str(projects),
                "--vault",
                str(federation),
                "--write",
            ]
        )
        == EXIT_OK
    )

    # NO_AUTHORITY_MERGE: neither project's own vault content changed --
    # cross-project identity/edges are derived metadata, never authority.
    assert _digest_tree(vault_a) == before_a
    assert _digest_tree(vault_b) == before_b

    # BOUNDED_SCOPE: every xproj-written path lives only under the
    # federation vault's documented derived-only location.
    written = [path for path in federation.rglob("*") if path.is_file()]
    assert written, "the pilot must actually produce at least one real derived registration"
    for path in written:
        rel = path.relative_to(federation).as_posix()
        assert rel.startswith(
            "state/global-entities"
        ), f"xproj output escaped its documented derived-only location: {rel}"

"""M3 fixture-backed bounded multi-project integration test (technical
acceptance -- see claim boundary below, NOT authentic INT-013
certification).

CLAIM BOUNDARY (owner review, 2026-09-02): this is a committed-fixture
integration test. It verifies bounded multi-project technical behavior
-- that the full production pipeline (``init``/``discover``/``ingest``/
``build-indexes``/``build-portfolio``) and the AS-XPROJ-001/002/003
derived cross-project registry commands (``register-global-entity``,
``register-global-edge``, ``detect-project-duplicates``) genuinely
compose into one coherent, bounded, end-to-end pilot run, against real
committed fixture projects. It does **not** itself certify authentic
INT-013, does **not** satisfy ``AUTHENTIC_PILOT``, and does **not**
authorize checking the INT-013 backlog item complete.
``docs/product/CODER-ALPHA-NORTH-STAR.md`` classifies INT-013
``EXTERNAL_BLOCKED`` -- it needs owner-provided authentic project roots,
and agents must not invent pilots to close it; committed
``DEMO_FIXTURE`` projects (``harbor-api``/``harbor-ops`` below) do not
satisfy that gate, matching ``docs/AS-PILOT-FIXTURE-ONLY-WAIVER.md``'s
existing, already-owner-authorized fixture-only precedent. See the
AS-ORIGIN-ACCEPTANCE-001 acceptance contract for this item's own,
separately-scoped fixture criteria (``docs/origination-acceptance-
contracts.yaml``) -- that contract widens what evidence exists; it does
not and cannot clear INT-013's real external blocker.

Previously marked ``skip`` pending a real, governed run proving it was
genuinely runnable (written un-skipped during authorship and confirmed
passing cleanly end to end, then marked ``skip`` again because it had
not yet actually been RUN and recorded that way). A real supervised
autonomous run (AS-ORCH-AUTONOMY-001E, dispatch ``local-process:
LEASE-14:0``) later removed the marker for real -- see WORKLOG.md's "M3
-- first supervised autonomous Atlas run" entry for that evidence. Now
enabled as an ongoing fixture-backed integration regression, kept
un-skipped going forward. ``docs/backlog.md``'s own INT-013 checkbox
stays unchecked, both outside this change's authorized scope and
substantively not owed a check while INT-013 remains
``EXTERNAL_BLOCKED``.

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

from project_atlas.cli import EXIT_OK, main

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

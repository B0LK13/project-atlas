"""AS-DEMO-2.2-001 — golden demo fixture acceptance (conflict + Time Machine).

One coherent journey over the committed DEMO_FIXTURE estate proving the two
previously-missing golden states come from **real Atlas production contracts**
(no mock truth, no hand-authored conflict/KDiff, no ingest-order dependence):

    fresh vault -> discover golden estate -> ingest -> build-indexes
      -> build-portfolio (derives the bitemporal validity catalog)
      -> validate -> Ask KNOWN / UNKNOWN / CONFLICT
      -> read_as_of T1 -> read_as_of T2 -> diff T1/T2

Plus mutation/negative proofs (§15): removing one conflict side removes the
conflict, and collapsing the temporal succession removes the value change — so
the acceptance can never be accidentally vacuous.

Golden handoff pins (kept in sync with tests/fixtures/demo/README.md):
    DEMO_PROJECT_ID   = harbor-api
    KNOWN_QUESTION    = "audit logging"          -> status known,   evidence > 0
    UNKNOWN_QUESTION  = "kubernetes gpu quota …"  -> status unknown, evidence = 0
    CONFLICT_QUESTION = "postgresql"             -> status conflict, no winner
    KDIFF_SUBJECT     = doc:harbor-api-datastore
    KDIFF_FIELD       = runtime
    T1 = 2024-03-01  -> PostgreSQL 15
    T2 = 2024-10-01  -> PostgreSQL 16   (EXPECTED_DIFF_CLASS = value_changed)
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from project_atlas.app_service import AppServiceError, open_app_service
from project_atlas.ask2 import ask_atlas_2
from project_atlas.cli import EXIT_OK, main
from project_atlas.knowledge_diff import diff_knowledge, read_as_of

pytestmark = pytest.mark.integration

DEMO_ESTATE = Path("tests/fixtures/demo/estate")

PROJECT = "harbor-api"
OTHER_PROJECTS = ("harbor-ops", "harbor-portal")

KNOWN_QUESTION = "audit logging"
UNKNOWN_QUESTION = "kubernetes gpu quota autoscaling"
CONFLICT_QUESTION = "postgresql"

KDIFF_SUBJECT = "doc:harbor-api-datastore"
KDIFF_FIELD = "runtime"
T1 = "2024-03-01"
T2 = "2024-10-01"
T1_VALUE = "PostgreSQL 15"
T2_VALUE = "PostgreSQL 16"
ADDED_SUBJECT = "doc:harbor-api-audit-logging"


def _build_vault(source: Path, tmp_path: Path, name: str = "vault") -> Path:
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
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    return vault


def _project_conflicts(vault: Path, project_id: str) -> list[dict]:
    path = vault / "review" / "conflicts" / f"{project_id}.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("entries", []))


def _cells_by_key(report: dict) -> dict[tuple[str, str], dict]:
    return {(c["subject"], c["field"]): c for c in report.get("cells", [])}


@pytest.fixture(scope="module")
def golden_vault(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("golden")
    return _build_vault(DEMO_ESTATE.resolve(), tmp)


# ---------------------------------------------------------------------------
# CONFLICT — real unresolved conflict from the normal pipeline
# ---------------------------------------------------------------------------


def test_conflict_is_real_and_unresolved(golden_vault: Path) -> None:
    entries = _project_conflicts(golden_vault, PROJECT)
    datastore = [
        e
        for e in entries
        if e.get("subject") == KDIFF_SUBJECT and e.get("field") == KDIFF_FIELD
    ]
    assert len(datastore) == 1, "expected exactly one datastore runtime conflict"
    entry = datastore[0]
    values = {c["claim"] for c in entry["claims"]}
    assert values == {T1_VALUE, T2_VALUE}, values
    assert len(entry["claim_ids"]) >= 2
    # Two distinct sources (provenance), not a single-source multi-row artifact.
    sources = {c.get("source_id") for c in entry["claims"]}
    assert len(sources) >= 2
    # NO_MOCK_TRUTH: conflict provenance points at real imported Layer-A evidence.
    resources = [p.get("resource", "") for p in entry.get("provenance", [])]
    assert any(r.startswith("sources/imported-documents/") for r in resources)


def test_ask_conflict_preserves_conflict_without_inventing_winner(
    golden_vault: Path,
) -> None:
    report = ask_atlas_2(golden_vault, question=CONFLICT_QUESTION, project_id=PROJECT)
    assert report["status"] == "conflict"
    assert report["ANSWER"] is None, "Atlas must not silently pick a conflict winner"
    assert report["CONFLICTS"]["unresolved_count"] >= 2
    assert report["llm_authority"] is False
    assert report["graph_authority"] is False


# ---------------------------------------------------------------------------
# ASK — known / unknown honesty
# ---------------------------------------------------------------------------


def test_ask_known_is_grounded(golden_vault: Path) -> None:
    report = ask_atlas_2(golden_vault, question=KNOWN_QUESTION, project_id=PROJECT)
    assert report["status"] == "known"
    assert report["evidence_count"] > 0
    assert report["UNKNOWN"]["is_unknown"] is False


def test_ask_unknown_stays_unknown(golden_vault: Path) -> None:
    report = ask_atlas_2(golden_vault, question=UNKNOWN_QUESTION, project_id=PROJECT)
    assert report["status"] == "unknown"
    assert report["evidence_count"] == 0
    assert report["ANSWER"] is None
    assert report["UNKNOWN"]["is_unknown"] is True


# ---------------------------------------------------------------------------
# TIME MACHINE — as-of reads + T1->T2 diff from real validity windows
# ---------------------------------------------------------------------------


def test_read_as_of_t1_and_t2_are_nonempty_and_differ(golden_vault: Path) -> None:
    at_t1 = read_as_of(golden_vault, project_id=PROJECT, as_of_valid_time=T1)
    at_t2 = read_as_of(golden_vault, project_id=PROJECT, as_of_valid_time=T2)
    # Real catalog was consumed (not fabricated at read time).
    assert (
        "generated/ops/bitemporal/harbor-api-validity-catalog.json"
        in at_t1["inspected_artifacts"]
    )
    t1_cell = _cells_by_key(at_t1)[(KDIFF_SUBJECT, KDIFF_FIELD)]
    t2_cell = _cells_by_key(at_t2)[(KDIFF_SUBJECT, KDIFF_FIELD)]
    assert t1_cell["disposition"] == "selected"
    assert t1_cell["value_sketch"] == T1_VALUE
    assert t2_cell["disposition"] == "selected"
    assert t2_cell["value_sketch"] == T2_VALUE


def test_diff_reports_value_changed_and_added(golden_vault: Path) -> None:
    diff = diff_knowledge(
        golden_vault, project_id=PROJECT, t1=T1, t2=T2
    )
    value_changed = {
        (d["subject"], d["field"]): d for d in diff.get("value_changed", [])
    }
    assert (KDIFF_SUBJECT, KDIFF_FIELD) in value_changed
    change = value_changed[(KDIFF_SUBJECT, KDIFF_FIELD)]
    assert change["from_value_sketch"] == T1_VALUE
    assert change["to_value_sketch"] == T2_VALUE
    added = {(d["subject"], d["field"]) for d in diff.get("added", [])}
    assert (ADDED_SUBJECT, "setup") in added


# ---------------------------------------------------------------------------
# PROJECT ISOLATION — no cross-project leakage in kdiff or ask
# ---------------------------------------------------------------------------


def test_kdiff_and_ask_are_project_isolated(golden_vault: Path) -> None:
    at_t2 = read_as_of(golden_vault, project_id=PROJECT, as_of_valid_time=T2)
    blob = json.dumps(at_t2)
    for other in OTHER_PROJECTS:
        assert other not in blob, f"kdiff leaked {other}"
    report = ask_atlas_2(golden_vault, question=CONFLICT_QUESTION, project_id=PROJECT)
    for entry in report.get("EVIDENCE", []):
        assert entry.get("record_id", "").find("harbor-ops") == -1
        assert entry.get("record_id", "").find("harbor-portal") == -1


# ---------------------------------------------------------------------------
# WEB / LIVE read projection (§16-18) — API can expose conflict + Time Machine
# ---------------------------------------------------------------------------


def test_app_service_exposes_conflict_and_kdiff(golden_vault: Path) -> None:
    svc = open_app_service(golden_vault)
    conflicts = svc.conflicts(PROJECT)
    assert conflicts["conflict_count"] == 1
    entry = conflicts["conflicts"][0]
    assert entry["subject"] == KDIFF_SUBJECT
    assert entry["field"] == KDIFF_FIELD
    assert {c["claim"] for c in entry["claims"]} == {T1_VALUE, T2_VALUE}

    at_t1 = svc.kdiff_as_of(PROJECT, T1)
    cell = _cells_by_key(at_t1)[(KDIFF_SUBJECT, KDIFF_FIELD)]
    assert cell["value_sketch"] == T1_VALUE

    diff = svc.kdiff_diff(PROJECT, T1, T2)
    value_changed = {(d["subject"], d["field"]) for d in diff["value_changed"]}
    assert (KDIFF_SUBJECT, KDIFF_FIELD) in value_changed


def test_app_service_rejects_unsafe_project_id(golden_vault: Path) -> None:
    svc = open_app_service(golden_vault)
    with pytest.raises(AppServiceError):
        svc.conflicts("../etc")


def test_kdiff_inspected_artifacts_are_project_scoped(golden_vault: Path) -> None:
    # Hardening: a sibling project's read must not disclose the harbor-api
    # validity-catalog filename in its inspected_artifacts provenance list.
    svc = open_app_service(golden_vault)
    api = svc.kdiff_as_of(PROJECT, T2)["inspected_artifacts"]
    assert any("bitemporal" in a for a in api)  # own catalog still listed
    for other in OTHER_PROJECTS:
        listed = svc.kdiff_as_of(other, T2)["inspected_artifacts"]
        assert not any("harbor-api-validity" in a for a in listed), (other, listed)


def test_conflict_projection_redacts_secret_shaped_values(tmp_path: Path) -> None:
    # NFR-004 defence-in-depth: even if a secret-shaped value reached a persisted
    # conflict (ingestion quarantines such sources upstream), the read projection
    # must never echo it verbatim — mirroring the kdiff value-sketch surface.
    from project_atlas.web_api.conflicts import list_project_conflicts

    conflicts_dir = tmp_path / "review" / "conflicts"
    conflicts_dir.mkdir(parents=True)
    (conflicts_dir / "harbor-api.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "conflict_id": "conflict-secret",
                        "subject": "doc:x",
                        "field": "runtime",
                        "conflict_type": "materially-incompatible",
                        "claims": [
                            {"claim": "AKIAIOSFODNN7EXAMPLE", "source_id": "s1"},
                            {"claim": "PostgreSQL 15", "source_id": "s2"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = list_project_conflicts(tmp_path, "harbor-api")
    values = [c["claim"] for c in result["conflicts"][0]["claims"]]
    assert "AKIAIOSFODNN7EXAMPLE" not in values
    assert any("redacted" in v for v in values)
    assert "PostgreSQL 15" in values  # non-secret value passes through


# ---------------------------------------------------------------------------
# MUTATION / NEGATIVE PROOF (§15) — acceptance depends on fixture semantics
# ---------------------------------------------------------------------------


def _mutable_estate(tmp_path: Path) -> Path:
    dest = tmp_path / "estate"
    shutil.copytree(DEMO_ESTATE, dest)
    return dest


def test_removing_conflict_side_removes_conflict(tmp_path: Path) -> None:
    estate = _mutable_estate(tmp_path)
    # Remove the PostgreSQL 16 (runtime pin) side of the datastore conflict.
    (estate / PROJECT / "src" / "datastore-runtime.md").unlink()
    vault = _build_vault(estate, tmp_path, name="mutant-noconflict")
    datastore = [
        e
        for e in _project_conflicts(vault, PROJECT)
        if e.get("subject") == KDIFF_SUBJECT and e.get("field") == KDIFF_FIELD
    ]
    assert datastore == [], "conflict must vanish when one competing side is removed"
    report = ask_atlas_2(vault, question=CONFLICT_QUESTION, project_id=PROJECT)
    assert report["status"] != "conflict"


def test_collapsing_temporal_succession_removes_value_change(tmp_path: Path) -> None:
    estate = _mutable_estate(tmp_path)
    # Collapse the succession: give the later runtime pin the SAME valid-time as
    # the architecture record. The KDiff value-change must then disappear —
    # proving it derives from real valid-time, not ingest/file order.
    runtime_doc = estate / PROJECT / "src" / "datastore-runtime.md"
    runtime_doc.write_text(
        runtime_doc.read_text(encoding="utf-8").replace(
            "timestamp: 2024-08-20", "timestamp: 2024-01-15"
        ),
        encoding="utf-8",
    )
    vault = _build_vault(estate, tmp_path, name="mutant-notime")
    diff = diff_knowledge(
        vault, project_id=PROJECT, t1=T1, t2=T2
    )
    value_changed = {(d["subject"], d["field"]) for d in diff.get("value_changed", [])}
    assert (KDIFF_SUBJECT, KDIFF_FIELD) not in value_changed

"""D-178 — #505 harness honesty: ASK semantics, portable fingerprint, scope."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.full_product_demo import (
    canonical_estate_bytes,
    demo_critical_missing,
    estate_fingerprint,
    score_ask2_fixture,
    score_query_authoritative_list,
)

REPO = Path(__file__).resolve().parents[2]
SCOPE = REPO / "docs" / "demo" / "full-product-demo-scope.json"
FIXTURE = REPO / "fixtures" / "demo" / "estate"


def _ask2(
    *,
    status: str,
    answer: object = None,
    unresolved: int = 0,
    evidence: list[dict[str, object]] | None = None,
    project_id: str = "project-a",
) -> str:
    payload = {
        "package_id": "AS-2.2-ASK2-001",
        "status": status,
        "ANSWER": answer,
        "project_id": project_id,
        "EVIDENCE": evidence
        if evidence is not None
        else ([{"record_id": "claim-pg16"}] if status != "unknown" else []),
        "CONFLICTS": {
            "unresolved_count": unresolved,
            "conflict_ids": ["conflict-pg"] if unresolved else [],
        },
        "UNKNOWN": {"is_unknown": status == "unknown", "reasons": []},
    }
    return "log line\n" + json.dumps(payload) + "\n"


def test_d178_ask_exit_zero_unknown_is_fail() -> None:
    status, detail = score_ask2_fixture(
        _ask2(status="unknown", answer=None, evidence=[]),
        exit_code=0,
        expected_project="project-a",
        expect_conflict=True,
    )
    assert status == "FAIL"
    assert detail == "ask2-ungrounded-unknown"


def test_d178_ask_conflict_with_evidence_is_pass() -> None:
    status, detail = score_ask2_fixture(
        _ask2(status="conflict", unresolved=1),
        exit_code=0,
        expected_project="project-a",
        expect_conflict=True,
    )
    assert status == "PASS"
    assert "unresolved=1" in detail


def test_d178_ask_nonzero_exit_is_blocked() -> None:
    status, _detail = score_ask2_fixture(
        "not json",
        exit_code=1,
        expected_project="project-a",
        expect_conflict=True,
    )
    assert status == "BLOCKED"


def test_d178_ask_wrong_project_fails() -> None:
    status, detail = score_ask2_fixture(
        _ask2(status="conflict", unresolved=1, project_id="other"),
        exit_code=0,
        expected_project="project-a",
        expect_conflict=True,
    )
    assert status == "FAIL"
    assert detail == "ask2-project-scope-mismatch"


def test_d178_ask_secret_leak_fails() -> None:
    text = _ask2(status="conflict", unresolved=1)
    text = text.replace("claim-pg16", "AKIAIOSFODNN7EXAMPLE")
    status, detail = score_ask2_fixture(
        text,
        exit_code=0,
        expected_project="project-a",
        expect_conflict=True,
    )
    assert status == "FAIL"
    assert detail.startswith("ask2-secret-leak")


def test_d178_query_empty_authoritative_is_partial() -> None:
    status, detail = score_query_authoritative_list("[]\n", exit_code=0)
    assert status == "PARTIAL"
    assert detail == "authoritative-list-empty"


def test_d178_query_nonempty_authoritative_is_pass() -> None:
    status, _detail = score_query_authoritative_list(
        json.dumps([{"subject": "s", "field": "f"}]),
        exit_code=0,
    )
    assert status == "PASS"


def test_d178_fingerprint_crlf_equals_lf(tmp_path: Path) -> None:
    lf = tmp_path / "lf"
    crlf = tmp_path / "crlf"
    (lf / "docs").mkdir(parents=True)
    (crlf / "docs").mkdir(parents=True)
    (lf / "docs" / "note.md").write_bytes(b"hello\nworld\n")
    (crlf / "docs" / "note.md").write_bytes(b"hello\r\nworld\r\n")
    (lf / "bin.dat").write_bytes(b"a\r\nb\x00c")
    (crlf / "bin.dat").write_bytes(b"a\r\nb\x00c")
    assert estate_fingerprint(lf) == estate_fingerprint(crlf)


def test_d178_fingerprint_does_not_rewrite_binary() -> None:
    crlf = b"a\r\nb\x00c"
    assert canonical_estate_bytes(crlf) == crlf
    assert canonical_estate_bytes(b"a\r\nb\n") == b"a\nb\n"


def test_d178_scope_graph_and_attention_not_demo_critical() -> None:
    scope = json.loads(SCOPE.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in scope["capabilities"]}
    assert by_id["mcp.graph"]["demo_critical"] is False
    assert by_id["mcp.graph"]["class"] == "UNIQUE_OPTIONAL"
    assert by_id["mcp.project_attention"]["demo_critical"] is False
    assert by_id["mcp.project_attention"]["class"] == "UNIQUE_OPTIONAL"
    missing = demo_critical_missing(scope)
    assert "mcp.graph" not in missing
    assert "mcp.project_attention" not in missing
    assert "mcp.mission_workspace" not in missing


def test_d178_fixture_fingerprint_stable_across_line_endings(tmp_path: Path) -> None:
    """Copy fixture with forced CRLF text and match the live Linux digest."""
    live = estate_fingerprint(FIXTURE)
    clone = tmp_path / "estate"
    for src in FIXTURE.rglob("*"):
        if not src.is_file() or ".git" in src.parts:
            continue
        dest = clone / src.relative_to(FIXTURE)
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        if b"\x00" not in data:
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                dest.write_bytes(data)
                continue
            dest.write_bytes(data.replace(b"\n", b"\r\n"))
        else:
            dest.write_bytes(data)
    assert estate_fingerprint(clone) == live


def test_d182_unowned_work_root_rejected(tmp_path: Path) -> None:
    from project_atlas.full_product_demo import _ensure_owned_work_root, _rmtree_under_owned

    foreign = tmp_path / "projects"
    foreign.mkdir()
    (foreign / "vault").mkdir()
    (foreign / "vault" / "keep.txt").write_text("do-not-delete\n", encoding="utf-8")
    try:
        _ensure_owned_work_root(foreign)
        raise AssertionError("expected refuse unowned work root")
    except RuntimeError as exc:
        assert "unowned work root" in str(exc)
    assert (foreign / "vault" / "keep.txt").is_file()

    owned = tmp_path / "demo-work"
    _ensure_owned_work_root(owned)
    vault = owned / "vault"
    vault.mkdir()
    (vault / "x").write_text("x\n", encoding="utf-8")
    _rmtree_under_owned(owned, vault)
    assert not vault.exists()

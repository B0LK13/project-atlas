"""AS-2.2-ASK2-001 — Ask Atlas 2 wire over LIVE /v1/ask (retrieval+compiler).

ADVANCE-005 Track C3. Consumes runtime_22 hybrid_retrieve + compile_context.
Never invents Knowledge/Graph evidence. Fail-closed UNKNOWN when empty.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.ask_atlas_live import AskAtlasLiveError, ask_atlas_live
from project_atlas.authz import elevated_operator


def _claims_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "generated" / "indexes").mkdir(parents=True)
    (vault / "state" / "claims").mkdir(parents=True)
    (vault / "projects" / "alpha").mkdir(parents=True)
    index = {
        "by_claim_id": {"claim-alpha": ["claim-alpha"], "claim-beta": ["claim-beta"]},
        "by_field": {},
        "by_concept_id": {},
        "by_source_lineage_id": {},
    }
    (vault / "generated" / "indexes" / "claims.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    claims = {
        "claims": [
            {
                "claim_id": "claim-alpha",
                "field": "status",
                "provenance": [{"ref": "sources/a.md"}],
            },
            {
                "claim_id": "claim-beta",
                "field": "owner",
                "provenance": [{"ref": "sources/b.md"}],
            },
        ]
    }
    (vault / "state" / "claims" / "claims.json").write_text(
        json.dumps(claims, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return vault


def test_ask2_wires_retrieval_and_compiler(tmp_path: Path) -> None:
    vault = _claims_vault(tmp_path)
    report = ask_atlas_live(vault, query="claim-")
    assert report["live_ask"] is True
    assert report["ask_atlas_2"] is True
    assert report["llm_authority"] is False
    assert report["canonical_write"] is False
    ask2 = report["ask2"]
    assert ask2["package_id"] == "AS-2.2-ASK2-001"
    assert ask2["status"] == "matched"
    assert ask2["ANSWER"] is None
    assert ask2["llm_authority"] is False
    assert ask2["graph_authority"] is False
    assert ask2["retrieval"]["estate_facts_invented"] is False
    assert ask2["retrieval"]["semantic_enabled"] is False
    assert ask2["retrieval"]["candidate_count"] >= 1
    assert "claim" in ask2["retrieval"]["kinds_probed"]
    assert ask2["context_status"] == "active"
    assert ask2["context"]["entry_count"] >= 1
    assert ask2["context"]["authority"]["estate_facts_invented"] is False
    assert ask2["EVIDENCE"]
    assert all(e.startswith("claim:") for e in ask2["EVIDENCE"])
    # Projection match still works (projects/alpha unused for claim- query).
    assert report["matches"]["projects"] == []


def test_ask2_unknown_when_no_hits(tmp_path: Path) -> None:
    vault = _claims_vault(tmp_path)
    report = ask_atlas_live(vault, query="zzz-no-such-record")
    ask2 = report["ask2"]
    assert ask2["status"] == "unknown"
    assert ask2["ANSWER"] == "UNKNOWN — no retrieval/compiler evidence for query"
    assert ask2["EVIDENCE"] == []
    assert "no-lexical-retrieval-hits" in ask2["UNKNOWN"]
    assert ask2["retrieval"]["candidate_count"] == 0
    assert ask2["context"]["entry_count"] == 0
    assert ask2["context"]["authority"]["estate_facts_invented"] is False


def test_ask2_indexes_absent_fail_closed_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    (vault / "projects" / "alpha").mkdir(parents=True)
    report = ask_atlas_live(vault, query="alpha")
    assert report["matches"]["projects"][0]["project_id"] == "alpha"
    ask2 = report["ask2"]
    assert ask2["status"] == "unknown"
    assert "lexical-indexes-absent" in ask2["UNKNOWN"]
    assert ask2["retrieval"]["status"] == "absent"
    assert ask2["EVIDENCE"] == []
    assert ask2["retrieval"]["estate_facts_invented"] is False
    # Must not invent knowledge / graph payloads.
    assert "knowledge" not in ask2
    assert ask2["graph_authority"] is False


def test_ask2_rejects_invalid_query(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(AskAtlasLiveError, match="ask-query-invalid"):
        ask_atlas_live(vault, query="   ")
    with pytest.raises(AskAtlasLiveError, match="ask-query-invalid"):
        ask_atlas_live(vault, query="x" * 257)


def test_api_ask_exposes_ask2_wire(tmp_path: Path) -> None:
    vault = _claims_vault(tmp_path)
    op = elevated_operator("api-ask2", extra={"web.action"})
    server = serve_api(vault, host="127.0.0.1", port=0, operator=op)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        read_auth = session_credentials(server).auth_headers()
        with urlopen(
            Request(
                f"http://{host}:{port}/v1/meta",
                headers=read_auth,
            ),
            timeout=2,
        ) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        assert meta["ask_atlas_live"] is True
        assert meta["ask_atlas_2"] is True
        with urlopen(
            Request(
                f"http://{host}:{port}/v1/ask?q={quote('claim-alpha')}",
                headers=read_auth,
            ),
            timeout=2,
        ) as resp:
            ask = json.loads(resp.read().decode("utf-8"))
        assert ask["ask_atlas_2"] is True
        assert ask["ask2"]["status"] == "matched"
        assert ask["ask2"]["context"]["entry_count"] >= 1
        with urlopen(
            Request(
                f"http://{host}:{port}/v1/ask?q={quote('xyzzy-unknown-999')}",
                headers=read_auth,
            ),
            timeout=2,
        ) as resp:
            unknown = json.loads(resp.read().decode("utf-8"))
        assert unknown["ask2"]["status"] == "unknown"
        assert unknown["ask2"]["EVIDENCE"] == []
    finally:
        server.shutdown()

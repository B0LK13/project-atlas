"""AS-SEC-SCAN-CTXCOMP-JSON-ESC-001 — scan decoded context-compiler refs.

``compile_context(..., write=True)`` persists sanitized provenance. JSON
``\\u`` escapes miss raw ``scan_text`` and must drop before write.
Distinct persist sink from ask2 provenance echo (#888) and ChatGPT
export-turn decode (#936).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.runtime_22 import Runtime22Error, compile_context
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"  # AKIA + 16 A — matches cloud-access-key
PROJECT_A = "proj-alpha"


def _mini_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "generated" / "indexes").mkdir(parents=True)
    (vault / "state" / "claims").mkdir(parents=True)
    index = {
        "by_claim_id": {"claim-alpha": ["claim-alpha"]},
        "by_field": {},
        "by_concept_id": {},
        "by_source_lineage_id": {},
    }
    (vault / "generated" / "indexes" / "claims.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (vault / "state" / "claims" / "claims.json").write_text(
        json.dumps(
            {
                "claims": [
                    {
                        "claim_id": "claim-alpha",
                        "field": "status",
                        "project_id": PROJECT_A,
                        "provenance": [{"ref": "sources/a.md"}],
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return vault


def test_unicode_escape_ref_is_not_written(tmp_path: Path) -> None:
    vault = _mini_vault(tmp_path)
    raw_path = tmp_path / "cands.json"
    raw_path.write_text(
        '{"candidates":[{"record_type":"claim","record_id":"claim-alpha",'
        '"provenance":[{"kind":"source","ref":"\\u0041KIAAAAAAAAAAAAAAAAA"}]}]}\n',
        encoding="utf-8",
    )
    raw = raw_path.read_text(encoding="utf-8")
    assert scan_text(raw) == []
    assert TOKEN not in raw
    candidates = json.loads(raw)["candidates"]
    assert candidates[0]["provenance"][0]["ref"] == TOKEN
    with pytest.raises(Runtime22Error, match="context-compiler-provenance-empty"):
        compile_context(
            vault,
            pack_id="ctx-esc",
            candidates=candidates,
            project_id=PROJECT_A,
            write=True,
        )
    out = vault / "generated" / "context-compiler" / "ctx-esc-context-compiler.json"
    assert not out.exists()


def test_mixed_secret_and_clean_ref_keeps_only_clean(tmp_path: Path) -> None:
    vault = _mini_vault(tmp_path)
    package = compile_context(
        vault,
        pack_id="ctx-mix",
        candidates=[
            {
                "record_type": "claim",
                "record_id": "claim-alpha",
                "provenance": [
                    {"kind": "source", "ref": TOKEN},
                    {"kind": "source", "ref": "sources/ok.md"},
                ],
            }
        ],
        project_id=PROJECT_A,
        write=True,
    )
    refs = [item["ref"] for item in package["entries"][0]["provenance"]]
    assert refs == ["sources/ok.md"]
    assert TOKEN not in json.dumps(package, sort_keys=True)
    written = (
        vault / "generated" / "context-compiler" / "ctx-mix-context-compiler.json"
    ).read_text(encoding="utf-8")
    assert TOKEN not in written


def test_clean_ref_still_compiles(tmp_path: Path) -> None:
    vault = _mini_vault(tmp_path)
    package = compile_context(
        vault,
        pack_id="ctx-ok",
        candidates=[
            {
                "record_type": "claim",
                "record_id": "claim-alpha",
                "provenance": [{"kind": "source", "ref": "sources/ok.md"}],
            }
        ],
        project_id=PROJECT_A,
        write=True,
    )
    assert package["entries"][0]["provenance"][0]["ref"] == "sources/ok.md"
    assert TOKEN not in json.dumps(package, sort_keys=True)

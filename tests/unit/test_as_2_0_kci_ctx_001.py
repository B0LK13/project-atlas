"""AS-2.0-KCI-001 and AS-2.0-CTX-001 thin contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.context_pack import (
    ContextEntry,
    ContextPackError,
    ProvenancePointer,
    build_context_pack,
)
from project_atlas.kci import (
    KciError,
    build_compile_request,
    issue_compile_receipt,
)
from project_atlas.schema import available_schemas, validate_record

ROOT = Path(__file__).resolve().parents[2]


def test_kci_compile_request_happy_path(tmp_path: Path) -> None:
    out = tmp_path / "vault"
    out.mkdir()
    report = build_compile_request(
        request_id="compile-alpha",
        source_refs=["sources/fixture-a.md", "sources/fixture-b.md"],
        subject_refs=["subjects/proj-a"],
        output_vault=out,
    )
    assert report["package_id"] == "AS-2.0-KCI-001"
    assert report["compat_snapshot_id"] == "atlas-1.0.0-compat"
    assert report["operation"] == "compile"
    assert report["authority"]["level"] == "derived"
    validate_record(report, "kci-compile-request")
    assert (out / "generated" / "kci" / "compile-alpha-compile-request.json").is_file()


def test_kci_compile_receipt_never_promotes_authority(tmp_path: Path) -> None:
    out = tmp_path / "vault"
    out.mkdir()
    report = issue_compile_receipt(
        receipt_id="receipt-alpha",
        request_id="compile-alpha",
        status="accepted",
        outcome_refs=["generated/kci/compile-alpha-compile-request.json"],
        output_vault=out,
    )
    assert report["consume_only"] is True
    assert report["authority_promoted"] is False
    assert report["truth_boundary"] == "KCI RECEIPT ≠ LAYER B AUTHORITY"
    validate_record(report, "kci-compile-receipt")


def test_kci_refuses_empty_source_refs(tmp_path: Path) -> None:
    out = tmp_path / "vault"
    out.mkdir()
    with pytest.raises(KciError, match="source-refs-empty"):
        build_compile_request(
            request_id="compile-empty",
            source_refs=[],
            output_vault=out,
        )


def test_kci_refused_receipt_requires_reason(tmp_path: Path) -> None:
    out = tmp_path / "vault"
    out.mkdir()
    with pytest.raises(KciError, match="refusal-reason-required"):
        issue_compile_receipt(
            receipt_id="receipt-refused",
            request_id="compile-alpha",
            status="refused",
            output_vault=out,
        )


def test_context_pack_happy_path(tmp_path: Path) -> None:
    out = tmp_path / "vault"
    out.mkdir()
    report = build_context_pack(
        pack_id="pack-alpha",
        provenance_pointers=[
            ProvenancePointer("sources/fixture-a.md", "source"),
            ProvenancePointer("routing/receipts/r1.json", "receipt"),
        ],
        entries=[
            ContextEntry("entry-a", "generated/indexes/terms.json", "terms"),
        ],
        output_vault=out,
    )
    assert report["fixture_safe"] is True
    assert report["estate_facts_invented"] is False
    assert report["compat_snapshot_id"] == "atlas-1.0.0-compat"
    validate_record(report, "context-pack")
    assert (out / "generated" / "context" / "pack-alpha-context-pack.json").is_file()


def test_context_pack_requires_provenance_and_forbids_invention(
    tmp_path: Path,
) -> None:
    out = tmp_path / "vault"
    out.mkdir()
    with pytest.raises(ContextPackError, match="provenance-pointers-empty"):
        build_context_pack(
            pack_id="pack-empty",
            provenance_pointers=[],
            output_vault=out,
        )
    with pytest.raises(ContextPackError, match="estate-facts-invent-forbidden"):
        build_context_pack(
            pack_id="pack-invent",
            provenance_pointers=[ProvenancePointer("sources/a.md", "source")],
            invent_estate_facts=True,
            output_vault=out,
        )


def test_kci_ctx_schemas_registered_and_docs() -> None:
    schemas = available_schemas()
    assert "kci-compile-request" in schemas
    assert "kci-compile-receipt" in schemas
    assert "context-pack" in schemas
    assert (ROOT / "docs" / "AS-2.0-KCI-001.md").is_file()
    assert (ROOT / "docs" / "AS-2.0-CTX-001.md").is_file()

"""AS-SEC-001 source quarantine and prompt-injection boundary integration tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.knowledge_compiler import compile_knowledge, render_bundle

CANARY_TOKEN = "CANARY-AS-SEC-001-a7f3d9e2"


def _fixture_adversarial_project(root: Path) -> Path:
    source = root / "adversarial-project"
    source.mkdir()
    marker = Path("tests/fixtures/adversarial-project/.atlas-project.yaml")
    marker_text = marker.read_text(encoding="utf-8")
    marker_text = marker_text.replace(
        "id: adversarial-project", f"id: {source.name}"
    ).replace("name: Adversarial Test Project", f"name: {source.name}")
    (source / ".atlas-project.yaml").write_text(marker_text, encoding="utf-8")
    for name in (
        "README.md",
        "instruction-bearing.md",
        "canary-bearing.md",
        "non-adversarial-control.md",
        "quoted-research.md",
    ):
        (source / name).write_text(
            Path(f"tests/fixtures/adversarial-project/{name}").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    return source


def _run_core_pipeline(source: Path, tmp_path: Path) -> Path:
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    return vault


def test_instruction_bearing_source_is_quarantined_and_reported(tmp_path: Path) -> None:
    source = _fixture_adversarial_project(tmp_path)
    vault = _run_core_pipeline(source, tmp_path)
    report = json.loads(
        (vault / "generated" / "reports" / "injection-findings.json").read_text(
            encoding="utf-8"
        )
    )
    findings = report["findings"]
    instruction_findings = [
        f for f in findings if "instruction-bearing.md" in f.get("path", "")
    ]
    assert instruction_findings, "instruction-bearing source must produce a finding"
    assert all(f.get("disposition") == "quarantined" for f in instruction_findings)
    assert all(f.get("source_id") for f in instruction_findings)


def test_canary_source_is_quarantined_and_canary_absent_from_generated(tmp_path: Path) -> None:
    source = _fixture_adversarial_project(tmp_path)
    vault = _run_core_pipeline(source, tmp_path)
    report = json.loads(
        (vault / "generated" / "reports" / "injection-findings.json").read_text(
            encoding="utf-8"
        )
    )
    canary_findings = [
        f for f in report["findings"] if "canary-bearing.md" in f.get("path", "")
    ]
    assert canary_findings, "canary-bearing source must produce a finding"
    generated_root = vault / "generated"
    for path in generated_root.rglob("*"):
        if path.is_file():
            assert CANARY_TOKEN not in path.read_text(
                encoding="utf-8"
            ), f"canary leaked into {path.relative_to(vault)}"


def test_non_adversarial_control_is_ingested_normally(tmp_path: Path) -> None:
    source = _fixture_adversarial_project(tmp_path)
    vault = _run_core_pipeline(source, tmp_path)
    report = json.loads(
        (vault / "generated" / "reports" / "ingestion-report.json").read_text(
            encoding="utf-8"
        )
    )
    injection = json.loads(
        (vault / "generated" / "reports" / "injection-findings.json").read_text(
            encoding="utf-8"
        )
    )
    quarantined_paths = {f["path"] for f in injection["findings"]}
    assert not any(
        "non-adversarial-control.md" in path for path in quarantined_paths
    ), "non-adversarial control must not be quarantined"
    assert report["documents_ingested"] == 3
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK


def test_quarantined_source_does_not_produce_claims_or_concepts(tmp_path: Path) -> None:
    source = _fixture_adversarial_project(tmp_path)
    vault = _run_core_pipeline(source, tmp_path)
    state = json.loads(
        (vault / "state" / "concepts" / f"{source.name}.json").read_text(encoding="utf-8")
    )
    concept_sources = {
        ref["source_id"]
        for concept in state["concepts"]
        for ref in concept.get("sources", [])
    }
    claims = json.loads(
        (vault / "state" / "claims" / f"{source.name}.json").read_text(encoding="utf-8")
    )
    claim_source_ids = {
        ref["source_id"]
        for claim in claims["claims"]
        for ref in claim.get("provenance", [])
    }
    assert "instruction-bearing" not in " ".join(concept_sources)
    assert "canary-bearing" not in " ".join(concept_sources)
    assert "instruction-bearing" not in " ".join(claim_source_ids)
    assert "canary-bearing" not in " ".join(claim_source_ids)


def test_quarantined_source_does_not_appear_in_lexical_indexes(tmp_path: Path) -> None:
    source = _fixture_adversarial_project(tmp_path)
    vault = _run_core_pipeline(source, tmp_path)
    indexes_dir = vault / "generated" / "indexes"
    if indexes_dir.exists():
        for path in indexes_dir.rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            assert "ignore prior rules" not in text.lower()
            assert CANARY_TOKEN not in text


def test_unchanged_replay_is_byte_identical(tmp_path: Path) -> None:
    source = _fixture_adversarial_project(tmp_path)
    vault = _run_core_pipeline(source, tmp_path)
    manifest = tmp_path / "manifest.json"
    # Stabilize the project marker and claim lifecycle states before measuring.
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    before = {
        path.relative_to(vault).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in vault.rglob("*") if path.is_file()
    }
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    after = {
        path.relative_to(vault).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in vault.rglob("*") if path.is_file()
    }
    assert after == before


def test_injection_findings_report_has_identity_and_disposition(tmp_path: Path) -> None:
    source = _fixture_adversarial_project(tmp_path)
    vault = _run_core_pipeline(source, tmp_path)
    report = json.loads(
        (vault / "generated" / "reports" / "injection-findings.json").read_text(
            encoding="utf-8"
        )
    )
    assert report.get("schema_version") == 1
    assert report["findings"]
    for finding in report["findings"]:
        assert finding["source_id"]
        assert finding["path"]
        assert finding["rule"]
        assert finding["confidence"] in {"high", "medium"}
        assert finding["disposition"] == "quarantined"
        # Identity is enriched when the source existed in the durable registry;
        # new adversarial sources may legitimately lack lineage/project identity.
        assert "source_lineage_id" in finding
        assert "project_uuid" in finding
        assert "text" not in finding
        assert CANARY_TOKEN not in str(finding)


def test_transaction_rollback_on_corrupted_quarantine_report_reference(tmp_path: Path) -> None:
    source = _fixture_adversarial_project(tmp_path)
    vault = _run_core_pipeline(source, tmp_path)
    report_path = vault / "generated" / "reports" / "injection-findings.json"
    original = report_path.read_text(encoding="utf-8")
    corrupted = original.replace("quarantined", "released")
    report_path.write_text(corrupted, encoding="utf-8")
    assert main(["validate", "--vault", str(vault)]) == EXIT_ERROR
    report_path.write_text(original, encoding="utf-8")
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK


def test_claim_values_are_rendered_as_quoted_literals(tmp_path: Path) -> None:
    entry = {
        "source_id": "source-quote",
        "path": "README.md",
        "classification": "project-overview",
        "source": "sources/imported-documents/source-quote.md",
        "sha256": "0" * 64,
        "text": "Purpose: render safely.",
    }
    rendered = render_bundle(compile_knowledge("quote-project", [entry], tmp_path), "quote-project")
    claims_md = rendered["projects/quote-project/claims.md"]
    assert "`render safely.`" in claims_md
    decisions_md = rendered["projects/quote-project/decisions.md"]
    assert "_No verified entries._" in decisions_md or "`" in decisions_md


def test_multiline_claim_value_is_rendered_in_fenced_block() -> None:
    from project_atlas.knowledge_compiler import _quote_source_text

    rendered = _quote_source_text("line one\nLine two")
    assert rendered.startswith("```source-excerpt")
    assert "line one" in rendered
    assert "Line two" in rendered
    assert rendered.endswith("```")


def test_inline_literal_escapes_internal_backticks() -> None:
    from project_atlas.knowledge_compiler import _quote_source_text

    assert "`` `foo` ``" in _quote_source_text("`foo`")


def test_source_identity_preserved_for_quarantined_source(tmp_path: Path) -> None:
    source = _fixture_adversarial_project(tmp_path)
    vault = _run_core_pipeline(source, tmp_path)
    report = json.loads(
        (vault / "generated" / "reports" / "injection-findings.json").read_text(
            encoding="utf-8"
        )
    )
    for finding in report["findings"]:
        lineage_id = finding.get("source_lineage_id")
        if lineage_id:
            registry = json.loads(
                (vault / "state" / "sources.json").read_text(encoding="utf-8")
            )
            assert any(
                str(item.get("source_lineage_id")) == str(lineage_id)
                for item in registry["sources"]
            ), f"lineage {lineage_id} must exist in source registry"

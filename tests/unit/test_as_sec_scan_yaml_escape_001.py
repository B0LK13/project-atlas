"""AS-SEC-SCAN-YAML-ESC-001 — decoded YAML claim scalars must be scanned.

``scan_text`` of raw UTF-8 YAML misses a double-quoted ``\\u0062earer`` /
``\\x62earer`` escape. ``load_safe_yaml`` then decodes the scalar to ASCII
``bearer`` + token, and evidence compilation persisted that decoded value
in ``state/claims/<project>.json`` and ``projects/<project>/claims.md``.

Remediation scans decoded user-facing claim leaves after YAML construct,
before any ExtractedRecord / render persist. Distinct from
AS-SEC-SCAN-JSON-ESC-001 (JSON export turns) and HTML/XML entity leftovers.
Does not reject non-claim documentation canaries (for example a fake AKIA
string in a receipt note). Synthetic token only.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.compilation import CompilationOutcome
from project_atlas.evidence_compiler import extract_source
from project_atlas.knowledge_compiler import compile_knowledge, render_bundle
from project_atlas.secrets import scan_text
from project_atlas.verify_profile import parse_verify_document
from project_atlas.yaml_structured import load_safe_yaml

# Synthetic — never a live credential.
_SYNTH = "A" * 32
_DECODED = f"bearer {_SYNTH}"
_HASH = "a" * 64


def _receipt(title_yaml: str) -> str:
    return (
        "schema_version: 1\n"
        "receipt_type: atlas-core-work-package\n"
        "work_package_id: AS-SEC-001\n"
        f"title: {title_yaml}\n"
        "status: done\n"
    )


def _entry(text: str) -> dict[str, str]:
    return {
        "source_id": "src-yamlesc",
        "source_lineage_id": "sline-test",
        "project_uuid": "11111111-1111-4111-8111-111111111111",
        "path": "docs/evidence/yaml-esc.yaml",
        "classification": "unknown",
        "source": "../../sources/imported-documents/yaml-esc.yaml",
        "sha256": _HASH,
        "text": text,
    }


def test_raw_yaml_unicode_escape_misses_and_decode_hits() -> None:
    raw = _receipt(f'"\\u0062earer {_SYNTH}"')
    assert "bearer " not in raw
    assert scan_text(raw) == []
    tree = load_safe_yaml(raw)
    assert isinstance(tree, dict)
    assert tree["title"] == _DECODED
    assert any(item.pattern == "bearer-token" for item in scan_text(tree["title"]))


def test_raw_yaml_hex_escape_misses_and_decode_hits() -> None:
    raw = _receipt(f'"\\x62earer {_SYNTH}"')
    assert "bearer " not in raw
    assert scan_text(raw) == []
    tree = load_safe_yaml(raw)
    assert isinstance(tree, dict)
    assert tree["title"] == _DECODED
    assert any(item.pattern == "bearer-token" for item in scan_text(tree["title"]))


def test_extract_source_withholds_unicode_escaped_bearer() -> None:
    raw = _receipt(f'"\\u0062earer {_SYNTH}"')
    extraction = extract_source("harbor-api", _entry(raw))
    assert extraction.candidate.outcome is CompilationOutcome.FAILED
    assert extraction.records == ()
    blob = json.dumps(
        [diagnostic.model_dump(mode="json") for diagnostic in extraction.diagnostics],
        sort_keys=True,
    )
    assert _DECODED not in blob
    assert _SYNTH not in blob
    assert "secret pattern" in blob


def test_compile_render_refuses_persist_of_decoded_yaml_escape(tmp_path: Path) -> None:
    raw = _receipt(f'"\\u0062earer {_SYNTH}"')
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    bundle = compile_knowledge("harbor-api", [_entry(raw)], vault)
    rendered = render_bundle(bundle, "harbor-api")
    claims_json = rendered["state/claims/harbor-api.json"]
    claims_md = rendered["projects/harbor-api/claims.md"]
    payload = json.loads(claims_json)
    values = [claim.get("value") for claim in payload.get("claims", [])]
    assert _DECODED not in values
    assert _DECODED not in claims_json
    assert _DECODED not in claims_md
    assert _SYNTH not in claims_json
    assert _SYNTH not in claims_md
    for path in vault.rglob("*"):
        if path.is_file():
            assert _SYNTH not in path.read_text(encoding="utf-8")


def test_hex_escape_also_refuses_persist(tmp_path: Path) -> None:
    raw = _receipt(f'"\\x62earer {_SYNTH}"')
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    bundle = compile_knowledge("harbor-api", [_entry(raw)], vault)
    rendered = render_bundle(bundle, "harbor-api")
    assert _DECODED not in rendered["state/claims/harbor-api.json"]
    assert _DECODED not in rendered["projects/harbor-api/claims.md"]


def test_plaintext_yaml_bearer_still_rejected() -> None:
    raw = _receipt(f'"{_DECODED}"')
    assert scan_text(raw)
    extraction = extract_source("harbor-api", _entry(raw))
    assert extraction.candidate.outcome is CompilationOutcome.FAILED
    assert extraction.records == ()
    blob = json.dumps(
        [diagnostic.model_dump(mode="json") for diagnostic in extraction.diagnostics],
        sort_keys=True,
    )
    assert _SYNTH not in blob


def test_clean_receipt_still_extracts() -> None:
    raw = _receipt('"Harbor API work package"')
    tree = load_safe_yaml(raw)
    assert tree["title"] == "Harbor API work package"
    extraction = extract_source("harbor-api", _entry(raw))
    assert extraction.candidate.outcome is CompilationOutcome.COMPLETE_CANDIDATE
    assert any(record.value == "Harbor API work package" for record in extraction.records)


def test_verify_profile_withholds_unicode_escaped_bearer() -> None:
    text = (
        "# VERIFY / escape scan\n"
        "\n"
        "status: decided\n"
        f'decision: "\\u0062earer {_SYNTH}"\n'
        "\n"
        "## Rationale\n"
        "\n"
        "Synthetic only.\n"
    )
    result = parse_verify_document(text, source_path="docs/VERIFY-esc.md")
    assert result.records == ()
    assert any("secret pattern" in item for item in result.diagnostics)
    blob = " ".join(result.diagnostics)
    assert _SYNTH not in blob
    assert _DECODED not in blob


def test_nonclaim_akia_canary_does_not_fail_receipt() -> None:
    """Documentation canaries in non-claim fields must not fail the loader path."""
    raw = (
        "schema_version: 1\n"
        "receipt_type: atlas-core-work-package\n"
        "work_package_id: AS-SEC-001\n"
        "title: Harbor API work package\n"
        "status: done\n"
        "note: safe canary string \"AKIAFAKEFAKEFAKEFAKE\"\n"
    )
    extraction = extract_source("harbor-api", _entry(raw))
    assert extraction.candidate.outcome is CompilationOutcome.COMPLETE_CANDIDATE
    assert any(record.value == "Harbor API work package" for record in extraction.records)

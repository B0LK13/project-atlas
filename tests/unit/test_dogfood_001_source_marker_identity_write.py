"""DOGFOOD-001 — genesis identity allocation must not clobber marker formatting.

Authentic first-run dogfooding (`atlas discover` -> `atlas ingest` against a
real checkout) found that a project's first ingest allocates durable project
identity (AS-ID-001 "genesis") by re-serializing the *entire*
``.atlas-project.yaml`` marker through ``yaml.safe_dump`` -- silently
rewriting block lists to flow style, dropping blank lines, and normalizing
quote style, even though the CLI signaled nothing beyond the vault-side
ingest counts. The marker is human-authored, tracked source configuration,
not vault-owned state.

That mutation into the source tree is intended (see
``tests/integration/test_as_mvp_001_release_closure.py``'s
``_FIXED_PROJECT_UUIDS`` docstring: "AS-ID-001's 'genesis' design"). What was
not intended, and is not declared anywhere, is rewriting content that has
nothing to do with identity. These tests pin the fixed contract:

- genesis still allocates a fresh UUIDv4 and persists it in the marker;
- the diff against the marker's original bytes is the appended
  ``project_uuid`` line and nothing else;
- the allocation is reported back to the caller (result dict + CLI stdout),
  not just discoverable by diffing the checkout afterwards;
- a marker whose shape makes a bare append unsafe (flow-style / a YAML
  document-end marker) still ingests correctly, falling back to a full
  re-dump rather than failing genesis.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
import yaml

from project_atlas.cli import EXIT_OK, main

pytestmark = pytest.mark.integration

_MARKER_TEXT = """schema_version: 1

project:
  id: fixture-genesis
  name: Fixture Genesis
  aliases:
    - fixture
  type: documentation-platform
  status: active

discovery:
  documentation_roots:
    - .
  include:
    - "**/*.md"
  exclude:
    - ".git/**"

authority:
  primary:
    - "README.md"
  derived:
    - "generated/**"
"""


def _fixture(root: Path, marker_text: str = _MARKER_TEXT) -> Path:
    source = root / "source"
    source.mkdir(parents=True)
    (source / ".atlas-project.yaml").write_text(marker_text, encoding="utf-8")
    (source / "README.md").write_text("# Fixture Genesis\n", encoding="utf-8")
    return source


def _ingest(source: Path, vault: Path, tmp_path: Path) -> dict[str, object]:
    manifest = tmp_path / "manifest.json"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    from project_atlas.ingestion import ingest

    return ingest(manifest, vault, authorized_source_root=source)


def test_genesis_appends_marker_and_preserves_unrelated_bytes(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    marker = source / ".atlas-project.yaml"
    before = marker.read_bytes()

    result = _ingest(source, tmp_path / "vault", tmp_path)

    after = marker.read_bytes()
    assert after.startswith(before), "unrelated marker bytes must be preserved verbatim"
    added = after[len(before) :].decode("utf-8")
    parsed = yaml.safe_load(after.decode("utf-8"))
    project_uuid = parsed["project_uuid"]
    assert added == f"project_uuid: {project_uuid}\n"

    # Every other field survives unchanged (list style, blank lines, quoting).
    original = yaml.safe_load(before.decode("utf-8"))
    assert parsed == {**original, "project_uuid": project_uuid}

    # The allocation is reported back, not just discoverable via git diff.
    assert result["identity_allocated"] == ["fixture-genesis"]


def test_genesis_reported_on_cli_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _fixture(tmp_path)
    vault = tmp_path / "vault"
    manifest = tmp_path / "manifest.json"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    capsys.readouterr()
    assert (
        main(
            [
                "ingest",
                "--manifest",
                str(manifest),
                "--vault",
                str(vault),
                "--source",
                str(source),
            ]
        )
        == EXIT_OK
    )
    out = capsys.readouterr().out
    assert "identity allocated for: fixture-genesis" in out


def test_second_ingest_of_same_project_does_not_touch_marker_again(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    marker = source / ".atlas-project.yaml"
    vault = tmp_path / "vault"

    first = _ingest(source, vault, tmp_path)
    assert first["identity_allocated"] == ["fixture-genesis"]
    stamped = marker.read_bytes()

    # Re-discover (no source content changed) and re-ingest into a *second*
    # fresh vault bound to the same, now-stamped marker: no further marker
    # mutation, and nothing reported as newly allocated.
    second = _ingest(source, tmp_path / "vault2", tmp_path)
    assert marker.read_bytes() == stamped
    assert second["identity_allocated"] == []


def test_append_unsafe_marker_falls_back_to_full_dump(tmp_path: Path) -> None:
    # A YAML document-end marker makes a bare textual append invalid YAML;
    # genesis must still succeed via the whole-document fallback.
    flow_marker = (
        "schema_version: 1\n"
        'project: {id: fixture-flow, name: "Fixture Flow"}\n'
        "...\n"
    )
    source = _fixture(tmp_path, marker_text=flow_marker)
    marker = source / ".atlas-project.yaml"

    result = _ingest(source, tmp_path / "vault", tmp_path)

    assert result["identity_allocated"] == ["fixture-flow"]
    parsed = yaml.safe_load(marker.read_text(encoding="utf-8"))
    assert parsed["project"]["id"] == "fixture-flow"
    assert uuid.UUID(str(parsed["project_uuid"])).version == 4


def result_project_uuid(marker: Path) -> str:
    data = yaml.safe_load(marker.read_text(encoding="utf-8"))
    uuid = data["project_uuid"]
    assert isinstance(uuid, str)
    return uuid


def test_allocation_receipt_still_records_uuid_once(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    vault = tmp_path / "vault"
    result = _ingest(source, vault, tmp_path)
    project_uuid = result_project_uuid(source / ".atlas-project.yaml")
    receipt = vault / "receipts" / "source-lineage" / "project-fixture-genesis-allocation.json"
    assert receipt.is_file()
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["project_uuid"] == project_uuid
    assert payload["receipt_type"] == "project-identity-allocation"

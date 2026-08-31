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
- the diff against the marker's original bytes is the appended (or, for a
  marker with a trailing explicit document-end marker, inserted)
  ``project_uuid`` line and nothing else -- in the marker's own line
  ending, not always LF;
- the allocation is reported back to the caller via ``ingest()``'s
  ``identity_allocated`` result, not just discoverable by diffing the
  checkout afterwards (cli.py itself is outside the owner-approved
  exception scope and is deliberately untouched -- see the disclosure
  note below);
- only a marker with no line to attach a new sibling key to at all (a
  bare single-line flow-style root mapping) falls back to a full re-dump;
  every other shape challenged here -- comments, anchors/aliases, CRLF,
  no trailing newline, non-ASCII, a UTF-8 BOM, an explicit ``---``
  start and/or ``...`` end marker -- is byte-preserving.
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
    # newline="" disables Windows' universal-newline translation on write --
    # without it, every "\n" in a literal here would silently become "\r\n"
    # on disk, which would make these fixtures untestable for exact line
    # endings (see test_crlf_marker_appends_with_crlf, which deliberately
    # writes "\r\n" itself and needs that to survive unchanged).
    source = root / "source"
    source.mkdir(parents=True)
    (source / ".atlas-project.yaml").write_text(marker_text, encoding="utf-8", newline="")
    (source / "README.md").write_text("# Fixture Genesis\n", encoding="utf-8", newline="")
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


# DOGFOOD-001's disclosure is a structured `_log.info(...)` call inside
# ingestion.py (project_atlas.logging.configure_logging(propagate=False)) --
# not a cli.py stdout line: cli.py is outside the owner-approved exception
# scope (see WORKLOG.md), so it is intentionally left untouched. Per this
# repo's own established convention (test_sec_adv004_scan_b_highs.py:72-73:
# "logging StreamHandler bypasses pytest capsys/capfd/caplog under
# configure_logging(propagate=False)"), the log line's text is not
# pytest-asserted here; `identity_allocated` in ingest()'s return value
# (asserted below and in test_genesis_appends_marker_and_preserves_unrelated_bytes)
# is the structured, testable disclosure channel. The log line itself was
# verified manually against the real CLI (see the WORKLOG entry's captured
# `INFO project_atlas.ingestion: allocated durable project identity; ...`
# output).
def test_genesis_disclosed_in_ingest_result(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    vault = tmp_path / "vault"
    result = _ingest(source, vault, tmp_path)
    assert result["identity_allocated"] == ["fixture-genesis"]

    # A second, independent project in the same batch that already has a
    # uuid must not be reported as newly allocated.
    other = tmp_path / "other-source"
    other.mkdir()
    (other / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: other-proj\nproject_uuid: "
        "11111111-1111-4111-8111-111111111111\n",
        encoding="utf-8",
    )
    (other / "README.md").write_text("# Other\n", encoding="utf-8")
    other_result = _ingest(other, tmp_path / "vault-other", tmp_path)
    assert other_result["identity_allocated"] == []


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


def test_document_end_marker_insertion_preserves_bytes(tmp_path: Path) -> None:
    # A trailing explicit YAML document-end marker (`...`) makes a bare
    # append at end-of-file unsafe (nothing may follow a closed document),
    # but the field can still be inserted immediately before that marker's
    # line, byte-preserving everything else -- this must NOT fall back to
    # a full re-dump.
    marker_text = (
        "schema_version: 1\n"
        'project: {id: fixture-docend, name: "Fixture DocEnd"}\n'
        "...\n"
    )
    source = _fixture(tmp_path, marker_text=marker_text)
    marker = source / ".atlas-project.yaml"
    before = marker.read_bytes()

    result = _ingest(source, tmp_path / "vault", tmp_path)

    after = marker.read_bytes()
    assert result["identity_allocated"] == ["fixture-docend"]
    project_uuid = yaml.safe_load(after.decode("utf-8"))["project_uuid"]
    assert after == (
        before[: -len(b"...\n")]
        + f"project_uuid: {project_uuid}\n".encode()
        + b"...\n"
    )


def test_crlf_marker_appends_with_crlf(tmp_path: Path) -> None:
    # An appended LF-only line onto an otherwise-CRLF-authored marker would
    # itself be a small unrelated formatting inconsistency; the appended
    # line must match the file's own line ending.
    marker_text = "schema_version: 1\r\nproject:\r\n  id: fixture-crlf\r\n"
    source = _fixture(tmp_path, marker_text=marker_text)
    marker = source / ".atlas-project.yaml"
    before = marker.read_bytes()
    assert b"\r\n" in before and b"\n\n" not in before.replace(b"\r\n", b"")

    result = _ingest(source, tmp_path / "vault", tmp_path)

    after = marker.read_bytes()
    assert result["identity_allocated"] == ["fixture-crlf"]
    assert after.startswith(before)
    tail = after[len(before) :]
    project_uuid = yaml.safe_load(after.decode("utf-8"))["project_uuid"]
    assert tail == f"project_uuid: {project_uuid}\r\n".encode()


def test_explicit_null_placeholder_is_replaced_not_duplicated(tmp_path: Path) -> None:
    # data.get("project_uuid") is None for BOTH a genuinely absent key and
    # an explicit `project_uuid: null` placeholder line. Appending a second
    # `project_uuid:` line in the latter case would produce ambiguous
    # duplicate-key YAML (PyYAML's own last-wins reading happens to still
    # resolve it correctly, but stricter YAML consumers reject duplicate
    # keys outright) -- the existing line must be replaced in place instead.
    marker_text = "schema_version: 1\nproject:\n  id: fixture-nullplaceholder\nproject_uuid: null\n"
    source = _fixture(tmp_path, marker_text=marker_text)
    marker = source / ".atlas-project.yaml"

    result = _ingest(source, tmp_path / "vault", tmp_path)

    after = marker.read_text(encoding="utf-8")
    assert result["identity_allocated"] == ["fixture-nullplaceholder"]
    assert after.count("project_uuid:") == 1, after
    parsed = yaml.safe_load(after)
    assert uuid.UUID(str(parsed["project_uuid"])).version == 4
    # Every other line is untouched -- only the one project_uuid line changed.
    assert after.startswith("schema_version: 1\nproject:\n  id: fixture-nullplaceholder\n")


@pytest.mark.parametrize(
    "case_id,marker_text,project_id",
    [
        (
            "comments",
            "# top comment\n"
            "schema_version: 1  # inline comment\n"
            "project:\n"
            "  id: fixture-comments  # trailing, no final newline",
            "fixture-comments",
        ),
        (
            "anchors_aliases",
            "defaults: &d\n"
            "  retries: 3\n"
            "project:\n"
            "  id: fixture-anchors\n"
            "  policy: *d\n",
            "fixture-anchors",
        ),
        (
            "non_ascii",
            'schema_version: 1\nproject:\n  id: fixture-nonascii\n  name: "Projet étoile"\n',
            "fixture-nonascii",
        ),
        (
            "utf8_bom",
            "﻿schema_version: 1\nproject:\n  id: fixture-bom\n",
            "fixture-bom",
        ),
        (
            "no_trailing_newline",
            "schema_version: 1\nproject:\n  id: fixture-notrail",
            "fixture-notrail",
        ),
        (
            "explicit_doc_start",
            "---\nschema_version: 1\nproject:\n  id: fixture-docstart\n",
            "fixture-docstart",
        ),
    ],
)
def test_append_challenge_shapes_are_byte_preserving(
    tmp_path: Path, case_id: str, marker_text: str, project_id: str
) -> None:
    source = _fixture(tmp_path, marker_text=marker_text)
    marker = source / ".atlas-project.yaml"
    before = marker.read_bytes()

    result = _ingest(source, tmp_path / "vault", tmp_path)

    after = marker.read_bytes()
    assert result["identity_allocated"] == [project_id], case_id
    original = yaml.safe_load(before.decode("utf-8"))
    parsed = yaml.safe_load(after.decode("utf-8"))
    project_uuid = parsed["project_uuid"]
    assert parsed == {**original, "project_uuid": project_uuid}, case_id
    # Byte-preserving: `after` is exactly `before` (terminated with a
    # newline if it wasn't already) plus the one new field line.
    newline = b"\n"
    prefix = before if before.endswith(b"\n") or not before else before + newline
    assert after == prefix + f"project_uuid: {project_uuid}\n".encode(), case_id


def test_bare_flow_root_falls_back_to_full_dump(tmp_path: Path) -> None:
    # The one shape with no line to append or insert a new sibling key at:
    # the entire document is a single-line flow-style root mapping.
    # Genesis must still succeed via the whole-document fallback.
    flow_marker = '{schema_version: 1, project: {id: fixture-flow, name: "Fixture Flow"}}\n'
    source = _fixture(tmp_path, marker_text=flow_marker)
    marker = source / ".atlas-project.yaml"

    result = _ingest(source, tmp_path / "vault", tmp_path)

    assert result["identity_allocated"] == ["fixture-flow"]
    parsed = yaml.safe_load(marker.read_text(encoding="utf-8"))
    assert parsed["project"]["id"] == "fixture-flow"
    assert uuid.UUID(str(parsed["project_uuid"])).version == 4


def result_project_uuid(marker: Path) -> str:
    data = yaml.safe_load(marker.read_text(encoding="utf-8"))
    project_uuid = data["project_uuid"]
    assert isinstance(project_uuid, str)
    return project_uuid


def test_allocation_receipt_still_records_uuid_once(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    vault = tmp_path / "vault"
    result = _ingest(source, vault, tmp_path)
    assert result["identity_allocated"] == ["fixture-genesis"]
    project_uuid = result_project_uuid(source / ".atlas-project.yaml")
    receipt = vault / "receipts" / "source-lineage" / "project-fixture-genesis-allocation.json"
    assert receipt.is_file()
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["project_uuid"] == project_uuid
    assert payload["receipt_type"] == "project-identity-allocation"

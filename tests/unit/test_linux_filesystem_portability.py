"""Linux filesystem semantics across the discover -> ingest boundary.

Linux permits filenames the shared portable path contract
(``atlas_contracts.paths``, CODEX-SEC-004/014/017/018) refuses on every
platform -- colons, control characters, Windows reserved basenames -- and
treats a backslash as an ordinary filename character rather than a separator.
It also routinely exposes files whose content the caller cannot read.

None of these may abort a run. Before this suite, ``discover`` emitted such
paths happily and ``ingest`` then failed the whole run closed on them, so a
single legally-named file made the pipeline permanently unrunnable on Linux;
an unreadable file aborted ``discover`` outright. They are now recorded as
excluded evidence -- never silently dropped, never ingested.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_OK, main
from project_atlas.ingestion import ingest

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="POSIX-only filenames and permission modes"
)

#: Legal on Linux, unrepresentable under the portable path contract.
NON_PORTABLE_NAMES = (
    "co:lon.md",  # Windows drive / alternate-data-stream separator
    "new\nline.md",  # control character
    "back\\slash.md",  # separator under the contract, a name character here
    "aux.md",  # Windows reserved device basename
)


def _write_source(root: Path) -> Path:
    """Build a source tree exercising Linux-only filesystem behaviour."""
    docs = root / "docs"
    docs.mkdir(parents=True)
    (root / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: fs-portability\n", encoding="utf-8"
    )
    (root / "README.md").write_text("# Readme\n", encoding="utf-8")
    for name in NON_PORTABLE_NAMES:
        (docs / name).write_text(f"# {name}\n", encoding="utf-8")
    return root


def _discover(tmp_path: Path, source: Path) -> dict[str, object]:
    manifest = tmp_path / "manifest.json"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    return json.loads(manifest.read_text(encoding="utf-8"))


def _by_path(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    sources = manifest["sources"]
    assert isinstance(sources, list)
    return {str(record["path"]): record for record in sources}


def test_non_portable_names_are_excluded_evidence_not_fatal(tmp_path: Path) -> None:
    """Each unrepresentable name is recorded as excluded, with a reason."""
    records = _by_path(_discover(tmp_path, _write_source(tmp_path / "source")))

    for name in NON_PORTABLE_NAMES:
        record = records[f"docs/{name}"]
        assert record["classification_state"] == "excluded", name
        assert record["exclusion_reason"] == "non-portable-path", name

    # Ordinary names are untouched by the guard.
    assert records["README.md"]["exclusion_reason"] is None
    assert records["README.md"]["classification_state"] != "excluded"


def test_pipeline_completes_with_non_portable_names(tmp_path: Path) -> None:
    """The full pipeline runs green; only representable sources are ingested."""
    source = _write_source(tmp_path / "source")
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"

    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
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
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK

    ingested = {
        path.read_text(encoding="utf-8")
        for path in (vault / "sources" / "imported-documents").rglob("*.md")
    }
    for name in NON_PORTABLE_NAMES:
        assert not any(f"# {name}" in body for body in ingested), name


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission bits")
def test_unreadable_file_is_recorded_not_fatal(tmp_path: Path) -> None:
    """An unreadable file yields real metadata, no digest, and no abort."""
    source = _write_source(tmp_path / "source")
    unreadable = source / "docs" / "unreadable.md"
    unreadable.write_text("# unreadable\n", encoding="utf-8")
    size = unreadable.stat().st_size
    unreadable.chmod(0o000)
    try:
        record = _by_path(_discover(tmp_path, source))["docs/unreadable.md"]
    finally:
        # Leave the tree removable for tmp_path teardown.
        unreadable.chmod(0o644)

    assert record["exclusion_reason"] == "unreadable"
    assert record["classification_state"] == "excluded"
    assert record["sha256"] is None, "content was never read, so it must not be claimed"
    assert record["size_bytes"] == size, "stat metadata is real, not invented"


def test_case_variant_filenames_stay_distinct(tmp_path: Path) -> None:
    """Linux is case-sensitive: variants are separate sources, never merged."""
    source = _write_source(tmp_path / "source")
    (source / "readme.md").write_text("# lower\n", encoding="utf-8")
    (source / "ReadMe.md").write_text("# mixed\n", encoding="utf-8")

    records = _by_path(_discover(tmp_path, source))

    variants = {path for path in records if path.lower() == "readme.md"}
    assert variants == {"README.md", "readme.md", "ReadMe.md"}
    ids = {str(records[path]["source_id"]) for path in variants}
    assert len(ids) == 3, "case variants must not collapse onto one source identity"


def test_symlinks_and_special_files_are_never_sources(tmp_path: Path) -> None:
    """Only regular files are evidence: no symlink, FIFO or device follow."""
    source = _write_source(tmp_path / "source")
    docs = source / "docs"
    (docs / "link-to-readme.md").symlink_to(source / "README.md")
    (docs / "link-outside.md").symlink_to(tmp_path / "outside.md")
    (docs / "dir-loop").symlink_to(source)
    os.mkfifo(docs / "fifo.md")

    records = _by_path(_discover(tmp_path, source))

    for name in ("link-to-readme.md", "link-outside.md", "fifo.md"):
        assert f"docs/{name}" not in records, name
    assert not any(path.startswith("docs/dir-loop") for path in records)


def test_symlinked_source_root_is_refused_with_the_physical_path(tmp_path: Path) -> None:
    """The authorized root stays symlink-free, but says which path to use.

    Refusing a symlinked root is deliberate (CODEX-SEC-001 / SEC-SCAN-A-014:
    resolve() would dereference it and defeat a later check). Symlinked
    project roots are ordinary on Linux, so the refusal must name the
    physical path rather than leave an existing directory unexplained.
    """
    source = _write_source(tmp_path / "source")
    link = tmp_path / "link-source"
    link.symlink_to(source)
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["discover", "--source", str(link), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK

    with pytest.raises(ValueError) as excinfo:
        ingest(manifest, vault, authorized_source_root=link)

    message = str(excinfo.value)
    assert "non-symlink directory" in message
    assert str(source) in message, "the physical path must be named"

    # The named physical path is genuinely accepted.
    assert ingest(manifest, vault, authorized_source_root=source)["documents_ingested"] >= 1


def test_non_utf8_filename_is_reported_not_fatal(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A filename that is not valid UTF-8 is skipped loudly, not fatally.

    Linux filenames are byte strings. Such a name decodes to lone surrogates
    and cannot be encoded into the UTF-8 JSON manifest, which previously
    aborted the entire run with a bare codec error.
    """
    source = _write_source(tmp_path / "source")
    raw_name = os.path.join(os.fsencode(source / "docs"), b"bad-\xff-name.md")
    with open(raw_name, "wb") as handle:
        handle.write(b"# undecodable name\n")

    with caplog.at_level("WARNING"):
        records = _by_path(_discover(tmp_path, source))

    assert "README.md" in records, "the rest of the tree still discovers"
    assert not any("bad-" in path for path in records), "never recorded as a source claim"
    assert any(
        "undecodable filename" in message for message in caplog.messages
    ), "the skip must be reported, not silent"

"""Unit tests for the internal normalization subsystem."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

SUBPROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SUBPROJECT / "scripts"))
sys.path.insert(0, str(SUBPROJECT))

import capture_event  # noqa: E402
from internal import process_runner, provenance, verification  # noqa: E402

PYTHON = sys.executable


class TestProcessRunner:
    def test_success(self) -> None:
        result = process_runner.run_command(
            [PYTHON, "-c", "print('hello')"], timeout_seconds=10,
            redact=capture_event.redact,
        )
        assert result.ok
        assert result.stdout.strip() == "hello"
        assert result.attempts == 1

    def test_executable_missing(self) -> None:
        result = process_runner.run_command(
            ["/nonexistent/binary"], timeout_seconds=5, redact=capture_event.redact
        )
        assert result.category == process_runner.CATEGORY_EXECUTABLE_MISSING

    def test_timeout(self) -> None:
        result = process_runner.run_command(
            [PYTHON, "-c", "import time; time.sleep(30)"],
            timeout_seconds=0.3, redact=capture_event.redact,
        )
        assert result.category == process_runner.CATEGORY_TIMEOUT

    def test_nonzero_exit_and_retry_attempts(self) -> None:
        result = process_runner.run_command(
            [PYTHON, "-c", "import sys; sys.exit(1)"],
            timeout_seconds=10, redact=capture_event.redact, retries=2,
        )
        assert result.category == process_runner.CATEGORY_PROCESS_FAILED
        assert result.attempts == 3

    def test_output_is_redacted(self) -> None:
        result = process_runner.run_command(
            [PYTHON, "-c", "import sys; sys.stderr.write('AKIAIOSFODNN7EXAMPLE')"],
            timeout_seconds=10, redact=capture_event.redact,
        )
        assert "AKIAIOSFODNN7EXAMPLE" not in result.stderr

    def test_missing_executable_not_retried(self) -> None:
        result = process_runner.run_command(
            ["/nonexistent/binary"], timeout_seconds=5,
            redact=capture_event.redact, retries=3,
        )
        assert result.attempts == 1

    def test_command_version(self) -> None:
        version = process_runner.command_version(
            PYTHON, timeout_seconds=10, redact=capture_event.redact
        )
        assert version.startswith("Python")
        missing = process_runner.command_version(
            "/nonexistent/binary", timeout_seconds=5, redact=capture_event.redact
        )
        assert missing == "unknown"


class TestProvenance:
    def test_sha256_streaming(self, tmp_path: Path) -> None:
        target = tmp_path / "data.bin"
        payload = b"x" * (3 * 1024 * 1024 + 7)
        target.write_bytes(payload)
        assert provenance.sha256_file(target) == hashlib.sha256(payload).hexdigest()

    def test_split_document_plain_and_fenced(self) -> None:
        doc = "---\ntype: X\n---\nbody\n"
        frontmatter, body = provenance.split_document(doc)
        assert "type: X" in frontmatter
        assert body.startswith("body")
        fenced = "````markdown\n" + doc + "\n````\n"
        frontmatter2, _ = provenance.split_document(fenced)
        assert frontmatter2 == frontmatter

    def test_split_document_rejects_garbage(self) -> None:
        with pytest.raises(ValueError):
            provenance.split_document("# no frontmatter\n")
        with pytest.raises(ValueError):
            provenance.split_document("---\nunterminated")

    def test_inject_provenance_idempotent(self) -> None:
        doc = "---\ntype: Agent Work Event\n---\n\n# Title\n"
        prov = provenance.Provenance(
            raw_event_id="E1", raw_event_hash="abc", normalized_at="t",
            tool="mda", command_version="1", command_arguments=("mda",),
            skill="s", provider="p", output_mode="sibling",
            verification_status="verified", verified_at="t2",
        )
        once = provenance.inject_provenance(doc, prov)
        twice = provenance.inject_provenance(once, prov)
        assert once == twice
        assert once.count("atlas_provenance:") == 1
        assert 'raw_event_id: "E1"' in once
        assert "schema_version: 1" in once  # integers unquoted

    def test_atomic_replace(self, tmp_path: Path) -> None:
        target = tmp_path / "f.md"
        target.write_text("old", encoding="utf-8")
        provenance.atomic_replace(target, "new")
        assert target.read_text(encoding="utf-8") == "new"
        assert list(tmp_path.glob("*.tmp")) == []


class TestVerification:
    def test_snapshot_missing_dir(self, tmp_path: Path) -> None:
        assert verification.snapshot(tmp_path / "nope") == frozenset()

    def test_ensure_inside_root(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        verification.ensure_inside_root(root, root / "a" / "b.md")
        with pytest.raises(ValueError, match="outside root"):
            verification.ensure_inside_root(root, tmp_path / "escape.md")

    def test_missing_output_flagged(self, tmp_path: Path) -> None:
        result = verification.verify_output(
            tmp_path / "missing.md",
            root=tmp_path, raw_event_id="E1",
            watch_directory=tmp_path, before=[],
        )
        assert not result.verified
        assert any("missing" in p for p in result.problems)

"""AS-OBSIDIAN-CAPTURE-001 — end-to-end capture journeys.

Exercises the architecture's acceptance criteria (§66) across the real CLI
adapter, the capture service, and the Obsidian projection, including the
concurrency contract of §49 and the boundary against the frozen
conversational-capture plane.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from project_atlas.capture_sources import build_capture_request
from project_atlas.cli import main
from project_atlas.conversation_capture import (
    ConversationCaptureError,
    capture_conversation,
)
from project_atlas.obsidian_capture import CAPTURE_DIR, capture, read_raw_content

pytestmark = pytest.mark.integration


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "projects" / "harbor-api").mkdir(parents=True)
    (root / "generated").mkdir(parents=True)
    return root


# --------------------------------------------------------------------------
# §66 — source acquisition converges on one service
# --------------------------------------------------------------------------


def test_text_stdin_and_clipboard_reach_the_same_capture_service(
    vault: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Architecture §66: every adapter converges on one CaptureService.

    The transport an operator happened to use is *not* part of logical
    identity, so the same bytes arriving by ``--text``, ``--stdin`` and
    ``--clipboard`` deduplicate to a single capture rather than three.
    """
    payload = "identical payload across adapters"

    assert main(["capture", "text", "--vault", str(vault), "--text", payload, "--json"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["duplicate"] is False

    monkeypatch.setattr("project_atlas.cli.read_stdin_text", lambda: payload)
    assert main(["capture", "text", "--vault", str(vault), "--stdin", "--json"]) == 0
    from_stdin = json.loads(capsys.readouterr().out)

    monkeypatch.setattr("project_atlas.cli.read_clipboard_text", lambda: payload)
    assert main(["capture", "text", "--vault", str(vault), "--clipboard", "--json"]) == 0
    from_clipboard = json.loads(capsys.readouterr().out)

    assert from_stdin["duplicate"] is True
    assert from_clipboard["duplicate"] is True
    assert from_stdin["capture_id"] == first["capture_id"]
    assert from_clipboard["capture_id"] == first["capture_id"]

    assert len(list((vault / CAPTURE_DIR).glob("rcap-*.json"))) == 1
    notes = list((vault / "generated" / "obsidian" / "captures").rglob("*.md"))
    assert len(notes) == 1
    assert read_raw_content(vault, first["capture_id"]) == payload


def test_adapter_is_recorded_as_provenance_not_identity(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The adapter is still preserved on the record for traceability (§9)."""
    assert (
        main(
            [
                "capture",
                "text",
                "--vault",
                str(vault),
                "--text",
                "provenance payload",
                "--json",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    record = json.loads(
        (vault / CAPTURE_DIR / f"{report['capture_id']}.json").read_text(encoding="utf-8")
    )
    assert record["source_adapter"] == "text"
    assert record["provenance"]["derived_from"] == "text:unknown"


def test_cli_requires_exactly_one_source(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["capture", "text", "--vault", str(vault)]) == 1
    assert "exactly one of --text, --stdin, or --clipboard" in capsys.readouterr().out

    assert (
        main(["capture", "text", "--vault", str(vault), "--text", "x", "--stdin"]) == 1
    )
    capsys.readouterr()


# --------------------------------------------------------------------------
# §66 — full journey: capture -> projection -> provenance -> recovery
# --------------------------------------------------------------------------


def test_full_capture_journey_through_the_cli(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "capture",
            "text",
            "--vault",
            str(vault),
            "--project",
            "harbor-api",
            "--source-type",
            "conversation",
            "--application",
            "chatgpt",
            "--title",
            "Atlas Obsidian Integration",
            "--text",
            "Owner decided: Model A. Raw evidence stays canonical.",
            "--json",
        ]
    )
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "ok"
    assert report["project_id"] == "harbor-api"
    assert report["classification"] == "conversation"
    note_path = report["outputs"][0]["relative_path"]
    assert note_path.startswith("10 Projects/harbor-api/Conversations/")

    note = vault / "generated" / "obsidian" / "captures" / note_path
    assert note.is_file()
    assert "Atlas Obsidian Integration" in note.read_text(encoding="utf-8")

    # Provenance closes: note -> capture record -> raw evidence.
    assert main(
        ["capture", "show", "--vault", str(vault), "--capture-id", report["capture_id"]]
    ) == 0
    assert (
        capsys.readouterr().out
        == "Owner decided: Model A. Raw evidence stays canonical."
    )

    # The capture is listed as quarantined evidence, never as authority.
    assert main(["capture", "raw-list", "--vault", str(vault), "--json"]) == 0
    listing = json.loads(capsys.readouterr().out)
    assert listing["count"] == 1
    assert listing["authority"] is False
    assert listing["captures"][0]["status"] == "quarantined-evidence"


def test_duplicate_capture_via_cli_reports_and_creates_nothing(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ["capture", "text", "--vault", str(vault), "--text", "same thing"]
    assert main(args) == 0
    capsys.readouterr()
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "Duplicate capture detected." in out
    assert "No duplicate note created." in out
    assert len(list((vault / CAPTURE_DIR).glob("rcap-*.json"))) == 1


def test_partial_render_fails_loud_but_preserves_evidence(
    vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Evidence survives; the operator is still told the projection failed."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("file", encoding="utf-8")

    exit_code = main(
        [
            "capture",
            "text",
            "--vault",
            str(vault),
            "--text",
            "durable",
            "--obsidian-vault",
            str(blocker),
        ]
    )
    assert exit_code == 1, "a partial result must not look like success"
    out = capsys.readouterr().out
    assert "Raw        : persisted" in out
    assert "retry with : atlas capture retry" in out

    capture_id = json.loads(
        (vault / CAPTURE_DIR / "latest.json").read_text(encoding="utf-8")
    )["capture_id"]
    assert read_raw_content(vault, capture_id) == "durable"

    assert main(["capture", "retry", "--vault", str(vault), "--capture-id", capture_id]) == 0


def test_no_render_persists_evidence_only(
    vault: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            ["capture", "text", "--vault", str(vault), "--text", "evidence", "--no-render"]
        )
        == 0
    )
    capsys.readouterr()
    assert not (vault / "generated" / "obsidian" / "captures").exists()
    assert list((vault / CAPTURE_DIR).glob("rcap-*.txt"))


# --------------------------------------------------------------------------
# §49 — concurrent identical captures must not duplicate
# --------------------------------------------------------------------------


def test_concurrent_identical_captures_produce_one_capture(vault: Path) -> None:
    request = build_capture_request(content="racing payload")
    results: list[dict[str, object]] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(8)

    def worker() -> None:
        try:
            barrier.wait(timeout=10)
            results.append(capture(vault, request))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == [], f"concurrent capture raised: {errors}"
    assert len(results) == 8
    assert len({str(item["capture_id"]) for item in results}) == 1
    assert len(list((vault / CAPTURE_DIR).glob("rcap-*.json"))) == 1
    notes = list((vault / "generated" / "obsidian" / "captures").rglob("*.md"))
    assert len(notes) == 1, "a race must not yield duplicate notes"


# --------------------------------------------------------------------------
# Boundary against the frozen conversational-capture plane (D-042)
# --------------------------------------------------------------------------


def test_raw_capture_does_not_relax_the_transcript_prohibition(vault: Path) -> None:
    """conversation_capture still refuses raw transcripts (D-042/CAPTURE-002)."""
    with pytest.raises(ConversationCaptureError) as excinfo:
        capture_conversation(
            vault,
            {
                "source_provider": "chatgpt",
                "summary": "a summary",
                "transcript": "raw transcript body",
                "capture_items": [{"item_type": "idea", "text": "x"}],
            },
            requested_project_id="harbor-api",
        )
    assert excinfo.value.code == "RAW_TRANSCRIPT_FORBIDDEN"


def test_raw_captures_are_not_promoted_into_the_knowledge_inbox(vault: Path) -> None:
    """Raw evidence stays in its own quarantine plane; promotion is explicit."""
    result = capture(vault, build_capture_request(content="evidence only"))
    assert result["status"] == "ok"
    inbox = vault / "generated" / "ops" / "inbox"
    assert not inbox.exists() or not list(inbox.glob("*.json"))

    record = json.loads(
        (vault / CAPTURE_DIR / f"{result['capture_id']}.json").read_text(encoding="utf-8")
    )
    assert record["authority"]["level"] == "quarantined-evidence"
    assert record["honesty"]["capture_is_authority"] is False


def test_capture_writes_nothing_outside_the_vault_by_default(
    vault: Path, tmp_path: Path
) -> None:
    """INV-005 / repo convention: no writes outside --vault without opt-in."""
    before = {path for path in tmp_path.rglob("*") if path.is_file()}
    capture(vault, build_capture_request(content="contained"))
    after = {path for path in tmp_path.rglob("*") if path.is_file()}
    assert all(str(path).startswith(str(vault)) for path in after - before)


def test_external_obsidian_vault_is_opt_in_and_contained(
    vault: Path, tmp_path: Path
) -> None:
    external = tmp_path / "ObsidianVault"
    external.mkdir()
    result = capture(
        vault,
        build_capture_request(content="external projection"),
        obsidian_root=external,
    )
    assert result["status"] == "ok"
    note = next(external.rglob("*.md"))
    assert note.is_relative_to(external)
    # Raw evidence still lives in the Atlas vault, never only in Obsidian.
    assert read_raw_content(vault, result["capture_id"]) == "external projection"

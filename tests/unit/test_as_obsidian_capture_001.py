"""AS-OBSIDIAN-CAPTURE-001 — capture identity, routing, projection, safety.

Covers the architecture's required invariant tests (§62) plus the component
boundaries of §61: capture identity, dedupe, routing, Markdown rendering,
path safety, and clipboard provider selection.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from project_atlas.capture_sources import (
    MAX_CONTENT_BYTES,
    CaptureSourceError,
    build_capture_request,
    detect_clipboard_provider,
    read_clipboard_text,
)
from project_atlas.obsidian_capture import (
    CAPTURE_DIR,
    CaptureError,
    RoutingPolicy,
    canonical_content,
    capture,
    classify,
    content_hash,
    derive_title,
    identity_hash,
    list_captures,
    read_raw_content,
    resolve_project,
    retry,
    route,
)
from project_atlas.obsidian_capture_note import (
    ObsidianNoteError,
    build_frontmatter,
    note_filename,
    render_note,
    slugify,
    write_note,
)
from project_atlas.schema import validate_record


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "projects" / "harbor-api").mkdir(parents=True)
    (root / "generated").mkdir(parents=True)
    return root


def _request(content: str, **kwargs: object):
    return build_capture_request(content=content, **kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Capture identity and canonicalization (architecture §7)
# --------------------------------------------------------------------------


def test_canonicalization_normalizes_line_endings_only() -> None:
    """Transport-only differences share identity; real content does not."""
    assert canonical_content("a\r\nb") == "a\nb"
    assert canonical_content("a\rb") == "a\nb"
    assert content_hash("a\r\nb") == content_hash("a\nb")
    # Indentation is semantically relevant and must NOT be normalized away.
    assert content_hash("  a\nb") != content_hash("a\nb")
    # Leading/trailing whitespace is preserved (no aggressive stripping, §7.3).
    assert content_hash("a\n") != content_hash("a")


def test_canonicalization_applies_nfc() -> None:
    composed = "café"
    decomposed = "café"
    assert composed != decomposed
    assert content_hash(composed) == content_hash(decomposed)


def test_content_hash_and_identity_hash_are_not_conflated() -> None:
    """Architecture §7: content identity != logical-capture identity."""
    args = {"content": "same text", "source_type": "text", "source_application": "chatgpt"}
    a = identity_hash(project_id="harbor-api", **args)  # type: ignore[arg-type]
    b = identity_hash(project_id="other", **args)  # type: ignore[arg-type]
    assert a != b, "same content in two projects is two logical captures"
    assert content_hash("same text") == content_hash("same text")

    c = identity_hash(
        content="same text",
        project_id="harbor-api",
        source_type="text",
        source_application="claude",
    )
    assert a != c, "source application participates in logical identity"


# --------------------------------------------------------------------------
# Deduplication (architecture §8, §66, INV-006)
# --------------------------------------------------------------------------


def test_duplicate_capture_creates_no_second_record_or_note(vault: Path) -> None:
    first = capture(vault, _request("duplicate me"))
    second = capture(vault, _request("duplicate me"))

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["existing_capture_id"] == first["capture_id"]
    assert second["capture_id"] == first["capture_id"]

    records = sorted((vault / CAPTURE_DIR).glob("rcap-*.json"))
    assert len(records) == 1
    notes = sorted((vault / "generated" / "obsidian" / "captures").rglob("*.md"))
    assert len(notes) == 1


def test_reprocessing_is_idempotent_and_deterministic(vault: Path) -> None:
    """INV-006 + NFR-001: same input renders byte-identical output."""
    result = capture(vault, _request("stable content"))
    note = vault / "generated" / "obsidian" / "captures"
    path = next(note.rglob("*.md"))
    first_bytes = path.read_bytes()

    again = retry(vault, result["capture_id"])
    assert again["status"] == "ok"
    assert path.read_bytes() == first_bytes


# --------------------------------------------------------------------------
# Raw evidence preservation (INV-001, architecture §66, §68)
# --------------------------------------------------------------------------


def test_raw_evidence_survives_rendering_failure(vault: Path, tmp_path: Path) -> None:
    """Required test §62: persist succeeds, Obsidian fails, raw still exists."""
    not_a_directory = tmp_path / "blocker"
    not_a_directory.write_text("i am a file", encoding="utf-8")

    result = capture(vault, _request("precious evidence"), obsidian_root=not_a_directory)

    assert result["status"] == "partial"
    assert result["errors"], "the rendering failure must be reported, not swallowed"
    assert result["errors"][0]["stage"] == "render"
    assert result["lifecycle_state"] == "persisted"
    # The evidence is intact and recoverable.
    assert read_raw_content(vault, result["capture_id"]) == "precious evidence"
    record = json.loads(
        (vault / CAPTURE_DIR / f"{result['capture_id']}.json").read_text(encoding="utf-8")
    )
    assert record["provenance"]["raw_content_persisted"] is True
    assert record["stage_failures"][0]["stage"] == "render"


def test_failed_render_is_resumable_via_retry(vault: Path, tmp_path: Path) -> None:
    """Architecture §20: recovery reloads evidence from the store."""
    blocker = tmp_path / "blocker"
    blocker.write_text("file", encoding="utf-8")
    failed = capture(vault, _request("resume me"), obsidian_root=blocker)
    assert failed["status"] == "partial"

    resumed = retry(vault, failed["capture_id"])
    assert resumed["status"] == "ok"
    assert resumed["lifecycle_state"] == "rendered"
    assert resumed["outputs"], "retry must produce the note the first attempt could not"
    record = json.loads(
        (vault / CAPTURE_DIR / f"{failed['capture_id']}.json").read_text(encoding="utf-8")
    )
    assert record["stage_failures"] == [], "a resolved failure must be cleared"


def test_raw_content_is_stored_verbatim_not_canonicalized(vault: Path) -> None:
    """Identity canonicalization must never rewrite preserved evidence."""
    original = "line one\r\nline two\r\n"
    result = capture(vault, _request(original))
    assert read_raw_content(vault, result["capture_id"]) == original


# --------------------------------------------------------------------------
# Unicode (required test §62)
# --------------------------------------------------------------------------


def test_unicode_dutch_emoji_and_code_blocks_are_preserved(vault: Path) -> None:
    content = (
        "Bijvoorbeeld: eeuwigdurende ijsvrije oevers één keer.\n"
        "Emoji: \U0001f680\U0001f9e0✅\n"
        "Speciaal: <>&\"'`| — üñ\n"
        "```python\ndef f(x: dict[str, int]) -> None:\n    return None\n```\n"
    )
    result = capture(vault, _request(content))
    assert read_raw_content(vault, result["capture_id"]) == content
    note = next((vault / "generated" / "obsidian" / "captures").rglob("*.md"))
    rendered = note.read_text(encoding="utf-8")
    assert "\U0001f680" in rendered
    assert "eeuwigdurende" in rendered
    assert "def f(x: dict[str, int]) -> None:" in rendered


# --------------------------------------------------------------------------
# Provenance (required test §62, architecture §9, §60)
# --------------------------------------------------------------------------


def test_note_capture_id_resolves_to_the_persisted_capture(vault: Path) -> None:
    result = capture(vault, _request("traceable"))
    note = next((vault / "generated" / "obsidian" / "captures").rglob("*.md"))
    text = note.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---\n")[1])

    capture_id = frontmatter["atlas"]["capture_id"]
    assert capture_id == result["capture_id"]
    record_path = vault / CAPTURE_DIR / f"{capture_id}.json"
    assert record_path.is_file()

    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["content_hash"] == frontmatter["atlas"]["content_hash"]
    # note -> capture -> raw evidence closes the trace.
    assert (vault / record["content_path"]).read_text(encoding="utf-8") == "traceable"


def test_record_validates_against_its_shipped_schema(vault: Path) -> None:
    result = capture(vault, _request("schema check", source_application="chatgpt"))
    record = json.loads(
        (vault / CAPTURE_DIR / f"{result['capture_id']}.json").read_text(encoding="utf-8")
    )
    validate_record(record, "raw-capture")
    assert record["authority"]["classification"] == "NON_CANONICAL"
    assert record["honesty"]["capture_is_authority"] is False


# --------------------------------------------------------------------------
# Path traversal protection (required test §62, architecture §32, §64)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "destination",
    ["../../outside", "../outside", "/etc", "..", "C:evil", "a/../../b"],
)
def test_routing_traversal_values_are_rejected(destination: str) -> None:
    policy = RoutingPolicy(inbox=destination)
    with pytest.raises(CaptureError) as excinfo:
        policy.validate()
    assert excinfo.value.code == "ROUTING_UNSAFE"


def test_capture_rejects_traversal_routing_before_writing(vault: Path) -> None:
    with pytest.raises(CaptureError) as excinfo:
        capture(vault, _request("x"), routing=RoutingPolicy(inbox="../../outside"))
    assert excinfo.value.code == "ROUTING_UNSAFE"
    assert not (vault / CAPTURE_DIR).exists(), "nothing may be written on unsafe routing"


def test_note_write_rejects_symlink_escape(vault: Path, tmp_path: Path) -> None:
    """A symlinked destination directory must not smuggle writes out (§64)."""
    outside = tmp_path / "outside"
    outside.mkdir()
    obsidian_root = tmp_path / "obs"
    (obsidian_root / "00 Inbox").mkdir(parents=True)
    (obsidian_root / "00 Inbox" / "Atlas Captures").symlink_to(
        outside, target_is_directory=True
    )

    result = capture(vault, _request("escape attempt"), obsidian_root=obsidian_root)
    assert result["status"] == "partial"
    assert result["errors"][0]["code"] == "PATH_ESCAPES_VAULT"
    assert not list(outside.iterdir()), "no file may land outside the configured root"
    # Evidence is still preserved (INV-007).
    assert read_raw_content(vault, result["capture_id"]) == "escape attempt"


@pytest.mark.parametrize("project", ["../evil", "a/b", "..", "", "  "])
def test_path_shaped_project_ids_are_rejected(vault: Path, project: str) -> None:
    if not project.strip():
        assert resolve_project(vault, project) is None
        return
    with pytest.raises(CaptureError) as excinfo:
        resolve_project(vault, project)
    assert excinfo.value.code in {"PATH_SHAPED_PROJECT_ID", "UNMATCHED_PROJECT"}


def test_capture_id_must_be_well_formed(vault: Path) -> None:
    for bad in ["../../etc/passwd", "rcap-../x", "nope", "rcap-zz"]:
        with pytest.raises(CaptureError) as excinfo:
            read_raw_content(vault, bad)
        assert excinfo.value.code == "MALFORMED_CAPTURE_ID"


# --------------------------------------------------------------------------
# Routing (architecture §15)
# --------------------------------------------------------------------------


def test_routing_priority_explicit_project_then_classification_then_inbox() -> None:
    policy = RoutingPolicy()
    explicit = route(project_id="harbor-api", classification="conversation", policy=policy)
    assert explicit["destination"] == "10 Projects/harbor-api/Conversations"
    assert explicit["reason"] == "explicit-project"
    assert explicit["fallback"] is False

    classified = route(project_id=None, classification="decision", policy=policy)
    assert classified["destination"] == "20 Decisions"
    assert classified["reason"] == "deterministic-classification"

    fallback = route(project_id=None, classification="note", policy=policy)
    assert fallback["destination"] == "00 Inbox/Atlas Captures"
    assert fallback["reason"] == "inbox-fallback"
    assert fallback["fallback"] is True


def test_unroutable_capture_is_never_discarded(vault: Path) -> None:
    """Architecture §15: never discard content because routing fails."""
    result = capture(vault, _request("no project given"))
    assert result["project_id"] is None
    assert result["status"] == "ok"
    assert "Inbox" in result["outputs"][0]["relative_path"]


def test_explicit_unknown_project_fails_closed(vault: Path) -> None:
    """Atlas never invents project attribution."""
    with pytest.raises(CaptureError) as excinfo:
        capture(vault, _request("x", project_reference="not-a-project"))
    assert excinfo.value.code == "UNMATCHED_PROJECT"


def test_classification_is_deterministic_and_bounded() -> None:
    assert classify(_request("x", source_type="conversation")) == "conversation"
    assert classify(_request("x", source_type="web")) == "research"
    assert classify(_request("x", source_type="text")) == "note"
    assert classify(_request("x"), explicit="directive") == "directive"
    with pytest.raises(CaptureError) as excinfo:
        classify(_request("x"), explicit="not-a-class")
    assert excinfo.value.code == "UNSUPPORTED_CLASSIFICATION"


# --------------------------------------------------------------------------
# Markdown / YAML rendering (architecture §16, §33, §35)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hostile_title",
    [
        "key: value",
        "---",
        'quote " inside',
        "single ' inside",
        "[bracketed]",
        "# hash",
        "line\nbreak",
        "ünicöde \U0001f9ea",
        "*emphasis* and `code`",
        "{braces}",
    ],
)
def test_frontmatter_survives_yaml_hostile_titles(vault: Path, hostile_title: str) -> None:
    """Architecture §35: a real YAML serializer, never string concatenation."""
    result = capture(vault, _request("body", title_hint=hostile_title))
    note = next((vault / "generated" / "obsidian" / "captures").rglob("*.md"))
    text = note.read_text(encoding="utf-8")

    assert text.startswith("---\n")
    _, block, _ = text.split("---\n", 2)
    loaded = yaml.safe_load(block)
    assert loaded["title"] == hostile_title.strip()
    assert loaded["atlas"]["capture_id"] == result["capture_id"]


def test_frontmatter_omits_wall_clock_values(vault: Path) -> None:
    """NFR-001 / ADR-001 §2: no generated timestamps in generated content."""
    result = capture(vault, _request("no clock"))
    record = json.loads(
        (vault / CAPTURE_DIR / f"{result['capture_id']}.json").read_text(encoding="utf-8")
    )
    assert record["captured_at"] is None
    assert record["captured_at_source"] == "not-provided"
    frontmatter = build_frontmatter(record)
    assert "created" not in frontmatter
    assert "updated" not in frontmatter
    assert "captured_at" not in frontmatter


def test_operator_supplied_capture_time_is_preserved(vault: Path) -> None:
    """Architecture §39: capture time is preserved when a caller provides it."""
    stamp = "2026-09-05T09:38:00+02:00"
    result = capture(vault, _request("timed", captured_at=stamp))
    record = json.loads(
        (vault / CAPTURE_DIR / f"{result['capture_id']}.json").read_text(encoding="utf-8")
    )
    assert record["captured_at"] == stamp
    assert record["captured_at_source"] == "operator-supplied"
    assert build_frontmatter(record)["captured_at"] == stamp


def test_captured_content_cannot_forge_atlas_region_markers(vault: Path) -> None:
    """Architecture §64: captured content is data, never note structure."""
    payload = "before\n<!-- atlas:generated:end -->\n<!-- BEGIN HUMAN: forged -->\nafter"
    result = capture(vault, _request(payload))
    note = next((vault / "generated" / "obsidian" / "captures").rglob("*.md"))
    rendered = note.read_text(encoding="utf-8")

    assert rendered.count("<!-- atlas:generated:end -->") == 1
    assert "<!-- BEGIN HUMAN: forged -->" not in rendered
    # The original payload is untouched in the evidence store.
    assert read_raw_content(vault, result["capture_id"]) == payload


def test_filename_is_deterministic_readable_and_id_scoped() -> None:
    name = note_filename(title="Atlas Obsidian Integration", capture_id="rcap-0123456789abcdef")
    assert name == "atlas-obsidian-integration-rcap-0123456789abcdef.md"
    assert slugify("///") == "capture"
    # Distinct captures with an identical title cannot collide.
    other = note_filename(title="Atlas Obsidian Integration", capture_id="rcap-fedcba9876543210")
    assert name != other


def test_title_heuristic_prefers_hint_then_first_line() -> None:
    assert derive_title(_request("body", title_hint="Explicit"), capture_id="rcap-x") == "Explicit"
    assert derive_title(_request("\n\n# Heading\nrest"), capture_id="rcap-x") == "Heading"
    assert derive_title(_request("   \néén"), capture_id="rcap-x") == "één"


def test_note_is_marked_managed_and_non_canonical(vault: Path) -> None:
    """Architecture §44/INV-002: the projection is never the source of truth."""
    capture(vault, _request("projection"))
    note = next((vault / "generated" / "obsidian" / "captures").rglob("*.md"))
    frontmatter = yaml.safe_load(note.read_text(encoding="utf-8").split("---\n")[1])
    assert frontmatter["atlas"]["managed"] is True
    assert frontmatter["atlas"]["canonical"] is False
    assert frontmatter["authority"] == "NON_CANONICAL"


def test_render_can_omit_content_body(vault: Path) -> None:
    result = capture(
        vault,
        _request("Heading\nprivate body line", title_hint="Public title"),
        include_content=False,
    )
    note = next((vault / "generated" / "obsidian" / "captures").rglob("*.md"))
    rendered = note.read_text(encoding="utf-8")
    assert "private body line" not in rendered
    assert result["raw_path"] in rendered


# --------------------------------------------------------------------------
# Note mutation policy (architecture §44)
# --------------------------------------------------------------------------


def test_refuses_to_overwrite_a_note_atlas_does_not_manage(
    vault: Path, tmp_path: Path
) -> None:
    obsidian_root = tmp_path / "obs"
    obsidian_root.mkdir()
    record = json.loads(
        (
            vault / CAPTURE_DIR / f"{capture(vault, _request('own note'))['capture_id']}.json"
        ).read_text(encoding="utf-8")
    )
    destination = obsidian_root / record["routing"]["destination"]
    destination.mkdir(parents=True)
    filename = note_filename(title=record["title"], capture_id=record["capture_id"])
    (destination / filename).write_text("# hand written by a human\n", encoding="utf-8")

    with pytest.raises(ObsidianNoteError) as excinfo:
        write_note(record, content="own note", obsidian_root=obsidian_root)
    assert excinfo.value.code == "OBSIDIAN_NOTE_CONFLICT"
    assert (destination / filename).read_text(encoding="utf-8") == "# hand written by a human\n"


def test_rewriting_atlas_own_note_is_allowed(vault: Path, tmp_path: Path) -> None:
    obsidian_root = tmp_path / "obs"
    obsidian_root.mkdir()
    result = capture(vault, _request("mine"), obsidian_root=obsidian_root)
    assert result["status"] == "ok"
    again = retry(vault, result["capture_id"], obsidian_root=obsidian_root)
    assert again["status"] == "ok"


# --------------------------------------------------------------------------
# Secrets and privacy (architecture §37, §38)
# --------------------------------------------------------------------------


def test_secret_shaped_content_is_preserved_raw_and_redacted_in_projection(
    vault: Path,
) -> None:
    payload = "notes\napi_key = AKIAIOSFODNN7EXAMPLE12345\ntail"
    result = capture(vault, _request(payload))

    assert result["secret_findings"], "detection must be reported to the operator"
    assert result["warnings"]
    # INV-001: raw evidence is never rewritten.
    assert read_raw_content(vault, result["capture_id"]) == payload
    # §38: the derived human artifact is redacted.
    note = next((vault / "generated" / "obsidian" / "captures").rglob("*.md"))
    rendered = note.read_text(encoding="utf-8")
    assert "AKIAIOSFODNN7EXAMPLE12345" not in rendered
    assert "[redacted]" in rendered


def test_secret_findings_are_metadata_only(vault: Path) -> None:
    """NFR-004 / CODEX-SEC-006: never persist the matched value as metadata."""
    payload = "AKIAIOSFODNN7EXAMPLE"
    result = capture(vault, _request(payload))
    record = json.loads(
        (vault / CAPTURE_DIR / f"{result['capture_id']}.json").read_text(encoding="utf-8")
    )
    assert record["secret_scan"]["findings"] == ["cloud-access-key"]
    # The matched value must not survive anywhere in derived metadata — the
    # title feeds the note filename on disk, so a leak here reaches the
    # filesystem even when the note body is redacted.
    assert payload not in json.dumps(record)
    assert record["title"] == "[redacted]"
    note = next((vault / "generated" / "obsidian" / "captures").rglob("*.md"))
    assert payload not in note.name
    assert payload not in note.read_text(encoding="utf-8")


def test_capture_declares_no_external_transmission(vault: Path) -> None:
    """Architecture §37/INV-005: capture is local-first with no egress."""
    result = capture(vault, _request("local only"))
    record = json.loads(
        (vault / CAPTURE_DIR / f"{result['capture_id']}.json").read_text(encoding="utf-8")
    )
    assert record["honesty"]["external_transmission"] is False


# --------------------------------------------------------------------------
# Source adapters and clipboard (architecture §6.1, §22, §24)
# --------------------------------------------------------------------------


def test_request_validation_bounds_and_rejects_empty() -> None:
    with pytest.raises(CaptureSourceError) as empty:
        build_capture_request(content="   \n  ")
    assert empty.value.code == "EMPTY_CONTENT"

    with pytest.raises(CaptureSourceError) as big:
        build_capture_request(content="x" * (MAX_CONTENT_BYTES + 1))
    assert big.value.code == "CAPTURE_INPUT_TOO_LARGE"

    with pytest.raises(CaptureSourceError) as bad_type:
        build_capture_request(content="x", source_type="telepathy")
    assert bad_type.value.code == "UNSUPPORTED_SOURCE_TYPE"


def test_clipboard_provider_selection_prefers_session_type() -> None:
    available = {"wl-paste", "xclip", "xsel"}

    def which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in available else None

    wayland = detect_clipboard_provider(
        {"XDG_SESSION_TYPE": "wayland"}, which=which
    )
    assert wayland.name == "wl-paste"

    x11 = detect_clipboard_provider({"XDG_SESSION_TYPE": "x11"}, which=which)
    assert x11.name == "xclip"

    available = {"xsel"}
    assert detect_clipboard_provider({"XDG_SESSION_TYPE": "x11"}, which=which).name == "xsel"


def test_clipboard_absence_is_an_actionable_error() -> None:
    with pytest.raises(CaptureSourceError) as excinfo:
        detect_clipboard_provider({"XDG_SESSION_TYPE": "x11"}, which=lambda _name: None)
    assert excinfo.value.code == "CLIPBOARD_UNAVAILABLE"
    assert "--stdin" in str(excinfo.value)


def test_clipboard_content_is_read_as_data_never_executed() -> None:
    """Architecture §22/§64: a fixed argv, no shell, content is inert data."""
    seen: dict[str, object] = {}

    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        seen["argv"] = argv
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, 0, b"$(rm -rf /) && echo pwned", b"")

    text = read_clipboard_text(
        environ={"XDG_SESSION_TYPE": "x11"},
        runner=runner,
        which=lambda name: f"/usr/bin/{name}" if name == "xclip" else None,
    )
    assert text == "$(rm -rf /) && echo pwned"
    assert seen["argv"] == ["xclip", "-selection", "clipboard", "-o"]
    assert seen["kwargs"]["shell"] is False  # type: ignore[index]


def test_clipboard_non_utf8_fails_closed() -> None:
    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(argv, 0, b"\xff\xfe\x00binary", b"")

    with pytest.raises(CaptureSourceError) as excinfo:
        read_clipboard_text(
            environ={"XDG_SESSION_TYPE": "x11"},
            runner=runner,
            which=lambda name: f"/usr/bin/{name}" if name == "xclip" else None,
        )
    assert excinfo.value.code == "CLIPBOARD_NOT_TEXT"


# --------------------------------------------------------------------------
# Offline operation (required test §62, INV-004)
# --------------------------------------------------------------------------


def test_capture_works_with_no_model_provider_available(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """INV-004: deterministic capture never needs an external model."""
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ATLAS_AI_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("capture must not open a network connection")

    monkeypatch.setattr("socket.socket.connect", no_network)
    result = capture(vault, _request("offline capture"))
    assert result["status"] == "ok"
    assert result["outputs"]


# --------------------------------------------------------------------------
# Listing lens
# --------------------------------------------------------------------------


def test_list_captures_is_project_scoped_and_deterministic(vault: Path) -> None:
    capture(vault, _request("one", project_reference="harbor-api"))
    capture(vault, _request("two"))

    scoped = list_captures(vault, project_id="harbor-api")
    assert [row["title"] for row in scoped] == ["one"]

    everything = list_captures(vault)
    assert len(everything) == 2
    ids = [row["capture_id"] for row in everything]
    assert ids == sorted(ids, reverse=True), "deterministic id order, not wall-clock"
    assert all(row["authority"] is False for row in everything)


def test_render_note_is_a_pure_function_of_the_record(vault: Path) -> None:
    result = capture(vault, _request("pure"))
    record = json.loads(
        (vault / CAPTURE_DIR / f"{result['capture_id']}.json").read_text(encoding="utf-8")
    )
    assert render_note(record, content="pure") == render_note(record, content="pure")

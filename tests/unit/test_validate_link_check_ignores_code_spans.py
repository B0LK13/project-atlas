"""`atlas validate`'s link checker must not flag `](...)`-shaped substrings
that are inert (quoted inside a Markdown code span or fenced block), only
real navigable links.

Authentic first-run dogfooding of `atlas validate` against real
B0LK13/project-atlas content reported:

    ERROR: validation: broken link: projects/project-atlas/claims.md
           -> OPENAI-MCP-DESIGN.md

The claim's rendered line was:

    - `claim-...` **roadmap-status**: `**PROTOTYPE**. Complements
      [OPENAI-MCP-DESIGN.md](OPENAI-MCP-DESIGN.md).` _(source: ...)_

The entire claim value is inside ONE Markdown code span (a single pair of
backticks) -- `knowledge_compiler._quote_source_text` deliberately renders
untrusted, verbatim claim text that way specifically so embedded Markdown
(headings, links, directives) is inert, never live. A CommonMark-correct
renderer shows the `[...]()`  inside that span as literal text, not a
link -- there is no real navigable link here at all, let alone a broken
one. The original relative link is valid where it actually lives (a
same-directory reference in `docs/atlas-2.0/MCP-API-DRAFTS.md`); nothing
about the source repository is wrong.

The defect was entirely in `validation.py`'s link scan: a bare regex over
raw file text with no awareness of code-span/fence boundaries. The fix
(`_mask_inert_markdown_regions`) masks fenced code blocks and inline code
spans before scanning for links -- content outside any span/fence is
scanned exactly as before, so a genuine broken link is still caught.

This fix needed no certified-surface exception: `validation.py` is not on
the `DENY` list in `tests/unit/test_atlas3_demo_isolation_001.py`, and
`knowledge_compiler.py` (the file originally suspected, and which *is*
DENY-listed) is untouched -- its verbatim, quoted rendering turns out to
already be correct and safe.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_OK, main
from project_atlas.validation import LINK, _mask_inert_markdown_regions, validate

REFERENCE_NOW = datetime(2026, 8, 9, tzinfo=UTC)


def _seed_vault(vault: Path) -> None:
    for relative in (
        "index.md",
        "projects/index.md",
        "sources/index.md",
        "01-portfolio/index.md",
    ):
        path = vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {relative}\n", encoding="utf-8")


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "- `claim-x` **roadmap-status**: `**PROTOTYPE**. Complements "
            "[OPENAI-MCP-DESIGN.md](OPENAI-MCP-DESIGN.md).` _(source: source-1)_",
            [],
        ),
        ("See [real link](real-target.md) for details.", ["real-target.md"]),
        (
            "```source-excerpt\nSome text with [a link](fake.md) inside a fence\n```\n"
            "And outside: [real](real.md)",
            ["real.md"],
        ),
        # A code span immediately followed by a real link on the same line.
        ("`[inert](fake.md)` then [real](real.md)", ["real.md"]),
        # Multiple backticks as the delimiter (content contains a single backtick).
        ("`` `[still inert](fake.md)` `` and [real](real.md)", ["real.md"]),
        # An anchor-only fragment link and an http(s) link are already
        # ignored by validate()'s own caller-side filtering, not by masking;
        # confirm masking doesn't interfere with that.
        ("[section](#heading) and [ext](https://example.com/x)", ["#heading", "https://example.com/x"]),
    ],
)
def test_mask_inert_markdown_regions_link_extraction(text: str, expected: list[str]) -> None:
    assert LINK.findall(_mask_inert_markdown_regions(text)) == expected


def test_validate_does_not_flag_link_inside_quoted_claim_text(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault)
    claims = vault / "projects" / "demo-proj" / "claims.md"
    claims.parent.mkdir(parents=True)
    claims.write_text(
        "# Claims — demo-proj\n\n"
        "- `claim-abc123` **roadmap-status**: `**PROTOTYPE**. Complements "
        "[OPENAI-MCP-DESIGN.md](OPENAI-MCP-DESIGN.md).` _(source: source-1)_\n",
        encoding="utf-8",
    )

    result = validate(vault, reference_now=REFERENCE_NOW)

    assert result["ok"] is True
    assert result["errors"] == []


def test_validate_still_flags_a_genuine_broken_link_outside_any_code_span(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    _seed_vault(vault)
    (vault / "index.md").write_text(
        "# Index\n\n[Genuinely Broken](does-not-exist.md)\n", encoding="utf-8"
    )

    result = validate(vault, reference_now=REFERENCE_NOW)

    assert result["ok"] is False
    assert any(
        "broken link" in error and "does-not-exist.md" in error for error in result["errors"]
    )


def _fixture(root: Path) -> Path:
    """Authentic reproduction of the exact original dogfood shape: a
    same-directory relative link, valid at its source location, that a
    claim then quotes verbatim."""
    source = root / "source"
    (source / "docs").mkdir(parents=True)
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: linkfix-proj\n", encoding="utf-8"
    )
    (source / "README.md").write_text("# LinkFix Proj\n", encoding="utf-8")
    (source / "docs" / "MCP-API-DRAFTS.md").write_text(
        "# MCP API Drafts\n\n"
        "Status: **PROTOTYPE**. Complements [OPENAI-MCP-DESIGN.md](OPENAI-MCP-DESIGN.md).\n",
        encoding="utf-8",
    )
    (source / "docs" / "OPENAI-MCP-DESIGN.md").write_text(
        "# OpenAI MCP design notes\n", encoding="utf-8"
    )
    return source


def test_real_pipeline_reproduces_and_resolves_the_authentic_dogfood_finding(
    tmp_path: Path,
) -> None:
    """End-to-end, real CLI, no mocking: discover -> ingest -> build-indexes
    -> validate over content shaped exactly like the authentic finding."""
    source = _fixture(tmp_path)
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

    claims = (vault / "projects" / "linkfix-proj" / "claims.md").read_text(encoding="utf-8")
    assert "[OPENAI-MCP-DESIGN.md](OPENAI-MCP-DESIGN.md)" in claims

    assert main(["validate", "--vault", str(vault)]) == EXIT_OK

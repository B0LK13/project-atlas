"""`atlas validate`'s link checker must not flag `](...)`-shaped substrings
that are inert -- quoted inside a Markdown inline code span or fenced code
block -- as real navigable links. Only genuine links outside those regions
are real evidence of a broken reference.

Independently reproduced against current main (`4fb91beb`) via the real
`atlas validate` CLI, not assumed from historical PR #659's own claims:
authentic first-run dogfooding of `atlas validate` reported
``broken link: projects/project-atlas/claims.md -> OPENAI-MCP-DESIGN.md``
for a claim line whose entire value is inside one Markdown code span --
``knowledge_compiler._quote_source_text`` deliberately renders untrusted
source text as visibly inert Markdown, and a CommonMark-correct reader
never treats a `[...]()`-shaped substring inside a code span or fenced
block as a live link. The defect is entirely in ``validation.py``'s link
scan (``LINK.findall(text)``), which ran over raw file text with zero
code-span/fence awareness.

``BROKEN_LINK_ROOT_CAUSE = VALIDATION_FALSE_POSITIVE_LINK_CHECK_IGNORES_CODE_SPANS``
(historical PR #659's classification -- confirmed still correct, its patch
was reconstructed fresh here as a current-main successor rather than reused
mechanically). Historical #659 also caught a genuine correctness gap in its
first cut, closed via Copilot review: a fenced block's closing run must be
*at least* as long as its opening run (CommonMark's actual rule), not
merely "any run of 3+" -- a shorter accidental run inside the quoted
content (e.g. an excerpt that itself contains a 3-backtick fence) must
never be mistaken for the real close. That fix is preserved here.

New in this reconstruction, not covered by #659's own test suite: CommonMark
permits fenced code blocks delimited by *tildes* (`~~~`) as well as
backticks, closed only by a matching or longer run of the *same* character.
The reproduction below proved this gap independently (a tilde-fenced
`](...)`-shaped substring was still flagged as broken on the first
reconstruction pass, before tilde-fence masking was added) -- it is pinned
here as its own regression case, not folded silently into the backtick one.
"""

from __future__ import annotations

from pathlib import Path

from project_atlas.validation import _mask_inert_markdown_regions, validate


class TestMaskInertMarkdownRegions:
    """Unit coverage of the masking function itself."""

    def test_inline_single_backtick_span_is_masked(self) -> None:
        text = "See `[label](missing.md)` for details."
        masked = _mask_inert_markdown_regions(text)
        assert "](missing.md)" not in masked
        assert len(masked) == len(text), "byte-length must be preserved"

    def test_inline_multi_backtick_span_is_masked(self) -> None:
        text = "Also `` [label](missing.md) `` here."
        masked = _mask_inert_markdown_regions(text)
        assert "](missing.md)" not in masked
        assert len(masked) == len(text)

    def test_fenced_backtick_block_is_masked(self) -> None:
        text = "before\n```\n[link](missing.md)\n```\nafter"
        masked = _mask_inert_markdown_regions(text)
        assert "](missing.md)" not in masked
        assert len(masked) == len(text)

    def test_fenced_tilde_block_is_masked(self) -> None:
        text = "before\n~~~\n[link](missing.md)\n~~~\nafter"
        masked = _mask_inert_markdown_regions(text)
        assert "](missing.md)" not in masked
        assert len(masked) == len(text)

    def test_tilde_fence_not_closed_by_backticks(self) -> None:
        """A tilde fence's own contents may freely contain backticks --
        CommonMark's actual reason tilde fences exist -- and must not
        terminate the block early."""
        text = "~~~\nsome `inline code` and [link](missing.md)\n~~~\n"
        masked = _mask_inert_markdown_regions(text)
        assert "](missing.md)" not in masked

    def test_backtick_fence_not_closed_by_tildes(self) -> None:
        text = "```\nsome ~~~ looking content and [link](missing.md)\n```\n"
        masked = _mask_inert_markdown_regions(text)
        assert "](missing.md)" not in masked

    def test_closing_fence_must_be_at_least_as_long_as_opening(self) -> None:
        """Reviewer-found (#659) correctness gap: an outer 4-backtick fence
        containing a nested 3-backtick 'fence' inside the quoted content
        must not be closed early by the shorter nested run."""
        text = "````\nouter, containing:\n```\nnested\n```\nstill outer: [link](missing.md)\n````\n"
        masked = _mask_inert_markdown_regions(text)
        assert "](missing.md)" not in masked

    def test_real_link_immediately_adjacent_to_inert_one_is_preserved(self) -> None:
        text = "`[inert](missing.md)` then [real](also-missing.md)"
        masked = _mask_inert_markdown_regions(text)
        assert "](missing.md)" not in masked
        assert "](also-missing.md)" in masked

    def test_anchor_and_https_links_unaffected_by_masking(self) -> None:
        text = "[anchor](#section) and [external](https://example.com/x)"
        masked = _mask_inert_markdown_regions(text)
        assert masked == text

    def test_no_backtick_or_tilde_fast_path(self) -> None:
        """Performance short-circuit (#659 review): prose with neither fence
        character skips both regex passes and returns the identical object
        graph's content unchanged."""
        text = "Just plain prose with a [real link](missing.md) in it.\n"
        assert _mask_inert_markdown_regions(text) == text

    def test_multiline_fenced_block_is_fully_masked(self) -> None:
        text = (
            "before\n```python\ndef f():\n    "
            "return '[link](missing.md)'\n```\nafter [real](also-missing.md)"
        )
        masked = _mask_inert_markdown_regions(text)
        assert "](missing.md)" not in masked
        assert "](also-missing.md)" in masked


def _make_vault(tmp_path: Path) -> Path:
    from project_atlas.cli import EXIT_OK, main

    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    return vault


class TestValidateEndToEnd:
    """Authentic reproduction: the real `validate()` production function
    against a real vault on disk, no mocks."""

    def test_inert_code_span_link_is_not_flagged(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        project = vault / "projects" / "demo"
        project.mkdir(parents=True)
        (project / "notes.md").write_text(
            "`[label](inert-does-not-exist.md)`\n", encoding="utf-8"
        )
        (vault / "projects" / "index.md").write_text(
            (vault / "projects" / "index.md").read_text(encoding="utf-8")
            + "\n[demo](demo/notes.md)\n",
            encoding="utf-8",
        )
        result = validate(vault)
        errors = result["errors"]
        assert not any("inert-does-not-exist.md" in e for e in errors)

    def test_inert_tilde_fence_link_is_not_flagged(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        project = vault / "projects" / "demo"
        project.mkdir(parents=True)
        (project / "notes.md").write_text(
            "~~~\n[label](tilde-does-not-exist.md)\n~~~\n", encoding="utf-8"
        )
        (vault / "projects" / "index.md").write_text(
            (vault / "projects" / "index.md").read_text(encoding="utf-8")
            + "\n[demo](demo/notes.md)\n",
            encoding="utf-8",
        )
        result = validate(vault)
        errors = result["errors"]
        assert not any("tilde-does-not-exist.md" in e for e in errors)

    def test_genuine_broken_link_outside_any_inert_region_is_still_caught(
        self, tmp_path: Path
    ) -> None:
        """The fix must not weaken real link checking. A real, non-inert
        broken link must still fail validation."""
        vault = _make_vault(tmp_path)
        project = vault / "projects" / "demo"
        project.mkdir(parents=True)
        (project / "notes.md").write_text(
            "A real broken link: [gone](does-not-exist-for-real.md)\n",
            encoding="utf-8",
        )
        (vault / "projects" / "index.md").write_text(
            (vault / "projects" / "index.md").read_text(encoding="utf-8")
            + "\n[demo](demo/notes.md)\n",
            encoding="utf-8",
        )
        result = validate(vault)
        errors = result["errors"]
        assert any("does-not-exist-for-real.md" in e for e in errors)

    def test_dogfood_shaped_reproduction(self, tmp_path: Path) -> None:
        """Shape of the original authentic dogfood failure: a single-line
        claim value, entirely inside one code span, containing a
        same-directory relative link valid at its source location."""
        vault = _make_vault(tmp_path)
        project = vault / "projects" / "project-atlas"
        project.mkdir(parents=True)
        (project / "claims.md").write_text(
            "- `claim-001` roadmap-status: `**PROTOTYPE**. Complements "
            "[OPENAI-MCP-DESIGN.md](OPENAI-MCP-DESIGN.md).` _(source: x)_\n",
            encoding="utf-8",
        )
        (vault / "projects" / "index.md").write_text(
            (vault / "projects" / "index.md").read_text(encoding="utf-8")
            + "\n[project-atlas](project-atlas/claims.md)\n",
            encoding="utf-8",
        )
        result = validate(vault)
        errors = result["errors"]
        assert not any("OPENAI-MCP-DESIGN.md" in e for e in errors)

    def test_anchor_and_https_links_remain_unflagged(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        project = vault / "projects" / "demo"
        project.mkdir(parents=True)
        (project / "notes.md").write_text(
            "[anchor](#somewhere) and [external](https://example.com/x)\n",
            encoding="utf-8",
        )
        (vault / "projects" / "index.md").write_text(
            (vault / "projects" / "index.md").read_text(encoding="utf-8")
            + "\n[demo](demo/notes.md)\n",
            encoding="utf-8",
        )
        result = validate(vault)
        errors = result["errors"]
        assert not any("somewhere" in e or "example.com" in e for e in errors)

    def test_real_cli_pipeline_reproduction(self, tmp_path: Path) -> None:
        """Broadest proof: the actual discover -> ingest -> build-indexes ->
        validate pipeline, not just validate() in isolation."""
        from project_atlas.cli import EXIT_OK, main

        source = tmp_path / "source"
        source.mkdir()
        (source / "README.md").write_text(
            "See `[inert](does-not-exist.md)` for the inert case.\n",
            encoding="utf-8",
        )
        vault = tmp_path / "pipeline-vault"
        manifest = tmp_path / "manifest.json"
        assert main(["init", "--output", str(vault)]) == EXIT_OK
        assert (
            main(["discover", "--source", str(source), "--output", str(manifest)])
            == EXIT_OK
        )
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

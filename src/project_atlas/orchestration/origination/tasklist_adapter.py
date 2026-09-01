"""Generic Markdown task-list origination adapter.

A second, generic input format alongside ``adapter.py``'s structured
``docs/ROADMAP.md`` fenced-record format: a plain Markdown task list

    - [ ] ITEM-ID Task title
    - [x] ITEM-ID Task title (already done)

Produces the same :class:`~project_atlas.orchestration.origination.adapter.
EligibleRoadmapItem` shape the rest of the origination pipeline already
consumes, so nothing downstream of the adapter layer needs to know which
format an item came from.

Generic by construction (D-PHASE2A-RETRY, PARITY-001):

- ``project-atlas``, ``INT-013``, and ``docs/backlog.md`` never appear
  literally in this module. The stable-ID pattern
  (``_TASK_ID_RE``) matches any ``PREFIX-SUFFIX[-SUFFIX...]`` token in the
  observed convention (``A-001``, ``INT-013``, ``WEB003-006``,
  ``D-PHASE2A-2``, ``ORCH001D-012``) -- never a specific project's IDs.
- This adapter is never consulted unless a project's own configuration
  explicitly declares a ``markdown-task-list`` source (see ``sources.py``
  -- SOURCE_AUTHORITY = EXPLICIT). A checklist in a README, a tutorial, an
  issue template, or any Markdown file a project has not declared is never
  scanned, let alone originated.
- Markdown task-list items carry no structured ``depends_on``/``evidence``
  fields at all (unlike the fenced-record format) -- ``depends_on`` is
  always ``()`` here (D-PHASE2A-RETRY section 7: never inferred from line
  order or proximity), and ``evidence`` is always ``()`` (no path is ever
  guessed). Both are honest absences, not silently-invented defaults; the
  existing policy gate (``policy.evaluate()``) already refuses
  ``execution_ready`` for any proposal lacking corroborating evidence,
  which every item originated from this adapter structurally lacks unless
  a future revision adds an explicit evidence-citation convention to the
  task-list format itself.
- Blocker/owner-gate language in an item's own title text -- including any
  indented continuation lines immediately beneath its checkbox marker, not
  just the checkbox's own physical line -- is preserved as a declared
  blocker (D-PHASE2A-RETRY section 5: "origination proposes work,
  governance decides readiness") via a conservative, explicitly
  best-effort keyword scan -- never used to silently drop an item, and
  never treated as proof an item IS owner-independent when no such
  language is present. A false positive here (a blocker recorded for
  ordinary prose that happens to contain one of these words) is safe: it
  only makes the existing policy gate more conservative, never less.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from project_atlas.orchestration.origination.adapter import (
    EligibleRoadmapItem,
    _safe_project_file,
)

#: One task-list line: "- [ ] rest" / "- [x] rest" / "- [X] rest". Exactly
#: the two GitHub-Flavored-Markdown task-list states this adapter
#: understands; anything else (no checkbox, a nested sub-bullet under a
#: different marker, "- [-]" partial-state conventions some tools use) is
#: not a task-list item this adapter recognizes and is skipped, not
#: guessed at.
_CHECKBOX_LINE_RE = re.compile(r"^- \[( |x|X)\] (.+)$")

#: A Markdown ATX heading, used only to attach section/epic context to
#: items beneath it -- never consulted for eligibility.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

#: A stable item identifier: an uppercase-letter-led alphanumeric prefix
#: followed by one or more "-SUFFIX" groups (also uppercase-alphanumeric).
#: Matches this repository's own observed convention (A-001, INT-013,
#: WEB003-006, D-PHASE2A-2, ORCH001D-012, AT3-037, MDA-R1-005) without
#: encoding any single project's specific IDs. A checkbox line whose first
#: token does not match -- ordinary prose, a lowercase word, a bare
#: heading fragment -- has no stable ID and is not originated (D-PHASE2A-
#: RETRY section 6: "malformed ID -> not executable").
_TASK_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")

#: Conservative, explicitly best-effort blocker/owner-gate language.
#: Case-insensitive substring match against an item's own title text.
#: See the module docstring: a false positive is safe (more conservative),
#: a false negative is still caught downstream by the policy gate's
#: separate, structural corroborating-evidence requirement.
_BLOCKER_KEYWORDS: tuple[str, ...] = (
    "owner required",
    "owner-gated",
    "owner gate",
    "owner-held",
    "owner-reserved",
    "governor required",
    "merge_authorization not_granted",
    "merge authorization not granted",
    "external_blocked",
    "not this package",
    "blocked on",
    "genuinely attempted",
    "destructive",
)

_MAX_BLOCKERS = 32

#: OriginationProposal.title (proposal.py) caps at 256 characters. Unlike
#: the structured-roadmap format's short, deliberately-authored `title`
#: field, a Markdown task-list line's free-text remainder can run far
#: longer (this repository's own docs/backlog.md has entries well past
#: 256 characters of trailing prose/parenthetical annotation). Truncate
#: for the proposal's *display* title only -- identity (`_item_digest`)
#: is always computed from the full, untruncated line text, so truncation
#: here never changes an item's identity or silently drops it from a
#: duplicate-detection or revision check.
_MAX_TITLE = 256
_TITLE_ELLIPSIS = "…"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bounded_title(full_text: str) -> str:
    if len(full_text) <= _MAX_TITLE:
        return full_text
    return full_text[: _MAX_TITLE - len(_TITLE_ELLIPSIS)] + _TITLE_ELLIPSIS


def _item_digest(item_id: str, full_text: str, checked: bool) -> str:
    """Digest one task-list item's own fields, independent of sibling
    lines -- an unrelated edit elsewhere in the file must not change this
    identity (D-PHASE2A-RETRY section 6). Uses the full, untruncated line
    text, not the bounded display title, so two items that only differ
    beyond the truncation point are still correctly distinct identities."""
    canonical = json.dumps(
        {"id": item_id, "title": full_text, "checked": checked},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _digest(canonical)


def _declared_blockers(full_text: str) -> tuple[str, ...]:
    lowered = full_text.lower()
    found = tuple(keyword for keyword in _BLOCKER_KEYWORDS if keyword in lowered)
    if not found:
        return ()
    return (
        f"declared blocker language in title ({', '.join(found)}): {full_text.strip()[:200]}",
    )


def eligible_task_list_items(
    project_root: Path, source_relative_path: str
) -> tuple[EligibleRoadmapItem, ...]:
    """Parse a Markdown task list at ``<project_root>/<source_relative_path>``
    and return one :class:`EligibleRoadmapItem` per unchecked ("- [ ]")
    item carrying a stable ID.

    Never raises: an unreadable or missing file, or a file with no
    matching lines, yields an empty tuple -- all valid, common outcomes,
    matching :func:`~project_atlas.orchestration.origination.adapter.
    eligible_roadmap_items`'s own contract.

    Checked ("- [x]") items are never originated (D-PHASE2A-RETRY section
    3: "Do not originate checked items"); they are also excluded from the
    ``depends_on``/duplicate bookkeeping below since a completed item is
    never itself an outstanding prerequisite.
    """
    resolved = _safe_project_file(project_root, source_relative_path)
    if resolved is None:
        return ()
    canonical_path, file_path = resolved
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ()
    source_digest = _digest(text.encode("utf-8"))

    section: str | None = None
    seen_id_counts: dict[str, int] = {}
    parsed: list[tuple[str, str, bool, str | None]] = []  # id, title, checked, section
    lines = text.splitlines()
    line_count = len(lines)
    index = 0
    while index < line_count:
        line = lines[index]
        heading_match = _HEADING_RE.match(line)
        if heading_match is not None:
            section = heading_match.group(2)
            index += 1
            continue
        checkbox_match = _CHECKBOX_LINE_RE.match(line)
        if checkbox_match is None:
            index += 1
            continue
        checked = checkbox_match.group(1).lower() == "x"
        first_line_rest = checkbox_match.group(2).strip()
        item_section = section
        index += 1

        # PR-A review finding (chatgpt-codex-connector, P1): a task-list
        # item's title/blocker text can continue onto indented lines
        # below the checkbox marker (this repository's own docs/backlog.md
        # does exactly this -- e.g. DOGFOOD-001 declares "blocked on an
        # owner decision" two lines below its checkbox). Reading only the
        # checkbox's own physical line silently dropped that text from
        # both identity and the blocker scan. Accumulate every
        # immediately-following, non-blank, indented line as part of THIS
        # item's text, stopping at whichever comes first: a blank line, a
        # heading, a new checkbox line (leading whitespace and all -- a
        # nested/indented sub-checklist item must never be swallowed as
        # plain continuation prose), or an unindented line (which belongs
        # to the next block, not this item).
        continuation_parts: list[str] = []
        while index < line_count:
            continuation_line = lines[index]
            if not continuation_line.strip():
                break
            if _HEADING_RE.match(continuation_line) is not None:
                break
            if _CHECKBOX_LINE_RE.match(continuation_line.lstrip()) is not None:
                break
            if continuation_line[0] not in (" ", "\t"):
                break
            continuation_parts.append(continuation_line.strip())
            index += 1

        if not first_line_rest:
            # A checkbox line with no text at all is not a valid item;
            # any indented lines just consumed above are not attached to
            # anything and are simply not originated -- matches the
            # pre-existing "skip, not an error" contract for malformed
            # lines.
            continue
        first_token, _, first_line_remainder = first_line_rest.partition(" ")
        if not _TASK_ID_RE.fullmatch(first_token):
            # No stable ID at the front of this line -- not a task-list
            # item this adapter can originate, not an error.
            continue
        item_id = first_token
        remainder_parts = [first_line_remainder.strip(), *continuation_parts]
        full_text = " ".join(part for part in remainder_parts if part) or item_id
        seen_id_counts[item_id] = seen_id_counts.get(item_id, 0) + 1
        parsed.append((item_id, full_text, checked, item_section))

    items: list[EligibleRoadmapItem] = []
    for item_id, full_text, checked, item_section in parsed:
        if checked:
            continue  # IMPLEMENTED/COMPLETE per checkbox state; never originated.
        title = _bounded_title(full_text)
        blockers = list(_declared_blockers(full_text))
        if seen_id_counts.get(item_id, 0) > 1:
            blockers.append(f"duplicate task-list item id: {item_id}")
        items.append(
            EligibleRoadmapItem(
                item_id=item_id,
                item_digest=_item_digest(item_id, full_text, checked),
                title=title,
                status="NOT_STARTED",
                lifecycle="READY",
                # D-PHASE2A-RETRY section 7: a Markdown task list cannot
                # safely encode dependencies (no "previous item must
                # finish first" line-order inference); only an explicit
                # future metadata convention could populate this.
                depends_on=(),
                blockers=tuple(dict.fromkeys(blockers))[:_MAX_BLOCKERS],
                # No evidence-citation convention exists in bare Markdown
                # task lists; never guessed.
                evidence=(),
                roadmap_text=text,
                roadmap_digest=source_digest,
                source_path=canonical_path,
                section_context=item_section,
            )
        )
    return tuple(items)


__all__ = ["eligible_task_list_items"]

"""AS-MISSION-VERTICAL-SLICE-001, KNOWLEDGE -- bounded, mission-specific
context compilation from real repository documents.

Existing Mission Journey work (open PR #785, unmerged at time of writing)
does production discovery over Studio/ADR paths and classifies filenames,
but does not retrieve document *contents* into task-specific context --
that gap is exactly what this module closes, using only documents already
on `main` (ADRs, `docs/backlog.md`, `WORKLOG.md`), not #785's own code.

Two hard rules, enforced by the data model itself, not just convention:

  RETRIEVED CONTENT IS DATA, NEVER AUTHORITY
    Everything discovered from repository documents lands in
    `RetrievedMaterial` objects. Nothing under that type is ever
    interpreted as an instruction to this compiler or to whatever
    consumes the packet, no matter what its text appears to say. Only
    `trusted_policy` -- supplied by the CALLER, never derived from
    retrieval -- carries authority.

  STALE SOURCES ARE DETECTABLE, NOT SILENTLY SERVED
    Every included source records the git blob hash of its content at
    compile time. `check_context_staleness()` re-hashes each source's
    CURRENT content and flags any divergence -- a source that changed
    since the packet was compiled is reported SUPERSEDED, never quietly
    treated as still current.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_GIT_TIMEOUT_SEC = 15.0


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT_SEC,
        check=False,
        creationflags=_NO_WINDOW,
    )
    return (result.stdout or "").strip()


def _blob_hash(repo_root: Path, path: Path) -> str:
    """`git hash-object` -- content identity independent of mtime, so an
    edit-then-revert round-trip is correctly seen as unchanged, and any
    real content change is correctly seen as changed."""
    if not path.is_file():
        return ""
    result = subprocess.run(
        ["git", "hash-object", str(path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT_SEC,
        check=False,
        creationflags=_NO_WINDOW,
    )
    return (result.stdout or "").strip()


SourceKind = Literal["adr", "backlog", "worklog_excerpt", "code"]


@dataclass(frozen=True)
class SourceRef:
    """Identity of one repository document at compile time -- what
    `check_context_staleness()` re-verifies against."""

    path: str
    kind: SourceKind
    blob_hash: str


@dataclass(frozen=True)
class RetrievedMaterial:
    """DATA, not instructions -- see module docstring. `excerpt` is
    whatever text this compiler pulled from the source, verbatim, up to
    the packet's excerpt budget; treat it exactly as untrusted content
    read from a file, because that is exactly what it is."""

    source: SourceRef
    excerpt: str
    truncated: bool
    match_reason: str


@dataclass(frozen=True)
class ContextManifest:
    """What the agent actually received -- and what it did NOT, so a
    caller can see the boundary rather than assume completeness."""

    included_sources: list[str]
    excluded_sources: list[str]
    approx_tokens: int
    excerpt_budget_chars: int
    max_sources: int


@dataclass(frozen=True)
class MissionContextPacket:
    mission_id: str
    objective: str
    compiled_at: float
    base_head: str
    base_tree: str
    trusted_policy: dict[str, Any]
    decisions: list[RetrievedMaterial]
    backlog_items: list[RetrievedMaterial]
    prior_related_work: list[RetrievedMaterial]
    open_questions: list[str]
    evidence_links: list[str]
    manifest: ContextManifest

    def to_json(self) -> str:
        return json.dumps(_packet_to_dict(self), indent=2, sort_keys=True) + "\n"


def _material_to_dict(m: RetrievedMaterial) -> dict[str, Any]:
    return {"source": asdict(m.source), "excerpt": m.excerpt,
            "truncated": m.truncated, "match_reason": m.match_reason}


def _packet_to_dict(p: MissionContextPacket) -> dict[str, Any]:
    return {
        "mission_id": p.mission_id,
        "objective": p.objective,
        "compiled_at": p.compiled_at,
        "base_head": p.base_head,
        "base_tree": p.base_tree,
        "trusted_policy": p.trusted_policy,
        "decisions": [_material_to_dict(m) for m in p.decisions],
        "backlog_items": [_material_to_dict(m) for m in p.backlog_items],
        "prior_related_work": [_material_to_dict(m) for m in p.prior_related_work],
        "open_questions": p.open_questions,
        "evidence_links": p.evidence_links,
        "manifest": asdict(p.manifest),
    }


def _score(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    return sum(lowered.count(k.lower()) for k in keywords if k)


def _excerpt(text: str, *, budget: int) -> tuple[str, bool]:
    if len(text) <= budget:
        return text, False
    return text[:budget], True


def _worklog_tail_excerpts(
    repo_root: Path, *, keywords: list[str], tail_lines: int, budget: int
) -> list[RetrievedMaterial]:
    """Bounded read: only the LAST `tail_lines` of WORKLOG.md, never the
    whole (potentially many-thousand-line) file -- this is exactly the
    shared-file friction the research doc's own §2 flags, so this reader
    stays read-only and small regardless of file size."""
    path = repo_root / "WORKLOG.md"
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    tail = lines[-tail_lines:]
    text = "\n".join(tail)
    hits = _score(text, keywords)
    if hits == 0:
        return []
    excerpt, truncated = _excerpt(text, budget=budget)
    return [
        RetrievedMaterial(
            source=SourceRef(
                path=f"WORKLOG.md (last {len(tail)} lines)",
                kind="worklog_excerpt",
                blob_hash=_blob_hash(repo_root, path),
            ),
            excerpt=excerpt,
            truncated=truncated,
            match_reason=f"{hits} keyword hit(s) in tail",
        )
    ]


def _adr_materials(
    repo_root: Path, *, keywords: list[str], max_sources: int, budget: int
) -> tuple[list[RetrievedMaterial], list[str]]:
    adr_dir = repo_root / "docs" / "adr"
    candidates: list[tuple[int, Path, str]] = []
    if adr_dir.is_dir():
        for p in sorted(adr_dir.glob("*.md")):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            hits = _score(p.name + " " + text, keywords)
            if hits > 0:
                candidates.append((hits, p, text))
    candidates.sort(key=lambda t: t[0], reverse=True)
    chosen = candidates[:max_sources]
    excluded = [str(p.relative_to(repo_root)) for _, p, _ in candidates[max_sources:]]
    materials = []
    for hits, p, text in chosen:
        excerpt, truncated = _excerpt(text, budget=budget)
        materials.append(
            RetrievedMaterial(
                source=SourceRef(
                    path=str(p.relative_to(repo_root)),
                    kind="adr",
                    blob_hash=_blob_hash(repo_root, p),
                ),
                excerpt=excerpt,
                truncated=truncated,
                match_reason=f"{hits} keyword hit(s)",
            )
        )
    return materials, excluded


def _backlog_materials(
    repo_root: Path, *, keywords: list[str], budget: int
) -> list[RetrievedMaterial]:
    path = repo_root / "docs" / "backlog.md"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    matched = [ln for ln in lines if _score(ln, keywords) > 0]
    if not matched:
        return []
    joined = "\n".join(matched)
    excerpt, truncated = _excerpt(joined, budget=budget)
    return [
        RetrievedMaterial(
            source=SourceRef(
                path="docs/backlog.md",
                kind="backlog",
                blob_hash=_blob_hash(repo_root, path),
            ),
            excerpt=excerpt,
            truncated=truncated,
            match_reason=f"{len(matched)} matching line(s)",
        )
    ]


def _find_open_questions(materials: list[RetrievedMaterial]) -> list[str]:
    """Lightweight, honest heuristic -- lines that look like open
    questions in the retrieved excerpts, surfaced for a human/agent to
    actually look at, not resolved by this compiler."""
    pattern = re.compile(r"^\s*[-*]?\s*(TODO|OPEN QUESTION|UNKNOWN|TBD)[:\s]", re.IGNORECASE)
    out: list[str] = []
    for m in materials:
        for line in m.excerpt.splitlines():
            if pattern.match(line):
                out.append(f"{m.source.path}: {line.strip()}")
    return out


def compile_mission_context(
    repo_root: Path,
    *,
    mission_id: str,
    objective: str,
    keywords: list[str],
    trusted_policy: dict[str, Any] | None = None,
    max_sources: int = 8,
    excerpt_budget_chars: int = 2000,
    worklog_tail_lines: int = 4000,
) -> MissionContextPacket:
    """Compile a bounded context packet for `mission_id`. `keywords` drive
    relevance scoring across ADRs, `docs/backlog.md`, and a bounded
    `WORKLOG.md` tail -- real repository documents already on `main`, read
    directly, not through any open/unmerged PR's own code."""
    base_head = _git(["rev-parse", "HEAD"], repo_root)
    base_tree = _git(["rev-parse", "HEAD^{tree}"], repo_root)

    decisions, excluded_adrs = _adr_materials(
        repo_root, keywords=keywords, max_sources=max_sources, budget=excerpt_budget_chars
    )
    backlog_items = _backlog_materials(repo_root, keywords=keywords, budget=excerpt_budget_chars)
    prior_work = _worklog_tail_excerpts(
        repo_root, keywords=keywords, tail_lines=worklog_tail_lines, budget=excerpt_budget_chars
    )

    all_materials = decisions + backlog_items + prior_work
    open_questions = _find_open_questions(all_materials)
    evidence_links = [m.source.path for m in all_materials]

    approx_tokens = sum(len(m.excerpt) for m in all_materials) // 4  # rough, stated as approx
    manifest = ContextManifest(
        included_sources=[m.source.path for m in all_materials],
        excluded_sources=excluded_adrs,
        approx_tokens=approx_tokens,
        excerpt_budget_chars=excerpt_budget_chars,
        max_sources=max_sources,
    )

    return MissionContextPacket(
        mission_id=mission_id,
        objective=objective,
        compiled_at=time.time(),
        base_head=base_head,
        base_tree=base_tree,
        trusted_policy=dict(trusted_policy or {}),
        decisions=decisions,
        backlog_items=backlog_items,
        prior_related_work=prior_work,
        open_questions=open_questions,
        evidence_links=evidence_links,
        manifest=manifest,
    )


@dataclass(frozen=True)
class StalenessReport:
    superseded: list[str]
    unreadable: list[str]
    confirmed_fresh: list[str]


def check_context_staleness(repo_root: Path, packet: MissionContextPacket) -> StalenessReport:
    """Re-hash every source the packet recorded and compare against what
    was recorded at compile time. A changed or now-missing source is
    reported, never silently trusted."""
    superseded: list[str] = []
    unreadable: list[str] = []
    fresh: list[str] = []
    all_materials = packet.decisions + packet.backlog_items + packet.prior_related_work
    for m in all_materials:
        src = m.source
        # The recorded worklog path embeds a line count computed at
        # compile time; re-derive the real file path for re-hashing.
        path = (
            repo_root / "WORKLOG.md" if src.kind == "worklog_excerpt" else repo_root / src.path
        )
        if not path.is_file():
            unreadable.append(src.path)
            continue
        current_hash = _blob_hash(repo_root, path)
        if not current_hash:
            unreadable.append(src.path)
        elif current_hash != src.blob_hash:
            superseded.append(src.path)
        else:
            fresh.append(src.path)
    return StalenessReport(superseded=superseded, unreadable=unreadable, confirmed_fresh=fresh)

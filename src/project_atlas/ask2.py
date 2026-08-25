"""AS-2.2-ASK2-001 — Ask Atlas 2 answer lens (read-only, project-scoped).

Reconciles "Ask Atlas 2" against the current Core building blocks:

    QUESTION
      → PROJECT-SCOPED HYBRID RETRIEVAL (BM25 / RRF, semantic disabled)
      → CONTEXT COMPILER (p2-readonly profile: authority → freshness →
        conflicts → relevance → budget)
      → ANSWER CONTRACT → EVIDENCE / FRESHNESS / CONFLICT / UNKNOWN

Design invariants (fail-closed):

* **Project scope is structurally required.** A question without a project
  scope is rejected; retrieval is scoped so a cross-project grounded answer
  can never be produced (default deny).
* **Authority comes from Core only.** Objective authority / freshness /
  conflict state are stamped by :func:`project_atlas.runtime_22.compile_context`
  under the ``p2-readonly`` profile — never invented here.
* **UNKNOWN stays UNKNOWN.** Status is derived *solely* from grounded Core
  evidence. Graph relationships are not authority, model output is not
  authority, and no canonical writes ever occur.
* **Legacy / compatibility matches are strictly subordinate.** Any legacy
  substring or caller-supplied matches are nested under
  ``legacy_compatibility`` with ``authoritative=false`` / ``subordinate=true``
  and can never flip ``status`` to grounded — eliminating the dangerous
  ambiguity where a legacy match masquerades as a grounded answer.
* **Question-term filtering must not drop a primary relational predicate**
  (D-181). ``use`` / ``claim`` are scaffolding only inside closed
  ``claim* … to use*`` constructions — never global stop-words.
* **Retrieved entity co-occurrence ≠ relational support.** Negated /
  rejected / migrated relation text cannot ground a positive ``use`` query.
* **Recall improvements must not reduce grounding precision.**

Bound to the Atlas 1.0 compatibility anchor (AS-2.0-COMPAT-001). Never Layer B.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.hybrid_retrieval import HybridRetrievalError, build_hybrid_rrf_fusion
from project_atlas.retrieval import RetrievalResult, VaultRetriever
from project_atlas.retrieval_fusion import tokenize
from project_atlas.runtime_22 import (
    PROFILE_P2,
    Runtime22Error,
    compile_context,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.2-ASK2-001"
ARTIFACT_KIND = "ask-atlas-2-answer"
SCHEMA_KIND = "ask-atlas-2-answer"
TRUTH_BOUNDARY = (
    "ASK ATLAS 2 ≠ CANONICAL WRITE / UI ≠ TRUTH / GRAPH ≠ AUTHORITY / "
    "MODEL ≠ AUTHORITY / UNKNOWN STAYS UNKNOWN"
)
AUTHORITY_NOTE = (
    "Objective authority/freshness/conflict stamped by Core p2-readonly "
    "context compiler; Ask Atlas 2 never invents authority"
)
LEGACY_NOTE = (
    "Legacy/compatibility matches are non-authoritative and subordinate; "
    "they never ground an answer or change status"
)

RetrievalMode = Literal["exact", "prefix"]
DEFAULT_CAP = 20
MAX_CAP = 100
MAX_QUESTION_CHARS = 4096
DEFAULT_KINDS: tuple[str, ...] = ("concept", "claim")
SUPPORTED_KINDS = frozenset(
    {"source", "claim", "concept", "conflict", "authority", "provenance"}
)
_PROV_REF_FIELDS = ("ref", "source_id", "path", "source_lineage_id")
_FRESHNESS_COUNT_KEYS = ("fresh", "stale", "unknown")
_QUESTION_FUNCTION_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "describe",
        "description",
        "did",
        "directories",
        "directory",
        "do",
        "does",
        "exist",
        "exists",
        "explain",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "in",
        "is",
        "it",
        "its",
        "me",
        "of",
        "on",
        "or",
        "overview",
        "please",
        "primary",
        "project",
        "purpose",
        "summary",
        "tell",
        "that",
        "the",
        "their",
        "there",
        "these",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
    }
)
# Closed meta-linguistic claim*/use* lemmas. Stripped from required terms ONLY
# when they appear inside a closed claim-to-use scaffolding phrase (D-181).
_CLAIM_SCAFFOLD_LEMMAS = frozenset({"claim", "claims", "claiming", "claimed"})
_USE_SCAFFOLD_LEMMAS = frozenset({"use", "uses", "using", "used"})
# Present-tense use* forms that may satisfy a required relational "use" token.
# Past "used" is intentionally excluded so historical use ≠ current use.
_USE_PRESENT_SUPPORT = frozenset({"use", "uses", "using"})
# Closed engine aliases that may satisfy question term "database" / "databases".
# Do not alias D-150 leftover nouns (target/forecast/vault/ledger/…).
_DATABASE_SUPPORT_TOKENS = frozenset(
    {
        "database",
        "databases",
        "datastore",
        "db",
        "mongodb",
        "mysql",
        "postgres",
        "postgresql",
        "sqlite",
    }
)
# claim* … to … use* (≤3 intervening tokens). Deterministic; no fuzzy NLP.
_CLAIM_TO_USE_SCAFFOLD = re.compile(
    r"\b(?:claims?|claiming|claimed)(?:\s+\w+){0,3}\s+to\s+"
    r"(?:uses?|using|used)\b",
    re.IGNORECASE,
)
# Closed negative / non-affirming relation markers on record text (D-181).
_NEGATIVE_RELATION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\bdo(?:es)?\s+not\s+use\b", re.IGNORECASE),
    re.compile(r"\bdon'?t\s+use\b", re.IGNORECASE),
    re.compile(r"\bnever\s+uses?\b", re.IGNORECASE),
    re.compile(r"\brejected\b", re.IGNORECASE),
    re.compile(r"\bevaluated\b.{0,80}\brejected\b", re.IGNORECASE),
    re.compile(r"\bmigrated\s+(?:away\s+from|to)\b", re.IGNORECASE),
)

Status = Literal["known", "unknown", "conflict"]


class Ask2Error(ValueError):
    """Fail-closed Ask Atlas 2 error."""


def _extract_ref(item: dict[str, Any]) -> str | None:
    """Extract a provenance ref from a record provenance element (or ``None``)."""
    for field in _PROV_REF_FIELDS:
        value = item.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _record_provenance(hit: RetrievalResult) -> list[dict[str, str]]:
    """Build ``{kind, ref}`` pointers from a record's real provenance only.

    No synthetic pointers are injected: a record whose provenance is malformed
    or empty yields an empty list, so the Core context compiler fails closed
    (never a fabricated grounding).
    """
    pointers: list[dict[str, str]] = []
    for item in hit.provenance:
        ref = _extract_ref(item)
        if ref is not None:
            pointers.append({"kind": "source", "ref": ref})
    return pointers


_RECORD_TEXT_KEYS: Final[tuple[str, ...]] = (
    "title",
    "name",
    "label",
    "summary",
    "description",
    "body",
    "text",
    "content",
    "claim",
    "statement",
    "question",
    "answer",
    "rationale",
    "note",
    "notes",
    "excerpt",
    "path",
    "field",  # claim attribute under discussion (substantive, not a schema-key leak)
    "subject",
    "value",
)


def _collect_record_text(value: Any, *, depth: int = 0) -> list[str]:
    """Extract substantive text fields from a record (never schema key names)."""
    if depth > 6:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        out: list[str] = []
        for key, item in value.items():
            key_l = str(key).lower()
            if key_l in _RECORD_TEXT_KEYS or key_l.endswith(("_text", "_body", "_name", "_title")):
                out.extend(_collect_record_text(item, depth=depth + 1))
            elif isinstance(item, (dict, list, tuple)):
                # Descend into nested containers but only harvest known text keys.
                out.extend(_collect_record_text(item, depth=depth + 1))
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(_collect_record_text(item, depth=depth + 1))
        return out
    return []


def _claim_to_use_scaffold_tokens(question: str) -> frozenset[str]:
    """Return claim*/use* tokens that are meta scaffolding in this question.

    Only tokens matched by the closed ``claim* … to use*`` phrase rule are
    returned. A bare relational ``use`` (e.g. ``Does Helix use PostgreSQL?``)
    is never scaffolding.
    """
    drop: set[str] = set()
    for match in _CLAIM_TO_USE_SCAFFOLD.finditer(question):
        for token in tokenize(match.group(0)):
            if token in _CLAIM_SCAFFOLD_LEMMAS or token in _USE_SCAFFOLD_LEMMAS:
                drop.add(token)
    return frozenset(drop)


def _question_claim_terms(question: str) -> frozenset[str]:
    """Extract explicit, discriminative claim terms from a natural-language query.

    Retrieval ranking is deliberately broad; it can return a record merely
    because it shares a generic word with the question.  Grounding is stricter:
    every non-function term asserted by the question must be present in the
    candidate's substantive record text.  An empty term set means the question
    has no discriminative claim content and cannot ground an answer.

    D-181: ``claim*`` / ``use*`` are removed only inside closed claim-to-use
    scaffolding phrases — never as global stop-words — so a primary relational
    predicate cannot be silently discarded.
    """
    scaffold = _claim_to_use_scaffold_tokens(question)
    return frozenset(
        token
        for token in tokenize(question)
        if token not in _QUESTION_FUNCTION_WORDS
        and token not in scaffold
        and len(token) > 1
    )


def _record_tokens(hit: RetrievalResult) -> frozenset[str]:
    """Return lexical support tokens from substantive record text only."""
    parts = _collect_record_text(hit.record)
    return frozenset(tokenize("\n".join(parts)))


def _record_text_blob(hit: RetrievalResult) -> str:
    """Joined substantive record text for closed negative-relation scans."""
    return "\n".join(_collect_record_text(hit.record))


def _record_has_negative_relation(hit: RetrievalResult) -> bool:
    """True when record text negates / rejects / migrates away from a relation."""
    blob = _record_text_blob(hit)
    return any(pattern.search(blob) for pattern in _NEGATIVE_RELATION_PATTERNS)


def _term_supported_by_record(term: str, record_tokens: frozenset[str]) -> bool:
    """Closed, auditable support check for one required question term."""
    if term in record_tokens:
        return True
    # Present-tense use* may satisfy relational "use"; past "used" does not.
    if term == "use" and bool(record_tokens & _USE_PRESENT_SUPPORT):
        return True
    if term in {"database", "databases"}:
        return bool(record_tokens & _DATABASE_SUPPORT_TOKENS)
    return False


def _record_supports_required_terms(
    hit: RetrievalResult, required_terms: frozenset[str]
) -> bool:
    """True when record text relationally supports every required term.

    Entity co-occurrence alone is insufficient when the record carries a
    closed negative/rejected/migrated relation marker (D-181 precision).
    """
    if _record_has_negative_relation(hit):
        return False
    tokens = _record_tokens(hit)
    return all(_term_supported_by_record(term, tokens) for term in required_terms)


def _build_candidate(
    retriever: VaultRetriever,
    kind: str,
    record_id: str,
    scope: str,
    required_terms: frozenset[str],
) -> dict[str, Any] | None:
    """Resolve a claim-supporting record into a compile-context candidate."""
    if not required_terms:
        return None
    try:
        hits = retriever.lookup(kind, record_id, prefix=False, project_id=scope)
    except ValueError:
        return None
    hit = next((item for item in hits if item.record_id == record_id), None)
    if hit is None or not _record_supports_required_terms(hit, required_terms):
        return None
    return {
        "record_type": kind,
        "record_id": record_id,
        "slot": "hybrid-rrf",
        "authority_level": "derived",
        "provenance": _record_provenance(hit),
    }


def _derive_pack_id(scope: str, question: str) -> str:
    """Deterministic schema-safe pack id (NFR-001 — no wall-clock)."""
    digest = hashlib.sha256(f"{scope}\x00{question}".encode()).hexdigest()
    return f"ask2-{digest[:24]}"


def _evidence_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Project a compiled context entry into a subordinate-free evidence row."""
    out: dict[str, Any] = {
        "entry_id": str(entry["entry_id"]),
        "record_type": str(entry["record_type"]),
        "record_id": str(entry["record_id"]),
        "slot": str(entry.get("slot", "unknown")),
        "authority_level": str(entry["authority_level"]),
        "freshness": str(entry.get("freshness", "unknown")),
        "conflict_state": str(entry.get("conflict_state", "none")),
        "reason_included": str(entry.get("reason_included", "")),
        "relevance_rank": int(entry.get("relevance_rank", 0)),
        "provenance": [
            {"kind": str(ptr["kind"]), "ref": str(ptr["ref"])}
            for ptr in entry.get("provenance", [])
        ],
    }
    conflict_ids = entry.get("conflict_ids")
    if isinstance(conflict_ids, list) and conflict_ids:
        out["conflict_ids"] = [str(cid) for cid in conflict_ids]
    return out


def _legacy_compatibility(
    retriever: VaultRetriever,
    kinds: tuple[str, ...],
    question: str,
    scope: str,
    *,
    extra: list[dict[str, Any]] | None,
    enabled: bool,
) -> dict[str, Any]:
    """Collect subordinate legacy/compatibility matches (never authority).

    A naive project-scoped substring scan mirrors the legacy Ask Atlas
    behaviour; results are explicitly non-authoritative and cannot ground an
    answer. Caller-supplied ``extra`` matches (e.g. from the legacy live path)
    are passed through with the same subordination.
    """
    matches: list[dict[str, str]] = []
    needle = question.lower()
    if enabled:
        for kind in kinds:
            try:
                corpus = retriever.bm25_corpus(kind, project_id=scope)
            except ValueError:
                continue
            for record_id, text in corpus:
                if needle in text.lower() or needle in record_id.lower():
                    matches.append(
                        {
                            "record_type": kind,
                            "record_id": record_id,
                            "source": "legacy-substring",
                        }
                    )
    for item in extra or []:
        matches.append(
            {
                "record_type": str(item.get("record_type") or "legacy"),
                "record_id": str(item.get("record_id") or ""),
                "source": "external",
            }
        )
    ordered = sorted(
        matches, key=lambda m: (m["record_type"], m["record_id"], m["source"])
    )
    return {
        "authoritative": False,
        "subordinate": True,
        "match_count": len(ordered),
        "matches": ordered,
        "note": LEGACY_NOTE,
    }


def _freshness_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {key: 0 for key in _FRESHNESS_COUNT_KEYS}
    for entry in entries:
        label = str(entry.get("freshness", "unknown"))
        if label in counts:
            counts[label] += 1
    if not entries:
        aggregate = "unknown"
    elif counts["stale"]:
        aggregate = "stale"
    elif counts["unknown"]:
        aggregate = "unknown"
    else:
        aggregate = "fresh"
    return {
        "aggregate": aggregate,
        "fresh_count": counts["fresh"],
        "stale_count": counts["stale"],
        "unknown_count": counts["unknown"],
    }


def ask_atlas_2(
    vault: Path,
    *,
    question: str,
    project_id: str,
    kinds: tuple[str, ...] = DEFAULT_KINDS,
    mode: RetrievalMode = "exact",
    budget: int = DEFAULT_CAP,
    retrieval_cap: int = DEFAULT_CAP,
    include_unresolved_conflicts: bool = True,
    legacy_matches: list[dict[str, Any]] | None = None,
    legacy_scan: bool = True,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Answer a project-scoped question over Core evidence (read-only).

    Runs project-scoped BM25/RRF hybrid retrieval, compiles the candidates
    through the Core ``p2-readonly`` context compiler, and renders a fail-closed
    answer contract. ``project_id`` is structurally required. Missing indexes
    and malformed/empty provenance fail closed. Legacy matches are always
    subordinate and never change ``status``.
    """
    anchor_obj = anchor or require_compatibility_anchor()

    q = question.strip()
    if not q:
        raise Ask2Error("ask2-question-empty")
    if len(q) > MAX_QUESTION_CHARS:
        raise Ask2Error(f"ask2-question-too-long:{len(q)}")

    scope = project_id.strip()
    if not scope:
        raise Ask2Error("ask2-project-scope-required")

    if mode not in ("exact", "prefix"):
        raise Ask2Error(f"ask2-mode-invalid:{mode}")

    probed = tuple(dict.fromkeys(kinds))
    if not probed:
        raise Ask2Error("ask2-kinds-empty")
    for kind in probed:
        if kind not in SUPPORTED_KINDS:
            raise Ask2Error(f"ask2-kind-unsupported:{kind}")

    if not isinstance(budget, int) or isinstance(budget, bool):
        raise Ask2Error(f"ask2-budget-invalid:{budget!r}")
    if not isinstance(retrieval_cap, int) or isinstance(retrieval_cap, bool):
        raise Ask2Error(f"ask2-retrieval-cap-invalid:{retrieval_cap!r}")

    retriever = VaultRetriever(vault)
    required_terms = _question_claim_terms(q)
    candidates: list[dict[str, Any]] = []
    total_results = 0
    for kind in probed:
        try:
            fusion = build_hybrid_rrf_fusion(
                vault,
                kind=kind,
                value=q,
                project_id=scope,
                mode=mode,
                cap=retrieval_cap,
                anchor=anchor_obj,
            )
        except HybridRetrievalError as exc:
            raise Ask2Error(f"ask2-retrieval-substrate:{exc}") from exc
        total_results += int(fusion["result_count"])
        for row in fusion["results"]:
            candidate = _build_candidate(
                retriever,
                kind,
                str(row["record_id"]),
                scope,
                required_terms,
            )
            if candidate is not None:
                candidates.append(candidate)

    pack_id = _derive_pack_id(scope, q)
    try:
        package = compile_context(
            vault,
            pack_id=pack_id,
            candidates=candidates,
            project_id=scope,
            budget=budget,
            profile_id=PROFILE_P2,
            on_overflow="truncate",
            include_unresolved_conflicts=include_unresolved_conflicts,
        )
    except Runtime22Error as exc:
        raise Ask2Error(f"ask2-context-compiler:{exc}") from exc

    entries: list[dict[str, Any]] = list(package["entries"])
    evidence = [_evidence_entry(entry) for entry in entries]
    unresolved = [e for e in entries if e.get("conflict_state") == "unresolved"]

    if not entries:
        status: Status = "unknown"
    elif unresolved:
        status = "conflict"
    else:
        status = "known"

    unknown_reasons: list[str] = []
    if not entries:
        unknown_reasons.append("no-grounded-evidence")
        if not required_terms:
            unknown_reasons.append("no-discriminative-claim-terms")
        elif not candidates and total_results:
            unknown_reasons.append("retrieval-hits-lack-claim-support")
        elif not candidates:
            unknown_reasons.append("no-project-scoped-retrieval-hits")
        else:
            unknown_reasons.append("all-candidates-excluded")

    conflict_ids = sorted(
        {
            str(cid)
            for entry in entries
            for cid in entry.get("conflict_ids", [])
        }
    )

    legacy = _legacy_compatibility(
        retriever,
        probed,
        q,
        scope,
        extra=legacy_matches,
        enabled=legacy_scan,
    )

    answer: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "artifact_kind": ARTIFACT_KIND,
        "question": q,
        "project_id": scope,
        "kinds_probed": list(probed),
        "status": status,
        "ANSWER": None,
        "EVIDENCE": evidence,
        "evidence_count": len(evidence),
        "AUTHORITY": {
            "level": "derived",
            "source": "core-context-compiler",
            "llm_authority": False,
            "graph_authority": False,
            "note": AUTHORITY_NOTE,
        },
        "FRESHNESS": _freshness_summary(entries),
        "CONFLICTS": {
            "unresolved_count": len(unresolved),
            "conflict_ids": conflict_ids,
            "retained_as_sidecars": bool(unresolved),
        },
        "UNKNOWN": {
            "is_unknown": status == "unknown",
            "reasons": unknown_reasons,
        },
        "legacy_compatibility": legacy,
        "retrieval": {
            "engine": "lexical-bm25-rrf",
            "project_scoped": True,
            "semantic_enabled": False,
            "mode": mode,
            "kinds": list(probed),
            "result_count": total_results,
            "candidate_count": len(candidates),
        },
        "context": {
            "pack_id": pack_id,
            "profile_id": str(package["profile_id"]),
            "entry_count": int(package["entry_count"]),
            "pipeline": [str(step) for step in package["pipeline"]],
            "truncated": bool(package["truncated"]),
        },
        "canonical_write": False,
        "ui_truth": False,
        "graph_authority": False,
        "llm_authority": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(answer, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise Ask2Error(f"ask2-answer-schema:{exc}") from exc
    return answer


def answer_to_json(payload: dict[str, Any]) -> str:
    """Serialize an Ask Atlas 2 answer deterministically (NFR-001)."""
    validate_record(payload, SCHEMA_KIND)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"

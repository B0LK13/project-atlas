"""Deterministic BM25 + Reciprocal Rank Fusion helpers (AS-RET hybrid P2).

Pure ranking utilities over AS-RET-001 lexical substrates. Semantic / embedding
signals are out of scope here — callers must keep semantic non-authoritative.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.ASCII)

# Okapi BM25 defaults (fixed — no runtime tuning drift).
BM25_K1 = 1.2
BM25_B = 0.75
# Classic Cormack et al. RRF constant.
RRF_K = 60


def tokenize(text: str) -> list[str]:
    """Lowercase ASCII alnum tokenization (deterministic, offline)."""
    return _TOKEN_RE.findall(text.lower())


def bm25_rank(
    query: str,
    corpus: Sequence[tuple[str, str]],
    *,
    k1: float = BM25_K1,
    b: float = BM25_B,
) -> list[tuple[str, float]]:
    """Rank corpus documents by Okapi BM25; ties break on record_id ascending.

    Returns ``(record_id, score)`` for documents with score > 0 only.
    Empty query raises ``ValueError`` (fail-closed).
    """
    query_tokens = tokenize(query)
    if not query_tokens:
        raise ValueError("bm25 query must be non-empty")

    docs: list[tuple[str, list[str]]] = [
        (record_id, tokenize(text)) for record_id, text in corpus
    ]
    n_docs = len(docs)
    if n_docs == 0:
        return []

    avgdl = sum(len(tokens) for _, tokens in docs) / n_docs
    df: Counter[str] = Counter()
    for _, tokens in docs:
        df.update(set(tokens))

    query_tf = Counter(query_tokens)
    scored: list[tuple[str, float]] = []
    for record_id, tokens in docs:
        if not tokens:
            continue
        tf = Counter(tokens)
        dl = len(tokens)
        score = 0.0
        for term, qtf in sorted(query_tf.items()):
            term_df = df.get(term, 0)
            if term_df == 0:
                continue
            idf = math.log(1.0 + (n_docs - term_df + 0.5) / (term_df + 0.5))
            freq = tf.get(term, 0)
            denom = freq + k1 * (1.0 - b + b * dl / avgdl)
            score += qtf * idf * ((freq * (k1 + 1.0)) / denom)
        if score > 0.0:
            scored.append((record_id, score))

    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored


def rrf_fuse(
    rankings: Mapping[str, Sequence[str]],
    *,
    k: int = RRF_K,
) -> list[tuple[str, float, dict[str, int]]]:
    """Fuse named ranked lists via Reciprocal Rank Fusion.

    ``rankings`` maps slot name → ordered record ids (rank 1 = first).
    Returns ``(record_id, rrf_score, ranks_by_slot)`` sorted by score desc,
    then record_id asc. Empty rankings yield an empty list.
    """
    if k < 1:
        raise ValueError("rrf k must be >= 1")

    scores: dict[str, float] = {}
    ranks_by_id: dict[str, dict[str, int]] = {}
    for slot_name in sorted(rankings):
        ordered = rankings[slot_name]
        seen: set[str] = set()
        for index, record_id in enumerate(ordered, start=1):
            if record_id in seen:
                continue
            seen.add(record_id)
            scores[record_id] = scores.get(record_id, 0.0) + 1.0 / (k + index)
            ranks_by_id.setdefault(record_id, {})[slot_name] = index

    fused = [
        (record_id, score, dict(sorted(ranks_by_id[record_id].items())))
        for record_id, score in scores.items()
    ]
    fused.sort(key=lambda item: (-item[1], item[0]))
    return fused


def ranking_ids(scored: Iterable[tuple[str, float]]) -> list[str]:
    """Project BM25 scored pairs to ordered ids."""
    return [record_id for record_id, _score in scored]

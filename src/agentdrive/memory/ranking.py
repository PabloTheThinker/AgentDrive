"""
Lexical + BM25 ranking for Memory Bank search.

Combines token overlap signals with Okapi-BM25 over the active candidate set.
Dependency-free — suitable for local MCP loops and offline swarms.
"""

from __future__ import annotations

import math
import re
from typing import Any

_TOKEN_RE = re.compile(r"\w{2,}", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return _TOKEN_RE.findall(text.lower())


def lexical_bm25_scores(
    query: str,
    documents: list[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Score each document against the query using smoothed Okapi-BM25."""
    doc_count = len(documents)
    query_terms = set(_tokenize(query))
    if not query_terms or doc_count == 0:
        return [0.0] * doc_count

    tokenized = [_tokenize(doc) for doc in documents]
    lengths = [len(tokens) for tokens in tokenized]
    if not any(lengths):
        return [0.0] * doc_count
    avg_len = sum(lengths) / doc_count or 1.0

    doc_freq = {term: 0 for term in query_terms}
    for tokens in tokenized:
        for term in set(tokens) & query_terms:
            doc_freq[term] += 1

    idf = {
        term: math.log((doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5) + 1)
        for term in query_terms
    }

    scores: list[float] = []
    for tokens, doc_len in zip(tokenized, lengths):
        if doc_len == 0:
            scores.append(0.0)
            continue
        term_freq: dict[str, int] = {}
        for token in tokens:
            if token in query_terms:
                term_freq[token] = term_freq.get(token, 0) + 1
        total = 0.0
        for term, freq in term_freq.items():
            numerator = freq * (k1 + 1)
            denominator = freq + k1 * (1 - b + b * doc_len / avg_len)
            total += idf[term] * numerator / denominator
        scores.append(total)
    return scores


def rank_memory_candidates(
    candidates: list[dict[str, Any]],
    query: str,
    *,
    signal_weight: float = 0.55,
    bm25_weight: float = 0.45,
) -> list[tuple[float, dict[str, Any]]]:
    """
    Rank memory candidate dicts.

    Each candidate needs ``text`` and optional ``signal_score`` from the store.
    """
    if not candidates:
        return []

    documents = [str(item.get("text") or "") for item in candidates]
    bm25_raw = lexical_bm25_scores(query, documents)
    bm25_peak = max(bm25_raw) if bm25_raw else 0.0
    bm25_scaled = (
        [value / bm25_peak for value in bm25_raw] if bm25_peak > 0 else [0.0] * len(bm25_raw)
    )

    ranked: list[tuple[float, dict[str, Any]]] = []
    for candidate, bm25_value in zip(candidates, bm25_scaled):
        signal = float(candidate.get("signal_score") or 0.0)
        signal_scaled = min(1.0, signal / 15.0) if signal > 0 else 0.0
        score = signal_weight * signal_scaled + bm25_weight * bm25_value
        ranked.append((score, candidate))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return ranked

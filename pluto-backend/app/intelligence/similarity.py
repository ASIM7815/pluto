"""Semantic similarity for PLUTO's local NLU.

Two orthogonal measures:
- TF-IDF cosine similarity: captures meaning over a vocabulary (used when we
  have a corpus / candidate corpus to compare against).
- Fuzzy sequence similarity (difflib): handles typos / near-identical strings.

Both are fully local and dependency-light (scikit-learn + difflib).
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from app.core.logging import get_logger

logger = get_logger(__name__)


def fuzzy_similarity(a: str, b: str) -> float:
    """Character-level similarity ratio (0..1) via difflib."""
    from difflib import SequenceMatcher

    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def cosine_similarity_matrix(
    corpus: Sequence[str],
    query: str,
    ngram_range: Tuple[int, int] = (1, 2),
) -> List[float]:
    """TF-IDF cosine similarity of ``query`` against each ``corpus`` item.

    Returns a list of floats in the same order as ``corpus``. Falls back to
    fuzzy similarity when scikit-learn is unavailable or the vocabulary is
    empty (e.g. degenerate single-word corpus).
    """
    docs = [query] + list(corpus)
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(
            lowercase=True, stop_words="english",
            ngram_range=ngram_range, analyzer="word",
            sublinear_tf=True, max_features=20000,
        )
        matrix = vectorizer.fit_transform(docs)
        sims = cosine_similarity(matrix[0:1], matrix[1:])[0]
        return [float(x) for x in sims]
    except Exception as e:  # noqa: BLE001
        logger.debug("cosine_similarity_fallback", error=str(e))
        return [fuzzy_similarity(query, item) for item in corpus]


def most_similar(
    query: str,
    candidates: Sequence[str],
    top: int = 3,
    threshold: float = 0.35,
) -> List[Tuple[str, float]]:
    """Return the most similar candidates (desc), above ``threshold``."""
    scores = cosine_similarity_matrix(candidates, query)
    ranked = sorted(
        ((cand, float(score)) for cand, score in zip(candidates, scores)),
        key=lambda x: x[1], reverse=True,
    )
    return [(cand, score) for cand, score in ranked
            if score >= threshold][:max(1, top)]

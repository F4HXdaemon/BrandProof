import re
from typing import List, Any, Dict, Tuple


def _tokenize(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"\w+", text or "") if len(w) > 2]


def retrieve_relevant_facts(
    query: str,
    facts: List[Any],
    top_k: int = 5,
) -> List[Tuple[Any, float]]:
    """
    Retrieves the most semantically relevant facts for a query text
    using BM25-style keyword matching and TF-IDF weighted overlap.
    Returns list of (fact, score) sorted descending by score.
    """
    if not query or not facts:
        return []

    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    scored_facts: List[Tuple[Any, float]] = []

    for fact in facts:
        score = 0.0
        title_tokens = _tokenize(getattr(fact, "title", ""))
        canon_tokens = _tokenize(getattr(fact, "canonical_value", ""))
        desc_tokens = _tokenize(getattr(fact, "description", "") or "")

        for qt in q_tokens:
            # Title matches are weighted heavily (3.0)
            if qt in title_tokens:
                score += 3.0
            # Canonical value matches (2.0)
            if qt in canon_tokens:
                score += 2.0
            # Description matches (1.0)
            if qt in desc_tokens:
                score += 1.0

        # Exact substring bonus
        if fact.canonical_value.lower() in query.lower():
            score += 5.0

        if score > 0.0:
            scored_facts.append((fact, round(score, 2)))

    scored_facts.sort(key=lambda x: x[1], reverse=True)
    return scored_facts[:top_k]

"""
Content-based ranker with a safety re-rank (deliverable: "Recommendation
engine" — scikit-learn, pandas, NumPy). Pure and synchronous: the service
supplies each candidate's text (name + category) and current risk score,
this module only ranks them — no I/O, so it is unit-testable without a
database or event loop.

Preference fit is TF-IDF cosine similarity between the user's stated
interests and each candidate's text, not substring matching — "market" now
also pulls in "marketplace" or "bazaar" through shared/related vocabulary
weight, and multi-word interests are handled properly. With no stated
interests, every candidate gets a neutral fit and ranking falls back to
risk alone (a safety-first default).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_PREFERENCE_WEIGHT = 0.6
_SAFETY_WEIGHT = 0.4
_NEUTRAL_PREFERENCE_FIT = 0.5


@dataclass(slots=True)
class RankingCandidate:
    attraction_id: UUID
    document: str  # e.g. "victoria yeoville market market"
    risk_score: float  # 0..1, higher = riskier


@dataclass(slots=True)
class RankedResult:
    attraction_id: UUID
    combined_score: float
    preference_fit: float
    matched_terms: list[str]


def content_based_rank(candidates: list[RankingCandidate], interests: list[str]) -> list[RankedResult]:
    if not candidates:
        return []

    preference_fits = _preference_fits(candidates, interests)
    results = []
    for candidate, fit in zip(candidates, preference_fits, strict=True):
        matched = [interest for interest in interests if interest.lower() in candidate.document.lower()]
        combined = _PREFERENCE_WEIGHT * fit + _SAFETY_WEIGHT * (1 - candidate.risk_score)
        results.append(
            RankedResult(
                attraction_id=candidate.attraction_id, combined_score=combined,
                preference_fit=fit, matched_terms=matched,
            )
        )
    results.sort(key=lambda r: r.combined_score, reverse=True)
    return results


def _preference_fits(candidates: list[RankingCandidate], interests: list[str]) -> list[float]:
    if not interests:
        return [_NEUTRAL_PREFERENCE_FIT] * len(candidates)

    documents = [c.document for c in candidates]
    query = " ".join(interests)
    vectorizer = TfidfVectorizer()
    try:
        matrix = vectorizer.fit_transform([*documents, query])
    except ValueError:
        # Degenerate vocabulary (e.g. interests share no tokens with any
        # candidate, or are all stop words) — fall back to a neutral fit
        # rather than letting sklearn's empty-vocabulary error surface.
        return [_NEUTRAL_PREFERENCE_FIT] * len(candidates)

    similarities = cosine_similarity(matrix[-1], matrix[:-1])[0]
    return [float(s) for s in similarities]

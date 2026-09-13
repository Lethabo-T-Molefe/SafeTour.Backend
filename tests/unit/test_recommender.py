"""Unit tests for the content-based ranker + safety re-rank."""

from uuid import uuid4

from safetour.modules.itineraries.recommender import RankingCandidate, content_based_rank


def test_no_interests_falls_back_to_risk_only_ranking() -> None:
    safe = RankingCandidate(attraction_id=uuid4(), document="quiet museum attraction", risk_score=0.1)
    risky = RankingCandidate(attraction_id=uuid4(), document="busy market market", risk_score=0.9)

    ranked = content_based_rank([safe, risky], [])

    assert ranked[0].attraction_id == safe.attraction_id
    assert ranked[0].preference_fit == ranked[1].preference_fit  # neutral for both


def test_matching_interest_outranks_a_safer_but_irrelevant_option() -> None:
    market = RankingCandidate(attraction_id=uuid4(), document="Yeoville market market", risk_score=0.5)
    museum = RankingCandidate(attraction_id=uuid4(), document="quiet history museum", risk_score=0.5)

    ranked = content_based_rank([market, museum], ["market"])

    assert ranked[0].attraction_id == market.attraction_id
    assert ranked[0].preference_fit > ranked[1].preference_fit
    assert "market" in ranked[0].matched_terms


def test_safety_rerank_can_overcome_a_weak_preference_edge() -> None:
    slightly_relevant_but_dangerous = RankingCandidate(
        attraction_id=uuid4(), document="market adjacent alley", risk_score=0.95
    )
    very_safe_and_relevant = RankingCandidate(attraction_id=uuid4(), document="market market market", risk_score=0.05)

    ranked = content_based_rank([slightly_relevant_but_dangerous, very_safe_and_relevant], ["market"])

    assert ranked[0].attraction_id == very_safe_and_relevant.attraction_id


def test_empty_candidate_list_returns_empty() -> None:
    assert content_based_rank([], ["market"]) == []


def test_degenerate_vocabulary_falls_back_to_neutral_fit() -> None:
    # Neither the document nor the interest tokenizes to a real word (TF-IDF's
    # default pattern needs word characters), so sklearn would raise on an
    # empty vocabulary — the ranker must catch that and stay neutral instead.
    candidate = RankingCandidate(attraction_id=uuid4(), document="!!!", risk_score=0.3)
    ranked = content_based_rank([candidate], ["???"])
    assert ranked[0].preference_fit == 0.5

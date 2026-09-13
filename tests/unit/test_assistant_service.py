"""Unit tests for the assistant's provenance validator and keyword fallback (MLR-6)."""

from safetour.modules.assistant.service import _extract_interests, _validate_llm_keywords


def test_deterministic_fallback_matches_known_keywords() -> None:
    # "rank" is itself a recognised keyword (taxi rank), so it is picked up
    # alongside "market" and "taxi" — sorted alphabetically.
    assert _extract_interests("I'd like to visit a market and a taxi rank") == ["market", "rank", "taxi"]


def test_deterministic_fallback_uses_longer_words_when_nothing_known_matches() -> None:
    result = _extract_interests("show me something historic and quiet")
    assert result  # falls back to any words longer than 3 chars
    assert all(len(word) > 3 for word in result)


def test_validator_accepts_a_clean_comma_separated_list() -> None:
    assert _validate_llm_keywords("market, museum, food") == ["market", "museum", "food"]


def test_validator_rejects_anything_that_is_not_plain_keywords() -> None:
    # A prompt-injected or hallucinating model might try to return a sentence,
    # a place name with punctuation, or a fabricated risk claim — none of
    # that should survive validation.
    assert _validate_llm_keywords("Sure! Visit 123 Main St, it's totally safe.") is None


def test_validator_caps_the_keyword_count() -> None:
    words = ["market", "museum", "food", "nightlife", "park", "shopping", "history", "art", "music", "sport"]
    result = _validate_llm_keywords(", ".join(words))
    assert result is not None
    assert len(result) <= 5


def test_validator_rejects_overly_long_tokens() -> None:
    assert _validate_llm_keywords("a" * 50) is None

"""Unit tests for the feedback content filter (FR-FDBK-1)."""

from safetour.modules.feedback.domain import contains_blocked_content


def test_clean_comment_is_not_blocked() -> None:
    assert not contains_blocked_content("This route felt safe and well lit.")


def test_none_comment_is_not_blocked() -> None:
    assert not contains_blocked_content(None)


def test_blocked_word_is_caught() -> None:
    assert contains_blocked_content("this place is stupid and unsafe")

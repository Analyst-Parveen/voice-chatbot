"""Unit tests for the fixed-window rate limit counter."""

from app.core.rate_limit import _FixedWindowCounter


def test_allows_up_to_limit_then_blocks() -> None:
    counter = _FixedWindowCounter(limit=3, window_seconds=60)
    results = [counter.allow("client-a")[0] for _ in range(4)]
    assert results == [True, True, True, False]


def test_keys_are_independent() -> None:
    counter = _FixedWindowCounter(limit=1, window_seconds=60)
    assert counter.allow("a")[0] is True
    assert counter.allow("b")[0] is True  # different key, own window
    assert counter.allow("a")[0] is False


def test_remaining_counts_down() -> None:
    counter = _FixedWindowCounter(limit=2, window_seconds=60)
    assert counter.allow("k") == (True, 1)
    assert counter.allow("k") == (True, 0)
    assert counter.allow("k") == (False, 0)

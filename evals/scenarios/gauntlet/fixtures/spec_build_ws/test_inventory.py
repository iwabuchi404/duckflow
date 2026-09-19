"""Tests for inventory.allocate — encodes every rule in SPEC.md."""

from inventory import allocate


def test_full_allocation() -> None:
    """Enough stock → full request allocated."""
    assert allocate({"apple": 10}, {"apple": 4}) == {"apple": 4}


def test_partial_allocation() -> None:
    """Request exceeds stock → only available stock is allocated."""
    assert allocate({"banana": 2}, {"banana": 5}) == {"banana": 2}


def test_missing_sku_omitted() -> None:
    """Sku not in stock is omitted, not zeroed."""
    assert allocate({}, {"cherry": 3}) == {}


def test_zero_and_negative_request_omitted() -> None:
    """Non-positive requested quantities are omitted."""
    result = allocate({"apple": 5}, {"apple": 0})
    assert result == {}
    result = allocate({"apple": 5}, {"apple": -2})
    assert result == {}


def test_mixed_request() -> None:
    """Mixed request: partial + full + missing + zero."""
    stock = {"a": 3, "b": 10}
    request = {"a": 5, "b": 2, "c": 1, "d": 0}
    assert allocate(stock, request) == {"a": 3, "b": 2}


def test_does_not_mutate_inputs() -> None:
    """Inputs must not be mutated."""
    stock = {"a": 3}
    request = {"a": 2}
    allocate(stock, request)
    assert stock == {"a": 3}
    assert request == {"a": 2}

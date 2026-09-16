"""Existing + new-behavior tests for paginated list_items."""

from api import list_items
from app import main


def test_returns_all() -> None:
    """Existing behavior: no args returns everything."""
    assert list_items() == ["a", "b", "c", "d", "e"]


def test_main_runs(capsys) -> None:
    """Existing caller still works."""
    main()
    assert capsys.readouterr().out.strip() == "5"


def test_pagination_page2() -> None:
    """New behavior: page 2 with 2 per page."""
    assert list_items(page=2, per_page=2) == ["c", "d"]


def test_pagination_out_of_range() -> None:
    """New behavior: out-of-range page returns empty."""
    assert list_items(page=10, per_page=2) == []

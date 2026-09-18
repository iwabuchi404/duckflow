from api import search
from cli import main
from reports import count
from store import load_entries
from worker import sync


def test_renamed_definition() -> None:
    """Renamed function returns three records."""
    assert load_entries("a") == ["a-0", "a-1", "a-2"]


def test_callers_updated() -> None:
    """All callers route through the renamed function."""
    assert search("b") == ["b-0", "b-1", "b-2"]
    assert sync("c") == 3
    assert count("d") == 3
    main("e")

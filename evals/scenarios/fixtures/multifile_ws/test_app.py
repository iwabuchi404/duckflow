from app import main
from core import calculate_total


def test_total_renamed() -> None:
    """Renamed function sums correctly."""
    assert calculate_total([1, 2, 3]) == 6


def test_main_runs(capsys) -> None:
    """App entry point prints 6."""
    main()
    assert capsys.readouterr().out.strip() == "6"

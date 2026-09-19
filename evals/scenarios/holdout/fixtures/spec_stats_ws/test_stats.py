from stats import summarize


def test_basic() -> None:
    s = summarize([1.0, 2.0, 3.0])
    assert s == {"count": 3, "total": 6.0, "mean": 2.0, "min": 1.0, "max": 3.0}


def test_empty_returns_empty_dict() -> None:
    assert summarize([]) == {}


def test_single_value() -> None:
    s = summarize([5.0])
    assert s["count"] == 1
    assert s["mean"] == 5.0
    assert s["min"] == s["max"] == 5.0


def test_negatives() -> None:
    s = summarize([-2.0, 4.0])
    assert s["min"] == -2.0
    assert s["total"] == 2.0


def test_does_not_mutate_input() -> None:
    data = [3.0, 1.0, 2.0]
    summarize(data)
    assert data == [3.0, 1.0, 2.0]

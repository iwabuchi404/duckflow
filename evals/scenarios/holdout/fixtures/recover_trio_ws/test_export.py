from export import render_lines


def test_render_lines_separates_rows() -> None:
    out = render_lines([("apple", 300.0), ("banana", 150.0)])
    lines = out.splitlines()
    assert len(lines) == 2
    assert "apple" in lines[0]
    assert "banana" in lines[1]

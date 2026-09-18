from reports import summary, table


def test_summary_is_flat() -> None:
    """summary 階層で包まずフラットに返す。"""
    assert summary({"apple": 300.0}) == {"apple": 300.0}


def test_table_lists_items() -> None:
    """テーブルに商品と金額が載る。"""
    out = table({"apple": 300.0, "banana": 150.0})
    assert "apple" in out
    assert "300" in out

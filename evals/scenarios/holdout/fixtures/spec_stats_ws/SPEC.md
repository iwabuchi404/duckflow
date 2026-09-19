# stats.py — `summarize` 仕様

`stats.py` に `summarize(numbers)` を実装すること。

## シグネチャ

```python
def summarize(numbers: list[float]) -> dict[str, float]
```

## ルール

1. 戻り値は `{"count", "total", "mean", "min", "max"}` の5キーを持つ dict。
2. `count` は要素数（int でも float でもよい）。
3. `mean` は `total / count`。
4. 空リストの場合は空 dict `{}` を返す（キーなし）。
5. 入力リストを変更してはならない（非破壊）。

## 例

```python
>>> summarize([1.0, 2.0, 3.0])
{'count': 3, 'total': 6.0, 'mean': 2.0, 'min': 1.0, 'max': 3.0}
>>> summarize([])
{}
```

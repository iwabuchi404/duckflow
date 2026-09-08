# Sym-Ops v2 vs v3.2 差分レポート

## 概要

本レポートは、`docs/old/Sym-Ops v2.md` に定義された v2 仕様と、現在の実装 `companion/utils/sym_ops.py` に基づく v3.2 実装の差分を特定する。

---

## 1. Vitals の命名変更（Breaking Change）

| 記号 | v2 の意味 | v3.2 の意味 | 影響 |
|:---:|:---|:---|:---|
| `::c` | Confidence (信頼度) | Confidence (信頼度) | **変更なし** |
| `::m` | **Mood** (気分) | **Memory** (メモリ使用量) | パースロジック変更 |
| `::f` | Focus (集中力) | Focus (集中力) | **変更なし** |
| `::s` | **Stamina** (スタミナ) | **Safety** (安全性) | 安全性の意味に統一 |

**v2 実装（sym_ops.py 309-316行目）:**
```python
patterns = {
    'confidence': r'::c([\d.]+)',
    'mood': r'::m([\d.]+)',
    'focus': r'::f([\d.]+)',
    'stamina': r'::s([\d.]+)'
}
```

**v3.2 実装（sym_ops.py 881-888行目）:**
```python
def _is_vitals(self, line: str) -> bool:
    v_matches = re.findall(r"::[cmfs][\d.]+", line)
    if not v_matches:
        return False
    return True
```
v3.2 では個々のパターンマッチから包括的な正規表現へ変更。`m` = Memory, `s` = Safety として処理される。

---

## 2. アクションプレフィックス

| 項目 | v2 | v3.2 |
|:---|:---|:---|
| プレフィックス | `$` 接頭辞（例: `$ create @file`） | `::` 接頭辞（例: `::write_file @path`） |
| 正規表現 | `^\$` | `^::` |

v3.2 では `$` を廃止し、`::` に統一。これにより Markdown内の `$` 変数記法との衝突を回避。

---

## 3. コンテンツブロック区切り

| 項目 | v2 | v3.2 |
|:---|:---|:---|
| 開始記号 | `<<<` | `<<<` |
| 終了記号 | `>>>` | `>>>` |
| 終了位置 | 全文字列一致 | **行頭（column 0）のみ**で認識 |

v3.2 では `>>>` に行頭制限を設け、Python doctest やコード内の `>>>` がブロック終端として誤認識されるのを防止。

---

## 4. バッチ区切り文字

| 項目 | v2 | v3.2 |
|:---|:---|:---|
| 区切り記号 | `---`（Markdown水平線） | `%%%` |
| 衝突リスク | Markdown/Diffと衝突（v1の問題を再発） | **衝突ゼロ** |

v2 仕様では `---` をバッチ区切りとしていたが、これは v1 の問題点（Markdownとの衝突）を再発させる。v3.2 で `%%%` に変更済み。

---

## 5. 推論（Reasoning）

| 項目 | v2 | v3.2 |
|:---|:---|:---|
| 形式 | `<reasoning>` タグ形式 | `>>` 接頭辞（Thought） |
| 処理 | XMLタグベースの抽出 | 行頭 `>>` の正規表現マッチ |

v3.2 では `strip_reasoning_tags()` や `reasoning_to_thought()` 等の preprocessor 関数を通じて `>>` 形式に変換。

---

## 6. YAML フロントマターサポート（新機能）

v3.2 で**新規追加**。コンテンツブロック内で YAML 形式のパラメータ指定が可能に。

```
::run_command @python script.py
key: value
limit: 10
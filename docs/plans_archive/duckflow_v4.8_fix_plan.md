# ドキュメント：v4.8 データ連携パイプラインの最終FIX・実装指示書

## 1. 概要

### 1.1. 目的
LLMがデータ連携のために計画した `action_id` が、Pythonコード側で意図せず上書きされてしまう問題を修正する。これにより、アクション間のデータ連携（`ref:`構文）を完全に機能させ、システムの信頼性を向上させる。

### 1.2. 根本原因
`enhanced_core_v8.py` の `_generate_next_actions` メソッドが、LLMからの `action_id` を確認せず、常に新しいIDを自動生成してしまっていた。

### 1.3. 解決策
`_generate_next_actions` メソッドを修正し、LLMが `action_id` を指定した場合はそれを尊重し、指定しなかった場合にのみフォールバックとしてIDを自動生成するロジックに変更する。

### 1.4. 主な対象ファイル
- `companion/enhanced_core_v8.py`

---

## 2. 実装ステップ

### ステップ1: `action_id` の処理ロジックの修正

**担当ファイル:** `companion/enhanced_core_v8.py`
**担当メソッド:** `_generate_next_actions`

**タスク:**
`replace` ツールを使用し、`_generate_next_actions` メソッド内の `action_id` を決定する行を修正してください。

**具体的な修正:**

```python
# old_string
                    action_id = f"{action_id_base}_{{i}}_{operation.replace('.', '_')}"
                    parameters = action_data.get("parameters", {})
                    reasoning = action_data.get("reasoning", "")

# new_string
                    # LLMが指定したaction_idを優先的に使用し、なければ自動生成する
                    action_id = action_data.get("action_id") or f"{action_id_base}_{{i}}_{operation.replace('.', '_')}"
                    parameters = action_data.get("parameters", {})
                    reasoning = action_data.get("reasoning", "")
```

**変更点の解説:**
この修正により、LLMの計画に `action_id` が含まれている場合はその値が維持され、データ連携が正しく機能するようになります。

## 3. レビューの観点

実装完了後、私がレビューする際の主要な確認項目は以下の通りです。

1.  `_generate_next_actions` の `action_id` 採番ロジックが、指示通りに修正されているか。
2.  修正後、「ファイルを読んで要約して」のようなデータ連携が必要なタスクを実行した際に、`WARNING - 参照IDが見つかりません` という警告や、`AttributeError: 'str' object has no attribute 'get'` といったエラーが発生せず、タスクが正常に完了するか。

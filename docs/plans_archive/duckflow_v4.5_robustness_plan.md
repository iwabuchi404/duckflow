# ドキュメント：v4.5 エラー耐性強化とインターフェース整合性確保・実装指示書

## 1. 概要

### 1.1. 目的
LLMが生成するプランの不備（必須引数の欠落など）によってシステムがクラッシュする問題を解決し、システムの堅牢性を向上させる。具体的には、以下の2点を実装する。
1.  ツールの関数（ハンドラー）のシグネチャを、ツール本体の仕様と一致させる。
2.  ツール実行前に引数を検証するガードレールを導入し、LLMの計画ミスを事前に検知できるようにする。

### 1.2. 根本原因の分析
ログ分析により、`TypeError: ... missing 1 required positional argument: 'offset'` というエラーが確認された。これは、LLMが `read_file_chunk` の呼び出し時に必須引数 `offset` を省略したこと、そして `enhanced_core_v8.py` 内のハンドラーメソッド `_handle_read_file_chunk` が `offset` の省略を許容していなかったことが直接的な原因である。

### 1.3. 主な対象ファイル
- `companion/enhanced_core_v8.py`: ツールハンドラーの修正と、引数検証ロジックの追加。

---

## 2. 実装ステップ

### ステップ1: ツールハンドラーのシグネチャ修正

**担当ファイル:** `companion/enhanced_core_v8.py`

**タスク:**
`_handle_read_file_chunk` メソッドのシグネチャを、ツール本体（`structured_file_ops.py`）の実装と一致させ、`offset` 引数を省略可能にしてください。

**具体的な修正:**
`replace` ツールを使用して、以下の通りメソッド定義を修正してください。

```python
# old_string
async def _handle_read_file_chunk(self, file_path: str, offset: int, size: int, **kwargs) -> Dict[str, Any]:

# new_string
async def _handle_read_file_chunk(self, file_path: str, size: int, offset: int = 0, **kwargs) -> Dict[str, Any]:
```

*(注: `size` と `offset` の順序も、より一般的な慣習に合わせて変更しています)*

### ステップ2: ツール実行前の引数検証ガードレールの導入

**担当ファイル:** `companion/enhanced_core_v8.py`

**タスク:**
`_execute_action_v8` メソッドを修正し、ツール呼び出しの前に必須引数が揃っているかを検証するロジックを追加します。

**具体的な修正:**
`replace` ツールを使用して、`_execute_action_v8` メソッドを以下の新しい内容に置き換えてください。`inspect`モジュールを利用した検証ロジックが追加されています。

```python
# old_string
async def _execute_action_v8(self, action: ActionV8) -> Dict[str, Any]:
    """V8アクションの実行"""
    try:
        tool_category, tool_method = action.operation.split('.')
        if tool_category in self.tools and tool_method in self.tools[tool_category]:
            tool_func = self.tools[tool_category][tool_method]
            return await self._call_tool(tool_func, action.args)
        else:
            raise ValueError(f"不明なツール: {action.operation}")
    except Exception as e:
        self.logger.error(f"V8アクション実行エラー: {e}", exc_info=True)
        return {"success": False, "error": str(e), "operation": action.operation}

# new_string
import inspect # ファイルの先頭に必ず import を追加してください

async def _execute_action_v8(self, action: ActionV8) -> Dict[str, Any]:
    """V8アクションの実行（引数検証ガードレール付き）"""
    try:
        tool_category, tool_method = action.operation.split('.')
        if tool_category in self.tools and tool_method in self.tools[tool_category]:
            tool_func = self.tools[tool_category][tool_method]

            # --- ▼▼▼ 引数検証ロジック ▼▼▼ ---
            sig = inspect.signature(tool_func)
            for param in sig.parameters.values():
                if param.default is inspect.Parameter.empty and param.kind in [inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY]:
                    if param.name not in action.args:
                        error_msg = f"ツール '{action.operation}' の必須引数 '{param.name}' が不足しています。"
                        self.logger.error(error_msg)
                        return {"success": False, "error": error_msg, "operation": action.operation}
            # --- ▲▲▲ 引数検証ロジック ▲▲▲ ---

            return await self._call_tool(tool_func, action.args)
        else:
            raise ValueError(f"不明なツール: {action.operation}")
    except Exception as e:
        self.logger.error(f"V8アクション実行エラー: {e}", exc_info=True)
        return {"success": False, "error": str(e), "operation": action.operation}
```

**重要:** `companion/enhanced_core_v8.py` のファイルの先頭に `import inspect` を追加することを忘れないでください。

## 3. レビューの観点

実装完了後、私がレビューする際の主要な確認項目は以下の通りです。

1.  `_handle_read_file_chunk` のシグネチャが正しく修正され、`offset` がデフォルト値を持つようになったか。
2.  `_execute_action_v8` に、`inspect`モジュールを使用した必須引数の検証ロジックが正しく挿入されているか。
3.  必須引数が欠落したアクションプランを意図的に実行させた場合に、`TypeError` でクラッシュせず、適切なエラーメッセージを返して処理を中断できるか。

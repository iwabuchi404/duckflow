# ドキュメント：v4.6 ファイル書き込み機能の有効化・実装指示書

## 1. 概要

### 1.1. 目的
`enhanced_core_v8.py` にファイル書き込み（`write_file`）の処理が登録されていなかった問題を修正し、LLMが立案したファイル作成・変更の計画を実際に実行できるようにする。

### 1.2. 根本原因
`enhanced_core_v8.py` の `__init__` メソッド内でツールを登録している `self.tools` 辞書に、`write_file` の項目が欠落していた。また、その処理を担当するハンドラーメソッド `_handle_write_file` も未定義だった。

### 1.3. 解決策
`_handle_write_file` メソッドを新たに追加し、それを `self.tools` 辞書に正しく登録する。

### 1.4. 主な対象ファイル
- `companion/enhanced_core_v8.py`

---

## 2. 実装ステップ

### ステップ1: `_handle_write_file` メソッドの追加とツール登録

**担当ファイル:** `companion/enhanced_core_v8.py`

**タスク:**
`replace` ツールを使用し、`__init__` メソッド内のツール登録部分と、ハンドラーメソッド群をまとめて更新してください。以下の修正は、`self.tools` 辞書に `"write_file": self._handle_write_file` を追加し、その実体である `_handle_write_file` メソッドを他のハンドラーと共に定義します。

**具体的な修正:**

```python
# old_string
        # ツール登録（v4アーキテクチャ対応）
        self.tools = {
            "structured_file_ops": {
                "analyze_file_structure": self._handle_analyze_file,
                "search_content": self._handle_search_content,
                "read_file": self._handle_read_file,
                "read_file_chunk": self._handle_read_file_chunk
            },
            "plan_tool": {
                "propose": self._handle_plan_propose,
                "update_step": self._handle_plan_update_step,
                "get": self._handle_plan_get
            },
            "task_tool": {
                "generate_list": self._handle_task_generate_list
            },
            "task_loop": {
                "run": self._handle_task_loop_run
            },
            "user_response_tool": {
                "generate_response": self.user_response_tool.generate_response if self.user_response_tool else None
            }
        }

# new_string
        # ツール登録（v4アーキテクチャ対応）
        self.tools = {
            "structured_file_ops": {
                "analyze_file_structure": self._handle_analyze_file,
                "search_content": self._handle_search_content,
                "write_file": self._handle_write_file, # 登録を追加
                "read_file": self._handle_read_file,
                "read_file_chunk": self._handle_read_file_chunk
            },
            "plan_tool": {
                "propose": self._handle_plan_propose,
                "update_step": self._handle_plan_update_step,
                "get": self._handle_plan_get
            },
            "task_tool": {
                "generate_list": self._handle_task_generate_list
            },
            "task_loop": {
                "run": self._handle_task_loop_run
            },
            "user_response_tool": {
                "generate_response": self.user_response_tool.generate_response if self.user_response_tool else None
            }
        }
```

```python
# old_string
    async def _handle_search_content(self, file_path: str, pattern: str, **kwargs) -> Dict[str, Any]:
        return await self.structured_file_ops.search_content(file_path, pattern, **kwargs)

# new_string
    async def _handle_search_content(self, file_path: str, pattern: str, **kwargs) -> Dict[str, Any]:
        return await self.structured_file_ops.search_content(file_path, pattern, **kwargs)

    async def _handle_write_file(self, file_path: str, content: str, **kwargs) -> Dict[str, Any]:
        return await self.structured_file_ops.write_file(file_path, content, **kwargs)
```

## 3. レビューの観点

実装完了後、私がレビューする際の主要な確認項目は以下の通りです。

1.  `enhanced_core_v8.py` の `self.tools` 辞書に `write_file` の項目が追加されているか。
2.  `enhanced_core_v8.py` に `_handle_write_file` メソッドが正しく実装されているか。
3.  修正後、「`xxx.ts` に `class A {}` を作成して」のようなファイル作成を伴う指示を実行した際に、`TypeError` や `不明な操作タイプ` エラーが発生せず、実際にファイルが作成されるか。

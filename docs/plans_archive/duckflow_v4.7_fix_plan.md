# ドキュメント：v4.7 エラー耐性強化と最終FIX・実装指示書

## 1. 概要

### 1.1. 目的
LLMが生成したプランの不備（引数不足など）に起因する実行時エラーを解消し、システム全体の堅牢性を向上させる。具体的には、以下の2点を実装する。
1.  ツールハンドラーのシグネチャを、プロンプトの指示内容と完全に一致させる。
2.  ツール実行前に必須引数を検証するガードレールを導入し、LLMの計画ミスを事前に検知・報告できるようにする。

### 1.2. 根本原因の分析
ログ分析により、`TypeError` が2種類発生していることが判明した。
1.  **`_handle_read_file_chunk` の引数不足:** LLMが `offset` を省略した計画を立て、`offset` を必須引数とするハンドラーがエラーを起こした。
2.  **`user_response_tool.generate_response` の引数不一致:** プロンプトの具体例で `prompt_override` という存在しない引数を渡すよう指示していたため、LLMがそれに従いエラーとなった。

これらの問題は、プロンプトの指示と、実際のツールの実装（シグネチャ）との間の不整合に起因する。

### 1.3. 主な対象ファイル
- `companion/enhanced_core_v8.py`
- `companion/tools/user_response_tool.py`

---

## 2. 実装ステップ

### ステップ1: `user_response_tool` のシグネチャ修正

**担当ファイル:** `companion/tools/user_response_tool.py`

**タスク:**
`generate_response` メソッドが `prompt_override` 引数を受け取れるように修正し、もしその引数が渡された場合は、その内容を優先してLLMに問い合わせるロジックを追加してください。

**具体的な修正:**
`replace` ツールを使用して、`generate_response` メソッド全体を以下の新しい内容に置き換えてください。

```python
# old_string
    async def generate_response(self, 
                              action_results: List[Dict[str, Any]], 
                              user_input: str,
                              agent_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        アクション実行結果からユーザーへの応答を生成する
        
        Args:
            action_results: 実行されたアクションの結果リスト
            user_input: ユーザーの元の要求
            agent_state: エージェントの現在の状態
            
        Returns:
            生成された応答の辞書
        """
        try:
            self.logger.info(f"応答生成開始: {len(action_results)}個のアクション結果")
            
            # agent_stateが辞書の場合は適切な形式に変換
            if isinstance(agent_state, dict):
                self.logger.warning("agent_stateが辞書として渡されました。適切な形式に変換します。")
                # 辞書の場合はNoneとして扱い、PromptCompilerでデフォルト処理を使用
                agent_state = None
            
            # 応答生成用のプロンプトをコンパイル
            prompt = self.prompt_compiler.compile_response_prompt(
                pattern="base_main_specialized",
                action_results=action_results,
                user_input=user_input,
                agent_state=agent_state
            )
            
            # LLMに応答生成を依頼
            response = await self._call_llm_for_response(prompt)
            
            result = {
                "success": True,
                "response": response,
                "generation_method": "llm_based",
                "prompt_length": len(prompt),
                "response_length": len(response),
                "action_count": len(action_results)
            }
            
            self.logger.info(f"応答生成完了: {len(response)}文字の応答を生成")
            return result
            
        except Exception as e:
            self.logger.error(f"応答生成エラー: {e}")
            fallback_response = self._generate_fallback_response(action_results, user_input)
            
            result = {
                "success": False,
                "error": str(e),
                "fallback_response": fallback_response,
                "generation_method": "fallback",
                "action_count": len(action_results)
            }
            
            return result

# new_string
    async def generate_response(self, 
                              user_input: str,
                              action_results: List[Dict[str, Any]] = [], 
                              agent_state: Optional[Any] = None, 
                              prompt_override: Optional[str] = None) -> Dict[str, Any]:
        """
        アクション実行結果やプロンプトオーバーライドからユーザーへの応答を生成する
        
        Args:
            user_input: ユーザーの元の要求
            action_results: 実行されたアクションの結果リスト
            agent_state: エージェントの現在の状態
            prompt_override: この引数が指定された場合、他の情報より優先してLLMへの指示として使用
            
        Returns:
            生成された応答の辞書
        """
        try:
            self.logger.info(f"応答生成開始: {len(action_results)}個のアクション結果, prompt_override: {prompt_override is not None}")
            
            if prompt_override:
                # prompt_overrideが指定されている場合は、それを最優先で使用
                prompt = prompt_override
            else:
                # agent_stateが辞書の場合は適切な形式に変換
                if isinstance(agent_state, dict):
                    self.logger.warning("agent_stateが辞書として渡されました。適切な形式に変換します。")
                    agent_state = None
                
                # 応答生成用のプロンプトをコンパイル
                prompt = self.prompt_compiler.compile_response_prompt(
                    pattern="base_main_specialized",
                    action_results=action_results,
                    user_input=user_input,
                    agent_state=agent_state
                )
            
            # LLMに応答生成を依頼
            response = await self._call_llm_for_response(prompt)
            
            result = {
                "success": True,
                "response": response,
                "generation_method": "llm_based_override" if prompt_override else "llm_based_summary",
                "prompt_length": len(prompt),
                "response_length": len(response),
                "action_count": len(action_results)
            }
            
            self.logger.info(f"応答生成完了: {len(response)}文字の応答を生成")
            return result
            
        except Exception as e:
            self.logger.error(f"応答生成エラー: {e}", exc_info=True)
            fallback_response = self._generate_fallback_response(action_results, user_input)
            
            result = {
                "success": False,
                "error": str(e),
                "fallback_response": fallback_response,
                "generation_method": "fallback",
                "action_count": len(action_results)
            }
            
            return result
```

### ステップ2: 引数検証ガードレールの導入とハンドラー修正

**担当ファイル:** `companion/enhanced_core_v8.py`

**タスク:**
`_execute_action_v8` に引数検証ロジックを追加し、`_handle_read_file_chunk` のシグネチャを修正します。

**具体的な修正:**
`replace` ツールを使用して、`_execute_action_v8` と `_handle_read_file_chunk` の2つのメソッドを、以下の新しい内容にまとめて置き換えてください。

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

    async def _handle_read_file_chunk(self, file_path: str, offset: int, size: int, **kwargs) -> Dict[str, Any]:
        """ファイルチャンク読み込みハンドラー"""
        return await self.structured_file_ops.read_file_chunk(file_path, offset, size, **kwargs)

# new_string
    async def _execute_action_v8(self, action: ActionV8) -> Dict[str, Any]:
        """V8アクションの実行（引数検証ガードレール付き）"""
        try:
            tool_category, tool_method = action.operation.split('.')
            if tool_category in self.tools and tool_method in self.tools[tool_category]:
                tool_func = self.tools[tool_category][tool_method]

                # --- ▼▼▼ 引数検証ロジック ▼▼▼ ---
                sig = inspect.signature(tool_func)
                for param in sig.parameters.values():
                    # 必須引数（デフォルト値なし）をチェック
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

    async def _handle_read_file_chunk(self, file_path: str, size: int, offset: int = 0, **kwargs) -> Dict[str, Any]:
        """ファイルチャンク読み込みハンドラー"""
        return await self.structured_file_ops.read_file_chunk(file_path=file_path, size=size, offset=offset, **kwargs)
```

**重要:** `companion/enhanced_core_v8.py` のファイルの先頭に `import inspect` が存在することを確認してください。なければ追加してください。

## 3. レビューの観点

実装完了後、私がレビューする際の主要な確認項目は以下の通りです。

1.  `user_response_tool.py` の `generate_response` が `prompt_override` 引数を正しく処理できるか。
2.  `enhanced_core_v8.py` の `_handle_read_file_chunk` のシグネチャが修正されているか。
3.  `_execute_action_v8` に引数検証ロジックが正しく実装されているか。
4.  修正後、ログに `TypeError` が発生せず、ファイル読み込みや実装プラン作成が正常に完了するか。

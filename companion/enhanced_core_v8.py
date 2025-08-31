#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EnhancedCompanionCoreV8 - JSON+LLM方式統合コア

設計思想:
- 構造化データ（JSON）での正確な内部処理
- LLMによる人間向けの自然な文章生成
- プロキシシステムの排除とシンプルな責任分離

主要改善:
- 辞書データの複雑なプロキシ処理を撤廃
- ツールは構造化データを返却、表示はLLMでフォーマット
- ActionID参照システムの簡素化
"""

import json
import logging
import asyncio
import inspect
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from pydantic import Field

# 新しいモジュール
from .output.human_formatter import HumanOutputFormatter, FormatterRequest, FormattedOutput
from .tools.structured_file_ops import StructuredFileOps

# 新実装のTool
from .plan_tool import PlanTool
from .tools.user_response_tool import UserResponseTool
from .tools.tool_registry import ToolRegistry
from .tools.task_management_tool import TaskManagementTool

# 既存システムからの継承
try:
    from .state.agent_state import AgentState
    from .llm.llm_client import LLMClient
    from .llm.llm_service import LLMService
    from .intent_understanding.intent_analyzer_llm import IntentAnalyzerLLM, ActionType
    from .prompts.prompt_context_service import PromptContextService
except ImportError:
    # フォールバック用のダミークラス
    class AgentState: pass
    class LLMClient: pass
    class LLMService: pass
    class IntentAnalyzerLLM: pass
    class PromptContextService: pass
    class ActionType:
        FILE_OPERATION = type('ActionType', (), {'value': 'file_operation'})()
        DIRECT_RESPONSE = type('ActionType', (), {'value': 'direct_response'})()

@dataclass
class ActionV8:
    """v4アーキテクチャのAction定義（統一ツールコールモデル対応）"""
    operation: str = Field(description="実行する高レベル操作 (例: 'plan_tool.propose', 'task_tool.generate_list')")
    args: Dict[str, Any] = Field(default_factory=dict, description="操作の引数")
    reasoning: Optional[str] = Field(default=None, description="このアクションが生成された理由")
    action_id: str = ""
    needs_human_formatting: bool = True

class EnhancedCompanionCoreV8:
    """JSON+LLM方式の統合コア"""
    
    def __init__(self, dual_loop_system):
        """初期化"""
        self.logger = logging.getLogger(__name__)
        
        # 基本システム継承
        self.dual_loop_system = dual_loop_system
        self.agent_state = dual_loop_system.agent_state
        self.llm_call_manager = dual_loop_system.llm_call_manager
        self.llm_service = dual_loop_system.llm_service
        self.intent_analyzer = dual_loop_system.intent_analyzer
        self.prompt_context_service = dual_loop_system.prompt_context_service
        
        # 新システム初期化
        self.human_formatter = HumanOutputFormatter(llm_service=self.llm_service)
        self.structured_file_ops = StructuredFileOps()
        
        # 新実装のTool初期化
        try:
            # LLMクライアントの取得
            llm_client = None
            if hasattr(self.dual_loop_system, 'llm_client') and self.dual_loop_system.llm_client:
                llm_client = self.dual_loop_system.llm_client
            elif hasattr(self.dual_loop_system, 'llm_call_manager') and self.dual_loop_system.llm_call_manager:
                llm_client = self.dual_loop_system.llm_call_manager.llm_client
            
            if not llm_client:
                self.logger.warning("LLMクライアントが取得できません。Tool初期化をスキップします。")
                self.plan_tool = None
                self.user_response_tool = None
                self.llm_client = None
            else:
                self.llm_client = llm_client  # インスタンス変数として保存
                
                # PlanToolの初期化
                try:
                    self.plan_tool = PlanTool(llm_client=llm_client)
                    self.logger.info("PlanTool初期化完了")
                except Exception as e:
                    self.logger.warning(f"PlanTool初期化エラー: {e}")
                    self.plan_tool = None
                
                # PromptCompilerの取得とUserResponseTool初期化
                prompt_compiler = None
                if hasattr(self.prompt_context_service, 'prompt_compiler'):
                    prompt_compiler = self.prompt_context_service.prompt_compiler
                
                if prompt_compiler:
                    try:
                        self.user_response_tool = UserResponseTool(
                            prompt_compiler=prompt_compiler,
                            llm_client=llm_client
                        )
                        self.logger.info("UserResponseTool初期化完了")
                    except Exception as e:
                        self.logger.warning(f"UserResponseTool初期化エラー: {e}")
                        self.user_response_tool = None
                else:
                    self.logger.warning("PromptCompilerが取得できません。UserResponseTool初期化をスキップします。")
                    self.user_response_tool = None
                    
        except Exception as e:
            self.logger.error(f"Tool初期化エラー: {e}")
            self.plan_tool = None
            self.user_response_tool = None
            self.llm_client = None
        
        self.tool_registry = ToolRegistry()
        
        # UI初期化
        self.ui = self._initialize_ui()
        
        # ツール登録（v4アーキテクチャ対応）
        self.tools = {
            "structured_file_ops": {
                "analyze_file_structure": self._handle_analyze_file,
                "search_content": self._handle_search_content,
                "write_file": self._handle_write_file,
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
        
        self.logger.info("EnhancedCompanionCoreV8 初期化完了")
    
    async def process_user_message(self, user_message: str) -> str:
        """ユーザーメッセージ処理のメインエントリーポイント"""
        try:
            self.logger.info(f"V8メッセージ処理開始: {user_message[:50]}...")
            
            intent_result = await self.analyze_intent_only(user_message)
            
            if intent_result.get("action_type") == "direct_response":
                response = await self._handle_direct_response(user_message, intent_result)
            else:
                response = await self._handle_action_execution(user_message, intent_result)
            
                if hasattr(self.agent_state, 'add_conversation_message'):
                    self.agent_state.add_conversation_message('user', user_message)
                    self.agent_state.add_conversation_message('assistant', response)
                    self.logger.info("会話履歴を更新しました")
            
            return response
                
        except Exception as e:
            self.logger.error(f"V8メッセージ処理エラー: {e}", exc_info=True)
            error_response = f"申し訳ありません、処理中にエラーが発生しました: {str(e)}"
            
            if hasattr(self.agent_state, 'add_conversation_message'):
                self.agent_state.add_conversation_message('user', user_message)
                self.agent_state.add_conversation_message('assistant', error_response)
            
            return error_response
    
    async def analyze_intent_only(self, user_message: str, context: Optional[Dict[str, Any]] = None):
        """意図分析のみを実行"""
        # This is a simplified fallback.
        if any(word in user_message.lower() for word in ['読んで', '分析', '確認', '見て']):
            return {
                "action_type": "action_execution", 
                "confidence": 0.8,
                "suggested_actions": ["file_analysis"]
            }
        else:
            return {"action_type": "direct_response", "confidence": 0.6}
    
    async def _handle_direct_response(self, user_message: str, intent_result: Dict[str, Any]) -> str:
        """直接応答処理"""
        return await self._handle_action_execution(user_message, intent_result)
    
    async def _handle_action_execution(self, user_message: str, intent_result: Dict[str, Any]) -> str:
        """ActionList生成・実行処理"""
        try:
            action_list = await self._generate_next_actions(user_message, intent_result)
            raw_results = await self._dispatch_actions(action_list)
            return await self._format_final_response(raw_results, user_message)
        except Exception as e:
            self.logger.error(f"Action実行エラー: {e}", exc_info=True)
            return f"タスク実行中にエラーが発生しました: {str(e)}"
    
    async def _dispatch_actions(self, action_list: List[ActionV8]) -> List[Dict[str, Any]]:
        """アクションリストを実行し、結果を連携させるパイプライン処理"""
        try:
            # そのターン内の実行結果を保存するための一時的な辞書
            turn_results: Dict[str, Any] = {}
            raw_results = []
            
            for action in action_list:
                # アクションの引数を前処理（データ連携のため）
                processed_args = self._preprocess_action_args(action.args, turn_results)
                
                # アクションを実行
                raw_result = await self._execute_action_v8(action)
                raw_results.append(raw_result)

                # ファイル読み込み処理の特別処理
                if action.operation in ["structured_file_ops.read_file", "structured_file_ops.read_file_chunk"] and raw_result.get("success"):
                    await self._handle_file_operation_result(action, raw_result)

                # アクション結果をturn_resultsに保存（データ連携のため）
                if action.action_id:
                    turn_results[action.action_id] = raw_result
                    self.logger.debug(f"アクション結果を保存: {action.action_id} -> {type(raw_result).__name__}")

                # AgentStateにアクション結果を記録
                if hasattr(self.agent_state, 'add_action_result'):
                    self.agent_state.add_action_result(
                        action_id=action.action_id,
                        operation=action.operation,
                        result=raw_result,
                        action_list_id="v8_action_list",
                        sequence_number=len(raw_results)
                    )
            
            return raw_results
            
        except Exception as e:
            self.logger.error(f"アクションディスパッチエラー: {e}", exc_info=True)
            return []
    
    async def _handle_file_operation_result(self, action: ActionV8, raw_result: Dict[str, Any]) -> None:
        """ファイル操作結果の処理"""
        try:
            # ファイル読み込み状態を更新（エラーが発生しても続行）
            if hasattr(self.agent_state, 'update_file_read_state'):
                try:
                    self.agent_state.update_file_read_state(raw_result)
                    self.logger.info(f"ファイル読み込み状態を更新: {raw_result.get('file_path')}")
                except Exception as e:
                    self.logger.warning(f"ファイル読み込み状態の更新に失敗（続行）: {e}")
            
            # ファイル内容をAgentStateに保存（重要：エラーが発生しても実行）
            if hasattr(self.agent_state, 'add_file_content'):
                try:
                    file_path = raw_result.get("file_path")
                    content = raw_result.get("content", "")
                    metadata = raw_result.get("metadata", {})
                    
                    if action.operation == "structured_file_ops.read_file_chunk":
                        # チャンク読み込みの場合は、全体のファイルサイズ情報も含める
                        if metadata.get("total_size_bytes"):
                            metadata["total_chars"] = metadata.get("total_size_bytes")
                            metadata["is_truncated"] = not metadata.get("is_complete", True)
                            metadata["truncated_chars"] = len(content.encode('utf-8'))
                    elif action.operation == "structured_file_ops.read_file":
                        # 通常のファイル読み込みの場合は、既存のメタデータを使用
                        if not metadata.get("total_chars"):
                            metadata["total_chars"] = len(content)
                            metadata["is_truncated"] = False
                            metadata["truncated_chars"] = len(content)
                    
                    self.agent_state.add_file_content(
                        file_path=file_path,
                        content=content,
                        metadata=metadata
                    )
                    self.logger.info(f"ファイル内容をAgentStateに保存: {file_path} ({len(content)}文字)")
                    
                    # デバッグ用：保存後の確認
                    try:
                        saved_content = self.agent_state.get_file_content_with_metadata(file_path)
                        if saved_content:
                            self.logger.info(f"保存確認: {file_path} - 内容長: {len(saved_content.get('content', ''))}文字, 切り詰め: {saved_content.get('metadata', {}).get('is_truncated', False)}")
                        else:
                            self.logger.warning(f"保存確認失敗: {file_path} - 内容が見つかりません")
                    except Exception as e:
                        self.logger.warning(f"保存確認中にエラー: {e}")
                except Exception as e:
                    self.logger.error(f"ファイル内容の保存に失敗: {e}")
        except Exception as e:
            self.logger.error(f"ファイル操作結果処理エラー: {e}")
    
    def _preprocess_action_args(self, args: Dict[str, Any], turn_results: Dict[str, Any]) -> Dict[str, Any]:
        """アクション引数の前処理（データ連携のため）"""
        try:
            processed_args = {}
            for key, value in args.items():
                if isinstance(value, str) and value.startswith("ref:"):
                    # ref:構文の処理
                    ref_id = value[4:]  # "ref:"を除去
                    if ref_id in turn_results:
                        processed_args[key] = turn_results[ref_id]
                        self.logger.debug(f"データ連携: {key} <- ref:{ref_id}")
                    else:
                        processed_args[key] = value
                        self.logger.warning(f"参照IDが見つかりません: {ref_id}")
                else:
                    processed_args[key] = value
            
            return processed_args
        except Exception as e:
            self.logger.error(f"アクション引数前処理エラー: {e}")
            return args
    
    async def _generate_next_actions(self, user_message: str, intent_result: Dict[str, Any]) -> List[ActionV8]:
        """v4アーキテクチャの次に実行すべきActionList生成（階層的プランニング対応）"""
        try:
            # 階層的思考を促す新しいプロンプトでLLMに問い合わせ
            llm_response = await self._generate_hierarchical_plan(user_message)
            
            if llm_response and llm_response.get("actions"):
                self.logger.info(f"階層的計画生成結果: {llm_response}")
                actions = []
                action_id_base = f"act_{datetime.now().strftime('%H%M%S')}"
                
                for i, action_data in enumerate(llm_response["actions"]):
                    operation = action_data.get("operation")
                    if not operation: continue

                    action_id = f"{action_id_base}_{i}_{operation.replace('.', '_')}"
                    parameters = action_data.get("parameters", {})
                    reasoning = action_data.get("reasoning", "")

                    # v4アーキテクチャの統一ツールコールモデルに対応
                    if operation in [
                        "structured_file_ops.analyze_file_structure",
                        "structured_file_ops.read_file_chunk",
                        "structured_file_ops.search_content",
                        "plan_tool.propose",
                        "plan_tool.update_step",
                        "plan_tool.get",
                        "task_tool.generate_list",
                        "task_loop.run",
                        "user_response_tool.generate_response"
                    ]:
                        actions.append(ActionV8(operation=operation, args=parameters, reasoning=reasoning, action_id=action_id))
                    else:
                        self.logger.warning(f"不明な操作タイプ: {operation}")

                return actions
            
            self.logger.warning("階層的計画生成に失敗、フォールバックロジックを使用")
            return await self._generate_fallback_action_list(user_message, intent_result)
            
        except Exception as e:
            self.logger.error(f"次に実行すべきActionList生成エラー: {e}", exc_info=True)
            return []
    
    async def _generate_hierarchical_plan(self, user_message: str) -> Dict[str, Any]:
        """v4アーキテクチャの階層的思考を促すプロンプトでLLMに計画生成を依頼"""
        try:
            # 現在のプラン状況を取得
            plan_summary = self._get_current_plan_summary()
            
                        # 意図認識に基づく永続化判断の新しいプロンプト
            prompt = f"""あなたはプロジェクトマネージャーとして機能するAIアシスタントの司令塔です。

## あなたの役割
ユーザーの要求を分析し、長期的な目標と短期的なタスクを階層的に管理し、適切な成果物を生成します。

## 現在の状況
{plan_summary}

{self._get_plan_continuity_instruction()}

## 思考プロセス

1. **意図の分類:** ユーザーの要求は、以下のA, Bどちらの意図に近いか、まず心の中で判断せよ。
   * **A) 実装・変更:** プロジェクトのソースコードを実際に作成または変更する要求。(キーワード例: 「〜を作成して」「〜を実装して」「〜を修正して」)
   * **B) 指針・例示:** 説明、コード例の提示、アイデア出し、ファイル内容の要約など、ユーザーの理解を助けるための要求。(キーワード例: 「〜の例を見せて」「〜はどう書く？」「〜を読んで内容を把握して」)

2. **計画の立案:** 上記の分類に基づき、後述の【意図別のツール利用指針】に従って、具体的なアクションプランを立案せよ。

## ユーザーの要求
{user_message}

## 意図別のツール利用指針

### A) 実装・変更 の場合
- **最終目標:** `structured_file_ops.write_file` または `structured_file_ops.replace` を実行し、ファイルシステムの変更を完了させること。
- **基本フロー:**
    1. 必要であれば `plan_tool.propose` で複数ステップの計画を立てる。
    2. `task_tool.generate_list` で具体的なファイル操作タスクを生成する。
    3. `task_loop.run` でタスクを実行する。
- **禁止事項:** コードを生成して `user_response_tool` で応答するだけで処理を終了してはならない。

### B) 指針・例示 の場合
- **最終目標:** `user_response_tool.generate_response` を使用し、ユーザーに有益な情報（説明、コード例、ファイル内容の要約など）を会話として提供すること。
- **ファイル読み込みが必要な場合:** ファイル内容の要約や分析が要求される場合は、まず `structured_file_ops.read_file_chunk` でファイルを読み、その結果を `user_response_tool.generate_response` に渡して要約を生成すること。
- **禁止事項:** この意図の場合、ファイル読み込みが必要でない限り `structured_file_ops` ツールを使用してはならない。

## 利用可能なツール一覧
- `plan_tool.propose(goal)`
- `task_tool.generate_list(step_id)`
- `task_loop.run(task_list)`
- `structured_file_ops.write_file(file_path, content)`
- `user_response_tool.generate_response(user_input, prompt_override)`

## アクション間のデータ連携
`actions`リスト内で、前のアクションの実行結果を後のアクションの入力として使用できます。
1. まず、結果を使いたいアクションに `"action_id": "some_id"` のようにIDを付与します。
2. 次に、後続のアクションの `parameters` の値に `"ref:some_id"` と指定します。

これにより、`some_id` のアクションの実行結果全体が、パラメータの値として自動的に引き渡されます。

## 出力形式
以下のJSON形式で回答してください:
```json
{{
    "reasoning": "思考プロセスに基づいた、あなたの判断と計画の要約",
    "actions": [
        {{
            "operation": "ツール名.メソッド名",
            "parameters": {{ "引数名": "値" }},
            "reasoning": "この個別のアクションを実行する理由"
        }}
    ]
}}
```

## 思考とアクションの具体例

### 例1：実装・変更の要求
- **ユーザー要求:** 「`Engine.ts` をシングルトンで実装して」
- **思考プロセス:**
    1. **意図の分類:** (A) 実装・変更
    2. **計画の立案:** `Engine.ts` というファイルを作成する必要がある。まずファイルの内容を考え、`write_file` ツールで保存する。
- **生成されるべきアクション:**
    ```json
    {{
        "reasoning": "ユーザーの要求はEngineクラスの実装であり、ファイルへの書き込みが必要と判断しました。",
        "actions": [
            {{
                "operation": "structured_file_ops.write_file",
                "parameters": {{
                    "file_path": "src/engine/Engine.ts",
                    "content": "export class Engine {{ ... (シングルトンのコード) ... }}"
                }},
                "reasoning": "Engineクラスのコードを生成し、指定されたパスに保存します。"
            }}
        ]
    }}
    ```

### 例2：指針・例示の要求
- **ユーザー要求:** 「シングルトンパターンの例をTypeScriptで見せて」
- **思考プロセス:**
    1. **意図の分類:** (B) 指針・例示
    2. **計画の立案:** サンプルコードを生成し、説明と共に会話で応答すればよい。`user_response_tool` を使用する。
- **生成されるべきアクション:**
    ```json
    {{
        "reasoning": "ユーザーはサンプルコードの提示を求めているため、ファイル作成は不要と判断しました。user_response_toolで応答を生成します。",
        "actions": [
            {{
                "operation": "user_response_tool.generate_response",
                "parameters": {{
                    "user_input": "シングルトンパターンの例をTypeScriptで見せて"
                }},
                "reasoning": "サンプルコードと解説を生成し、ユーザーに提示します。"
            }}
        ]
    }}
    ```

### 例3：データ連携を含む複合要求
- **ユーザー要求:** 「game_doc.mdを読んで、その概要を教えて」
- **思考プロセス:**
    1. **意図の分類:** (B) 指針・例示
    2. **計画の立案:** これは2段階のタスクだ。まず `read_file_chunk` でファイルを読み、その結果を次の `user_response_tool` に渡して要約を生成させる必要がある。そのためには、最初のアクションに `action_id` を設定し、次のアクションで `ref:` を使って参照する必要がある。
- **生成されるべきアクション:**
    ```json
    {{
        "reasoning": "ユーザーはファイル内容の要約を求めている。まずファイルを読み、その結果を次のアクションに渡して要約を生成する、2段階の計画を立てる。",
        "actions": [
            {{
                "action_id": "read_game_doc",
                "operation": "structured_file_ops.read_file_chunk",
                "parameters": {{ "file_path": "game_doc.md", "size": 16384 }},
                "reasoning": "まずファイルの全体像を把握するために、最大16KBを読み込む。"
            }},
            {{
                "operation": "user_response_tool.generate_response",
                "parameters": {{
                    "action_results": "ref:read_game_doc",
                    "user_input": "game_doc.mdを読んで、その概要を教えて"
                }},
                "reasoning": "前のアクションで読み込んだファイル内容(ref:read_game_doc)を基に、ユーザー向けの要約を生成する。"
            }}
        ]
    }}
    ```"""
            
            if self.llm_client:
                response = await self.llm_client.chat(prompt=prompt, tools=False, tool_choice="none")
                if response and response.content:
                    return self._parse_hierarchical_response(response.content)
                return None
        except Exception as e:
            self.logger.error(f"階層的計画生成エラー: {e}", exc_info=True)
            return None
    
    def _parse_hierarchical_response(self, llm_response: str) -> Optional[Dict[str, Any]]:
        """v4アーキテクチャの階層的応答からJSON処理計画を解析"""
        try:
            # JSONの開始と終了を探す
            start_idx = llm_response.find('{')
            if start_idx == -1:
                self.logger.warning("JSONの開始記号'{'が見つかりません")
                return None
            
            # ネストされた括弧を考慮して終了位置を探す
            brace_count = 0
            end_idx = -1
            
            for i in range(start_idx, len(llm_response)):
                if llm_response[i] == '{':
                    brace_count += 1
                elif llm_response[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break
            
            if end_idx == -1:
                self.logger.warning("JSONの終了記号'}'が見つかりません")
                return None
            
            json_str = llm_response[start_idx:end_idx + 1]
            self.logger.debug(f"抽出された階層的JSON文字列: {json_str}")
            
            parsed_response = json.loads(json_str)
            
            # 新しい形式に変換（後方互換性のため）
            if "actions" in parsed_response:
                return parsed_response
            elif "operations" in parsed_response:
                # 古い形式から新しい形式に変換
                return {
                    "reasoning": "古い形式から変換",
                    "actions": [
                        {
                            "operation": op.get("type", ""),
                            "parameters": op.get("parameters", {}),
                            "reasoning": op.get("reasoning", "")
                        }
                        for op in parsed_response.get("operations", [])
                    ]
                }
            
            return parsed_response
        except Exception as e:
            self.logger.error(f"階層的応答解析エラー: {e}")
            return None
    
    async def _generate_fallback_action_list(self, user_message: str, intent_result: Dict[str, Any]) -> List[ActionV8]:
        """フォールバック用のActionList生成（v4アーキテクチャ対応）"""
        actions = []
        
        # 複雑な要求の場合は計画を提案
        if any(word in user_message.lower() for word in ['実装', '作成', '開発', '構築', '設計']):
            actions.append(ActionV8(
                operation="plan_tool.propose",
                args={"goal": user_message},
                reasoning="複雑な要求のため、長期計画を提案します",
                action_id="fallback_plan"
            ))
        
        # ファイル分析が必要な場合
        if 'game_doc.md' in user_message:
            actions.append(ActionV8(
                operation="structured_file_ops.analyze_file_structure",
                args={"file_path": "game_doc.md"},
                reasoning="ドキュメントの構造を分析",
                action_id="fallback_analyze"
            ))
            actions.append(ActionV8(
                operation="structured_file_ops.read_file_chunk",
                args={"file_path": "game_doc.md", "offset": 0, "size": 8192},
                reasoning="ファイルの先頭部分を読み込み",
                action_id="fallback_read_chunk"
            ))
        
        # 最後に応答生成
        actions.append(ActionV8(
            operation="user_response_tool.generate_response",
            args={"action_results": [], "user_input": user_message, "agent_state": self.agent_state},
            reasoning="フォールバック処理の結果を人間向けに要約",
            action_id="fallback_response"
        ))
        
        return actions
            
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
    
    async def _call_tool(self, tool_func, args: Dict[str, Any]):
        """ツール呼び出し"""
        if asyncio.iscoroutinefunction(tool_func):
            return await tool_func(**args)
        else:
            return tool_func(**args)
    
    async def _handle_analyze_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        return await self.structured_file_ops.analyze_file_structure(file_path, **kwargs)
    
    async def _handle_search_content(self, file_path: str, pattern: str, **kwargs) -> Dict[str, Any]:
        return await self.structured_file_ops.search_content(file_path, pattern, **kwargs)
    
    async def _handle_write_file(self, file_path: str, content: str, **kwargs) -> Dict[str, Any]:
        return await self.structured_file_ops.write_file(file_path, content, **kwargs)

    async def _handle_read_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        return await self.structured_file_ops.read_file(file_path, **kwargs)

    async def _handle_read_file_chunk(self, file_path: str, size: int, offset: int = 0, **kwargs) -> Dict[str, Any]:
        """ファイルチャンク読み込みハンドラー"""
        return await self.structured_file_ops.read_file_chunk(file_path, offset, size, **kwargs)
    
    # v4アーキテクチャ対応の新しいハンドラー
    async def _handle_plan_propose(self, goal: str, **kwargs) -> Dict[str, Any]:
        """PlanTool.proposeのハンドラー"""
        try:
            from .state.agent_state import Plan, Step
            import uuid
            
            # 新しいPlanを作成
            plan = Plan(
                plan_id=f"plan_{uuid.uuid4().hex[:8]}",
                name=f"目標: {goal[:50]}",
                goal=goal,
                status="draft",
                steps=[]
            )
            
            # AgentStateに追加
            self.agent_state.plans.append(plan)
            self.agent_state.active_plan_id = plan.plan_id
            
            return {
                "success": True,
                "plan_id": plan.plan_id,
                "message": f"新しい計画を作成しました: {plan.name}"
            }
        except Exception as e:
            self.logger.error(f"計画作成エラー: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_plan_update_step(self, step_id: str, status: str, **kwargs) -> Dict[str, Any]:
        """PlanTool.update_stepのハンドラー"""
        try:
            # アクティブなプランのステップを更新
            if self.agent_state.active_plan_id:
                for plan in self.agent_state.plans:
                    if plan.plan_id == self.agent_state.active_plan_id:
                        for step in plan.steps:
                            if step.step_id == step_id:
                                step.status = status
                                return {"success": True, "message": f"ステップ {step_id} の状態を {status} に更新しました"}
            
            return {"success": False, "error": "ステップが見つかりません"}
        except Exception as e:
            self.logger.error(f"ステップ更新エラー: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_plan_get(self, plan_id: str, **kwargs) -> Dict[str, Any]:
        """PlanTool.getのハンドラー"""
        try:
            for plan in self.agent_state.plans:
                if plan.plan_id == plan_id:
                    return {"success": True, "plan": plan}
            
            return {"success": False, "error": "プランが見つかりません"}
        except Exception as e:
            self.logger.error(f"プラン取得エラー: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_task_generate_list(self, step_id: str, **kwargs) -> Dict[str, Any]:
        """TaskTool.generate_listのハンドラー"""
        try:
            from .state.agent_state import Task
            import uuid
            
            # アクティブなプランのステップを取得
            if self.agent_state.active_plan_id:
                for plan in self.agent_state.plans:
                    if plan.plan_id == self.agent_state.active_plan_id:
                        for step in plan.steps:
                            if step.step_id == step_id:
                                # 実際のTaskToolを使用してタスクリストを生成（実装可能な場合）
                                if hasattr(self, 'task_tool') and self.task_tool:
                                    try:
                                        task_list = await self.task_tool.generate_list(step_id)
                                        if task_list:
                                            step.task_list = task_list
                                            return {
                                                "success": True,
                                                "task_count": len(task_list),
                                                "message": f"ステップ '{step.name}' のために {len(task_list)} 件のタスクを生成しました"
                                            }
                                    except Exception as e:
                                        self.logger.warning(f"TaskTool使用エラー、フォールバック処理を使用: {e}")
                                
                                # フォールバック: 簡易版タスクリストを生成
                                task_list = [
                                    Task(
                                        task_id=f"task_{uuid.uuid4().hex[:8]}",
                                        operation="structured_file_ops.analyze_file_structure",
                                        args={"file_path": "game_doc.md"},
                                        reasoning=f"ステップ '{step.name}' の最初のタスクとして、ファイル構造を分析します"
                                    )
                                ]
                                
                                # 重要: TaskListをAgentState内の対応するStepに保存
                                step.task_list = task_list
                                
                                # 保存確認
                                self.logger.info(f"ステップ '{step.name}' に {len(task_list)} 件のタスクを保存しました")
                                
                                return {
                                    "success": True,
                                    "task_count": len(task_list),
                                    "message": f"ステップ '{step.name}' のために {len(task_list)} 件のタスクを生成・保存しました"
                                }
            
            return {"success": False, "error": "ステップが見つかりません"}
        except Exception as e:
            self.logger.error(f"タスクリスト生成エラー: {e}")
            return {"success": False, "error": str(e)}
    
    async def _handle_task_loop_run(self, task_list: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """TaskLoop.runのハンドラー"""
        try:
            # タスクリストをTaskLoopに委譲（非同期実行）
            if hasattr(self.dual_loop_system, 'task_queue'):
                # TaskLoopのキューにタスクを投入
                task_command = {
                    "type": "execute_task_list",
                    "task_list": task_list,
                    "timestamp": datetime.now().isoformat()
                }
                
                self.dual_loop_system.task_queue.put(task_command)
                self.logger.info(f"TaskLoopに {len(task_list)} 件のタスクを委譲しました")
                
                return {
                    "success": True,
                    "message": f"{len(task_list)} 件のタスクをTaskLoopに委譲しました",
                    "delegated": True,
                    "queue_command": task_command
                }
            else:
                # TaskLoopが利用できない場合は、直接実行を試行
                self.logger.warning("TaskLoopが利用できません。直接実行を試行します。")
                
                results = []
                for task in task_list:
                    try:
                        # 簡易的な直接実行
                        if task.get("operation") == "structured_file_ops.analyze_file_structure":
                            result = await self._handle_analyze_file(**task.get("args", {}))
                        else:
                            result = {"success": False, "error": "未対応の操作", "operation": task.get("operation")}
                        
                        results.append(result)
                    except Exception as e:
                        results.append({"success": False, "error": str(e), "operation": task.get("operation")})
                
                return {
                    "success": True,
                    "message": f"{len(task_list)} 件のタスクを直接実行しました",
                    "delegated": False,
                    "results": results
                }
                
        except Exception as e:
            self.logger.error(f"TaskLoop委譲エラー: {e}")
            return {"success": False, "error": str(e)}
    
    async def _echo_response_v8(self, template: str, **kwargs) -> str:
        return template

    async def _format_final_response(self, raw_results: List[Dict[str, Any]], user_message: str) -> str:
        """最終応答のフォーマット"""
        if not raw_results:
            return "実行できるタスクが見つかりませんでした。"
        
        if self.user_response_tool:
            try:
                action_results_for_prompt = [
                    {"sequence": i + 1, "success": r.get("success", False), "data": r, "summary": str(r)[:200], "operation": r.get("operation", f"op_{i}")}
                    for i, r in enumerate(raw_results)
                ]
                response_result = await self.user_response_tool.generate_response(
                    action_results=action_results_for_prompt,
                    user_input=user_message,
                    agent_state=self.agent_state
                )
                if response_result.get("success"):
                    return response_result.get("response", "処理が完了しました。")
            except Exception as e:
                self.logger.error(f"UserResponseTool使用エラー: {e}", exc_info=True)

        # Fallback formatting
        formatted_response = "以下が処理結果です:\n\n"
        for i, result in enumerate(raw_results, 1):
            formatted_response += f"{i}. {json.dumps(result, ensure_ascii=False, indent=2)}\n\n"
        return formatted_response.strip()
    
    def _get_current_plan_summary(self) -> str:
        """現在のプラン状況とファイル読み込み状況を要約して返す"""
        try:
            summary_lines = []
            
            # プラン状況
            if not hasattr(self.agent_state, 'plans') or not self.agent_state.plans:
                summary_lines.append("📋 **プラン状況**: 現在進行中のプランはありません。")
            else:
                summary_lines.append("📋 **プラン状況**:")
                for plan in self.agent_state.plans:
                    status_emoji = {
                        "draft": "📝",
                        "approved": "✅",
                        "in_progress": "🚀",
                        "completed": "🎉",
                        "failed": "❌"
                    }.get(plan.status, "❓")
                    
                    summary_lines.append(f"  {status_emoji} **{plan.name}** (ステータス: {plan.status})")
                    summary_lines.append(f"     目標: {plan.goal}")
                    
                    if plan.steps:
                        completed_steps = sum(1 for step in plan.steps if step.status == "completed")
                        total_steps = len(plan.steps)
                        summary_lines.append(f"     進捗: {completed_steps}/{total_steps} ステップ完了")
                        
                        for step in plan.steps:
                            step_emoji = {
                                "pending": "⏳",
                                "in_progress": "🔄",
                                "completed": "✅",
                                "failed": "❌"
                            }.get(step.status, "❓")
                            
                            summary_lines.append(f"       {step_emoji} {step.name}: {step.status}")
                    else:
                        summary_lines.append("     ステップ: 未定義")
                    
                    summary_lines.append("")
            
            # ファイル読み込み状況
            summary_lines.append("📁 **ファイル読み込み状況**:")
            if hasattr(self.agent_state, 'file_read_states') and self.agent_state.file_read_states:
                for file_path, state in self.agent_state.file_read_states.items():
                    status_emoji = "✅" if state.is_complete else "📖"
                    summary_lines.append(f"  {status_emoji} {file_path}: {state.bytes_read} / {state.total_size_bytes} バイト読み込み済み")
                    if not state.is_complete:
                        summary_lines.append(f"     (完了: {state.is_complete})")
            else:
                summary_lines.append("  読み込み済みファイルはありません")
            
            # ファイル内容の要約
            summary_lines.append("\n📄 **ファイル内容要約**:")
            try:
                # short_term_memoryからファイル内容を取得
                file_contents = getattr(self.agent_state, 'short_term_memory', {}).get('file_contents', {})
                if file_contents:
                    for file_path, file_data in file_contents.items():
                        content = file_data.get('content', '')
                        metadata = file_data.get('metadata', {})
                        total_chars = metadata.get('total_chars', len(content))
                        is_truncated = metadata.get('is_truncated', False)
                        
                        status_emoji = "📄" if not is_truncated else "📄✂️"
                        summary_lines.append(f"  {status_emoji} {file_path}: {len(content)} / {total_chars} 文字")
                        if is_truncated:
                            summary_lines.append(f"     (切り詰め: 最初の{len(content)}文字のみ)")
                        
                        # 内容の最初の100文字を表示
                        if content:
                            preview = content[:100].replace('\n', ' ').strip()
                            if len(content) > 100:
                                preview += "..."
                            summary_lines.append(f"     内容: {preview}")
                else:
                    summary_lines.append("  保存されたファイル内容はありません")
            except Exception as e:
                summary_lines.append(f"  ファイル内容の取得に失敗: {e}")
            
            return "\n".join(summary_lines)
        except Exception as e:
            self.logger.error(f"状況要約取得エラー: {e}")
            return "状況の取得に失敗しました。"
    
    def _get_plan_continuity_instruction(self) -> str:
        """現在のプラン状況に応じた継続性指示を生成"""
        try:
            if hasattr(self.agent_state, 'active_plan_id') and self.agent_state.active_plan_id:
                return """**指示**: 現在、上記のプランが進行中です。ユーザーの要求がこのプランの継続であるか、または関連するものであるかを検討してください。新しいプランを提案するのは、ユーザーが明確に指示した場合のみにしてください。"""
            else:
                return """**指示**: 現在進行中の長期プランはありません。ユーザーの要求が複雑な場合は、`plan_tool.propose` を使用して新しいプランを作成することを検討してください。"""
        except Exception as e:
            self.logger.error(f"プラン継続性指示生成エラー: {e}")
            return """**指示**: 現在進行中の長期プランはありません。ユーザーの要求が複雑な場合は、`plan_tool.propose` を使用して新しいプランを作成することを検討してください。"""
    
    def _initialize_ui(self):
        return None # Simplified

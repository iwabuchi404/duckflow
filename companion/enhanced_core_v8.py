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
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

# 新しいモジュール
from .output.human_formatter import HumanOutputFormatter, FormatterRequest, FormattedOutput
from .tools.structured_file_ops import StructuredFileOps

# 新実装のTool
from .tools.action_plan_tool import ActionPlanTool
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
    """V8アクション定義（構造化出力対応）"""
    operation: str
    args: Dict[str, Any]
    reasoning: str = ""
    action_id: str = ""
    needs_human_formatting: bool = True  # 新フィールド: 人間向けフォーマットが必要か

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
                self.action_plan_tool = None
                self.user_response_tool = None
            else:
                self.llm_client = llm_client  # インスタンス変数として保存
                self.action_plan_tool = ActionPlanTool(llm_client=llm_client)
                
                # PromptCompilerの取得
                prompt_compiler = None
                if hasattr(self.prompt_context_service, 'prompt_compiler'):
                    prompt_compiler = self.prompt_context_service.prompt_compiler
                elif hasattr(self.prompt_context_service, 'prompt_compiler'):
                    prompt_compiler = self.prompt_context_service.prompt_compiler
                
                if prompt_compiler:
                    self.user_response_tool = UserResponseTool(
                        prompt_compiler=prompt_compiler,
                        llm_client=llm_client
                    )
                else:
                    self.logger.warning("PromptCompilerが取得できません。UserResponseTool初期化をスキップします。")
                    self.user_response_tool = None
                    
        except Exception as e:
            self.logger.error(f"Tool初期化エラー: {e}")
            self.action_plan_tool = None
            self.user_response_tool = None
            self.llm_client = None
        
        self.tool_registry = ToolRegistry()
        
        # 重複表示防止
        self._last_response_hash = None
        self._response_count = 0
        self._last_response_time = None
        
        # UI初期化
        self.ui = self._initialize_ui()
        
        # ツール登録（構造化版）
        self.tools = {
            "structured_file_ops": {
                "analyze_file_structure": self._handle_analyze_file,
                "search_content": self._handle_search_content,
                "write_file": self._handle_write_file,
                "read_file": self._handle_read_file  # 従来互換
            },
            "response": {
                "echo": self._echo_response_v8
            }
        }
        
        # 新実装のToolが利用可能な場合のみ登録
        if self.action_plan_tool:
            self.tools["action_plan_tool"] = {
                "decompose_task": self.action_plan_tool.decompose_task
            }
        
        if self.user_response_tool:
            self.tools["user_response_tool"] = {
                "generate_response": self.user_response_tool.generate_response
            }
        
        # タスク管理ツールを登録
        self.task_management_tool = TaskManagementTool(self.agent_state)
        self.tools["task_management"] = {
            "start_task": self.task_management_tool.start_task,
            "complete_task": self.task_management_tool.complete_task,
            "add_task_result": self.task_management_tool.add_task_result,
            "get_task_status": self.task_management_tool.get_task_status,
            "list_tasks": self.task_management_tool.list_tasks
        }
        
        self.logger.info("EnhancedCompanionCoreV8 初期化完了")
    
    async def process_user_message(self, user_message: str) -> str:
        """ユーザーメッセージ処理のメインエントリーポイント"""
        try:
            self.logger.info(f"V8メッセージ処理開始: {user_message[:50]}...")
            
            # 意図分析
            intent_result = await self.analyze_intent_only(user_message)
            
            if intent_result.get("action_type") == "direct_response":
                # 直接応答
                response = await self._handle_direct_response(user_message, intent_result)
            else:
                # ActionList生成・実行
                response = await self._handle_action_execution(user_message, intent_result)
            
            # 会話履歴を更新
            try:
                if hasattr(self.agent_state, 'add_conversation_message'):
                    self.agent_state.add_conversation_message('user', user_message)
                    self.agent_state.add_conversation_message('assistant', response)
                    self.logger.info("会話履歴を更新しました")
                else:
                    self.logger.warning("AgentStateにadd_conversation_messageメソッドがありません")
            except Exception as e:
                self.logger.error(f"会話履歴更新エラー: {e}")
            
            return response
                
        except Exception as e:
            self.logger.error(f"V8メッセージ処理エラー: {e}")
            error_response = f"申し訳ありません、処理中にエラーが発生しました: {str(e)}"
            
            # エラー時も会話履歴を更新
            try:
                if hasattr(self.agent_state, 'add_conversation_message'):
                    self.agent_state.add_conversation_message('user', user_message)
                    self.agent_state.add_conversation_message('assistant', error_response)
            except Exception as update_error:
                self.logger.error(f"エラー時の会話履歴更新エラー: {update_error}")
            
            return error_response
    
    async def analyze_intent_only(self, user_message: str, context: Optional[Dict[str, Any]] = None):
        """意図分析のみを実行"""
        try:
            if self.intent_analyzer:
                # 実際の既存メソッド名を使用（非同期版）
                result = await self.intent_analyzer.analyze(user_message, context or {})
                return {
                    "action_type": getattr(result, 'action_type', 'direct_response'),
                    "confidence": 0.8,
                    "suggested_actions": ["file_analysis"]
                }
            else:
                # フォールバック: シンプルな意図推定
                if any(word in user_message.lower() for word in ['読んで', '分析', '確認', '見て']):
                    return {
                        "action_type": "action_execution", 
                        "confidence": 0.8,
                        "suggested_actions": ["file_analysis"]
                    }
                else:
                    return {"action_type": "direct_response", "confidence": 0.6}
        except Exception as e:
            self.logger.error(f"意図分析エラー: {e}")
            return {"action_type": "direct_response", "confidence": 0.3}
    
    async def _handle_direct_response(self, user_message: str, intent_result: Dict[str, Any]) -> str:
        """直接応答処理"""
        try:
            # LLMサービスで応答生成（利用可能なメソッドを使用）
            if self.llm_service:
                # 既存のメソッドを活用してシンプルな応答を生成
                if any(word in user_message.lower() for word in ['こんにちは', 'hello', '助けて', 'ヘルプ']):
                    return "こんにちは！何かお手伝いできることはありますか？ファイルの分析や内容の確認など、お気軽にお声がけください。"
                else:
                    # 直接ActionListを生成する方向に誘導
                    return await self._handle_action_execution(user_message, intent_result)
            else:
                return "申し訳ありません、現在直接応答機能が利用できません。"
                
        except Exception as e:
            self.logger.error(f"直接応答エラー: {e}")
            return f"応答生成中にエラーが発生しました: {str(e)}"
    
    async def _handle_action_execution(self, user_message: str, intent_result: Dict[str, Any]) -> str:
        """ActionList生成・実行処理"""
        try:
            # ActionList生成
            action_list = await self._generate_action_list_v8(user_message, intent_result)
            
            # ActionList実行
            results = []
            for action in action_list:
                result = await self._execute_action_v8(action)
                results.append(result)
                
                # AgentStateに結果保存（引数を正しく指定）
                try:
                    if hasattr(self.agent_state, 'add_action_result'):
                        # AgentStateの実際のメソッドシグネチャに合わせる
                        self.agent_state.add_action_result(
                            action_id=action.action_id,
                            operation=action.operation,
                            result=result,
                            action_list_id="v8_action_list",
                            sequence_number=len(results)
                        )
                except Exception as e:
                    self.logger.warning(f"AgentState結果保存エラー（処理継続）: {e}")
            
            # 最終応答をフォーマット
            return await self._format_final_response(results, user_message)
            
        except Exception as e:
            self.logger.error(f"Action実行エラー: {e}")
            return f"タスク実行中にエラーが発生しました: {str(e)}"
    
    async def _generate_action_list_v8(self, user_message: str, intent_result: Dict[str, Any]) -> List[ActionV8]:
        """V8対応のActionList生成（LLMベース・動的版）"""
        try:
            actions = []
            
            # LLMにツール使用計画を生成させる
            llm_plan = await self._generate_llm_plan(user_message)
            
            if llm_plan and llm_plan.get("operations"):
                self.logger.info(f"LLM計画解析結果: {llm_plan}")
                
                # operationsの型と内容を検証
                operations = llm_plan["operations"]
                if not isinstance(operations, list):
                    self.logger.error(f"operationsが配列ではありません: {type(operations)}, 内容: {operations}")
                    # 文字列の場合は配列に変換を試行
                    if isinstance(operations, str):
                        # 文字列の内容を解析して適切な操作タイプを推測
                        if "analyze" in operations.lower():
                            operations = [{"type": "analyze_structure", "reasoning": "ファイル構造分析"}]
                        elif "search" in operations.lower():
                            operations = [{"type": "search_content", "reasoning": "コンテンツ検索"}]
                        elif "read" in operations.lower():
                            operations = [{"type": "read_file", "reasoning": "ファイル読み込み"}]
                        else:
                            operations = [{"type": "read_file", "reasoning": "ファイル読み込み"}]
                        llm_plan["operations"] = operations
                        self.logger.info(f"operationsを配列に変換: {operations}")
                    else:
                        self.logger.warning("operationsの形式が不正、フォールバックロジックを使用")
                        return await self._generate_fallback_action_list(user_message, intent_result)
                
                action_id_base = f"act_{datetime.now().strftime('%H%M%S')}"
                
                for i, operation in enumerate(operations):
                    # operationの型と内容を検証
                    if not isinstance(operation, dict):
                        self.logger.error(f"operation {i}が辞書ではありません: {type(operation)}, 内容: {operation}")
                        continue
                    
                    operation_type = operation.get("type")
                    if not operation_type:
                        self.logger.error(f"operation {i}にtypeフィールドがありません: {operation}")
                        continue
                    
                    action_id = f"{action_id_base}_{i}_{operation_type}"
                    
                    if operation_type == "analyze_structure":
                        actions.append(ActionV8(
                            operation="structured_file_ops.analyze_file_structure",
                            args={"file_path": llm_plan["target_file"]},
                            reasoning=operation["reasoning"],
                            action_id=action_id,
                            needs_human_formatting=True
                        ))
                    
                    elif operation_type == "search_content":
                        # LLMが生成した検索パターンを使用
                        search_pattern = "|".join(llm_plan.get("search_patterns", ["概要"]))
                        actions.append(ActionV8(
                            operation="structured_file_ops.search_content",
                            args={
                                "file_path": llm_plan["target_file"], 
                                "pattern": search_pattern
                            },
                            reasoning=operation.get("reasoning", "検索実行"),
                            action_id=action_id,
                            needs_human_formatting=True
                        ))
                    
                    elif operation_type == "read_file":
                        actions.append(ActionV8(
                            operation="structured_file_ops.read_file",
                            args={"file_path": llm_plan["target_file"]},
                            reasoning=operation.get("reasoning", "ファイル読み込み"),
                            action_id=action_id,
                            needs_human_formatting=True
                        ))
                    
                    elif operation_type == "decompose_task":
                        actions.append(ActionV8(
                            operation="action_plan_tool.decompose_task",
                            args={
                                "user_input": user_message,
                                "task_profile": "planning",
                                "complexity": "medium"
                            },
                            reasoning=operation.get("reasoning", "タスク分解"),
                            action_id=action_id,
                            needs_human_formatting=True
                        ))
                    
                    elif operation_type == "generate_response":
                        actions.append(ActionV8(
                            operation="user_response_tool.generate_response",
                            args={
                                "action_results": [],  # 前のアクション結果を渡す必要がある
                                "user_input": user_message,
                                "agent_state": self.agent_state
                            },
                            reasoning=operation.get("reasoning", "応答生成"),
                            action_id=action_id,
                            needs_human_formatting=True
                        ))
                
                self.logger.info(f"LLM計画ベース ActionList生成完了: {len(actions)}個のアクション")
                return actions
            
            # フォールバック: 従来のロジック
            self.logger.warning("LLM計画生成に失敗、フォールバックロジックを使用")
            fallback_actions = await self._generate_fallback_action_list(user_message, intent_result)
            if fallback_actions:
                self.logger.info(f"フォールバックロジックで{len(fallback_actions)}個のアクションを生成")
            else:
                self.logger.warning("フォールバックロジックでもアクション生成に失敗")
            return fallback_actions
            
        except Exception as e:
            self.logger.error(f"ActionList生成エラー: {e}")
            return []
    
    async def _generate_llm_plan(self, user_message: str) -> Dict[str, Any]:
        """LLMに処理計画を生成させる"""
        try:
            # 汎用的なタスク実行計画生成プロンプト
            prompt = f"""
ユーザーの要求を分析し、適切な実行計画を立ててください。

ユーザー要求: {user_message}

利用可能なツールと使い方：

1. structured_file_ops.analyze_file_structure(file_path: str)
   - ファイルの構造を分析（ヘッダー、セクション、行数など）
   - 例: analyze_file_structure("game_doc.md")

2. structured_file_ops.search_content(file_path: str, pattern: str)
   - ファイル内を検索（patternは検索キーワード）
   - 例: search_content("game_doc.md", "概要|ゲーム|RPG")

3. structured_file_ops.read_file(file_path: str)
   - ファイルの内容を読み込み
   - 例: read_file("game_doc.md")

4. action_plan_tool.decompose_task(user_input: str, task_profile: str, complexity: str)
   - タスクをサブタスクに分解
   - 例: decompose_task("実装プランを作成", "planning", "medium")

5. user_response_tool.generate_response(action_results: list, user_input: str, agent_state: object)
   - アクション結果を基にユーザー向け応答を生成

以下のJSON形式で処理計画を回答してください：

{{
    "target_file": "対象ファイルパス（ファイル操作の場合）",
    "operations": [
        {{
            "type": "analyze_structure|search_content|read_file|decompose_task|generate_response",
            "parameters": {{}},
            "reasoning": "この操作を行う理由"
        }}
    ],
    "search_patterns": ["検索キーワード1", "検索キーワード2"]（検索が必要な場合）
}}

例：
- ユーザーが「game_doc.mdの概要を把握したい」と言った場合
  {{
    "target_file": "game_doc.md",
    "operations": [
      {{"type": "analyze_structure", "reasoning": "ファイル構造を把握するため"}},
      {{"type": "search_content", "reasoning": "概要情報を検索するため"}},
      {{"type": "read_file", "reasoning": "詳細内容を読み込むため"}}
    ],
    "search_patterns": ["概要", "ゲーム", "RPG"]
  }}

- ユーザーが「実装プランを作成してください」と言った場合
  {{
    "target_file": null,
    "operations": [
      {{"type": "decompose_task", "reasoning": "タスクをサブタスクに分解するため"}}
    ]
  }}
"""

            # LLM呼び出し
            if self.llm_client:
                self.logger.info("LLMに処理計画生成を依頼")
                response = await self.llm_client.chat(
                    prompt=prompt,
                    tools=False,  # ツール使用を無効化
                    tool_choice="none"  # ツール選択を無効化
                )
                
                self.logger.info(f"LLM応答受信: {len(response.content)}文字")
                self.logger.debug(f"LLM応答内容（最初の200文字）: {response.content[:200]}...")
                
                return self._parse_llm_plan(response.content)
            else:
                self.logger.warning("LLMクライアントが利用できません")
                return None
                
        except Exception as e:
            self.logger.error(f"LLM計画生成エラー: {e}")
            return None
    
    def _parse_llm_plan(self, llm_response: str) -> Dict[str, Any]:
        """LLMの応答から処理計画を解析（拡張版）"""
        try:
            self.logger.info(f"LLM応答解析開始: {len(llm_response)}文字")
            
            # 方法1: 既存の正規表現パターン（改善）
            self.logger.debug("方法1: 正規表現パターンでのJSON抽出を試行")
            plan = self._extract_json_with_regex(llm_response)
            if plan and self._validate_plan_structure(plan):
                self.logger.info("方法1でJSON抽出成功")
                return plan
            
            # 方法2: より柔軟なJSON抽出
            self.logger.debug("方法2: 柔軟なJSON抽出を試行")
            plan = self._extract_json_flexible(llm_response)
            if plan:
                self.logger.info("方法2でJSON抽出成功")
                return plan
            
            # 方法3: 構造化テキスト解析
            self.logger.debug("方法3: 構造化テキスト解析を試行")
            plan = self._extract_structured_text(llm_response)
            if plan:
                self.logger.info("方法3でJSON抽出成功")
                return plan
            
            self.logger.warning("LLM応答からJSONを抽出できませんでした")
            return None
            
        except Exception as e:
            self.logger.error(f"LLM計画解析エラー: {e}")
            return None
    
    def _validate_plan_structure(self, plan: Dict[str, Any]) -> bool:
        """計画の構造を検証"""
        try:
            # 基本的な構造チェック
            if not isinstance(plan, dict):
                self.logger.warning("計画が辞書形式ではありません")
                return False
            
            # operationsフィールドの検証
            if "operations" in plan:
                if not isinstance(plan["operations"], list):
                    self.logger.warning(f"operationsが配列ではありません: {type(plan['operations'])}")
                    # 文字列の場合は後で変換可能なので、検証をスキップ
                    if isinstance(plan["operations"], str):
                        self.logger.info("operationsが文字列ですが、後で変換可能です")
                        return True
                    return False
                
                if len(plan["operations"]) == 0:
                    self.logger.warning("operations配列が空です")
                    return False
                
                # 各操作の基本構造をチェック
                for i, op in enumerate(plan["operations"]):
                    if not isinstance(op, dict):
                        self.logger.warning(f"操作 {i} が辞書形式ではありません: {type(op)}")
                        return False
                    
                    if "type" not in op:
                        self.logger.warning(f"操作 {i} にtypeフィールドがありません")
                        return False
            
            # target_fileフィールドの検証（存在する場合）
            if "target_file" in plan and plan["target_file"] is not None:
                if not isinstance(plan["target_file"], str):
                    self.logger.warning(f"target_fileが文字列ではありません: {type(plan['target_file'])}")
                    return False
            
            self.logger.debug("計画構造の検証が完了しました")
            return True
            
        except Exception as e:
            self.logger.error(f"計画構造検証エラー: {e}")
            return False
    
    def _repair_incomplete_json(self, llm_response: str) -> Optional[Dict[str, Any]]:
        """不完全なJSONの修復を試行"""
        try:
            import re
            import json
            
            # 1. 基本的なJSONブロックを検索
            json_block_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', llm_response, re.DOTALL)
            if not json_block_match:
                return None
            
            json_text = json_block_match.group()
            self.logger.debug(f"修復対象JSONテキスト: {json_text}")
            
            # 2. 一般的な問題を修復
            # 末尾のカンマを削除
            json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
            
            # 不完全な文字列を修復
            json_text = re.sub(r'"([^"]*)$', r'"\1"', json_text)
            
            # 不完全な数値を修復
            json_text = re.sub(r'(\d+\.\d*)$', r'\1', json_text)
            
            # 3. operations配列の特別処理
            if '"operations"' in json_text:
                # operations配列の境界を修復
                json_text = re.sub(r'"operations"\s*:\s*\[([^\]]*)$', r'"operations": [\1]', json_text)
                
                # 不完全なオブジェクトを修復
                json_text = re.sub(r'\{([^{}]*)$', r'{\1}', json_text)
            
            # 4. JSON解析を試行
            try:
                repaired_plan = json.loads(json_text)
                self.logger.debug(f"JSON修復成功: {repaired_plan}")
                return repaired_plan
            except json.JSONDecodeError as e:
                self.logger.debug(f"JSON修復失敗: {e}")
                
                # 5. 最後の手段として、手動で構造を構築
                return self._build_plan_manually(llm_response)
            
        except Exception as e:
            self.logger.debug(f"不完全JSON修復エラー: {e}")
            return None
    
    def _build_plan_manually(self, llm_response: str) -> Optional[Dict[str, Any]]:
        """手動で計画を構築（最後の手段）"""
        try:
            import re
            
            plan = {}
            
            # target_fileの抽出
            target_file_match = re.search(r'"target_file"\s*:\s*"([^"]+)"', llm_response)
            if target_file_match:
                plan["target_file"] = target_file_match.group(1)
            
            # operationsの手動構築
            operations = []
            
            # 操作タイプの検出
            operation_types = re.findall(r'"type"\s*:\s*"([^"]+)"', llm_response)
            reasoning_texts = re.findall(r'"reasoning"\s*:\s*"([^"]+)"', llm_response)
            
            for i, op_type in enumerate(operation_types):
                operation = {
                    "type": op_type,
                    "reasoning": reasoning_texts[i] if i < len(reasoning_texts) else f"操作 {i+1} の実行",
                    "parameters": {}
                }
                operations.append(operation)
            
            if operations:
                plan["operations"] = operations
            
            # search_patternsの抽出
            search_patterns_match = re.search(r'"search_patterns"\s*:\s*\[(.*?)\]', llm_response, re.DOTALL)
            if search_patterns_match:
                patterns_text = search_patterns_match.group(1)
                patterns = re.findall(r'"([^"]+)"', patterns_text)
                if patterns:
                    plan["search_patterns"] = patterns
            
            self.logger.debug(f"手動構築された計画: {plan}")
            return plan if plan else None
            
        except Exception as e:
            self.logger.debug(f"手動計画構築エラー: {e}")
            return None
    
    def _extract_json_with_regex(self, llm_response: str) -> Optional[Dict[str, Any]]:
        """既存の正規表現パターンを改善したJSON抽出"""
        try:
            import json
            import re
            
            # 複数のパターンで検索（既存の改善）
            patterns = [
                r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # ネストしたJSON（既存の改善）
                r'\{[^{}]*\}',  # シンプルなJSON（既存）
                r'\[[^\[\]]*\]',  # 配列形式（新規）
            ]
            
            for pattern in patterns:
                json_match = re.search(pattern, llm_response, re.DOTALL)
                if json_match:
                    json_text = json_match.group().strip()
                    # 基本的な修復を試行
                    json_text = self._basic_json_repair(json_text)
                    if self._is_valid_json(json_text):
                        return json.loads(json_text)
            
            return None
            
        except Exception as e:
            self.logger.debug(f"正規表現JSON抽出エラー: {e}")
            return None
    
    def _extract_json_flexible(self, llm_response: str) -> Optional[Dict[str, Any]]:
        """より柔軟なJSON抽出"""
        try:
            import json
            import re
            
            # 不完全なJSONの修復を試行
            # 1. 末尾のカンマを削除
            repaired = re.sub(r',(\s*[}\]])', r'\1', llm_response)
            
            # 2. 不完全な文字列を修復
            repaired = re.sub(r'"([^"]*)$', r'"\1"', repaired)
            
            # 3. 不完全な数値を修復
            repaired = re.sub(r'(\d+\.\d*)$', r'\1', repaired)
            
            # 4. 不完全なブール値を修復
            repaired = re.sub(r'(true|false)$', r'\1', repaired)
            
            # 修復後のテキストでJSON解析を試行
            if self._is_valid_json(repaired):
                return json.loads(repaired)
            
            return None
            
        except Exception as e:
            self.logger.debug(f"柔軟JSON抽出エラー: {e}")
            return None
    
    def _extract_structured_text(self, llm_response: str) -> Optional[Dict[str, Any]]:
        """構造化されたテキストからJSONを推測"""
        try:
            import re
            import json
            
            # より高度なパターンマッチング
            result = {}
            
            # 1. まずoperations配列を処理（優先度最高）
            if "operations" in llm_response.lower():
                # operationsセクションを検索（より堅牢な境界検出）
                operations_match = re.search(r'"operations"\s*:\s*\[(.*?)\s*\]', llm_response, re.DOTALL | re.IGNORECASE)
                if operations_match:
                    operations_text = operations_match.group(1).strip()
                    self.logger.debug(f"operations抽出テキスト: {operations_text}")
                    
                    # 個別の操作を抽出（ネストしたオブジェクトに対応）
                    operations = []
                    
                    # 各操作オブジェクトを検索（より正確なパターン）
                    # 中括弧のネストを考慮した抽出
                    operation_blocks = []
                    brace_count = 0
                    start_pos = -1
                    
                    for i, char in enumerate(operations_text):
                        if char == '{':
                            if brace_count == 0:
                                start_pos = i
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0 and start_pos != -1:
                                operation_blocks.append(operations_text[start_pos:i+1])
                                start_pos = -1
                    
                    self.logger.debug(f"抽出された操作ブロック数: {len(operation_blocks)}")
                    
                    for op_block in operation_blocks:
                        self.logger.debug(f"操作ブロック抽出: {op_block}")
                        op_data = {}
                        
                        # typeフィールドを抽出
                        type_match = re.search(r'"type"\s*:\s*"([^"]+)"', op_block)
                        if type_match:
                            op_data["type"] = type_match.group(1)
                        
                        # reasoningフィールドを抽出
                        reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]+)"', op_block)
                        if reasoning_match:
                            op_data["reasoning"] = reasoning_match.group(1)
                        
                        # parametersフィールドを抽出
                        parameters_match = re.search(r'"parameters"\s*:\s*(\{[^}]*\})', op_block)
                        if parameters_match:
                            try:
                                # パラメータをJSONとして解析
                                params = json.loads(parameters_match.group(1))
                                op_data["parameters"] = params
                            except:
                                op_data["parameters"] = {}
                        
                        if op_data:
                            operations.append(op_data)
                            self.logger.debug(f"操作データ追加: {op_data}")
                    
                    if operations:
                        result["operations"] = operations
                        self.logger.debug(f"operations配列完成: {operations}")
                    else:
                        self.logger.warning("operations配列の抽出に失敗しました")
            
            # 2. target_fileの検出
            target_file_match = re.search(r'"target_file"\s*:\s*"([^"]+)"', llm_response)
            if target_file_match:
                result["target_file"] = target_file_match.group(1)
            
            # 3. search_patternsの検出
            search_patterns_match = re.search(r'"search_patterns"\s*:\s*\[(.*?)\]', llm_response, re.DOTALL)
            if search_patterns_match:
                patterns_text = search_patterns_match.group(1)
                patterns = []
                # クォートで囲まれたパターンを抽出
                pattern_matches = re.findall(r'"([^"]+)"', patterns_text)
                for pattern in pattern_matches:
                    if pattern.strip():
                        patterns.append(pattern.strip())
                
                if patterns:
                    result["search_patterns"] = patterns
            
            # 4. 基本的なキー・バリューペア（operations配列の外のみ）
            # operations配列内のフィールドを誤って抽出しないよう制限
            if "operations" in result:
                # operations配列が既に処理済みの場合、個別フィールドの抽出はスキップ
                self.logger.debug("operations配列が既に処理済みのため、個別フィールド抽出をスキップ")
            else:
                # operations配列がない場合のみ、基本的なキー・バリューペアを抽出
                key_value_patterns = [
                    r'"([^"]+)":\s*([^,\n]+)',  # "key": value
                    r'(\w+)\s*=\s*([^,\n]+)',  # key = value
                ]
                
                for pattern in key_value_patterns:
                    matches = re.findall(pattern, llm_response)
                    for key, value in matches:
                        # operations配列内のフィールドは除外
                        if key not in ['type', 'reasoning', 'parameters']:
                            converted_value = self._convert_value(value.strip())
                            if converted_value is not None:
                                result[key] = converted_value
            
            # 5. 結果の検証とログ出力
            if "operations" in result:
                if isinstance(result["operations"], list):
                    self.logger.info(f"operations配列正常に抽出: {len(result['operations'])}個の操作")
                    # 各操作の詳細をログ出力
                    for i, op in enumerate(result["operations"]):
                        self.logger.debug(f"  操作 {i+1}: {op}")
                else:
                    self.logger.error(f"operationsが配列ではありません: {type(result['operations'])}, 内容: {result['operations']}")
                    # 文字列の場合は適切な操作に変換を試行
                    if isinstance(result["operations"], str):
                        operations_text = result["operations"]
                        if "analyze" in operations_text.lower():
                            result["operations"] = [{"type": "analyze_structure", "reasoning": "ファイル構造分析"}]
                        elif "search" in operations_text.lower():
                            result["operations"] = [{"type": "search_content", "reasoning": "コンテンツ検索"}]
                        elif "read" in operations_text.lower():
                            result["operations"] = [{"type": "read_file", "reasoning": "ファイル読み込み"}]
                        else:
                            result["operations"] = [{"type": "read_file", "reasoning": "ファイル読み込み"}]
                        self.logger.info(f"operations文字列を配列に変換: {result['operations']}")
                    else:
                        # 配列でない場合は削除
                        del result["operations"]
            
            # 全体の結果をログ出力
            self.logger.info(f"LLM計画解析結果: {result}")
            return result if result else None
            
        except Exception as e:
            self.logger.debug(f"構造化テキスト抽出エラー: {e}")
            return None
    
    def _basic_json_repair(self, json_text: str) -> str:
        """基本的なJSON修復"""
        try:
            import re
            
            # 1. 末尾のカンマを削除
            json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
            
            # 2. 不完全な文字列を修復
            json_text = re.sub(r'"([^"]*)$', r'"\1"', json_text)
            
            # 3. 不完全な数値を修復
            json_text = re.sub(r'(\d+\.\d*)$', r'\1', json_text)
            
            return json_text
            
        except Exception as e:
            self.logger.debug(f"JSON修復エラー: {e}")
            return json_text
    
    def _is_valid_json(self, text: str) -> bool:
        """JSONの妥当性をチェック"""
        try:
            import json
            json.loads(text)
            return True
        except:
            return False
    
    def _convert_value(self, value: str) -> Any:
        """文字列値を適切な型に変換"""
        try:
            import re
            
            # null
            if value.lower() in ['null', 'none', '']:
                return None
            
            # ブール値
            if value.lower() in ['true', 'false']:
                return value.lower() == 'true'
            
            # 数値
            if value.isdigit():
                return int(value)
            if re.match(r'^\d+\.\d+$', value):
                return float(value)
            
            # 文字列（クォートを除去）
            cleaned = value.strip('"\'')
            return cleaned
            
        except:
            return value
    
    async def _generate_fallback_action_list(self, user_message: str, intent_result: Dict[str, Any]) -> List[ActionV8]:
        """フォールバック用のActionList生成（従来ロジック）"""
        try:
            actions = []
            
            # game_doc.mdの直接分析
            if 'game_doc.md' in user_message or 'game_doc' in user_message:
                self.logger.info("フォールバック: game_doc.md分析要求を検出")
                action_id_base = f"act_{datetime.now().strftime('%H%M%S')}"
                
                actions.append(ActionV8(
                    operation="structured_file_ops.analyze_file_structure",
                    args={"file_path": "game_doc.md"},
                    reasoning="RPGゲーム設計ドキュメントの構造を分析",
                    action_id=f"{action_id_base}_analyze",
                    needs_human_formatting=True
                ))
                
                # デフォルト検索パターン
                actions.append(ActionV8(
                    operation="structured_file_ops.search_content", 
                    args={"file_path": "game_doc.md", "pattern": "概要|ゲーム|RPG"},
                    reasoning="ゲームの概要情報を検索",
                    action_id=f"{action_id_base}_search",
                    needs_human_formatting=True
                ))
                
                return actions
            
            # プラン生成の処理
            action_type = intent_result.get("action_type")
            if (hasattr(action_type, 'value') and action_type.value == "plan_generation") or action_type == "plan_generation":
                self.logger.info("フォールバック: プラン生成要求を検出")
                action_id_base = f"act_{datetime.now().strftime('%H%M%S')}"
                
                if 'game_doc' in user_message or 'ドキュメント' in user_message:
                    actions.append(ActionV8(
                        operation="structured_file_ops.analyze_file_structure",
                        args={"file_path": "game_doc.md"},
                        reasoning="プラン作成のためのドキュメント分析",
                        action_id=f"{action_id_base}_analyze",
                        needs_human_formatting=True
                    ))
                
                actions.append(ActionV8(
                    operation="action_plan_tool.decompose_task",
                    args={
                        "user_input": user_message,
                        "task_profile": "planning",
                        "complexity": "medium"
                    },
                    reasoning="ドキュメントを基にした実装プランの生成",
                    action_id=f"{action_id_base}_plan",
                    needs_human_formatting=True
                ))
                
                return actions
            
            # その他の一般的なファイル処理
            file_candidates = [word for word in user_message.split() if '.' in word and len(word) > 3]
            if file_candidates:
                file_path = file_candidates[0]
                action_id_base = f"act_{datetime.now().strftime('%H%M%S')}"
                
                actions.append(ActionV8(
                    operation="structured_file_ops.analyze_file_structure",
                    args={"file_path": file_path},
                    reasoning=f"ファイル {file_path} の構造分析",
                    action_id=f"{action_id_base}_analyze",
                    needs_human_formatting=True
                ))
                
                return actions
            
            return []
            
        except Exception as e:
            self.logger.error(f"フォールバックActionList生成エラー: {e}")
            return []
    
    async def _execute_action_v8(self, action: ActionV8) -> Union[Dict[str, Any], str]:
        """V8アクションの実行"""
        try:
            self.logger.info(f"V8アクション実行: {action.operation}")
            
            # ツール実行
            tool_parts = action.operation.split('.')
            if len(tool_parts) >= 2:
                tool_category = tool_parts[0]
                tool_method = tool_parts[1]
                
                if tool_category in self.tools and tool_method in self.tools[tool_category]:
                    raw_result = await self._call_tool(self.tools[tool_category][tool_method], action.args)
                    
                    # 人間向けフォーマットが必要な場合
                    if action.needs_human_formatting and isinstance(raw_result, dict):
                        return await self._format_structured_data(raw_result, action)
                    else:
                        return raw_result
                else:
                    return f"不明なツール: {action.operation}"
            else:
                return f"無効な操作形式: {action.operation}"
                
        except Exception as e:
            self.logger.error(f"V8アクション実行エラー: {e}")
            return f"実行エラー: {str(e)}"
    
    async def _format_structured_data(self, data: Dict[str, Any], action: ActionV8) -> str:
        """構造化データを人間向けにフォーマット"""
        try:
            # フォーマットタイプを決定
            format_type = "generic"
            if "analyze_file" in action.operation:
                format_type = "file_analysis"
            elif "search_content" in action.operation:
                format_type = "search_result"
            elif "generate_implementation_plan" in action.operation:
                format_type = "plan_generation"
            elif any(op in action.operation for op in ["write", "create", "delete"]):
                format_type = "operation_result"
            
            # フォーマット要求作成
            request = FormatterRequest(
                data=data,
                context=action.reasoning,
                format_type=format_type,
                user_intent=action.reasoning
            )
            
            # フォーマット実行
            formatted = await self.human_formatter.format_data(request)
            
            if formatted.success:
                return formatted.human_text
            else:
                self.logger.warning(f"フォーマット失敗: {formatted.error_message}")
                return f"データ処理完了（詳細: {formatted.summary}）"
                
        except Exception as e:
            self.logger.error(f"データフォーマットエラー: {e}")
            return f"データを処理しましたが、表示形式の変換でエラーが発生しました: {str(e)}"
    
    async def _call_tool(self, tool_func, args: Dict[str, Any]):
        """ツール呼び出しの統一インターフェース"""
        try:
            if asyncio.iscoroutinefunction(tool_func):
                return await tool_func(**args)
            else:
                return tool_func(**args)
        except Exception as e:
            raise Exception(f"ツール呼び出しエラー: {str(e)}")
    
    # 新しいツールハンドラー
    async def _handle_analyze_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """ファイル分析ハンドラー（シンプル版）"""
        try:
            return await self.structured_file_ops.analyze_file_structure(file_path, **kwargs)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _handle_search_content(self, file_path: str, pattern: str, **kwargs) -> Dict[str, Any]:
        """コンテンツ検索ハンドラー（シンプル版）"""
        try:
            return await self.structured_file_ops.search_content(file_path, pattern, **kwargs)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _handle_write_file(self, file_path: str, content: str, **kwargs) -> Dict[str, Any]:
        """ファイル書き込みハンドラー（シンプル版）"""
        try:
            return await self.structured_file_ops.write_file(file_path, content, **kwargs)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _handle_read_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """ファイル読み込みハンドラー（シンプル版）"""
        try:
            # 実際のファイル内容を読み込み
            result = await self.structured_file_ops.read_file(file_path, **kwargs)
            
            # 結果を検証
            if result.get("success") and "content" in result:
                content = result["content"]
                # 実際の行数をカウント
                actual_lines = len(content.split('\n')) if isinstance(content, str) else 0
                actual_chars = len(content) if isinstance(content, str) else 0
                
                # 結果を更新
                result["actual_lines"] = actual_lines
                result["actual_chars"] = actual_chars
                
                # ファイル内容の検証ログ
                self.logger.info(f"ファイル読み込み完了: {file_path}")
                self.logger.info(f"  実際の行数: {actual_lines}")
                self.logger.info(f"  実際の文字数: {actual_chars}")
                self.logger.info(f"  ファイルサイズ: {result.get('size_bytes', 'N/A')} bytes")
                
                # 内容の要約（最初の数行と最後の数行）
                if isinstance(content, str) and content.strip():
                    lines = content.split('\n')
                    if len(lines) > 0:
                        first_lines = lines[:3]
                        last_lines = lines[-3:] if len(lines) > 3 else []
                        
                        self.logger.info(f"  最初の行: {first_lines}")
                        if last_lines and len(lines) > 3:
                            self.logger.info(f"  最後の行: {last_lines}")
                
                # 警告: 行数が予想と大きく異なる場合
                if actual_lines > 100:  # 100行を超える場合は警告
                    self.logger.warning(f"⚠️ ファイル {file_path} の行数が予想より多いです: {actual_lines}行")
                    self.logger.warning("  実際のファイル内容を確認してください")
                
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _echo_response_v8(self, template: str, **kwargs) -> str:
        """V8版echo応答（シンプル化）"""
        try:
            # テンプレート変数の簡易処理
            response_text = template
            
            # ActionID参照があれば置換（簡略化）
            import re
            references = re.findall(r'{@([^}]+)}', template)
            
            for ref in references:
                try:
                    # AgentStateから結果を取得
                    action_result = self.agent_state.get_action_result_by_id(ref)
                    reference_pattern = '{@' + ref + '}'
                    if action_result and isinstance(action_result, str):
                        response_text = response_text.replace(reference_pattern, action_result)
                    else:
                        response_text = response_text.replace(reference_pattern, '[参照データ]')
                except Exception:
                    reference_pattern = '{@' + ref + '}'
                    response_text = response_text.replace(reference_pattern, '[参照エラー]')
            
            return response_text
            
        except Exception as e:
            self.logger.error(f"Echo応答エラー: {e}")
            return f"応答生成エラー: {str(e)}"
    
    async def _format_final_response(self, results: List[Any], user_message: str) -> str:
        """最終応答のフォーマット（UserResponseTool使用）"""
        try:
            # 結果をまとめて自然な文章で返答
            if not results:
                return "申し訳ありません、実行できるタスクが見つかりませんでした。"
            
            # UserResponseToolが利用可能な場合はLLMベースで応答生成
            if self.user_response_tool:
                try:
                    self.logger.info("UserResponseToolを使用して応答生成を開始")
                    
                    # ファイル読み込み結果の検証
                    file_read_results = []
                    for result in results:
                        if isinstance(result, dict) and "actual_lines" in result:
                            file_read_results.append(result)
                    
                    # ファイル内容の検証警告を追加
                    verification_warning = ""
                    for file_result in file_read_results:
                        actual_lines = file_result.get("actual_lines", 0)
                        file_path = file_result.get("file_path", "unknown")
                        
                        if actual_lines > 100:
                            verification_warning += f"\n\n⚠️ **重要**: ファイル {file_path} の実際の行数は {actual_lines}行 です。"
                            verification_warning += "\nAIが報告した内容と実際のファイル内容が異なる可能性があります。"
                            verification_warning += "\n実際のファイル内容を直接確認することをお勧めします。"
                    
                    # アクション結果を辞書形式に変換
                    action_results = []
                    for i, result in enumerate(results):
                        if isinstance(result, dict):
                            # 辞書結果を適切な形式に変換
                            action_result = {
                                "sequence": i + 1,
                                "success": result.get("success", True),
                                "data": result.get("data", result),
                                "summary": result.get("summary", str(result)),
                                "operation": result.get("operation", f"operation_{i+1}")
                            }
                            action_results.append(action_result)
                        else:
                            # 文字列結果を辞書形式に変換
                            action_results.append({
                                "sequence": i + 1,
                                "result_type": "text",
                                "content": str(result),
                                "success": True,
                                "summary": str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
                            })
                    
                    # UserResponseToolで応答生成
                    # 実際のファイル内容を強制的に参照するためのコンテキストを追加
                    enhanced_user_input = user_message
                    if file_read_results:
                        enhanced_user_input += "\n\n【重要】実際のファイル内容の検証結果:\n"
                        for file_result in file_read_results:
                            actual_lines = file_result.get("actual_lines", 0)
                            file_path = file_result.get("file_path", "unknown")
                            enhanced_user_input += f"- {file_path}: 実際の行数 {actual_lines}行\n"
                        enhanced_user_input += "\n上記の実際のファイル内容のみを基に応答を生成してください。"
                    
                    response_result = await self.user_response_tool.generate_response(
                        action_results=action_results,
                        user_input=enhanced_user_input,  # 強化されたユーザー入力
                        agent_state=self.agent_state
                    )
                    
                    if response_result.get("success"):
                        self.logger.info("UserResponseToolによる応答生成完了")
                        response_text = response_result.get("response", "応答生成が完了しました。")
                        
                        # 検証警告を追加
                        if verification_warning:
                            response_text += verification_warning
                        
                        return response_text
                    else:
                        self.logger.warning(f"UserResponseTool応答生成失敗: {response_result.get('error')}")
                        # フォールバック: 従来の方法
                        fallback_response = self._format_fallback_response(results)
                        
                        # 検証警告を追加
                        if verification_warning:
                            fallback_response += verification_warning
                        
                        return fallback_response
                        
                except Exception as e:
                    self.logger.error(f"UserResponseTool使用エラー: {e}")
                    # フォールバック: 従来の方法
                    fallback_response = self._format_fallback_response(results)
                    
                    # 検証警告を追加
                    if verification_warning:
                        fallback_response += verification_warning
                    
                    return fallback_response
            else:
                # UserResponseToolが利用できない場合は従来の方法
                fallback_response = self._format_fallback_response(results)
                
                # 検証警告を追加
                if verification_warning:
                    fallback_response += verification_warning
                
                return fallback_response
                
        except Exception as e:
            self.logger.error(f"最終応答フォーマットエラー: {e}")
            return f"処理は完了しましたが、結果の表示でエラーが発生しました: {str(e)}"
    
    def _format_fallback_response(self, results: List[Any]) -> str:
        """フォールバック用の応答フォーマット（従来の方法）"""
        try:
            # 文字列結果をまとめる
            text_results = [str(result) for result in results if result]
            
            if len(text_results) == 1:
                return text_results[0]
            else:
                # 複数の結果をまとめる
                formatted_response = "以下が処理結果です:\n\n"
                for i, result in enumerate(text_results, 1):
                    formatted_response += f"{i}. {result}\n\n"
                
                return formatted_response.strip()
                
        except Exception as e:
            self.logger.error(f"フォールバック応答フォーマットエラー: {e}")
            return f"処理は完了しましたが、結果の表示でエラーが発生しました: {str(e)}"
    
    def _initialize_ui(self):
        """UI初期化（既存システムから継承）"""
        try:
            from .ui import rich_ui
            return rich_ui
        except ImportError:
            return None
    
    def _setup_encoding_environment(self):
        """文字エンコーディング環境設定（既存から継承）"""
        import sys
        import os
        
        # UTF-8環境の確保
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stderr.reconfigure(encoding='utf-8')
            except Exception:
                pass
        
        # 環境変数設定
        os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    
    # V7互換性メソッド
    def get_conversation_history(self):
        """対話履歴を取得（V7互換）"""
        return getattr(self.agent_state, 'conversation_history', [])
    
    def add_to_conversation_history(self, user_message: str, assistant_response: str):
        """対話履歴に追加（V7互換）"""
        try:
            if hasattr(self.agent_state, 'add_conversation_message'):
                self.agent_state.add_conversation_message('user', user_message)
                self.agent_state.add_conversation_message('assistant', assistant_response)
        except Exception as e:
            self.logger.error(f"対話履歴追加エラー: {e}")
    
    def get_current_context(self):
        """現在のコンテキストを取得（V7互換）"""
        try:
            return getattr(self.agent_state, 'collected_context', {})
        except Exception:
            return {}
    
    def update_context(self, key: str, value: Any):
        """コンテキストを更新（V7互換）"""
        try:
            if hasattr(self.agent_state, 'collected_context'):
                if not isinstance(self.agent_state.collected_context, dict):
                    self.agent_state.collected_context = {}
                self.agent_state.collected_context[key] = value
        except Exception as e:
            self.logger.error(f"コンテキスト更新エラー: {e}")
    
    def _load_config(self):
        """設定読み込み（V7互換）"""
        try:
            from .config.config_manager import ConfigManager
            return ConfigManager().load_config()
        except Exception:
            return {}
    
    # V7で使用される重要なメソッド群を追加
    async def process_request(self, request_data: Dict[str, Any]) -> str:
        """タスクループからの要求処理（V7互換）"""
        try:
            user_message = request_data.get('user_message', '')
            if user_message:
                return await self.process_user_message(user_message)
            else:
                return "処理すべきメッセージが見つかりません。"
        except Exception as e:
            self.logger.error(f"要求処理エラー: {e}")
            return f"要求処理中にエラーが発生しました: {str(e)}"
    
    def execute_action_list(self, action_list, context=None):
        """ActionList実行（V7互換・同期版）"""
        try:
            # 非同期メソッドを同期実行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._execute_action_list_async(action_list, context))
            finally:
                loop.close()
        except Exception as e:
            self.logger.error(f"ActionList実行エラー: {e}")
            return f"ActionList実行中にエラーが発生しました: {str(e)}"
    
    async def _execute_action_list_async(self, action_list, context=None):
        """ActionList非同期実行"""
        try:
            results = []
            for action_data in action_list:
                # 辞書からActionV8オブジェクトを作成
                if isinstance(action_data, dict):
                    action = ActionV8(
                        operation=action_data.get('operation', ''),
                        args=action_data.get('args', {}),
                        reasoning=action_data.get('reasoning', ''),
                        action_id=action_data.get('action_id', ''),
                        needs_human_formatting=True
                    )
                else:
                    action = action_data
                
                result = await self._execute_action_v8(action)
                results.append(result)
            
            return await self._format_final_response(results, context or "ActionList実行")
            
        except Exception as e:
            self.logger.error(f"ActionList非同期実行エラー: {e}")
            return f"ActionList実行中にエラーが発生しました: {str(e)}"
    
    # V7 ChatLoop互換性メソッド
    async def process_user_input(self, user_input: str) -> str:
        """ユーザー入力処理（V7 ChatLoop互換）"""
        return await self.process_user_message(user_input)
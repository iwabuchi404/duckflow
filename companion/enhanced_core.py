"""
EnhancedCompanionCore - Step 2: 既存システム統合版
AgentState、ConversationMemory、PromptCompilerとの統合
"""

import asyncio
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

# Enhanced v2.0システムの正しい依存関係
from companion.state.agent_state import AgentState, Step
from companion.enhanced.types import ActionType, IntentResult, TaskContext
from .memory.conversation_memory import conversation_memory
from .prompts.prompt_compiler import prompt_compiler
from .prompts.context_builder import PromptContextBuilder
# from .base.llm_client import llm_manager  # 削除: 新しいシステムに置き換え
from .ui import rich_ui
from companion.validators.llm_output import LLMOutputFormatter, MainLLMOutput
from companion.prompts.context_assembler import ContextAssembler
from .simple_approval import ApprovalMode

# 新しいLLM呼び出しシステム
from companion.prompts.prompt_context_service import PromptContextService, PromptPattern
from companion.prompts.llm_call_manager import LLMCallManager
from companion.intent_understanding.intent_analyzer_llm import IntentAnalyzerLLM


class EnhancedCompanionCore:
    """既存システム統合版CompanionCore
    
    Step 2の改善:
    - AgentStateによる統一状態管理（単一ソース・オブ・トゥルース）
    - ConversationMemoryによる自動記憶要約
    - PromptCompilerによる高度なプロンプト最適化
    - PromptContextBuilderによる構造化コンテキスト管理
    
    状態管理統一（改修後）:
    - AgentState: 唯一の書き込み可能な状態ソース
    - Legacy CompanionCore: 読み取り専用ミラー（AgentState → Legacy の一方向同期）
    - 状態の競合と二重化問題を解決
    """
    
    def __init__(self, session_id: Optional[str] = None, approval_mode: ApprovalMode = ApprovalMode.STANDARD):
        """初期化
        
        Args:
            session_id: セッションID（省略時は自動生成）
            approval_mode: 承認モード
        """
        # AgentStateを初期化
        self.state = AgentState(
            session_id=session_id or str(uuid.uuid4())
        )
        
        # 既存システムとの統合
        
        # プラン状態管理（実行阻害改善）
        self.current_plan_state = {
            "pending": False,
            "plan_content": None,
            "plan_type": None,
            "created_at": None
        }
        self.memory_manager = conversation_memory
        self.prompt_compiler = prompt_compiler
        self.context_builder = PromptContextBuilder()
        
        # 遅延初期化用のキャッシュ
        self._collaborative_planner_cache = None
        
        # Enhanced v2.0では独立したコア機能を提供
        self.approval_mode = approval_mode
        
        # ファイル操作統合
        from .file_ops import SimpleFileOps
        self.file_ops = SimpleFileOps(approval_mode=approval_mode)
        
        # Enhanced v2.0では簡易プラン管理
        self.current_plan = None
        
        # PlanTool統合（Enhanced v2.0用に簡略化）
        try:
            from .plan_tool import PlanTool
            self.plan_tool = PlanTool()
        except ImportError:
            self.logger.warning("PlanToolが利用できません。簡易プラン管理モードで動作します。")
            self.plan_tool = None
        
        # Phase 1.6: コード実行機能統合
        from .code_runner import SimpleCodeRunner
        self.code_runner = SimpleCodeRunner(approval_mode=approval_mode)
        
        # 統合モードフラグ
        self.use_enhanced_mode = True
        # LLM出力バリデータ（Phase 1）
        self.llm_output_formatter = LLMOutputFormatter()
        # Phase 2: Context Assembler（Base+Main）
        self.context_assembler = ContextAssembler()
        
        # 新しいLLM呼び出しシステム
        self.prompt_context_service = PromptContextService()
        self.llm_call_manager = LLMCallManager()
        
        # IntentAnalyzerLLMを初期化
        self.intent_analyzer = IntentAnalyzerLLM()
        
        # ログ設定
        import logging
        self.logger = logging.getLogger(__name__)
    
    def _generate_plan_unified(self, user_input: str):
        """統一プラン生成（全パスで使用、コンテキスト引き継ぎ対応）"""
        try:
            # 短期記憶からコンテキストを取得
            short_term_memory = getattr(self.state, 'short_term_memory', {})
            last_read_file = short_term_memory.get('last_read_file')

            # プラン生成のためのプロンプトを動的に構築
            if last_read_file:
                plan_generation_prompt = f"""
ユーザーの要求: {user_input}

関連コンテキスト:
直前にファイル「{last_read_file.get('path')}」を読み込みました。
そのファイルの要約は以下の通りです。
---
{last_read_file.get('summary', 'なし')}
---

上記のコンテキストを完全に踏まえた上で、ユーザーの要求に対する具体的な実装プランを生成してください。
"""
                rationale = f"ユーザー要求（{user_input[:50]}...）とファイルコンテキスト（{last_read_file.get('path')}）に基づく"
            else:
                plan_generation_prompt = user_input
                rationale = f"ユーザー要求: {user_input[:100]}..."

            # プラン作成に必要な引数を準備
            from .plan_tool import MessageRef
            sources = [MessageRef(message_id="user_request", timestamp=datetime.now().isoformat())]
            tags = ["user_request", "auto_generated", "context_aware"]

            # プラン作成（PlanToolが利用可能な場合のみ）
            if self.plan_tool:
                plan_id = self.plan_tool.propose(plan_generation_prompt, sources, rationale, tags)

                # ActionSpec保証（ActionSpecの生成は元の入力で行う）
                self._ensure_action_specs(plan_id, user_input)

                # 承認要求
                from .plan_tool import SpecSelection
                self.plan_tool.request_approval(plan_id, SpecSelection(all=True))
            else:
                # PlanToolが利用できない場合は簡易プラン管理
                plan_id = str(uuid.uuid4())
                self.current_plan = {
                    'id': plan_id,
                    'content': plan_generation_prompt,
                    'created_at': datetime.now().isoformat()
                }
                self.logger.info(f"簡易プラン作成: {plan_id}")

            return plan_id

        except Exception as e:
            self.logger.error(f"統一プラン生成エラー: {e}", exc_info=True)
            raise
    
    def _ensure_action_specs(self, plan_id: str, content: str):
        """ActionSpec保証（PlanToolが利用可能な場合のみ）"""
        if not self.plan_tool:
            self.logger.warning("PlanToolが利用できないため、ActionSpec設定をスキップします")
            return
            
        try:
            from .collaborative_planner import ActionSpec
            
            # 動的なファイルパスと説明の生成
            file_path = self._generate_dynamic_file_path(content)
            description = self._generate_dynamic_description(content)
            
            action_spec = ActionSpec(
                kind='implement',
                path=file_path,
                description=description,
                optional=False
            )
            
            # ActionSpec設定
            self.plan_tool.set_action_specs(plan_id, [action_spec])
        except Exception as e:
            self.logger.error(f"ActionSpec設定エラー: {e}")
            # エラー時はログ出力のみ（システム停止は回避）
    
    def _generate_dynamic_file_path(self, content: str) -> str:
        """動的なファイルパスを生成"""
        if "計画" in content or "プラン" in content:
            return "plan.md"
        elif "実装" in content:
            return "implementation.md"
        elif "作成" in content:
            return "implementation.md"
        elif "設計" in content or "アーキテクチャ" in content:
            return "design.md"
        else:
            return "task.md"
    
    def _generate_dynamic_description(self, content: str) -> str:
        """動的な説明を生成"""
        if "実装" in content:
            return f"ユーザー要求に基づく実装: {content[:100]}..."
        elif "計画" in content:
            return f"ユーザー要求に基づく計画作成: {content[:100]}..."
        elif "設計" in content:
            return f"ユーザー要求に基づく設計: {content[:100]}..."
        else:
            return f"ユーザー要求の処理: {content[:100]}..."
    
    # 意図検出処理は削除 - IntentAnalyzerLLMを使用するため
    
    # 意図検出関連メソッドは削除 - IntentAnalyzerLLMを使用するため
    # _analyze_intent_enhanced, _determine_action_type, _analyze_intent_simple, _build_main_llm_output
    
    async def analyze_intent_only(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """IntentAnalyzerLLMを使用した意図理解"""
        try:
            # IntentAnalyzerLLMで意図理解を実行
            intent_result = await self.intent_analyzer.analyze(user_message, self.state, context)
            
            # 結果をEnhancedCompanionCore形式に変換
            return {
                "action_type": intent_result.action_type,
                "understanding_result": intent_result,
                "message": user_message,
                "enhanced_mode": True,
                "session_id": self.state.session_id,
                "conversation_count": len(self.state.conversation_history),
                "route_type": "intent_analyzer_llm",
                "risk_level": "low",
                "prerequisite_status": "ready"
            }
        except Exception as e:
            self.logger.error(f"IntentAnalyzerLLM意図理解エラー: {e}")
            # フォールバック: 簡易意図理解
            return await self._analyze_intent_fallback(user_message)
    
    async def _analyze_intent_fallback(self, user_message: str) -> Dict[str, Any]:
        """フォールバック用の簡易意図理解"""
        # LLMによる意図理解を試行
        try:
            action_type = await self._determine_action_type_llm(user_message)
        except Exception as e:
            self.logger.warning(f"LLM意図理解エラー: {e}, フォールバックキーワード判定を使用")
            # 基本的なキーワードベースの判定（緊急時のみ）
            message_lower = user_message.lower()
            
            if any(kw in message_lower for kw in ["読", "見て", "確認", "内容", "ファイル", "file", "読み"]):
                action_type = ActionType.FILE_OPERATION
            elif any(kw in message_lower for kw in ["作成", "書", "出力", "生成", "create", "write"]):
                action_type = ActionType.FILE_OPERATION
            elif any(kw in message_lower for kw in ["実行", "run", "テスト", "test"]):
                action_type = ActionType.CODE_EXECUTION
            elif any(kw in message_lower for kw in ["プラン", "計画", "設計", "plan"]):
                action_type = ActionType.PLAN_GENERATION
            else:
                action_type = ActionType.DIRECT_RESPONSE
        
        return {
            "action_type": action_type,
            "understanding_result": None,
            "message": user_message,
            "enhanced_mode": False,
            "session_id": self.state.session_id,
            "conversation_count": len(self.state.conversation_history),
            "route_type": "fallback_keyword",
            "risk_level": "medium",
            "prerequisite_status": "ready"
        }
    
    async def process_with_intent_result(self, intent_result: Dict[str, Any]) -> str:
        """IntentAnalyzerLLMによる意図理解結果を処理"""
        try:
            # 意図分析結果の構造を確認
            self.logger.info(f"意図分析結果の構造: {type(intent_result)}")
            self.logger.info(f"意図分析結果の内容: {intent_result}")
            
            # IntentAnalyzerLLMの結果を正しく取り出す
            if hasattr(intent_result, 'action_type'):
                # IntentAnalysisResultオブジェクトの場合
                action_type = intent_result.action_type
                file_target = intent_result.file_target
                user_message = getattr(intent_result, 'user_input', '')
                confidence = intent_result.confidence
                reasoning = intent_result.reasoning
            elif isinstance(intent_result, dict):
                # 辞書形式の場合
                action_type = intent_result.get("action_type")
                file_target = intent_result.get("file_target")
                user_message = intent_result.get("message", "")
                confidence = intent_result.get("confidence", 0.0)
                reasoning = intent_result.get("reasoning", "")
            else:
                # 不明な形式の場合
                self.logger.error(f"不明な意図分析結果の形式: {type(intent_result)}")
                return "申し訳ありません。意図分析結果の形式が不明です。"

            # ユーザーメッセージが空の場合は、元のメッセージを使用
            if not user_message and hasattr(intent_result, 'user_input'):
                user_message = intent_result.user_input

            self._show_enhanced_thinking_process(user_message)

            # アクション実行（型安全）
            self.logger.info(f"アクションタイプ: {action_type}")
            self.logger.info(f"ActionType.SUMMARY_GENERATION: {ActionType.SUMMARY_GENERATION}")
            self.logger.info(f"比較結果: action_type == ActionType.SUMMARY_GENERATION: {action_type == ActionType.SUMMARY_GENERATION}")
            
            # ActionTypeの値を文字列として取得して比較
            action_type_value = action_type.value if hasattr(action_type, 'value') else str(action_type)
            self.logger.info(f"アクションタイプの値: {action_type_value}")
            
            if action_type_value == "direct_response":
                self.logger.info("DIRECT_RESPONSE処理を実行")
                result = await self._generate_enhanced_response(user_message, file_target)
            elif action_type_value == "file_operation":
                self.logger.info("FILE_OPERATION処理を実行")
                result = await self._handle_enhanced_file_operation(user_message, file_target)
            elif action_type_value == "code_execution":
                self.logger.info("CODE_EXECUTION処理を実行")
                result = await self._handle_enhanced_code_execution(user_message, file_target)
            elif action_type_value == "plan_generation":
                self.logger.info("PLAN_GENERATION処理を実行")
                result = await self._handle_enhanced_plan_generation(user_message, file_target)
            elif action_type_value == "summary_generation":
                self.logger.info("SUMMARY_GENERATION処理を実行")
                # summary_generation意図に対する具体的な処理を実装
                result = await self._handle_enhanced_summary_generation(user_message, file_target)
            elif action_type_value == "content_extraction":
                self.logger.info("CONTENT_EXTRACTION処理を実行")
                result = await self._handle_enhanced_content_extraction(user_message, file_target)
            else:
                # 不明なアクションタイプの場合
                self.logger.warning(f"不明なアクションタイプ: {action_type_value}")
                result = await self._handle_enhanced_multi_step_task(user_message, file_target)
            
            if self._looks_like_plan(result):
                self.set_plan_state(result, "execution_plan")
            
            self.state.add_message("assistant", result)
            self._sync_to_legacy_readonly()
            
            return result
        except Exception as e:
            self.logger.error(f"Enhanced処理エラー: {e}")
            return f"申し訳ありません。処理中にエラーが発生しました: {str(e)}"
    
    def _build_recent_conversation_context(self) -> str:
        """直近の会話履歴から重要なコンテキストを構築"""
        try:
            if not self.state.conversation_history:
                return ""
            
            recent_messages = self.state.conversation_history[-3:]
            context_parts = []
            
            for msg in recent_messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:150]
                if content:
                    context_parts.append(f"{role}: {content}")
            
            return "直近の会話:\n" + "\n".join(context_parts) if context_parts else ""
            
        except Exception as e:
            self.logger.warning(f"会話コンテキスト構築エラー: {e}")
            return ""
    
    def _build_session_summary(self) -> str:
        """セッション全体の要約を構築"""
        try:
            summary_parts = []
            if hasattr(self.state, 'created_at'):
                summary_parts.append(f"セッション開始: {self.state.created_at.strftime('%H:%M:%S')}")
            if self.state.conversation_history:
                summary_parts.append(f"会話数: {len(self.state.conversation_history)}件")
            if hasattr(self.state, 'step'):
                summary_parts.append(f"現在のステップ: {getattr(self.state.step, 'value', str(self.state.step))}")
            
            return "セッション概要:\n" + "\n".join(summary_parts) if summary_parts else ""
            
        except Exception as e:
            self.logger.warning(f"セッション要約構築エラー: {e}")
            return ""
    
    def _record_file_operation(self, operation_type: str, file_path: str, content_summary: str = ""):
        """ファイル操作履歴を記録"""
        try:
            if 'file_operations' not in self.state.short_term_memory:
                self.state.short_term_memory['file_operations'] = []
            
            operation_record = {
                'type': operation_type,
                'path': file_path,
                'timestamp': datetime.now().isoformat(),
                'summary': content_summary
            }
            
            self.state.short_term_memory['file_operations'].append(operation_record)
            
            if len(self.state.short_term_memory['file_operations']) > 10:
                self.state.short_term_memory['file_operations'] = self.state.short_term_memory['file_operations'][-10:]
                
        except Exception as e:
            self.logger.warning(f"ファイル操作履歴記録エラー: {e}")
    
    async def _collect_file_context(self) -> Dict[str, Any]:
        """ファイルコンテキストを収集（直近の操作履歴を含む）"""
        try:
            file_operations = []
            if file_ops := getattr(self.state, 'short_term_memory', {}).get('file_operations', []):
                for op in file_ops[-5:]:
                    if isinstance(op, dict):
                        file_operations.append(f"{op.get('type', '?')}: {op.get('path', '?')}")
            
            return {"file_operations_history": file_operations}
            
        except Exception as e:
            self.logger.warning(f"ファイルコンテキスト収集エラー: {e}")
            return {}
    
    def set_plan_state(self, plan_content: str, plan_type: str = "execution_plan"):
        """プラン状態を設定（PlanTool統合版）"""
        try:
            if self.plan_tool:
                plan_id = self.plan_tool.propose(
                    content=plan_content,
                    sources=[MessageRef(message_id=str(uuid.uuid4()), timestamp=datetime.now().isoformat())],
                    rationale=f"AI生成プラン: {plan_type}",
                    tags=[plan_type, "ai_generated"]
                )
                self.current_plan_state = {
                    "pending": True,
                    "plan_content": plan_content,
                    "plan_type": plan_type,
                    "created_at": datetime.now(),
                    "plan_id": plan_id
                }
            else:
                # PlanToolが利用できない場合は簡易プラン管理
                plan_id = str(uuid.uuid4())
                self.current_plan_state = {
                    "pending": True,
                    "plan_content": plan_content,
                    "plan_type": plan_type,
                    "created_at": datetime.now(),
                    "plan_id": plan_id
                }
                self.logger.info(f"簡易プラン状態設定: {plan_id}")
        except Exception as e:
            self.logger.error(f"プラン状態設定エラー: {e}")
            self.current_plan_state = {"pending": True, "plan_content": plan_content, "plan_type": plan_type, "created_at": datetime.now()}
        
        self.state.short_term_memory["current_plan_state"] = self.current_plan_state
        self._record_file_operation("plan_creation", f"plan_{plan_type}", plan_content[:100])
    
    def get_plan_state(self) -> Dict[str, Any]:
        """現在のプラン状態を取得"""
        return self.current_plan_state
    
    def clear_plan_state(self):
        """プラン状態をクリア"""
        if self.plan_tool:
            self.plan_tool.clear_current()
        self.current_plan_state = {"pending": False, "plan_content": None, "plan_type": None, "created_at": None}
        if "current_plan_state" in self.state.short_term_memory:
            del self.state.short_term_memory["current_plan_state"]

    def _looks_like_plan(self, text: str) -> bool:
        """応答テキストが「実装プラン/ロードマップ」的かを簡易判定"""
        if not text or len(text) < 50: return False
        import re
        indicators = ["実装プラン", "ロードマップ", "フェーズ", "次のステップ", "アクションアイテム", "タスク実行計画"]
        return sum(1 for kw in indicators if kw in text) >= 2 and bool(re.search(r"\n\s*\d+\|\|\n\s*-\s", text))

    def _summarize_plan_for_context(self, text: str) -> str:
        """PlanContext 用の軽い要約"""
        lines = text.splitlines()
        header = next((l for l in lines if l.strip().startswith("#")), "")
        bullets = [l.strip() for l in lines if l.strip().startswith(("- ", "1."))][:5]
        return "\n".join([header] + bullets)
    
    async def _generate_enhanced_response(self, user_message: str, file_target: Optional[str] = None) -> str:
        """拡張版直接応答生成（新しいLLM呼び出しシステム使用）"""
        try:
            rich_ui.print_message("💬 拡張コンテキストで応答を生成中...", "info")
            
            # 新しいLLM呼び出しシステムを使用
            # BaseMainSpecializedパターンでプロンプトを合成
            full_system_prompt = self.prompt_context_service.compose(
                PromptPattern.BASE_MAIN_SPECIALIZED, 
                self.state
            )
            
            # LLMCallManagerで統一呼び出し
            response = await self.llm_call_manager.call(
                mode="conversation",
                input_text=user_message,
                system_prompt=full_system_prompt,
                pattern=PromptPattern.BASE_MAIN_SPECIALIZED
            )
            
            rich_ui.print_message("✨ 拡張応答を生成しました！", "success")
            return response
            
        except Exception as e:
            self.logger.error(f"拡張応答生成エラー: {e}")
            # Enhanced v2.0独立の直接応答生成
            return await self._generate_enhanced_response_fallback(user_message)
    
    async def _handle_enhanced_file_operation(self, user_message: str, file_target: Optional[str] = None) -> str:
        """拡張版ファイル操作処理"""
        try:
            rich_ui.print_message("📁 ファイル操作タスクとして処理中...", "info")
            
            # ファイルパスの抽出（IntentAnalyzerLLMの結果を優先）
            file_path = file_target if file_target else await self._extract_file_path_from_llm(user_message)
            
            # LLMによるファイル操作タイプ判定
            operation_type = await self._determine_file_operation_type(user_message, file_path)
            
            # ファイル操作タイプに基づく処理
            if operation_type == "read":
                return await self._handle_file_read_operation(user_message, file_path)
            elif operation_type == "write":
                if file_path:
                    return await self._handle_file_write_operation(user_message)
                else:
                    # ファイルパスが不明な場合、ユーザーに確認
                    return "ファイルを作成したいと思いますが、ファイル名が特定できませんでした。\n\n具体的なファイル名を教えてください（例: 'game_doc.md' や 'README.txt' など）。"
            elif operation_type == "list":
                return await self._handle_file_list_operation(user_message)
            elif operation_type == "plan":
                plan = self._generate_plan_unified(user_message)
                return plan
            else:
                # その他の場合は通常の応答生成
                return await self._generate_enhanced_response(user_message, file_path)
                
        except Exception as e:
            self.logger.error(f"拡張ファイル操作エラー: {e}")
            # Enhanced v2.0独立のファイル操作処理
            return await self._handle_file_operation_fallback(user_message)
    
    async def _handle_file_read_operation(self, user_message: str, file_target: Optional[str] = None) -> str:
        """ファイル読み込み操作を処理"""
        try:
            # ファイル名の取得（IntentAnalyzerLLMの結果を優先）
            file_path = file_target if file_target else await self._extract_file_path_from_llm(user_message)
            
            rich_ui.print_message(f"📖 ファイル読み込み: {file_path}", "info")
            content = self.file_ops.read_file(file_path)
            summary = await self._generate_file_summary(file_path, content)

            self.state.short_term_memory["last_read_file"] = {
                "path": file_path,
                "summary": summary,
                "length": len(content),
                "timestamp": datetime.now().isoformat()
            }
            self._record_file_operation("read", file_path, summary)
            self.state.add_message("assistant", f"ファイル '{file_path}' を読み込みました")
            
            # 処理完了のログ出力を追加
            self.logger.info(f"ファイル読み込み処理完了: {file_path}, 内容長: {len(content)}, 要約長: {len(summary)}")
            
            return f"📄 ファイル '{file_path}' の内容:\n\n{summary}\n\n--- 完全な内容 ---\n{content}"
        except Exception as e:
            return f"ファイル '{file_path}' の読み込みに失敗しました: {str(e)}"
    
    async def _extract_file_path_from_llm(self, user_message: str) -> str:
        """LLMの出力からファイルパスを抽出（新しいLLM呼び出しシステム使用）"""
        try:
            # 新しいLLM呼び出しシステムを使用
            # BaseSpecializedパターンで軽量なプロンプトを合成
            extraction_system_prompt = self.prompt_context_service.compose(
                PromptPattern.BASE_SPECIALIZED, 
                self.state
            )
            
            # ファイル抽出用のプロンプトを構築
            extraction_prompt = f"""以下のユーザーメッセージから、操作対象のファイル名を正確に抽出してください。

ユーザーメッセージ: {user_message}

以下のJSON形式で回答してください:
{{
    "file_target": "ファイル名（例: game_doc.md）",
    "action": "実行するアクション（例: read_file）",
    "reasoning": "なぜこのファイル名を抽出したかの理由",
    "confidence": 0.95
}}

ファイル名のみを抽出し、余分な文字は含めないでください。
拡張子が不明な場合は、一般的な拡張子を推測してください。"""

            # LLMCallManagerで統一呼び出し
            response = await self.llm_call_manager.call(
                mode="extract",
                input_text=extraction_prompt,
                system_prompt=extraction_system_prompt,
                pattern=PromptPattern.BASE_SPECIALIZED
            )
            
            # JSONレスポンスをパース
            import json
            try:
                # デバッグ用：LLM応答をログ出力
                self.logger.info(f"LLM応答: {response}")
                
                # JSON部分を抽出
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    self.logger.info(f"抽出されたJSON文字列: {json_str}")
                    
                    parsed = json.loads(json_str)
                    file_target = parsed.get('file_target', '')
                    
                    if file_target:
                        self.logger.info(f"LLM抽出成功: {file_target} (信頼度: {parsed.get('confidence', 'unknown')})")
                        return file_target
                else:
                    self.logger.warning(f"JSON文字列が見つかりません: response={response}")
                    
            except Exception as e:
                self.logger.warning(f"JSONパースエラー: {e}, response={response}")
            
            # フォールバック: 既存のCollaborativePlanner機能を使用
            return self._extract_file_path_from_message(user_message) or self._fallback_file_extraction(user_message)
            
        except Exception as e:
            self.logger.error(f"LLMファイル名抽出エラー: {e}")
            # フォールバック: 既存のCollaborativePlanner機能を使用
            return self._extract_file_path_from_message(user_message) or self._fallback_file_extraction(user_message)
    
    def _fallback_file_extraction(self, user_message: str) -> str:
        """フォールバック用のファイル名抽出（最適化版）"""
        import re
        
        # .md, .txt, .py などの拡張子を持つファイル名を探す
        file_extensions = r'\.(md|txt|py|js|html|css|json|yaml|yml|xml|csv|log)$'
        file_match = re.search(r'(\S+' + file_extensions + r')', user_message)
        if file_match:
            return file_match.group(1)
        
        # 一般的なファイル名パターンを探す
        words = user_message.split()
        for word in words:
            if re.search(r'\.\w+$', word):
                return word
        
        # 最後の手段：簡易抽出のみ使用（CollaborativePlannerは使用しない）
        # fallback_result = self._extract_file_path_from_message(user_message)
        # if fallback_result:
        #     return fallback_result
        
        # 最終フォールバック：最初の単語
        return words[0] if words else "unknown_file"
    
    async def _handle_file_write_operation(self, user_message: str) -> str:
        """ファイル書き込み操作を処理（新しいLLM呼び出しシステム使用）"""
        try:
            file_path = await self._extract_file_path_from_llm(user_message)
            
            if not file_path:
                return "ファイル名を特定できませんでした。具体的なファイル名を指定してください。"
            
            # 新しいLLM呼び出しシステムを使用
            # BaseMainパターンでプロンプトを合成
            content_system_prompt = self.prompt_context_service.compose(
                PromptPattern.BASE_MAIN, 
                self.state
            )
            
            # ファイル内容生成用のプロンプトを構築
            content_prompt = f"""以下の要求に基づいて、ファイル '{file_path}' の内容を生成してください。

要求: {user_message}

ファイル名: {file_path}

適切な内容を生成し、ファイルの種類に応じた形式で出力してください。"""

            # LLMCallManagerで統一呼び出し
            content = await self.llm_call_manager.call(
                mode="generate_content",
                input_text=content_prompt,
                system_prompt=content_system_prompt,
                pattern=PromptPattern.BASE_MAIN
            )
            
            # ファイルに書き込み
            try:
                self.file_ops.write_file(file_path, content)
                
                # 状態を更新
                self.state.short_term_memory["last_written_file"] = {
                    "path": file_path,
                    "length": len(content),
                    "timestamp": datetime.now().isoformat()
                }
                self._record_file_operation("write", file_path, content[:100])
                self.state.add_message("assistant", f"ファイル '{file_path}' を作成・更新しました")
                
                return f"✅ ファイル '{file_path}' を作成・更新しました\n\n📄 内容:\n{content}"
                
            except Exception as e:
                return f"❌ ファイル書き込みエラー: {str(e)}"
                
        except Exception as e:
            self.logger.error(f"ファイル書き込み操作エラー: {e}")
            return f"ファイル書き込み処理中にエラーが発生しました: {str(e)}"
    
    async def _handle_file_list_operation(self, user_message: str) -> str:
        """ファイル一覧操作を処理"""
        try:
            import os
            from pathlib import Path
            
            # 現在のディレクトリを取得
            current_dir = Path.cwd()
            
            # ファイルとディレクトリを取得
            items = []
            for item in current_dir.iterdir():
                if item.is_file():
                    # ファイルサイズを取得
                    try:
                        size = item.stat().st_size
                        size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB"
                    except:
                        size_str = "unknown"
                    items.append(f"📄 {item.name} ({size_str})")
                elif item.is_dir():
                    items.append(f"📁 {item.name}/")
            
            # ソート
            items.sort()
            
            # 結果を整形
            if items:
                result = f"📂 現在のディレクトリ: {current_dir}\n\n"
                result += "ファイルとディレクトリ:\n"
                result += "\n".join(items)
                result += f"\n\n合計: {len(items)} 項目"
            else:
                result = f"📂 現在のディレクトリ: {current_dir}\n\nディレクトリは空です。"
            
            # 状態を更新
            self.state.short_term_memory["last_directory_listing"] = {
                "path": str(current_dir),
                "count": len(items),
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"ファイル一覧操作エラー: {e}")
            return f"ファイル一覧の取得に失敗しました: {str(e)}"

    async def _generate_file_summary(self, file_path: str, content: str) -> str:
        """ファイル内容の要約を生成（新しいLLM呼び出しシステム使用）"""
        if len(content) < 200: return "(内容が短いため要約省略)"
        try:
            # 新しいLLM呼び出しシステムを使用
            # BaseSpecializedパターンで軽量なプロンプトを合成
            summary_system_prompt = self.prompt_context_service.compose(
                PromptPattern.BASE_SPECIALIZED, 
                self.state
            )
            
            # 要約生成用のプロンプトを構築
            summary_prompt = f"以下のファイル内容を3-5行で簡潔に要約してください。\n\nファイル: {file_path}\n\n内容:{content[:3000]}"
            
            # LLMCallManagerで統一呼び出し
            summary = await self.llm_call_manager.call(
                mode="summarize",
                input_text=summary_prompt,
                system_prompt=summary_system_prompt,
                pattern=PromptPattern.BASE_SPECIALIZED
            )
            
            # 要約生成完了のログ出力を追加
            self.logger.info(f"ファイル要約生成完了: {file_path}, 要約長: {len(summary)}")
            
            # 要約の前処理を追加
            if summary and len(summary.strip()) > 0:
                processed_summary = summary.strip()
            else:
                processed_summary = "(要約の生成に失敗しました)"
            
            self.logger.info(f"要約処理完了: {file_path}, 最終要約長: {len(processed_summary)}")
            
            return f"📋 要約:\n{processed_summary}"
        except Exception as e:
            self.logger.warning(f"ファイル要約生成エラー: {e}")
            return "(要約の生成に失敗しました)"
    
    def get_agent_state(self) -> AgentState:
        return self.state
    
    def get_session_summary(self) -> Dict[str, Any]:
        return {
            **self.state.get_context_summary(),
            "memory_status": self.state.get_memory_status(),
            "enhanced_mode": self.use_enhanced_mode
        }

    def toggle_enhanced_mode(self, enabled: bool = None) -> bool:
        if enabled is None:
            self.use_enhanced_mode = not self.use_enhanced_mode
        else:
            self.use_enhanced_mode = enabled
        rich_ui.print_message(f"🔧 拡張モード: {'有効' if self.use_enhanced_mode else '無効'}", "info")
        return self.use_enhanced_mode

    def _sync_to_legacy_readonly(self):
        """AgentState → Legacy CompanionCore への読み取り専用同期"""
        try:
            legacy_history = []
            user_msg = None
            for msg in self.state.conversation_history:
                if msg.role == "user":
                    user_msg = msg.content
                elif msg.role == "assistant" and user_msg is not None:
                    legacy_history.append({"user": user_msg, "assistant": msg.content, "timestamp": msg.timestamp})
                    user_msg = None
            
            # Enhanced v2.0では独立した会話履歴管理
            self.logger.debug("Enhanced v2.0では独立した会話履歴を使用します")
        except Exception as e:
            self.logger.warning(f"AgentState → Legacy 同期エラー: {e}")

    def _show_enhanced_thinking_process(self, message: str) -> None:
        """Enhanced v2.0独立の思考過程表示"""
        rich_ui.print_message("🤔 Enhanced v2.0でメッセージを分析中...", "info")
        import time
        time.sleep(0.3)
        if any(keyword in message.lower() for keyword in ["ファイル", "file", "作成", "create", "読み", "read"]):
            rich_ui.print_message("📁 ファイル操作が必要そうですね...", "info")
            time.sleep(0.3)
        elif any(keyword in message.lower() for keyword in ["実行", "run", "テスト", "test"]):
            rich_ui.print_message("⚡ コードの実行が必要そうですね...", "info")
            time.sleep(0.3)
        rich_ui.print_message("💭 Enhanced v2.0で処理方法を決定中...", "info")
        time.sleep(0.2)
    
    async def _generate_enhanced_response_fallback(self, user_message: str) -> str:
        """Enhanced v2.0独立の直接応答生成（フォールバック）"""
        try:
            # 簡易応答生成
            if "こんにちは" in user_message or "hello" in user_message.lower():
                return "こんにちは！Enhanced v2.0システムです。何かお手伝いできることはありますか？"
            elif "ありがとう" in user_message or "thank" in user_message.lower():
                return "どういたしまして！他に何かご質問があればお聞かせください。"
            else:
                return f"申し訳ありません。現在LLMが利用できないため、詳細な回答ができません。\n\nあなたのメッセージ: {user_message}\n\nシステム状態: Enhanced v2.0 独立モード"
        except Exception as e:
            return f"エラーが発生しました: {str(e)}"
    
    async def _handle_file_operation_fallback(self, user_message: str) -> str:
        """Enhanced v2.0独立のファイル操作処理（型安全）"""
        try:
            # ファイルパスの抽出
            file_path = self._extract_file_path_from_message(user_message)
            if not file_path:
                return "ファイル名が特定できませんでした。具体的なファイル名を教えてください。"
            
            # ファイル操作の実行
            operation = self._determine_file_operation(user_message)
            return await self._execute_file_operation(operation, file_path, user_message)
            
        except Exception as e:
            self.logger.error(f"ファイル操作エラー: {e}")
            return f"ファイル操作中にエラーが発生しました: {str(e)}"
    
    async def _determine_file_operation_type(self, user_message: str, file_path: Optional[str] = None) -> str:
        """LLMによるファイル操作タイプ判定"""
        try:
            # 新しいLLM呼び出しシステムを使用
            # BaseSpecializedパターンで軽量なプロンプトを合成
            operation_system_prompt = self.prompt_context_service.compose(
                PromptPattern.BASE_SPECIALIZED, 
                self.state
            )
            
            # ファイル操作タイプ判定用のプロンプトを構築
            operation_prompt = f"""以下のユーザーメッセージから、実行すべきファイル操作のタイプを判定してください。

ユーザーメッセージ: {user_message}
ファイルパス: {file_path if file_path else "未指定"}

以下のJSON形式で回答してください:
{{
    "operation_type": "read|write|list|plan|other",
    "confidence": 0.95,
    "reasoning": "なぜこの操作タイプを判定したかの理由"
}}

操作タイプの説明:
- read: ファイルの読み込み、内容確認、表示
- write: ファイルの作成、書き込み、更新
- list: ファイル一覧、ディレクトリ表示
- plan: プラン生成、計画作成
- other: 上記以外の操作"""

            # LLMCallManagerで統一呼び出し
            response = await self.llm_call_manager.call(
                mode="extract",
                input_text=operation_prompt,
                system_prompt=operation_system_prompt,
                pattern=PromptPattern.BASE_SPECIALIZED
            )
            
            # JSONレスポンスをパース
            import json
            try:
                # JSON部分を抽出
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    parsed = json.loads(json_str)
                    operation_type = parsed.get('operation_type', 'other')
                    
                    self.logger.info(f"LLM操作タイプ判定成功: {operation_type} (信頼度: {parsed.get('confidence', 'unknown')})")
                    return operation_type
                else:
                    self.logger.warning(f"JSON文字列が見つかりません: response={response}")
                    
            except Exception as e:
                self.logger.warning(f"JSONパースエラー: {e}, response={response}")
            
            # フォールバック: 簡易キーワード判定
            return self._fallback_operation_type_determination(user_message)
            
        except Exception as e:
            self.logger.error(f"LLM操作タイプ判定エラー: {e}")
            # フォールバック: 簡易キーワード判定
            return self._fallback_operation_type_determination(user_message)
    
    def _fallback_operation_type_determination(self, user_message: str) -> str:
        """フォールバック用の簡易操作タイプ判定"""
        message_lower = user_message.lower()
        
        # 簡易キーワード判定（フォールバック用）
        if any(kw in message_lower for kw in ["読", "確認", "内容", "見て", "把握", "表示"]):
            return "read"
        elif any(kw in message_lower for kw in ["書", "作成", "作成して", "作って", "出力", "生成", "更新"]):
            return "write"
        elif any(kw in message_lower for kw in ["一覧", "ls", "dir", "表示"]):
            return "list"
        elif any(kw in message_lower for kw in ["プラン", "計画", "設計"]):
            return "plan"
        else:
            return "other"
    
    async def _determine_action_type_llm(self, user_message: str) -> ActionType:
        """LLMによるアクションタイプ判定"""
        try:
            # 新しいLLM呼び出しシステムを使用
            # BaseSpecializedパターンで軽量なプロンプトを合成
            action_system_prompt = self.prompt_context_service.compose(
                PromptPattern.BASE_SPECIALIZED, 
                self.state
            )
            
            # アクションタイプ判定用のプロンプトを構築
            action_prompt = f"""以下のユーザーメッセージから、実行すべきアクションのタイプを判定してください。

ユーザーメッセージ: {user_message}

以下のJSON形式で回答してください:
{{
    "action_type": "file_operation|code_execution|plan_generation|direct_response",
    "confidence": 0.95,
    "reasoning": "なぜこのアクションタイプを判定したかの理由"
}}

アクションタイプの説明:
- file_operation: ファイルの読み込み、書き込み、一覧表示、削除など
- code_execution: コードの実行、テスト、デバッグなど
- plan_generation: プラン生成、計画作成、設計など
- direct_response: 上記以外の一般的な応答"""

            # LLMCallManagerで統一呼び出し
            response = await self.llm_call_manager.call(
                mode="extract",
                input_text=action_prompt,
                system_prompt=action_system_prompt,
                pattern=PromptPattern.BASE_SPECIALIZED
            )
            
            # JSONレスポンスをパース
            import json
            try:
                # JSON部分を抽出
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    parsed = json.loads(json_str)
                    action_type_str = parsed.get('action_type', 'direct_response')
                    
                    # ActionTypeに変換
                    if action_type_str == 'file_operation':
                        return ActionType.FILE_OPERATION
                    elif action_type_str == 'code_execution':
                        return ActionType.CODE_EXECUTION
                    elif action_type_str == 'plan_generation':
                        return ActionType.PLAN_GENERATION
                    else:
                        return ActionType.DIRECT_RESPONSE
                    
                else:
                    self.logger.warning(f"JSON文字列が見つかりません: response={response}")
                    
            except Exception as e:
                self.logger.warning(f"JSONパースエラー: {e}, response={response}")
            
            # フォールバック: デフォルト値
            return ActionType.DIRECT_RESPONSE
            
        except Exception as e:
            self.logger.error(f"LLMアクションタイプ判定エラー: {e}")
            # フォールバック: デフォルト値
            return ActionType.DIRECT_RESPONSE
    
    def _extract_file_path_from_message(self, user_message: str) -> Optional[str]:
        """メッセージからファイルパスを抽出（最適化版）"""
        try:
            # まず簡易抽出を試行（高速）
            simple_result = self._simple_file_extraction(user_message)
            if simple_result:
                return simple_result
            
            # 簡易抽出で見つからない場合のみCollaborativePlannerを使用（遅延初期化）
            if self._collaborative_planner_cache is None:
                try:
                    from .collaborative_planner import CollaborativePlanner
                    self._collaborative_planner_cache = CollaborativePlanner()
                except Exception as e:
                    self.logger.warning(f"CollaborativePlanner初期化エラー: {e}")
                    return None
            
            if self._collaborative_planner_cache:
                return self._collaborative_planner_cache._extract_file_path(user_message)
            else:
                return None
                
        except Exception as e:
            self.logger.warning(f"ファイルパス抽出エラー: {e}、簡易抽出を使用")
            return self._simple_file_extraction(user_message)
    
    def _simple_file_extraction(self, user_message: str) -> Optional[str]:
        """簡易ファイル抽出（強化版）"""
        import re
        
        # 一般的なファイルパスパターン（高速処理）
        patterns = [
            r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']',  # クォート内のファイル
            r'([a-zA-Z0-9_/\\.-]+\.[a-zA-Z0-9]+)',  # 拡張子付きファイル
            r'([a-zA-Z0-9_/\\.-]+\.md)',  # Markdownファイル
            r'([a-zA-Z0-9_/\\.-]+\.txt)',  # テキストファイル
            r'([a-zA-Z0-9_/\\.-]+\.py)',   # Pythonファイル
        ]
        
        for pattern in patterns:
            match = re.search(pattern, user_message)
            if match:
                return match.group(1)
        
        # 特定のファイル名のキーワード（フォールバック）
        if "game_doc.md" in user_message:
            return "game_doc.md"
        elif "readme" in user_message.lower():
            return "README.md"
        
        return None
    
    async def _determine_file_operation(self, user_message: str) -> str:
        """LLMによるファイル操作の種類を判定"""
        try:
            # LLMによる判定を試行
            return await self._determine_file_operation_type(user_message, None)
        except Exception as e:
            self.logger.warning(f"LLMファイル操作判定エラー: {e}, フォールバックキーワード判定を使用")
            # フォールバック: 簡易キーワード判定
            message_lower = user_message.lower()
            
            if any(kw in message_lower for kw in ["読", "見て", "確認", "内容", "読み"]):
                return "read"
            elif any(kw in message_lower for kw in ["作成", "書", "出力", "生成"]):
                return "write"
            elif any(kw in message_lower for kw in ["削除", "消去"]):
                return "delete"
            elif any(kw in message_lower for kw in ["一覧", "ls", "dir"]):
                return "list"
            else:
                return "read"  # デフォルトは読み取り
    
    async def _execute_file_operation(self, operation: str, file_path: str, user_message: str) -> str:
        """ファイル操作を実行"""
        try:
            if operation == "read":
                content = self.file_ops.read_file(file_path)
                preview = content if len(content) < 1000 else content[:1000] + '...'
                return f"📄 {file_path} の内容:\n\n{preview}"
            elif operation == "write":
                return f"📝 {file_path} への書き込み機能は現在実装中です。"
            elif operation == "delete":
                return f"🗑️ {file_path} の削除機能は現在実装中です。"
            elif operation == "list":
                return f"📋 ディレクトリ一覧機能は現在実装中です。"
            else:
                return f"❓ 不明な操作: {operation}"
                
        except FileNotFoundError:
            return f"❌ ファイル '{file_path}' が見つかりません。"
        except PermissionError:
            return f"❌ ファイル '{file_path}' へのアクセス権限がありません。"
        except Exception as e:
            return f"❌ ファイル操作エラー: {str(e)}"
    
    async def _handle_enhanced_code_execution(self, user_message: str, file_target: Optional[str] = None) -> str:
        """Enhanced v2.0独立のコード実行処理"""
        return "Enhanced v2.0独立モードでは、コード実行機能は現在実装されていません。"
    
    async def _handle_enhanced_multi_step_task(self, user_message: str, file_target: Optional[str] = None) -> str:
        """Enhanced v2.0独立の複数ステップタスク処理"""
        return "Enhanced v2.0独立モードでは、複数ステップタスク機能は現在実装されていません。"
    
    async def _handle_enhanced_plan_generation(self, user_message: str, file_target: Optional[str] = None) -> str:
        """Enhanced v2.0独立のプラン生成処理"""
        try:
            # プラン生成のロジック
            plan_content = f"""
# プラン生成結果

## ユーザー要求
{user_message}

## 生成されたプラン
1. 要求の分析と理解
2. 実行可能なタスクの特定
3. 優先順位の決定
4. 実行手順の策定

## 次のステップ
このプランに基づいて具体的な実装を進めることができます。
"""
            return plan_content
        except Exception as e:
            self.logger.error(f"プラン生成エラー: {e}")
            return f"プラン生成中にエラーが発生しました: {str(e)}"

    async def _handle_enhanced_summary_generation(self, user_message: str, file_target: Optional[str] = None) -> str:
        """summary_generation意図に対する具体的な処理"""
        try:
            rich_ui.print_message("📊 要約生成タスクとして処理中...", "info")
            
            # ファイルパスの取得（IntentAnalyzerLLMの結果を優先）
            file_path = file_target if file_target else await self._extract_file_path_from_llm(user_message)
            
            if not file_path:
                return "ファイル名を特定できませんでした。具体的なファイル名を指定してください。"
            
            rich_ui.print_message(f"📖 ファイル読み込み: {file_path}", "info")
            
            # ファイルの存在確認
            if not self.file_ops.exists(file_path):
                return f"ファイル '{file_path}' が見つかりません。ファイル名を確認してください。"
            
            # ファイルの読み込み
            try:
                content = self.file_ops.read_file(file_path)
                self.logger.info(f"ファイル読み込み成功: {file_path}, 内容長: {len(content)}")
            except Exception as e:
                self.logger.error(f"ファイル読み込みエラー: {e}")
                return f"ファイル '{file_path}' の読み込みに失敗しました: {str(e)}"
            
            # ファイルの要約生成
            summary = await self._generate_file_summary(file_path, content)
            
            # 結果を状態に記録
            self.state.short_term_memory["last_read_file"] = {
                "path": file_path,
                "summary": summary,
                "length": len(content),
                "timestamp": datetime.now().isoformat()
            }
            self._record_file_operation("read", file_path, summary)
            self.state.add_message("assistant", f"ファイル '{file_path}' の要約を生成しました")
            
            # 処理完了のログ出力
            self.logger.info(f"要約生成処理完了: {file_path}, 内容長: {len(content)}, 要約長: {len(summary)}")
            
            return f"📄 ファイル '{file_path}' の要約:\n\n{summary}\n\n--- 完全な内容 ---\n{content}"
            
        except Exception as e:
            self.logger.error(f"要約生成処理エラー: {e}")
            return f"要約生成処理中にエラーが発生しました: {str(e)}"
    
    async def _handle_enhanced_content_extraction(self, user_message: str, file_target: Optional[str] = None) -> str:
        """content_extraction意図に対する具体的な処理"""
        try:
            rich_ui.print_message("🔍 コンテンツ抽出タスクとして処理中...", "info")
            
            # ファイルパスの取得（IntentAnalyzerLLMの結果を優先）
            file_path = file_target if file_target else await self._extract_file_path_from_llm(user_message)
            
            if not file_path:
                return "ファイル名を特定できませんでした。具体的なファイル名を指定してください。"
            
            rich_ui.print_message(f"📖 ファイル読み込み: {file_path}", "info")
            
            # ファイルの存在確認
            if not self.file_ops.exists(file_path):
                return f"ファイル '{file_path}' が見つかりません。ファイル名を確認してください。"
            
            # ファイルの読み込み
            try:
                content = self.file_ops.read_file(file_path)
                self.logger.info(f"ファイル読み込み成功: {file_path}, 内容長: {len(content)}")
            except Exception as e:
                self.logger.error(f"ファイル読み込みエラー: {e}")
                return f"ファイル '{file_path}' の読み込みに失敗しました: {str(e)}"
            
            # コンテンツの抽出（ユーザーの要求に基づいて）
            extracted_content = await self._extract_content_based_on_request(user_message, content, file_path)
            
            # 結果を状態に記録
            self.state.short_term_memory["last_extracted_content"] = {
                "path": file_path,
                "extracted": extracted_content,
                "original_length": len(content),
                "timestamp": datetime.now().isoformat()
            }
            self._record_file_operation("extract", file_path, extracted_content[:200])
            self.state.add_message("assistant", f"ファイル '{file_path}' からコンテンツを抽出しました")
            
            return f"🔍 ファイル '{file_path}' から抽出されたコンテンツ:\n\n{extracted_content}"
            
        except Exception as e:
            self.logger.error(f"コンテンツ抽出処理エラー: {e}")
            return f"コンテンツ抽出処理中にエラーが発生しました: {str(e)}"
    
    def _extract_content_based_on_request(self, user_message: str, content: str, file_path: str) -> str:
        """ユーザーの要求に基づいてコンテンツを抽出"""
        try:
            # ユーザーの要求を分析して抽出条件を決定
            message_lower = user_message.lower()
            
            if "概要" in message_lower or "要約" in message_lower:
                # 概要・要約の場合
                return self._extract_summary_content(content, file_path)
            elif "重要な" in message_lower or "ポイント" in message_lower:
                # 重要なポイントの場合
                return self._extract_key_points(content, file_path)
            elif "構造" in message_lower or "構成" in message_lower:
                # 構造・構成の場合
                return self._extract_structure_content(content, file_path)
            else:
                # デフォルト：最初の部分を抽出
                return content[:1000] + ("..." if len(content) > 1000 else "")
                
        except Exception as e:
            self.logger.warning(f"コンテンツ抽出エラー: {e}")
            return content[:1000] + ("..." if len(content) > 1000 else "")
    
    def _extract_summary_content(self, content: str, file_path: str) -> str:
        """要約的なコンテンツを抽出"""
        lines = content.split('\n')
        
        # 最初の数行（ヘッダー部分）を抽出
        header_lines = lines[:10]
        
        # 重要なセクションを探す
        important_sections = []
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in ['概要', '要約', '目的', '背景', '結論']):
                # そのセクションの内容を抽出（最大20行）
                section_content = lines[i:i+20]
                important_sections.extend(section_content)
        
        # 結果を組み合わせ
        result = '\n'.join(header_lines)
        if important_sections:
            result += '\n\n--- 重要なセクション ---\n'
            result += '\n'.join(important_sections)
        
        return result
    
    def _extract_key_points(self, content: str, file_path: str) -> str:
        """重要なポイントを抽出"""
        lines = content.split('\n')
        key_points = []
        
        for line in lines:
            # 箇条書きや番号付きリストを探す
            if line.strip().startswith(('-', '•', '*', '1.', '2.', '3.')):
                key_points.append(line.strip())
            # 重要なキーワードを含む行を探す
            elif any(keyword in line.lower() for keyword in ['重要', '注意', '警告', '必須', '必要']):
                key_points.append(line.strip())
        
        if key_points:
            return '\n'.join(key_points[:20])  # 最大20個
        else:
            # キーポイントが見つからない場合は最初の部分を返す
            return content[:800] + ("..." if len(content) > 800 else "")
    
    def _extract_structure_content(self, content: str, file_path: str) -> str:
        """構造・構成に関するコンテンツを抽出"""
        lines = content.split('\n')
        structure_lines = []
        
        for line in lines:
            # 見出しやセクション区切りを探す
            if line.strip().startswith(('#', '##', '###', '---', '===')):
                structure_lines.append(line.strip())
            # 目次やインデックスを探す
            elif any(keyword in line.lower() for keyword in ['目次', 'index', 'contents', '構造']):
                structure_lines.append(line.strip())
            # 階層的な構造を示す行を探す
            elif line.strip().startswith(('  ', '\t')) and any(keyword in line.lower() for keyword in ['├', '│', '└', '─']):
                structure_lines.append(line.strip())
        
        if structure_lines:
            return '\n'.join(structure_lines)
        else:
            # 構造が見つからない場合は最初の部分を返す
            return content[:600] + ("..." if len(content) > 600 else "")
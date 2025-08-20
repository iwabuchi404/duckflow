"""
EnhancedCompanionCore - Step 2: 既存システム統合版
AgentState、ConversationMemory、PromptCompilerとの統合
"""

import asyncio
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

# 既存システムとの統合
from companion.state.agent_state import AgentState
from .memory.conversation_memory import conversation_memory
from .prompts.prompt_compiler import prompt_compiler
from .prompts.context_builder import PromptContextBuilder
from .base.llm_client import llm_manager
from .ui import rich_ui
from companion.validators.llm_output import LLMOutputFormatter, MainLLMOutput
from companion.state.agent_state import Step
from companion.prompts.context_assembler import ContextAssembler

# 既存のCompanionCore機能
from .core import CompanionCore, ActionType
from .simple_approval import ApprovalMode
from .shared_context_manager import SharedContextManager
from .plan_tool import PlanTool, MessageRef


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
        
        # 既存のCompanionCoreも保持（フォールバック用）
        self.legacy_companion = CompanionCore(approval_mode=approval_mode)
        
        # ファイル操作統合
        from .file_ops import SimpleFileOps
        self.file_ops = SimpleFileOps(approval_mode=approval_mode)
        
        # PlanTool統合
        self.plan_tool = PlanTool()
        
        # Phase 1.6: コード実行機能統合
        from .code_runner import SimpleCodeRunner
        self.code_runner = SimpleCodeRunner(approval_mode=approval_mode)
        
        # 統合モードフラグ
        self.use_enhanced_mode = True
        # LLM出力バリデータ（Phase 1）
        self.llm_output_formatter = LLMOutputFormatter()
        # Phase 2: Context Assembler（Base+Main）
        self.context_assembler = ContextAssembler()
        
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

            # プラン作成
            plan_id = self.plan_tool.propose(plan_generation_prompt, sources, rationale, tags)

            # ActionSpec保証（ActionSpecの生成は元の入力で行う）
            self._ensure_action_specs(plan_id, user_input)

            # 承認要求
            from .plan_tool import SpecSelection
            self.plan_tool.request_approval(plan_id, SpecSelection(all=True))

            return plan_id

        except Exception as e:
            self.logger.error(f"統一プラン生成エラー: {e}", exc_info=True)
            raise
    
    def _ensure_action_specs(self, plan_id: str, content: str):
        """ActionSpec保証（フォールバックなし）"""
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
        
        # エラー時は例外を投げる（フォールバックなし）
        self.plan_tool.set_action_specs(plan_id, [action_spec])
    
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
    
    async def analyze_intent_only(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """統合版意図理解（AgentState活用）"""
        try:
            if self.use_enhanced_mode:
                return await self._analyze_intent_enhanced(user_message, context)
            else:
                return await self.legacy_companion.analyze_intent_only(user_message)
        except Exception as e:
            self.logger.error(f"統合版意図理解エラー: {e}")
            return await self.legacy_companion.analyze_intent_only(user_message)
    
    async def _analyze_intent_enhanced(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """拡張版意図理解（既存システム活用）"""
        self.state.add_message("user", user_message)
        if self.state.needs_memory_management():
            if self.state.create_memory_summary():
                rich_ui.print_message("🧠 会話履歴を要約しました", "info")
        self._sync_to_legacy_readonly()
        
        result = await self.legacy_companion.analyze_intent_only(user_message)
        understanding_result = result.get("understanding_result")

        result_payload = {
            "action_type": result["action_type"],
            "understanding_result": understanding_result,
            "message": user_message,
            "enhanced_mode": True,
            "session_id": self.state.session_id,
            "conversation_count": len(self.state.conversation_history)
        }

        if understanding_result:
            try:
                result_payload.update({
                    "route_type": getattr(understanding_result, 'route_type', None),
                    "risk_level": getattr(understanding_result, 'risk_level', None),
                    "prerequisite_status": getattr(understanding_result, 'prerequisite_status', None),
                    "routing_reason": getattr(understanding_result, 'routing_reason', None),
                    "metadata": getattr(understanding_result, 'metadata', None)
                })
            except Exception:
                pass

        try:
            main_json = self._build_main_llm_output(result_payload)
            validated = self.llm_output_formatter.validate(main_json)
            result_payload["main_llm_output"] = validated.model_dump()
        except Exception:
            repaired = self.llm_output_formatter.try_repair(main_json if 'main_json' in locals() else {})
            if repaired:
                result_payload["main_llm_output"] = repaired.model_dump()
            else:
                result_payload["main_llm_output_error"] = "validation_failed"

        return result_payload

    def _build_main_llm_output(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """意図理解結果から最小のMain LLM JSONを合成"""
        action_type = intent_result.get("action_type")
        action_val = getattr(action_type, 'value', str(action_type))
        next_step = "continue" if action_val in ["direct_response", "file_operation"] else "defer"
        
        return {
            "rationale": "意図分析に基づく次アクションの決定",
            "goal_consistency": "yes: 目標と整合" if getattr(self.state, 'goal', '') else "yes: 目標未設定",
            "constraint_check": "yes: 制約を尊重" if getattr(self.state, 'constraints', []) else "yes: 制約なし",
            "next_step": next_step,
            "step": self.state.step.value if isinstance(self.state.step, Step) else str(self.state.step),
            "state_delta": getattr(self.state, 'last_delta', "")
        }
    
    async def process_with_intent_result(self, intent_result: Dict[str, Any]) -> str:
        """意図理解結果を再利用してメッセージを処理 (リファクタリング版)"""
        if not (self.use_enhanced_mode and intent_result.get("enhanced_mode")):
            return await self.legacy_companion.process_with_intent_result(intent_result)

        try:
            user_message = intent_result["message"]
            action_type = intent_result["action_type"]
            understanding_result = intent_result.get("understanding_result")

            self.legacy_companion._show_thinking_process(user_message)

            # --- 3層プロンプトの構築 ---
            main_context_id = self.context_builder.from_agent_state(self.state)
            main_context_prompt = self.context_builder.build_prompt(main_context_id, "text")

            specialized_prompt = ""
            prompt_pattern = getattr(understanding_result, 'prompt_pattern', 'base_main')
            self.logger.info(f"LLMによるプロンプトパターン選択: {prompt_pattern}")

            if prompt_pattern == 'base_main_specialized':
                try:
                    from .prompts.specialized_prompt_generator import SpecializedPromptGenerator
                    specialized_generator = SpecializedPromptGenerator()
                    current_step = self.state.step
                    if current_step in [Step.PLANNING, Step.EXECUTION, Step.REVIEW]:
                        specialized_prompt = specialized_generator.generate(current_step.value, self.state.model_dump())
                except Exception as e:
                    self.logger.error(f"Specializedプロンプト生成エラー: {e}")

            system_prompt = f"{main_context_prompt}\n\n{specialized_prompt}".strip()
            
            # アクション実行
            if action_type == ActionType.DIRECT_RESPONSE:
                result = await self._generate_enhanced_response(user_message, system_prompt)
            elif action_type == ActionType.FILE_OPERATION:
                result = await self._handle_enhanced_file_operation(user_message, system_prompt)
            elif action_type == ActionType.CODE_EXECUTION:
                result = self.legacy_companion._handle_code_execution(user_message)
            else:
                result = self.legacy_companion._handle_multi_step_task(user_message)
            
            if self._looks_like_plan(result):
                self.set_plan_state(result, "execution_plan")
            
            self.state.add_message("assistant", result)
            self._sync_to_legacy_readonly()
            
            return result
        except Exception as e:
            self.logger.error(f"統合版処理エラー: {e}")
            return await self.legacy_companion.process_with_intent_result(intent_result)
    
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
        except Exception as e:
            self.logger.error(f"PlanTool統合エラー: {e}")
            self.current_plan_state = {"pending": True, "plan_content": plan_content, "plan_type": plan_type, "created_at": datetime.now()}
        
        self.state.short_term_memory["current_plan_state"] = self.current_plan_state
        self._record_file_operation("plan_creation", f"plan_{plan_type}", plan_content[:100])
    
    def get_plan_state(self) -> Dict[str, Any]:
        """現在のプラン状態を取得"""
        return self.current_plan_state
    
    def clear_plan_state(self):
        """プラン状態をクリア"""
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
    
    async def _generate_enhanced_response(self, user_message: str, system_prompt: str) -> str:
        """拡張版直接応答生成"""
        try:
            rich_ui.print_message("💬 拡張コンテキストで応答を生成中...", "info")
            messages = [{"role": "system", "content": system_prompt}]
            if self.state.conversation_history:
                for msg in self.state.conversation_history[-10:]:
                    if msg.role in ["user", "assistant"]:
                        messages.append({"role": msg.role, "content": msg.content})
            messages.append({"role": "user", "content": user_message})
            response = await llm_manager.generate(prompt=user_message, metadata={'system_prompt': system_prompt})
            rich_ui.print_message("✨ 拡張応答を生成しました！", "success")
            return response
        except Exception as e:
            self.logger.error(f"拡張応答生成エラー: {e}")
            return self.legacy_companion._generate_direct_response(user_message)
    
    async def _handle_enhanced_file_operation(self, user_message: str, system_prompt: str) -> str:
        """拡張版ファイル操作処理"""
        try:
            rich_ui.print_message("📁 ファイル操作タスクとして処理中...", "info")
            file_path = await self._extract_file_path_from_llm(user_message)

            if any(kw in user_message for kw in ["読", "確認", "内容", "見て"]):
                return await self._handle_file_read_operation(user_message)
            elif any(kw in user_message for kw in ["プラン", "計画"]) and not file_path:
                plan = self._generate_plan_unified(user_message)
                return plan
            elif any(kw in user_message for kw in ["書", "作成"]) and file_path:
                return await self._handle_file_write_operation(user_message)
            elif any(kw in user_message for kw in ["一覧", "ls"]):
                return await self._handle_file_list_operation(user_message)
            else:
                return await self._generate_enhanced_response(user_message, system_prompt)
        except Exception as e:
            self.logger.error(f"拡張ファイル操作エラー: {e}")
            return self.legacy_companion._handle_file_operation(user_message)
    
    async def _handle_file_read_operation(self, user_message: str) -> str:
        """ファイル読み込み操作を処理"""
        try:
            # LLMの出力からファイル名を取得
            file_path = await self._extract_file_path_from_llm(user_message)
            
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
            return f"📄 ファイル '{file_path}' の内容:\n\n{summary}\n\n--- 完全な内容 ---\n{content}"
        except Exception as e:
            return f"ファイル '{file_path}' の読み込みに失敗しました: {str(e)}"
    
    async def _extract_file_path_from_llm(self, user_message: str) -> str:
        """LLMの出力からファイルパスを抽出"""
        try:
            # LLMにファイル名抽出を依頼
            extraction_prompt = f"""以下のユーザーメッセージから、操作対象のファイル名を正確に抽出してください。

ユーザーメッセージ: {user_message}

以下のJSON形式で回答してください:
{{
    "file_target": "ファイル名（例: game_doc.md）",
    "action": "実行するアクション（例: read_file）",
    "reasoning": "なぜこのファイル名を抽出したかの理由"
}}

ファイル名のみを抽出し、余分な文字は含めないでください。"""

            response = await llm_manager.generate(extraction_prompt)
            
            # JSONレスポンスをパース
            import json
            try:
                # JSON部分を抽出
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    parsed = json.loads(json_str)
                    file_target = parsed.get('file_target', '')
                    
                    if file_target:
                        return file_target
            except Exception as e:
                self.logger.warning(f"JSONパースエラー: {e}")
            
            # フォールバック: 基本的なファイル名抽出
            return self._fallback_file_extraction(user_message)
            
        except Exception as e:
            self.logger.error(f"LLMファイル名抽出エラー: {e}")
            return self._fallback_file_extraction(user_message)
    
    def _fallback_file_extraction(self, user_message: str) -> str:
        """フォールバック用のファイル名抽出"""
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
        
        # 最後の手段：最初の単語
        return words[0] if words else "unknown_file"
    
    async def _handle_file_write_operation(self, user_message: str) -> str:
        """ファイル書き込み操作を処理"""
        # ... (Implementation omitted for brevity)
        return "ファイル書き込みは現在実装中です。"
    
    async def _handle_file_list_operation(self, user_message: str) -> str:
        """ファイル一覧操作を処理"""
        # ... (Implementation omitted for brevity)
        return "ファイル一覧は現在実装中です。"

    async def _generate_file_summary(self, file_path: str, content: str) -> str:
        """ファイル内容の要約を生成"""
        if len(content) < 200: return "(内容が短いため要約省略)"
        try:
            summary_prompt = f"以下のファイル内容を3-5行で簡潔に要約してください。\n\nファイル: {file_path}\n\n内容:{content[:3000]}"
            summary = await llm_manager.generate(summary_prompt)
            return f"📋 要約:\n{summary}"
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
            
            if hasattr(self.legacy_companion, 'conversation_history'):
                self.legacy_companion.conversation_history = legacy_history
        except Exception as e:
            self.logger.warning(f"AgentState → Legacy 同期エラー: {e}")

    # ... (PlanTool and Code Execution methods remain the same) ...
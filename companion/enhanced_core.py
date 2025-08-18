"""
EnhancedCompanionCore - Step 2: 既存システム統合版
AgentState、ConversationMemory、PromptCompilerとの統合
"""

import asyncio
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

# 既存システムとの統合
from codecrafter.state.agent_state import AgentState
from codecrafter.memory.conversation_memory import conversation_memory
from codecrafter.prompts.prompt_compiler import prompt_compiler
from codecrafter.prompts.context_builder import PromptContextBuilder
from codecrafter.base.llm_client import llm_manager
from codecrafter.ui.rich_ui import rich_ui

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
        
        # 統合モードフラグ
        self.use_enhanced_mode = True
        
        # ログ設定
        import logging
        self.logger = logging.getLogger(__name__)
    
    async def analyze_intent_only(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """統合版意図理解（AgentState活用）
        
        Args:
            user_message: ユーザーからのメッセージ
            
        Returns:
            Dict: 意図理解結果
        """
        try:
            if self.use_enhanced_mode:
                return await self._analyze_intent_enhanced(user_message, context)
            else:
                # フォールバック: 既存システム使用
                return await self.legacy_companion.analyze_intent_only(user_message)
                
        except Exception as e:
            self.logger.error(f"統合版意図理解エラー: {e}")
            # フォールバック
            return await self.legacy_companion.analyze_intent_only(user_message)
    
    async def _analyze_intent_enhanced(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """拡張版意図理解（既存システム活用）
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            Dict: 意図理解結果
        """
        # AgentStateに記録（単一ソース・オブ・トゥルース）
        self.state.add_message("user", user_message)
        
        # 記憶管理（自動要約）
        if self.state.needs_memory_management():
            success = self.state.create_memory_summary()
            if success:
                rich_ui.print_message("🧠 会話履歴を要約しました", "info")
        
        # Legacy CompanionCoreへの読み取り専用同期（AgentState → Legacy）
        self._sync_to_legacy_readonly()
        
        # 既存の意図理解システムを活用（コンテキスト付き）
        result = await self.legacy_companion.analyze_intent_only(user_message)
        action_type = result["action_type"]
        understanding_result = result.get("understanding_result")

        # ベース結果
        result: Dict[str, Any] = {
            "action_type": action_type,
            "understanding_result": understanding_result,
            "message": user_message,
            "enhanced_mode": True,
            "session_id": self.state.session_id,
            "conversation_count": len(self.state.conversation_history)  # 同期確認用
        }

        # ルーティング対応: 意図統合結果があれば主要フィールドをトップレベルへ昇格
        try:
            if understanding_result is not None:
                # dataclass 風オブジェクトを想定
                route_type = getattr(understanding_result, 'route_type', None)
                risk_level = getattr(understanding_result, 'risk_level', None)
                prereq = getattr(understanding_result, 'prerequisite_status', None)
                routing_reason = getattr(understanding_result, 'routing_reason', None)
                metadata = getattr(understanding_result, 'metadata', None)

                if route_type is not None:
                    result["route_type"] = route_type
                if risk_level is not None:
                    result["risk_level"] = risk_level
                if prereq is not None:
                    result["prerequisite_status"] = prereq
                if routing_reason is not None:
                    result["routing_reason"] = routing_reason
                if metadata is not None:
                    result["metadata"] = metadata
        except Exception:
            # 取得に失敗しても致命ではないため無視
            pass

        return result
    
    async def process_with_intent_result(self, intent_result: Dict[str, Any]) -> str:
        """統合版意図理解結果処理
        
        Args:
            intent_result: analyze_intent_onlyの結果
            
        Returns:
            str: 応答メッセージ
        """
        try:
            if self.use_enhanced_mode and intent_result.get("enhanced_mode"):
                return await self._process_with_enhanced_context(intent_result)
            else:
                # フォールバック: 既存システム使用
                return await self.legacy_companion.process_with_intent_result(intent_result)
                
        except Exception as e:
            self.logger.error(f"統合版処理エラー: {e}")
            # フォールバック
            return await self.legacy_companion.process_with_intent_result(intent_result)
    
    async def _process_with_enhanced_context(self, intent_result: Dict[str, Any]) -> str:
        """拡張コンテキストでの処理
        
        Args:
            intent_result: 意図理解結果
            
        Returns:
            str: 処理結果
        """
        user_message = intent_result["message"]
        action_type = intent_result["action_type"]
        
        # 思考過程表示
        self.legacy_companion._show_thinking_process(user_message)
        
        # 高度なコンテキスト構築
        context = await self._build_enhanced_context(action_type)
        
        # システムプロンプトをコンパイル
        system_prompt = self.prompt_compiler.compile_system_prompt_dto(context)
        
        # アクション実行（既存ロジック活用）
        if action_type == ActionType.DIRECT_RESPONSE:
            result = await self._generate_enhanced_response(user_message, system_prompt)
        elif action_type == ActionType.FILE_OPERATION:
            result = await self._handle_enhanced_file_operation(user_message, system_prompt)
        elif action_type == ActionType.CODE_EXECUTION:
            result = self.legacy_companion._handle_code_execution(user_message)
        else:
            result = self.legacy_companion._handle_multi_step_task(user_message)
        
        # プラン提示の検出と状態設定（実行阻害改善）
        if self._looks_like_plan(result):
            self.set_plan_state(result, "execution_plan")
        
        # AgentStateに応答を記録（単一ソース・オブ・トゥルース）
        self.state.add_message("assistant", result)
        
        # Legacy CompanionCoreへの読み取り専用同期（AgentState → Legacy）
        self._sync_to_legacy_readonly()
        
        return result
    
    async def _build_enhanced_context(self, action_type: ActionType) -> Any:
        """拡張コンテキストを構築
        
        Args:
            action_type: アクションタイプ
            
        Returns:
            PromptContext: 構築されたコンテキスト
        """
        # テンプレート選択
        template_name = "system_base"
        if action_type == ActionType.FILE_OPERATION:
            template_name = "system_rag_enhanced"
        
        # ファイルコンテキスト収集（簡易版）
        file_context = await self._collect_file_context()
        
        # RAG検索（将来の拡張用）
        rag_results = None  # 現在は未実装
        
        # PromptContextを構築
        context = self.context_builder.from_agent_state(
            state=self.state,
            template_name=template_name,
            rag_results=rag_results,
            file_context_dict=file_context
        ).with_token_budget(8000).build()
        
        return context
    
    async def _collect_file_context(self) -> Dict[str, Any]:
        """ファイルコンテキストを収集（簡易版）
        
        Returns:
            Dict: ファイルコンテキスト
        """
        # 現在は基本的な情報のみ
        # 将来的にはfile_toolsとの統合を予定
        return {
            "files_list": [],
            "file_contents": {},
            "read_request_targets": []
        }
    
    def set_plan_state(self, plan_content: str, plan_type: str = "execution_plan"):
        """プラン状態を設定（PlanTool統合版）
        
        Args:
            plan_content: プランの内容
            plan_type: プランの種類
        """
        # PlanToolでプランを提案
        try:
            plan_id = self.plan_tool.propose(
                content=plan_content,
                sources=[MessageRef(
                    message_id=str(uuid.uuid4()),
                    timestamp=datetime.now().isoformat()
                )],
                rationale=f"AI生成プラン: {plan_type}",
                tags=[plan_type, "ai_generated"]
            )
            
            # 従来の状態も維持（互換性のため）
            self.current_plan_state = {
                "pending": True,
                "plan_content": plan_content,
                "plan_type": plan_type,
                "created_at": datetime.now(),
                "plan_id": plan_id  # PlanTool ID を追加
            }
            
        except Exception as e:
            self.logger.error(f"PlanTool統合エラー: {e}")
            # フォールバック: 従来の方式
            self.current_plan_state = {
                "pending": True,
                "plan_content": plan_content,
                "plan_type": plan_type,
                "created_at": datetime.now()
            }
        
        # プラン状態をAgentStateにも記録
        self.state.collected_context["current_plan_state"] = self.current_plan_state
        
        # DualLoop の PlanContext にも反映（存在する場合）
        if hasattr(self, "plan_context") and self.plan_context is not None:
            try:
                self.plan_context.pending = True
                self.plan_context.current_plan = {
                    "type": plan_type,
                    "created_at": self.current_plan_state["created_at"],
                    "summary": self._summarize_plan_for_context(plan_content)[:2000],
                    "plan_id": self.current_plan_state.get("plan_id")
                }
            except Exception:
                pass
    
    def get_plan_state(self) -> Dict[str, Any]:
        """現在のプラン状態を取得（PlanTool統合版）
        
        Returns:
            Dict: プラン状態
        """
        # PlanToolからの情報も含める
        plan_state = self.current_plan_state.copy()
        
        if plan_state.get("plan_id"):
            try:
                plan_tool_state = self.plan_tool.get_state(plan_state["plan_id"])
                plan_state["plan_tool_state"] = plan_tool_state
            except Exception as e:
                self.logger.warning(f"PlanTool状態取得エラー: {e}")
        
        return plan_state
    
    def clear_plan_state(self):
        """プラン状態をクリア（PlanTool統合版）"""
        # PlanToolの現在のプランもクリア
        try:
            self.plan_tool.clear_current()
        except Exception as e:
            self.logger.warning(f"PlanTool クリアエラー: {e}")
        
        self.current_plan_state = {
            "pending": False,
            "plan_content": None,
            "plan_type": None,
            "created_at": None
        }
        
        # AgentStateからも削除
        self.state.collected_context["current_plan_state"] = self.current_plan_state
        # PlanContext 側も同期
        if hasattr(self, "plan_context") and self.plan_context is not None:
            try:
                self.plan_context.reset()
            except Exception:
                pass

    def _looks_like_plan(self, text: str) -> bool:
        """応答テキストが「実装プラン/ロードマップ」的かを簡易判定"""
        if not text or len(text) < 50:
            return False
        import re
        indicators = [
            "実装プラン", "実装ロードマップ", "ロードマップ", "開発フロー", "フェーズ", "次のステップ",
            "アクションアイテム", "タスク実行計画", "ファイル構成", "テスト戦略", "CI/CD"
        ]
        hits = sum(1 for kw in indicators if kw in text)
        # 番号付きリストやテーブル/コードブロックの存在
        has_list = bool(re.search(r"\n\s*\d+\)\s|\n\s*\d+\.\s|\n\s*-\s", text))
        has_code = "```" in text
        return hits >= 2 and (has_list or has_code)

    def _summarize_plan_for_context(self, text: str) -> str:
        """PlanContext 用の軽い要約（先頭見出しと箇条書き先頭数件）"""
        lines = text.splitlines()
        header = next((l for l in lines if l.strip().startswith("#")), "")
        bullets = [l.strip() for l in lines if l.strip().startswith(("- ", "1.", "2.", "3."))][:10]
        return "\n".join([header] + bullets)
    
    async def _generate_enhanced_response(self, user_message: str, system_prompt: str) -> str:
        """拡張版直接応答生成（Chatと同じ内容を使用）
        
        Args:
            user_message: ユーザーメッセージ
            system_prompt: システムプロンプト
            
        Returns:
            str: 応答メッセージ
        """
        try:
            rich_ui.print_message("💬 拡張コンテキストで応答を生成中...", "info")
            
            # Chatと同じ方式: システムプロンプト + 会話履歴 + 現在のメッセージ
            messages = [{"role": "system", "content": system_prompt}]

            # AgentStateの会話履歴を使用（最新20件）
            if self.state.conversation_history:
                recent_history = self.state.conversation_history[-20:]
                for msg in recent_history:
                    if msg.role in ["user", "assistant"]:
                        messages.append({"role": msg.role, "content": msg.content})
            
            # 現在のユーザーメッセージを最後に追加
            messages.append({"role": "user", "content": user_message})
            
            # LLM実行
            response = llm_manager.chat_with_history(messages)
            
            rich_ui.print_message("✨ 拡張応答を生成しました！", "success")
            return response
            
        except Exception as e:
            self.logger.error(f"拡張応答生成エラー: {e}")
            # フォールバック: 既存システム
            return self.legacy_companion._generate_direct_response(user_message)
    
    async def _handle_enhanced_file_operation(self, user_message: str, system_prompt: str) -> str:
        """拡張版ファイル操作処理
        
        Args:
            user_message: ユーザーメッセージ
            system_prompt: システムプロンプト
            
        Returns:
            str: 処理結果
        """
        try:
            rich_ui.print_message("📁 ファイル操作タスクとして処理中...", "info")
            
            # ファイル操作の種類を判定
            user_message_lower = user_message.lower()
            
            # ファイル読み込み操作の検出と実行
            if any(kw in user_message for kw in ["読", "読み", "確認", "内容", "見て", "把握"]) or "read" in user_message_lower:
                return await self._handle_file_read_operation(user_message)
            
            # ファイル書き込み操作の検出と実行
            elif "書" in user_message or "作成" in user_message or "write" in user_message_lower or "create" in user_message_lower:
                return await self._handle_file_write_operation(user_message)
            
            # ファイル一覧操作の検出と実行
            elif "一覧" in user_message or "list" in user_message_lower or "ls" in user_message_lower:
                return await self._handle_file_list_operation(user_message)
            
            else:
                # 汎用的なファイル操作として処理
                return await self._handle_generic_file_operation(user_message, system_prompt)
            
        except Exception as e:
            self.logger.error(f"拡張ファイル操作エラー: {e}")
            # フォールバック
            return self.legacy_companion._handle_file_operation(user_message)
    
    async def _handle_file_read_operation(self, user_message: str) -> str:
        """ファイル読み込み操作を処理
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            str: 読み込み結果
        """
        try:
            # ファイル名の抽出（改善版）
            import re
            
            # より柔軟なファイル名パターンを検索
            file_patterns = [
                # 引用符で囲まれたファイル名
                r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']',
                r'["\']([^"\']+)["\']',  # 引用符で囲まれた任意の文字列
                
                # パス付きファイル名（Windows/Unix両対応）
                r'([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+)',  # パス付き拡張子ファイル名
                r'([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+)',   # パス付き拡張子ファイル名（アンダースコア対応）
                
                # 拡張子付きファイル名
                r'([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)',     # 拡張子付きファイル名
                r'([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)',     # 拡張子付きファイル名（アンダースコア対応）
                
                # 特定の拡張子ファイル
                r'([a-zA-Z0-9_\-\.]+\.(?:py|md|txt|json|yaml|yml|js|html|css|java|cpp|c|h|sql|sh|bat|ps1))',
                
                # 日本語ファイル名（基本的なパターン）
                r'([一-龯a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)',
                
                # 拡張子のないファイル名（最後の手段）
                r'([a-zA-Z0-9_\-\.]+)(?:\s|$|。|、|です|ます)',
            ]
            
            file_path = None
            for pattern in file_patterns:
                match = re.search(pattern, user_message)
                if match:
                    file_path = match.group(1)
                    # ファイル名の妥当性チェック
                    if self._is_valid_file_path(file_path):
                        break
                    else:
                        file_path = None
            
            # 正規表現で抽出できない場合、LLMにファイル名抽出を依頼
            if not file_path:
                file_path = await self._extract_filename_with_llm(user_message)
            
            if not file_path:
                return "ファイル名が特定できませんでした。ファイル名を明示してください。\n\n例:\n- `example.py` を読んで\n- \"test.txt\" の内容を確認して\n- README.md を見て"
            
            rich_ui.print_message(f"📖 ファイル読み込み: {file_path}", "info")
            
            # ファイル読み込み実行（複数パターンを試行）
            try:
                # まず指定されたパスで試行
                content = None
                tried_paths = []
                
                try:
                    content = self.file_ops.read_file(file_path)
                    tried_paths.append(f"✓ {file_path}")
                except Exception as e1:
                    tried_paths.append(f"✗ {file_path} ({e1})")
                    
                    # カレントディレクトリでも試行
                    if "/" not in file_path and "\\" not in file_path:
                        try:
                            import os
                            current_path = os.path.join(".", file_path)
                            content = self.file_ops.read_file(current_path)
                            file_path = current_path  # 成功したパスを更新
                            tried_paths.append(f"✓ {current_path}")
                        except Exception as e2:
                            tried_paths.append(f"✗ {current_path} ({e2})")
                
                if content is None:
                    return f"ファイル '{file_path}' の読み込みに失敗しました。\n試行したパス:\n" + "\n".join(tried_paths)
                
                # 内容の要約を生成
                summary = await self._generate_file_summary(file_path, content)
                
                # AgentStateに記録
                self.state.add_message("assistant", f"ファイル '{file_path}' を読み込みました")
                
                return f"📄 ファイル '{file_path}' の内容:\n\n{summary}\n\n--- 完全な内容 ---\n{content}"
                
            except Exception as e:
                return f"ファイル '{file_path}' の読み込みに失敗しました: {str(e)}"
                
        except Exception as e:
            self.logger.error(f"ファイル読み込み操作エラー: {e}")
            return f"ファイル読み込み処理でエラーが発生しました: {str(e)}"
    
    async def _handle_file_write_operation(self, user_message: str) -> str:
        """ファイル書き込み操作を処理
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            str: 書き込み結果
        """
        try:
            # ファイル名と内容の抽出（改善版）
            import re
            
            # より柔軟なファイル名パターンを検索
            file_patterns = [
                # 引用符で囲まれたファイル名
                r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']',
                r'["\']([^"\']+)["\']',  # 引用符で囲まれた任意の文字列
                
                # パス付きファイル名（Windows/Unix両対応）
                r'([a-zA-Z0-9_\-\\./\\]+\.[a-zA-Z0-9]+)',  # パス付き拡張子ファイル名
                r'([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+)',   # パス付き拡張子ファイル名（アンダースコア対応）
                
                # 拡張子付きファイル名
                r'([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)',     # 拡張子付きファイル名
                r'([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)',     # 拡張子付きファイル名（アンダースコア対応）
                
                # 特定の拡張子ファイル
                r'([a-zA-Z0-9_\-\.]+\.(?:py|md|txt|json|yaml|yml|js|html|css|java|cpp|c|h|sql|sh|bat|ps1))',
                
                # 日本語ファイル名（基本的なパターン）
                r'([一-龯a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)',
                
                # 拡張子のないファイル名（最後の手段）
                r'([a-zA-Z0-9_\-\.]+)(?:\s|$|。|、|です|ます)',
            ]
            
            file_path = None
            for pattern in file_patterns:
                match = re.search(pattern, user_message)
                if match:
                    file_path = match.group(1)
                    # ファイル名の妥当性チェック
                    if self._is_valid_file_path(file_path):
                        break
                    else:
                        file_path = None
            
            # 正規表現で抽出できない場合、LLMにファイル名抽出を依頼
            if not file_path:
                file_path = await self._extract_filename_with_llm(user_message)
            
            if not file_path:
                return "ファイル名が特定できませんでした。ファイル名を明示してください。\n\n例:\n- `example.py` を作成して\n- \"test.txt\" に書き込んで\n- README.md を作成して"
            
            # 内容の抽出（実際のプロジェクトでは、より高度な内容抽出が必要）
            content_keywords = ["内容", "コンテンツ", "テキスト", "データ", "コード", "内容を"]
            if any(kw in user_message for kw in content_keywords):
                # LLMを使って適切な内容を生成
                content_prompt = f"""
ユーザー要求: {user_message}
ファイルパス: {file_path}

上記の要求に基づいて、適切なファイル内容を生成してください。
要求が不明確な場合は、一般的なテンプレートを提供してください。
"""
                
                from codecrafter.base.llm_client import llm_manager
                generated_content = llm_manager.chat_with_history([
                    {"role": "system", "content": "ユーザーの要求に基づいて適切なファイル内容を生成してください。"},
                    {"role": "user", "content": content_prompt}
                ])
                
                content = generated_content
            else:
                # デフォルト内容
                content = f"""# {file_path}

このファイルは {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} に作成されました。

## 内容
ユーザー要求: {user_message}

# TODO: 必要な内容を追加してください
"""
            
            rich_ui.print_message(f"📝 ファイル書き込み: {file_path}", "info")
            
            # ファイル書き込み実行
            result = self.file_ops.write_file(file_path, content)
            
            if result["success"]:
                # AgentStateに記録
                self.state.add_message("assistant", f"ファイル '{file_path}' を作成しました")
                
                return f"""📄 ファイル '{file_path}' を正常に作成しました

📊 書き込み情報:
- サイズ: {result.get('size', 0)}バイト
- 行数: {result.get('lines', 0)}行
- 更新日時: {result.get('modified', 'N/A')}

📝 書き込み内容:
```
{content[:500]}{'...' if len(content) > 500 else ''}
```
"""
            else:
                return f"ファイル '{file_path}' の書き込みに失敗しました: {result.get('message', '不明なエラー')}"
                
        except Exception as e:
            self.logger.error(f"ファイル書き込み操作エラー: {e}")
            return f"ファイル書き込み処理でエラーが発生しました: {str(e)}"
    
    def _is_valid_file_path(self, file_path: str) -> bool:
        """ファイルパスの妥当性をチェック"""
        if not file_path or len(file_path.strip()) == 0:
            return False
        
        # 基本的なファイル名の妥当性チェック
        import os
        from pathlib import Path
        
        try:
            # パスの正規化
            normalized_path = Path(file_path).resolve()
            
            # ファイル名部分の妥当性
            filename = normalized_path.name
            if len(filename) == 0 or filename.startswith('.'):
                return False
            
            # 禁止文字のチェック（Windows/Unix両対応）
            invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\0']
            if any(char in filename for char in invalid_chars):
                return False
            
            # ファイル名の長さチェック
            if len(filename) > 255:  # 一般的なファイルシステムの制限
                return False
            
            return True
            
        except Exception:
            return False
    
    async def _extract_filename_with_llm(self, user_message: str) -> Optional[str]:
        """LLMを使用してファイル名を抽出"""
        try:
            from codecrafter.base.llm_client import llm_manager
            
            extraction_prompt = f"""
ユーザーのメッセージから、作成・編集・読み込みしたいファイル名を抽出してください。

ユーザーメッセージ: {user_message}

抽出ルール:
1. ファイル名のみを抽出（パス情報は含めない）
2. 拡張子がある場合は含める
3. 日本語ファイル名も対応
4. ファイル名が見つからない場合は空文字列を返す
5. 引用符やバッククォートで囲まれた部分を優先的に抽出
6. 一般的なファイル拡張子（.py, .md, .txt, .json, .yaml, .yml, .js, .html, .css等）を認識

例:
- "test.pyを作成して" → test.py
- `README.md` を読んで → README.md
- 設定ファイルconfig.yaml → config.yaml
- 日本語ファイル.txt → 日本語ファイル.txt

抽出結果（ファイル名のみ、見つからない場合は空文字列）:
"""
            
            response = llm_manager.chat_with_history([
                {"role": "system", "content": "ファイル名抽出の専門家です。ユーザーメッセージからファイル名のみを抽出し、見つからない場合は空文字列を返してください。"},
                {"role": "user", "content": extraction_prompt}
            ])
            
            # レスポンスからファイル名を抽出
            extracted_name = response.strip()
            
            # 基本的な妥当性チェック
            if extracted_name and self._is_valid_file_path(extracted_name):
                return extracted_name
            
            return None
            
        except Exception as e:
            self.logger.error(f"LLMファイル名抽出エラー: {e}")
            return None
    
    async def _handle_file_list_operation(self, user_message: str) -> str:
        """ファイル一覧操作を処理
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            str: 一覧結果
        """
        try:
            # ディレクトリを指定されている場合はその値を使用、なければカレントディレクトリ
            directory = "."
            
            rich_ui.print_message(f"📂 ディレクトリ一覧: {directory}", "info")
            
            files = self.file_ops.list_files(directory)
            
            if not files:
                return f"ディレクトリ '{directory}' にファイルが見つかりませんでした。"
            
            result = f"📂 ディレクトリ '{directory}' の内容:\n\n"
            for file_info in files[:20]:  # 最大20件
                file_type = file_info["type"]
                name = file_info["name"]
                size = file_info.get("size", 0)
                
                emoji = "📁" if file_type == "directory" else "📄"
                size_str = f" ({size}B)" if file_type == "file" else ""
                result += f"{emoji} {name}{size_str}\n"
            
            if len(files) > 20:
                result += f"\n... および他 {len(files) - 20} 個のアイテム"
            
            return result
            
        except Exception as e:
            self.logger.error(f"ファイル一覧操作エラー: {e}")
            return f"ファイル一覧処理でエラーが発生しました: {str(e)}"
    
    async def _handle_generic_file_operation(self, user_message: str, system_prompt: str) -> str:
        """汎用ファイル操作を処理
        
        Args:
            user_message: ユーザーメッセージ
            system_prompt: システムプロンプト
            
        Returns:
            str: 処理結果
        """
        try:
            from codecrafter.base.llm_client import llm_manager
            
            # LLMを使って汎用的な応答を生成
            messages = [
                {"role": "system", "content": system_prompt + "\n\nファイル操作に関する質問です。適切に回答してください。"},
                {"role": "user", "content": user_message}
            ]
            
            response = llm_manager.chat_with_history(messages)
            return response
            
        except Exception as e:
            self.logger.error(f"汎用ファイル操作エラー: {e}")
            return f"ファイル操作処理でエラーが発生しました: {str(e)}"
    
    async def _generate_file_summary(self, file_path: str, content: str) -> str:
        """ファイル内容の要約を生成
        
        Args:
            file_path: ファイルパス
            content: ファイル内容
            
        Returns:
            str: 要約
        """
        try:
            from codecrafter.base.llm_client import llm_manager
            
            # 内容が短い場合は要約を省略
            if len(content) < 500:
                return "（内容が短いため要約を省略）"
            
            # LLMで要約を生成
            messages = [
                {"role": "system", "content": "以下のファイル内容を簡潔に要約してください。重要なポイントを3-5行でまとめてください。"},
                {"role": "user", "content": f"ファイル: {file_path}\n\n内容:\n{content[:2000]}"}  # 最初の2000文字
            ]
            
            summary = llm_manager.chat_with_history(messages)
            return f"📋 要約:\n{summary}"
            
        except Exception as e:
            self.logger.warning(f"ファイル要約生成エラー: {e}")
            return "（要約の生成に失敗しました）"
    
    def get_agent_state(self) -> AgentState:
        """AgentStateを取得
        
        Returns:
            AgentState: 現在の状態
        """
        return self.state
    
    def get_session_summary(self) -> Dict[str, Any]:
        """セッションサマリーを取得
        
        Returns:
            Dict: セッション情報
        """
        base_summary = self.state.get_context_summary()
        
        # 記憶管理情報を追加
        memory_status = self.state.get_memory_status()
        
        return {
            **base_summary,
            "memory_status": memory_status,
            "enhanced_mode": self.use_enhanced_mode,
            "session_id": self.state.session_id
        }
    
    def toggle_enhanced_mode(self, enabled: bool = None) -> bool:
        """拡張モードの切り替え
        
        Args:
            enabled: 有効にするかどうか（Noneの場合はトグル）
            
        Returns:
            bool: 現在の拡張モード状態
        """
        if enabled is None:
            self.use_enhanced_mode = not self.use_enhanced_mode
        else:
            self.use_enhanced_mode = enabled
        
        mode_str = "有効" if self.use_enhanced_mode else "無効"
        rich_ui.print_message(f"🔧 拡張モード: {mode_str}", "info")
        
        return self.use_enhanced_mode
    
    def _sync_to_legacy_readonly(self):
        """AgentState → Legacy CompanionCore への読み取り専用同期
        
        単一ソース・オブ・トゥルース（AgentState）から読み取り専用ミラー（Legacy）へ同期
        逆同期は禁止（AgentStateが唯一の書き込み可能ソース）
        """
        try:
            # AgentStateの会話履歴をlegacy形式に変換
            legacy_history = []
            
            # ペアを作成（user-assistant）
            for i in range(0, len(self.state.conversation_history)):
                msg = self.state.conversation_history[i]
                
                if msg.role == "user":
                    # ユーザーメッセージの場合、次のアシスタントメッセージとペアにする
                    user_content = msg.content
                    assistant_content = ""
                    
                    # 対応するアシスタントメッセージを探す
                    if i + 1 < len(self.state.conversation_history):
                        next_msg = self.state.conversation_history[i + 1]
                        if next_msg.role == "assistant":
                            assistant_content = next_msg.content
                    
                    # legacy形式のエントリを作成（完了ペアのみ）
                    if assistant_content:
                        legacy_entry = {
                            "user": user_content,
                            "assistant": assistant_content,
                            "timestamp": msg.timestamp,
                            "session_time": (msg.timestamp - self.state.created_at).total_seconds()
                        }
                        legacy_history.append(legacy_entry)
            
            # legacy CompanionCoreの履歴を更新（読み取り専用ミラー）
            try:
                if hasattr(self.legacy_companion, '_history_lock'):
                    with self.legacy_companion._history_lock:
                        self.legacy_companion.conversation_history = legacy_history
                else:
                    self.legacy_companion.conversation_history = legacy_history
            except AttributeError:
                # legacy_companionに会話履歴がない場合は無視
                pass
            
            # 明示的にログ出力（同期確認用）
            self.logger.debug(f"AgentState → Legacy 読み取り専用同期完了: "
                             f"AgentState({len(self.state.conversation_history)}) → Legacy({len(legacy_history)})")
            
        except Exception as e:
            self.logger.warning(f"AgentState → Legacy 同期エラー: {e}")
            # エラーは無視して続行（Legacy依存を回避）
    # === PlanTool API メソッド ===
    
    def propose_plan(self, content: str, rationale: str = "", tags: List[str] = None) -> str:
        """プランを提案（PlanTool API）
        
        Args:
            content: プラン内容
            rationale: 目的・前提
            tags: タグリスト
            
        Returns:
            str: プランID
        """
        return self.plan_tool.propose(
            content=content,
            sources=[MessageRef(
                message_id=str(uuid.uuid4()),
                timestamp=datetime.now().isoformat()
            )],
            rationale=rationale or "ユーザー要求によるプラン",
            tags=tags or ["user_requested"]
        )
    
    def set_plan_action_specs(self, plan_id: str, specs: List[Any]) -> Dict[str, Any]:
        """プランにActionSpecを設定（PlanTool API）
        
        Args:
            plan_id: プランID
            specs: ActionSpecリスト
            
        Returns:
            Dict: バリデーション結果
        """
        from .collaborative_planner import ActionSpec
        
        # ActionSpecに変換（必要に応じて）
        action_specs = []
        for spec in specs:
            if isinstance(spec, ActionSpec):
                action_specs.append(spec)
            elif isinstance(spec, dict):
                action_specs.append(ActionSpec(**spec))
            else:
                self.logger.warning(f"不明なActionSpec形式: {spec}")
        
        validation_result = self.plan_tool.set_action_specs(plan_id, action_specs)
        return {
            "ok": validation_result.ok,
            "issues": validation_result.issues,
            "action_count": len(validation_result.normalized)
        }
    
    def preview_plan(self, plan_id: str) -> Dict[str, Any]:
        """プランをプレビュー（PlanTool API）
        
        Args:
            plan_id: プランID
            
        Returns:
            Dict: プレビュー情報
        """
        preview = self.plan_tool.preview(plan_id)
        return {
            "files": preview.files,
            "diffs": preview.diffs,
            "risk_score": preview.risk_score
        }
    
    def approve_plan(self, plan_id: str, approver: str = "user") -> Dict[str, Any]:
        """プランを承認（PlanTool API）
        
        Args:
            plan_id: プランID
            approver: 承認者
            
        Returns:
            Dict: 承認結果
        """
        from .plan_tool import SpecSelection
        
        # 全ActionSpecを承認対象とする
        selection = SpecSelection(all=True)
        
        # 承認要求
        self.plan_tool.request_approval(plan_id, selection)
        
        # 承認実行
        return self.plan_tool.approve(plan_id, approver, selection)
    
    def execute_plan(self, plan_id: str) -> Dict[str, Any]:
        """プランを実行（PlanTool API）
        
        Args:
            plan_id: プランID
            
        Returns:
            Dict: 実行結果
        """
        result = self.plan_tool.execute(plan_id)
        return {
            "success": result.overall_success,
            "results": result.results,
            "started_at": result.started_at,
            "finished_at": result.finished_at
        }
    
    def list_plans(self) -> List[Dict[str, Any]]:
        """プラン一覧を取得（PlanTool API）
        
        Returns:
            List[Dict]: プラン一覧
        """
        return self.plan_tool.list()
    
    def get_current_plan(self) -> Optional[Dict[str, str]]:
        """現在のプランを取得（PlanTool API）
        
        Returns:
            Optional[Dict]: 現在のプラン情報
        """
        return self.plan_tool.get_current()

    def test_filename_extraction(self, test_messages: List[str]) -> Dict[str, str]:
        """ファイル名抽出のテスト用メソッド（デバッグ用）"""
        results = {}
        
        for message in test_messages:
            # 正規表現パターンでの抽出をテスト
            file_path = None
            import re
            
            file_patterns = [
                # 引用符で囲まれたファイル名
                r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']',
                r'["\']([^"\']+)["\']',  # 引用符で囲まれた任意の文字列
                
                # パス付きファイル名（Windows/Unix両対応）
                r'([a-zA-Z0-9_\-\\./\\]+\.[a-zA-Z0-9]+)',  # パス付き拡張子ファイル名
                r'([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+)',   # パス付き拡張子ファイル名（アンダースコア対応）
                
                # 拡張子付きファイル名
                r'([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)',     # 拡張子付きファイル名
                r'([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)',     # 拡張子付きファイル名（アンダースコア対応）
                
                # 特定の拡張子ファイル
                r'([a-zA-Z0-9_\-\.]+\.(?:py|md|txt|json|yaml|yml|js|html|css|java|cpp|c|h|sql|sh|bat|ps1))',
                
                # 日本語ファイル名（基本的なパターン）
                r'([一-龯a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)',
                
                # 拡張子のないファイル名（最後の手段）
                r'([a-zA-Z0-9_\-\.]+)(?:\s|$|。|、|です|ます)',
            ]
            
            for pattern in file_patterns:
                match = re.search(pattern, message)
                if match:
                    file_path = match.group(1)
                    if self._is_valid_file_path(file_path):
                        break
                    else:
                        file_path = None
            
            results[message] = file_path or "抽出失敗"
        
        return results
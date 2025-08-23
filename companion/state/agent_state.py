"""
Enhanced AgentState for Phase 1

- Adds the fixed five items (goal, why_now, constraints, plan_brief, open_questions)
- Introduces Step/Status enums to separate activity kind and outcome state
- Keeps compatibility with legacy fields used by EnhancedCompanionCore

Note: This file is based on `codecrafter/state/agent_state.py` with minimal
extensions required for Phase 1 integration.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Literal
from enum import Enum
from pydantic import BaseModel, Field
import logging

from .enums import Step as LegacyStep, Status as LegacyStatus
from .action_result import ActionResult

# --- v4 階層的プランニングのための新しいデータモデル ---

class Action(BaseModel):
    """メインLLMが生成する高レベルの行動計画"""
    operation: str = Field(description="実行する高レベル操作 (例: 'plan_tool.propose')")
    args: Dict[str, Any] = Field(default_factory=dict, description="操作の引数")
    reasoning: Optional[str] = Field(default=None, description="このアクションが生成された理由")

class Task(BaseModel):
    """単一のツール実行を表すタスク"""
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    operation: str = Field(description="実行する操作 (例: 'file_ops.write_file')")
    args: Dict[str, Any] = Field(default_factory=dict, description="操作の引数")
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: Optional[Any] = Field(default=None, description="実行結果")
    reasoning: Optional[str] = Field(default=None, description="このタスクが生成された理由")

class Step(BaseModel):
    """Planを構成する、より大きな単位のステップ"""
    step_id: str = Field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    name: str = Field(description="ステップの短い名前")
    description: str = Field(description="このステップが何をするかの説明")
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    depends_on: List[str] = Field(default_factory=list, description="このステップが依存する他のstep_idのリスト")
    task_list: List[Task] = Field(default_factory=list, description="このステップを実行するための具体的なタスクリスト")

class Plan(BaseModel):
    """ユーザーの長期的な目標を達成するための抽象的な計画"""
    plan_id: str = Field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    name: str = Field(description="プランの短い名前")
    goal: str = Field(description="このプランが達成しようとする最終的な目標")
    status: Literal["draft", "approved", "in_progress", "completed", "failed"] = "draft"
    steps: List[Step] = Field(default_factory=list, description="プランを構成するステップのリスト")

# --- 既存のデータモデル ---

class ConversationMessage(BaseModel):
    role: str = Field(description="メッセージの役割 (user, assistant, system)")
    content: str = Field(description="メッセージの内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="メッセージのタイムスタンプ")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="追加のメタデータ")


class TaskStep(BaseModel):
    id: str = Field(description="ステップのID")
    description: str = Field(description="ステップの説明")
    status: str = Field(default="pending", description="ステップの状態 (pending, in_progress, completed, failed)")
    result: Optional[str] = Field(default=None, description="ステップの実行結果")
    error: Optional[str] = Field(default=None, description="エラーメッセージ")
    created_at: datetime = Field(default_factory=datetime.now, description="作成日時")
    completed_at: Optional[datetime] = Field(default=None, description="完了日時")


class WorkspaceInfo(BaseModel):
    path: str = Field(description="ワークスペースのパス")
    files: List[str] = Field(default_factory=list, description="ワークスペース内のファイル一覧")
    current_file: Optional[str] = Field(default=None, description="現在作業中のファイル")
    last_modified: Optional[datetime] = Field(default=None, description="最終更新日時")


class ToolExecution(BaseModel):
    tool_name: str = Field(description="実行したツール名")
    arguments: Dict[str, Any] = Field(description="ツールの引数")
    result: Optional[Any] = Field(default=None, description="ツールの実行結果")
    error: Optional[str] = Field(default=None, description="エラーメッセージ")
    execution_time: float = Field(default=0.0, description="実行時間（秒）")
    timestamp: datetime = Field(default_factory=datetime.now, description="実行時刻")


class Vitals(BaseModel):
    mood: float = Field(default=1.0, description="気分・機嫌 (0.0-1.0)")
    focus: float = Field(default=1.0, description="集中力 (0.0-1.0)")
    stamina: float = Field(default=1.0, description="体力 (0.0-1.0)")
    total_loops: int = Field(default=0, description="総ループ回数")
    error_count: int = Field(default=0, description="エラー発生回数")
    last_confidence_score: float = Field(default=1.0, description="最新の自己評価スコア")
    consecutive_similar_actions: int = Field(default=0, description="連続した類似アクション回数")

    def update_mood(self, confidence_score: float, user_feedback: Optional[float] = None):
        self.last_confidence_score = confidence_score
        self.mood = 0.7 * confidence_score + 0.3 * self.mood
        if user_feedback is not None:
            self.mood = min(1.0, self.mood + user_feedback * 0.2)
        self.mood = max(0.0, min(1.0, self.mood))

    def update_focus(self, is_progress: bool = True, context_size: int = 0):
        if is_progress:
            self.focus = min(1.0, self.focus + 0.1)
            self.consecutive_similar_actions = 0
        else:
            self.consecutive_similar_actions += 1
            focus_penalty = 0.15 * min(self.consecutive_similar_actions, 5)
            self.focus = max(0.0, self.focus - focus_penalty)
        if context_size > 5000:
            self.focus = max(0.0, self.focus - 0.05)

    def update_stamina(self, had_error: bool = False):
        self.total_loops += 1
        loop_penalty = 0.02 * self.total_loops
        if had_error:
            self.error_count += 1
            error_penalty = 0.1 * self.error_count
        else:
            error_penalty = 0
        self.stamina = max(0.0, 1.0 - loop_penalty - error_penalty)


class GraphState(BaseModel):
    current_node: Optional[str] = Field(default=None, description="現在実行中のノード")
    next_nodes: List[str] = Field(default_factory=list, description="次に実行予定のノード一覧")
    execution_path: List[str] = Field(default_factory=list, description="実行済みノードのパス")
    loop_count: int = Field(default=0, description="ループ実行回数")
    max_loops: int = Field(default=5, description="最大ループ回数")


class AgentState(BaseModel):
    """エージェントの全体状態（Phase 1 拡張版）"""

    model_config = {"arbitrary_types_allowed": True}

    # 固定5項目（文脈の核）
    goal: str = Field(default="", description="目的（1行、最大200文字）")
    why_now: str = Field(default="", description="なぜ今やるのか（1行、最大200文字）")
    constraints: List[str] = Field(default_factory=list, description="制約（最大2個、各100文字以内）")
    plan_brief: List[str] = Field(default_factory=list, description="直近の短い計画（最大3手）")
    open_questions: List[str] = Field(default_factory=list, description="未解決の問い（最大2個）")

    # 追加フィールド
    short_term_memory: Dict[str, Any] = Field(default_factory=dict, description="タスクをまたいで引き継がれる短期記憶")
    context_refs: List[str] = Field(default_factory=list, description="関連参照")
    decision_log: List[str] = Field(default_factory=list, description="採択済みの方針ログ")
    pending_gate: bool = Field(default=False, description="承認待ちの有無")
    last_delta: str = Field(default="", description="直近の変更の要約")

    # 行動と結果（分離）
    step: LegacyStep = Field(default=LegacyStep.IDLE, description="現在のステップ")
    status: LegacyStatus = Field(default=LegacyStatus.PENDING, description="現在のステータス")
    
    # v4 階層的プランニングの状態
    plans: List[Plan] = Field(default_factory=list, description="セッション内で生成されたすべての長期計画のリスト")
    active_plan_id: Optional[str] = Field(default=None, description="現在アクティブな長期計画のID")

    # タスク結果管理（v3a）
    last_task_result: Optional[Dict[str, Any]] = Field(default=None, description="最新のタスク実行結果")
    last_task_timestamp: Optional[datetime] = Field(default=None, description="最新タスク結果のタイムスタンプ")

    # 既存フィールド（互換性維持）
    conversation_history: List[ConversationMessage] = Field(default_factory=list, description="対話履歴")
    current_task: Optional[str] = Field(default=None, description="現在実行中のタスク")
    task_steps: List[TaskStep] = Field(default_factory=list, description="タスクのステップ一覧")
    workspace: Optional[WorkspaceInfo] = Field(default=None, description="ワークスペース情報")
    tool_executions: List[ToolExecution] = Field(default_factory=list, description="ツール実行履歴")
    graph_state: GraphState = Field(default_factory=GraphState, description="グラフの実行状態")
    session_id: str = Field(description="セッションID")
    created_at: datetime = Field(default_factory=datetime.now, description="セッション開始時刻")
    last_activity: datetime = Field(default_factory=datetime.now, description="最終活動時刻")
    debug_mode: bool = Field(default=False, description="デバッグモード")
    auto_approve: bool = Field(default=False, description="自動承認モード")
    vitals: Vitals = Field(default_factory=Vitals, description="エージェントの健康状態バイタル")
    error_count: int = Field(default=0, description="エラー発生回数")
    last_error: Optional[str] = Field(default=None, description="最後に発生したエラー")
    retry_count: int = Field(default=0, description="リトライ回数")
    max_retries: int = Field(default=3, description="最大リトライ回数")
    history_summary: Optional[str] = Field(default=None, description="対話履歴の要約")
    summary_created_at: Optional[datetime] = Field(default=None, description="要約作成時刻")
    original_conversation_length: int = Field(default=0, description="要約前の元の対話数")
    safety_assessment: Dict[str, Any] = Field(default_factory=dict, description="安全性評価結果")
    error_analysis: Dict[str, Any] = Field(default_factory=dict, description="エラー分析結果")
    approval_result: Optional[str] = Field(default=None, description="人間承認の結果")
    collected_context: Dict[str, Any] = Field(default_factory=dict, description="収集済みコンテキスト")
    rag_context: List[Dict[str, Any]] = Field(default_factory=list, description="直近のRAG検索結果")

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """AgentStateに会話メッセージを追加"""
        message = ConversationMessage(role=role, content=content, metadata=metadata or {})
        self.conversation_history.append(message)
        self.last_activity = datetime.now()
        
        # 短期記憶に会話履歴の要約を保存
        self._update_short_term_memory_from_conversation()
        
        # 会話メッセージからコンテキストを抽出
        self._extract_context_from_message(role, content)

    def set_fixed_five(self, goal: str = "", why_now: str = "", constraints: Optional[List[str]] = None,
                       plan_brief: Optional[List[str]] = None, open_questions: Optional[List[str]] = None) -> None:
        self.goal = goal[:200]
        self.why_now = why_now[:200]
        self.constraints = (constraints or [])[:2]
        self.plan_brief = (plan_brief or [])[:3]
        self.open_questions = (open_questions or [])[:2]
        self.last_delta = "fixed_five_updated"
        
        # 短期記憶に固定5項目を保存
        self._update_short_term_memory_fixed_five()

    def set_step_status(self, step: LegacyStep, status: LegacyStatus) -> None:
        self.step = step
        self.status = status
        self.last_delta = f"step={step.value}, status={status.value}"
        
        # 短期記憶にステップ情報を保存
        self._update_short_term_memory_step_status()

    def set_task_result(self, result: Dict[str, Any]) -> None:
        """タスク結果を設定（v3a）"""
        self.last_task_result = result
        self.last_task_timestamp = datetime.now()
        self.last_delta = "task_result_updated"
        
        # 短期記憶にタスク結果を保存
        self._update_short_term_memory_task_result(result)

    def clear_task_result(self) -> None:
        """タスク結果をクリア（v3a）"""
        self.last_task_result = None
        self.last_task_timestamp = None
        self.last_delta = "task_result_cleared"
        
        # 短期記憶からタスク結果を削除
        if 'last_task_result' in self.short_term_memory:
            del self.short_term_memory['last_task_result']
        if 'last_task_timestamp' in self.short_term_memory:
            del self.short_term_memory['last_task_timestamp']

    def add_short_term_memory(self, key: str, value: Any, max_items: int = 10) -> None:
        """短期記憶に項目を追加"""
        try:
            if key not in self.short_term_memory:
                self.short_term_memory[key] = []
            
            # リスト形式で保存
            if isinstance(self.short_term_memory[key], list):
                self.short_term_memory[key].append({
                    'value': value,
                    'timestamp': datetime.now().isoformat(),
                    'step': self.step.value,
                    'status': self.status.value
                })
                
                # 最大数を制限
                if len(self.short_term_memory[key]) > max_items:
                    self.short_term_memory[key] = self.short_term_memory[key][-max_items:]
            else:
                # 単一値の場合は上書き
                self.short_term_memory[key] = {
                    'value': value,
                    'timestamp': datetime.now().isoformat(),
                    'step': self.step.value,
                    'status': self.status.value
                }
                
        except Exception as e:
            # エラー時は単純な上書き
            self.short_term_memory[key] = value

    def get_short_term_memory(self, key: str, default: Any = None) -> Any:
        """短期記憶から項目を取得"""
        try:
            if key in self.short_term_memory:
                memory_item = self.short_term_memory[key]
                
                # リスト形式の場合、最新の値を返す
                if isinstance(memory_item, list) and memory_item:
                    return memory_item[-1].get('value', default)
                # 辞書形式の場合、値を返す
                elif isinstance(memory_item, dict) and 'value' in memory_item:
                    return memory_item['value']
                # その他の場合はそのまま返す
                else:
                    return memory_item
            
            return default
            
        except Exception as e:
            return default

    def clear_short_term_memory(self, key: Optional[str] = None) -> None:
        """短期記憶をクリア"""
        if key is None:
            # 全クリア
            self.short_term_memory.clear()
        elif key in self.short_term_memory:
            # 特定のキーのみクリア
            del self.short_term_memory[key]

    def _update_short_term_memory_from_conversation(self) -> None:
        """会話履歴から短期記憶を更新"""
        try:
            if self.conversation_history:
                recent_messages = self.conversation_history[-5:]  # 最新5件
                conversation_summary = []
                
                for msg in recent_messages:
                    role = getattr(msg, 'role', 'unknown')
                    content = getattr(msg, 'content', '')
                    if content:
                        conversation_summary.append({
                            'role': role,
                            'content': content[:100] + '...' if len(content) > 100 else content,
                            'timestamp': getattr(msg, 'timestamp', datetime.now()).isoformat()
                        })
                
                self.short_term_memory['recent_conversation'] = conversation_summary
                
        except Exception as e:
            # エラー時は無視
            pass

    def _update_short_term_memory_fixed_five(self) -> None:
        """固定5項目から短期記憶を更新"""
        try:
            fixed_five = {
                'goal': self.goal,
                'why_now': self.why_now,
                'constraints': self.constraints,
                'plan_brief': self.plan_brief,
                'open_questions': self.open_questions,
                'timestamp': datetime.now().isoformat()
            }
            self.short_term_memory['fixed_five'] = fixed_five
            
        except Exception as e:
            # エラー時は無視
            pass

    def _update_short_term_memory_step_status(self) -> None:
        """ステップ・ステータスから短期記憶を更新"""
        try:
            step_status = {
                'step': self.step.value,
                'status': self.status.value,
                'timestamp': datetime.now().isoformat()
            }
            self.short_term_memory['current_step_status'] = step_status
            
        except Exception as e:
            # エラー時は無視
            pass

    def _update_short_term_memory_task_result(self, result: Dict[str, Any]) -> None:
        """タスク結果から短期記憶を更新"""
        try:
            task_memory = {
                'result': result,
                'timestamp': datetime.now().isoformat(),
                'step': self.step.value,
                'status': self.status.value
            }
            self.short_term_memory['last_task_result'] = task_memory
            
        except Exception as e:
            # エラー時は無視
            pass
    
    def add_file_content(self, file_path: str, content: str, content_type: str = "text") -> None:
        """ファイル読み込み結果を短期記憶に保存"""
        try:
            file_info = {
                'file_path': file_path,
                'content': content,  # 文字数制限を撤廃
                'content_length': len(content),
                'content_type': content_type,
                'timestamp': datetime.now().isoformat()
            }
            
            # recent_filesリストに追加
            if 'recent_files' not in self.short_term_memory:
                self.short_term_memory['recent_files'] = []
            
            self.short_term_memory['recent_files'].append(file_info)
            
            # 最新15ファイルまで保持
            if len(self.short_term_memory['recent_files']) > 15:
                self.short_term_memory['recent_files'] = self.short_term_memory['recent_files'][-15:]
            
            # current_contextに最新ファイル情報を更新
            self.short_term_memory['current_context'] = {
                'last_read_file': file_path,
                'last_read_content_type': content_type,
                'last_read_timestamp': datetime.now().isoformat(),
                'content_summary': content[:500] + "..." if len(content) > 500 else content  # サマリーは500文字制限維持
            }
            
        except Exception as e:
            # エラー時は無視
            pass
    
    def get_file_contents(self) -> Dict[str, str]:
        """保存されたファイル内容を辞書形式で取得"""
        try:
            file_contents = {}
            recent_files = self.short_term_memory.get('recent_files', [])
            
            for file_info in recent_files:
                if isinstance(file_info, dict) and 'file_path' in file_info and 'content' in file_info:
                    file_path = file_info['file_path']
                    content = file_info['content']
                    file_contents[file_path] = content
            
            return file_contents
            
        except Exception as e:
            # エラー時は空の辞書を返す
            return {}
    
    # ActionResult管理メソッド
    def add_action_result(self, action_id: str, operation: str, result: Any, 
                         action_list_id: str, sequence_number: int, 
                         metadata: Optional[Dict[str, Any]] = None) -> None:
        """アクション実行結果をshort_term_memoryに保存"""
        try:
            if 'action_results' not in self.short_term_memory:
                self.short_term_memory['action_results'] = []
            
            action_result = ActionResult(
                action_id=action_id,
                operation=operation,
                result=result,
                timestamp=datetime.now(),
                action_list_id=action_list_id,
                sequence_number=sequence_number,
                metadata=metadata or {}
            )
            
            # 辞書形式で保存
            self.short_term_memory['action_results'].append(action_result.to_dict())
            
            # 最新100件まで保持（メモリ制限）
            if len(self.short_term_memory['action_results']) > 100:
                self.short_term_memory['action_results'] = self.short_term_memory['action_results'][-100:]
            
            # ログ出力
            logger = logging.getLogger(__name__)
            logger.info(f"ActionResult保存: {action_id} ({operation}) - {action_result.get_result_summary(50)}")
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"ActionResult保存エラー: {e}")
    
    def get_action_result_by_id(self, action_id: str, action_list_id: str) -> Any:
        """特定のActionIDの結果を取得"""
        try:
            action_results = self.short_term_memory.get('action_results', [])
            
            for result_data in reversed(action_results):  # 新しいものから検索
                if (result_data['action_id'] == action_id and 
                    result_data['action_list_id'] == action_list_id):
                    logger = logging.getLogger(__name__)
                    logger.info(f"ActionID参照成功: {action_id} in {action_list_id}")
                    return result_data['result']
            
            logger = logging.getLogger(__name__)
            logger.warning(f"ActionID参照失敗: {action_id} in {action_list_id}")
            return None
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"ActionID取得エラー: {e}")
            return None
    
    def get_latest_result_by_operation(self, operation: str, max_age_minutes: int = 30) -> Any:
        """特定操作の最新結果を取得（時間制限付き）"""
        try:
            action_results = self.short_term_memory.get('action_results', [])
            cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
            
            for result_data in reversed(action_results):  # 新しいものから検索
                if result_data['operation'] == operation:
                    result_time = datetime.fromisoformat(result_data['timestamp'])
                    if result_time >= cutoff_time:
                        logger = logging.getLogger(__name__)
                        logger.info(f"最新結果取得成功: {operation}")
                        return result_data['result']
                    else:
                        logger = logging.getLogger(__name__)
                        logger.warning(f"古いデータ検出: {operation}, 実行時刻: {result_time}")
                        return None
            
            logger = logging.getLogger(__name__)
            logger.warning(f"最新結果なし: {operation} (過去{max_age_minutes}分)")
            return None
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"最新結果取得エラー: {e}")
            return None
    
    def get_action_results_by_list_id(self, action_list_id: str) -> List[Dict[str, Any]]:
        """特定のActionListの全結果を取得"""
        try:
            action_results = self.short_term_memory.get('action_results', [])
            list_results = [
                result_data for result_data in action_results 
                if result_data['action_list_id'] == action_list_id
            ]
            # sequence_numberでソート
            list_results.sort(key=lambda x: x['sequence_number'])
            return list_results
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"ActionList結果取得エラー: {e}")
            return []
    
    def cleanup_old_action_results(self, max_age_hours: int = 24) -> int:
        """古いActionResultをクリーンアップ"""
        try:
            if 'action_results' not in self.short_term_memory:
                return 0
            
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            action_results = self.short_term_memory['action_results']
            original_count = len(action_results)
            
            # 新しいもののみ保持
            self.short_term_memory['action_results'] = [
                result_data for result_data in action_results
                if datetime.fromisoformat(result_data['timestamp']) >= cutoff_time
            ]
            
            removed_count = original_count - len(self.short_term_memory['action_results'])
            
            logger = logging.getLogger(__name__)
            logger.info(f"古いActionResult削除: {removed_count}件削除, {len(self.short_term_memory['action_results'])}件残存")
            
            return removed_count
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"ActionResultクリーンアップエラー: {e}")
            return 0
    
    def update_plan_context(self, plan_id: str, context_data: Dict[str, Any]) -> None:
        """プラン関連コンテキストを更新"""
        try:
            if 'plan_context' not in self.short_term_memory:
                self.short_term_memory['plan_context'] = {}
            
            self.short_term_memory['plan_context'][plan_id] = {
                **context_data,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            # エラー時は無視
            pass
    
    def _extract_context_from_message(self, role: str, content: str) -> None:
        """会話メッセージからコンテキストを抽出"""
        try:
            # ファイル関連の言及を検出
            import re
            file_patterns = [
                r'([\w\-_./]+\.(md|py|js|ts|html|css|json|yaml|yml|txt))',
                r'`([^`]+\.(md|py|js|ts|html|css|json|yaml|yml|txt))`'
            ]
            
            mentioned_files = []
            for pattern in file_patterns:
                matches = re.findall(pattern, content.lower())
                for match in matches:
                    file_name = match[0] if isinstance(match, tuple) else match
                    mentioned_files.append(file_name)
            
            if mentioned_files:
                if 'mentioned_files' not in self.short_term_memory:
                    self.short_term_memory['mentioned_files'] = []
                
                for file_name in mentioned_files:
                    self.short_term_memory['mentioned_files'].append({
                        'file_name': file_name,
                        'mentioned_by': role,
                        'timestamp': datetime.now().isoformat()
                    })
                
                # 最新20件まで保持
                if len(self.short_term_memory['mentioned_files']) > 20:
                    self.short_term_memory['mentioned_files'] = self.short_term_memory['mentioned_files'][-20:]
            
        except Exception as e:
            # エラー時は無視
            pass

    @property
    def session_start_time(self) -> Optional[datetime]:
        """セッション開始時刻を取得（互換性のため）"""
        return self.created_at

    @property
    def current_step(self) -> str:
        """現在のステップを取得（互換性のため）"""
        return self.step.value

    @property
    def current_status(self) -> str:
        """現在のステータスを取得（互換性のため）"""
        return self.status.value

    def get_context_summary_old(self) -> Dict[str, Any]:
        """コンテキストサマリーを取得（旧版、互換性のため）"""
        return {
            "session_id": self.session_id,
            "conversation_count": len(self.conversation_history),
            "current_step": self.step.value,
            "current_status": self.status.value,
            "goal": self.goal,
            "why_now": self.why_now,
            "constraints": self.constraints,
            "plan_brief": self.plan_brief,
            "open_questions": self.open_questions,
            "last_delta": self.last_delta,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "vitals": {
                "mood": self.vitals.mood,
                "focus": self.vitals.focus,
                "stamina": self.vitals.stamina,
                "total_loops": self.vitals.total_loops,
                "error_count": self.vitals.error_count
            }
        }

    def needs_memory_management(self) -> bool:
        """記憶管理が必要かチェック"""
        return len(self.conversation_history) > 20

    def create_memory_summary(self) -> bool:
        """記憶要約を作成"""
        try:
            if len(self.conversation_history) <= 10:
                return False
            
            recent_messages = self.conversation_history[-10:]
            old_messages = self.conversation_history[:-10]
            
            if old_messages:
                summary_content = f"過去{len(old_messages)}件のメッセージを要約"
                summary_message = ConversationMessage(
                    role="system",
                    content=summary_content,
                    metadata={"type": "memory_summary", "count": len(old_messages)}
                )
                
                self.conversation_history = [summary_message] + recent_messages
                self.history_summary = summary_content
                self.summary_created_at = datetime.now()
                self.original_conversation_length = len(old_messages)
                
                return True
            
            return False
            
        except Exception:
            return False

    def get_memory_status(self) -> Dict[str, Any]:
        """記憶管理の状態を取得"""
        return {
            "total_messages": len(self.conversation_history),
            "has_summary": self.history_summary is not None,
            "summary_created_at": self.summary_created_at.isoformat() if self.summary_created_at else None,
            "original_length": self.original_conversation_length,
            "needs_management": self.needs_memory_management()
        }

    def get_recent_messages(self, count: int = 10) -> List[ConversationMessage]:
        """最近のメッセージを取得（互換API）"""
        if not self.conversation_history:
            return []
        if count <= 0:
            return []
        return self.conversation_history[-count:] if len(self.conversation_history) > count else self.conversation_history

    def get_context_summary(self) -> Dict[str, Any]:
        """LLMに渡すための、現在の状態の要約を生成する"""
        active_plan_summary = None
        if self.active_plan_id:
            plan = next((p for p in self.plans if p.plan_id == self.active_plan_id), None)
            if plan:
                active_plan_summary = {
                    "plan_id": plan.plan_id,
                    "name": plan.name,
                    "goal": plan.goal,
                    "status": plan.status,
                    "steps_total": len(plan.steps),
                    "steps_completed": sum(1 for s in plan.steps if s.status == "completed")
                }

        # 最新の会話履歴を取得、短期記憶と統合
        recent_messages = []
        if self.conversation_history:
            for msg in self.conversation_history[-3:]:  # 最新3件
                recent_messages.append({
                    "role": msg.role,
                    "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,
                    "timestamp": msg.timestamp.isoformat()
                })

        # ファイル読み込み結果を取得
        recent_files = self.short_term_memory.get("recent_files", [])
        
        return {
            "active_plan": active_plan_summary,
            "recent_conversation": recent_messages,
            "recent_files": recent_files[-3:] if recent_files else [],  # 最新3件
            "goal": self.goal,
            "why_now": self.why_now,
            "constraints": self.constraints,
            "plan_brief": self.plan_brief,
            "open_questions": self.open_questions,
            "current_step": self.step.value if self.step else "UNKNOWN",
            "current_status": self.status.value if self.status else "UNKNOWN",
            "current_context": self.short_term_memory.get("current_context", {})
        }

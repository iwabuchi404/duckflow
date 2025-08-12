"""
エージェントの状態を管理するためのデータクラス
LangGraphと統合されたステートフル処理に対応
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from .pecking_order import Task, PeckingOrderManager


class ConversationMessage(BaseModel):
    """対話メッセージを表現するクラス"""
    
    role: str = Field(description="メッセージの役割 (user, assistant, system)")
    content: str = Field(description="メッセージの内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="メッセージのタイムスタンプ")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="追加のメタデータ")


class TaskStep(BaseModel):
    """タスクステップを表現するクラス"""
    
    id: str = Field(description="ステップのID")
    description: str = Field(description="ステップの説明")
    status: str = Field(default="pending", description="ステップの状態 (pending, in_progress, completed, failed)")
    result: Optional[str] = Field(default=None, description="ステップの実行結果")
    error: Optional[str] = Field(default=None, description="エラーメッセージ")
    created_at: datetime = Field(default_factory=datetime.now, description="作成日時")
    completed_at: Optional[datetime] = Field(default=None, description="完了日時")


class WorkspaceInfo(BaseModel):
    """ワークスペース情報を表現するクラス"""
    
    path: str = Field(description="ワークスペースのパス")
    files: List[str] = Field(default_factory=list, description="ワークスペース内のファイル一覧")
    current_file: Optional[str] = Field(default=None, description="現在作業中のファイル")
    last_modified: Optional[datetime] = Field(default=None, description="最終更新日時")


class ToolExecution(BaseModel):
    """ツール実行情報を表現するクラス"""
    
    tool_name: str = Field(description="実行したツール名")
    arguments: Dict[str, Any] = Field(description="ツールの引数")
    result: Optional[Any] = Field(default=None, description="ツールの実行結果")
    error: Optional[str] = Field(default=None, description="エラーメッセージ")
    execution_time: float = Field(default=0.0, description="実行時間（秒）")
    timestamp: datetime = Field(default_factory=datetime.now, description="実行時刻")


class Vitals(BaseModel):
    """D.U.C.K. Vitals System - エージェントの健康状態を監視"""
    
    mood: float = Field(default=1.0, description="気分・機嫌 (0.0-1.0): AIの自信度・確信度")
    focus: float = Field(default=1.0, description="集中力 (0.0-1.0): 思考の一貫性・停滞度")
    stamina: float = Field(default=1.0, description="体力 (0.0-1.0): 消耗度・エラー発生による疲労")
    
    # 内部計算用フィールド
    total_loops: int = Field(default=0, description="総ループ回数")
    error_count: int = Field(default=0, description="エラー発生回数")
    last_confidence_score: float = Field(default=1.0, description="最新の自己評価スコア")
    consecutive_similar_actions: int = Field(default=0, description="連続した類似アクション回数")
    
    def update_mood(self, confidence_score: float, user_feedback: Optional[float] = None):
        """気分を更新（AIの自己評価ベース）"""
        self.last_confidence_score = confidence_score
        # 重み付け平均で更新（過去の状態も考慮）
        self.mood = 0.7 * confidence_score + 0.3 * self.mood
        if user_feedback is not None:
            self.mood = min(1.0, self.mood + user_feedback * 0.2)
        self.mood = max(0.0, min(1.0, self.mood))
    
    def update_focus(self, is_progress: bool = True, context_size: int = 0):
        """集中力を更新（思考の一貫性ベース）"""
        if is_progress:
            # 進歩があった場合は集中力上昇
            self.focus = min(1.0, self.focus + 0.1)
            self.consecutive_similar_actions = 0
        else:
            # 停滞の場合は集中力低下
            self.consecutive_similar_actions += 1
            focus_penalty = 0.15 * min(self.consecutive_similar_actions, 5)
            self.focus = max(0.0, self.focus - focus_penalty)
        
        # コンテキストサイズによる調整
        if context_size > 5000:  # 長すぎるコンテキスト
            self.focus = max(0.0, self.focus - 0.05)
    
    def update_stamina(self, had_error: bool = False):
        """体力を更新（物理的消耗ベース）"""
        self.total_loops += 1
        
        # ループ回数による消耗
        loop_penalty = 0.02 * self.total_loops
        
        # エラーによる追加消耗
        if had_error:
            self.error_count += 1
            error_penalty = 0.1 * self.error_count
        else:
            error_penalty = 0
        
        self.stamina = max(0.0, 1.0 - loop_penalty - error_penalty)
    
    def get_health_status(self) -> str:
        """健康状態の簡易診断"""
        if self.stamina < 0.1:
            return "危険状態"
        elif self.focus < 0.3:
            return "集中力低下"
        elif self.mood < 0.7:
            return "自信不足"
        elif all(v > 0.8 for v in [self.mood, self.focus, self.stamina]):
            return "絶好調"
        else:
            return "普通"
    
    def get_emoji_status(self) -> Dict[str, str]:
        """絵文字でのバイタル表示"""
        mood_emoji = "😎" if self.mood > 0.8 else "😐" if self.mood > 0.5 else "😔"
        focus_emoji = "🧘" if self.focus > 0.8 else "🤔" if self.focus > 0.5 else "😵"
        stamina_emoji = "💪" if self.stamina > 0.8 else "🤕" if self.stamina > 0.5 else "💀"
        
        return {
            "mood": mood_emoji,
            "focus": focus_emoji, 
            "stamina": stamina_emoji
        }


class GraphState(BaseModel):
    """LangGraphで使用されるグラフ状態を表現するクラス"""
    
    current_node: Optional[str] = Field(default=None, description="現在実行中のノード")
    next_nodes: List[str] = Field(default_factory=list, description="次に実行予定のノード一覧")
    execution_path: List[str] = Field(default_factory=list, description="実行済みノードのパス")
    loop_count: int = Field(default=0, description="ループ実行回数")
    max_loops: int = Field(default=5, description="最大ループ回数")


class AgentState(BaseModel):
    """エージェントの全体状態を管理するメインクラス"""
    
    # Pydanticの設定を追加してPeckingOrderManagerを許可
    model_config = {"arbitrary_types_allowed": True}
    
    # 対話履歴
    conversation_history: List[ConversationMessage] = Field(
        default_factory=list, 
        description="対話履歴"
    )
    
    # 現在のタスク
    current_task: Optional[str] = Field(default=None, description="現在実行中のタスク")
    task_steps: List[TaskStep] = Field(default_factory=list, description="タスクのステップ一覧")
    
    # ワークスペース情報
    workspace: Optional[WorkspaceInfo] = Field(default=None, description="ワークスペース情報")
    
    # ツール実行履歴
    tool_executions: List[ToolExecution] = Field(default_factory=list, description="ツール実行履歴")
    
    # LangGraphの状態管理
    graph_state: GraphState = Field(default_factory=GraphState, description="グラフの実行状態")
    
    # エージェントのメタデータ
    session_id: str = Field(description="セッションID")
    created_at: datetime = Field(default_factory=datetime.now, description="セッション開始時刻")
    last_activity: datetime = Field(default_factory=datetime.now, description="最終活動時刻")
    
    # 設定とフラグ
    debug_mode: bool = Field(default=False, description="デバッグモード")
    auto_approve: bool = Field(default=False, description="自動承認モード")
    
    # D.U.C.K. Vitals System - エージェントの健康状態監視
    vitals: Vitals = Field(default_factory=Vitals, description="エージェントの健康状態バイタル")
    
    # エラーハンドリング関連
    error_count: int = Field(default=0, description="エラー発生回数")
    last_error: Optional[str] = Field(default=None, description="最後に発生したエラー")
    retry_count: int = Field(default=0, description="リトライ回数")
    max_retries: int = Field(default=3, description="最大リトライ回数")
    
    # 記憶管理関連 (ステップ2c)
    history_summary: Optional[str] = Field(default=None, description="対話履歴の要約")
    summary_created_at: Optional[datetime] = Field(default=None, description="要約作成時刻")
    original_conversation_length: int = Field(default=0, description="要約前の元の対話数")

    # --- 追加: ランタイムで参照される可変フィールド（安全性/分析/文脈） ---
    safety_assessment: Dict[str, Any] = Field(default_factory=dict, description="安全性評価結果")
    error_analysis: Dict[str, Any] = Field(default_factory=dict, description="エラー分析結果")
    approval_result: Optional[str] = Field(default=None, description="人間承認の結果")
    collected_context: Dict[str, Any] = Field(default_factory=dict, description="収集済みコンテキスト")
    rag_context: List[Dict[str, Any]] = Field(default_factory=list, description="直近のRAG検索結果")
    
    # Phase 2: 継続ループ機能
    continuation_context: Optional[Any] = Field(default=None, description="継続実行コンテキスト")
    
    # Phase 1: 知的探索・分析エンジン
    investigation_plan: List[str] = Field(default_factory=list, description="調査対象ファイルの優先順位リスト")
    project_summary: Optional[str] = Field(default=None, description="プロジェクト統合理解結果")
    
    # The Pecking Order - 階層的タスク管理システム
    main_goal: str = Field(default="", description="メインゴール")
    task_tree: Optional[Task] = Field(default=None, description="タスク全体の階層序列")
    current_task_id: Optional[str] = Field(default=None, description="現在つついているタスクのID")
    pecking_order_manager: Optional[PeckingOrderManager] = Field(default=None, exclude=True, description="The Pecking Order管理オブジェクト")

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """対話履歴にメッセージを追加"""
        message = ConversationMessage(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.conversation_history.append(message)
        self.last_activity = datetime.now()
    
    def start_task(self, task_description: str) -> None:
        """新しいタスクを開始"""
        self.current_task = task_description
        self.task_steps.clear()
        self.last_activity = datetime.now()
    
    def add_task_step(self, step_id: str, description: str) -> TaskStep:
        """タスクステップを追加"""
        step = TaskStep(id=step_id, description=description)
        self.task_steps.append(step)
        self.last_activity = datetime.now()
        return step
    
    def update_task_step(self, step_id: str, status: str, result: Optional[str] = None, error: Optional[str] = None) -> bool:
        """タスクステップを更新"""
        for step in self.task_steps:
            if step.id == step_id:
                step.status = status
                step.result = result
                step.error = error
                if status in ["completed", "failed"]:
                    step.completed_at = datetime.now()
                self.last_activity = datetime.now()
                return True
        return False
    
    def get_recent_messages(self, count: int = 10) -> List[ConversationMessage]:
        """最近のメッセージを取得"""
        return self.conversation_history[-count:] if len(self.conversation_history) > count else self.conversation_history
    
    def get_active_task_steps(self) -> List[TaskStep]:
        """アクティブなタスクステップを取得"""
        return [step for step in self.task_steps if step.status in ["pending", "in_progress"]]
    
    def add_tool_execution(
        self, 
        tool_name: str, 
        arguments: Dict[str, Any], 
        result: Optional[Any] = None,
        error: Optional[str] = None, 
        execution_time: float = 0.0
    ) -> None:
        """ツール実行履歴を追加"""
        execution = ToolExecution(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            error=error,
            execution_time=execution_time
        )
        self.tool_executions.append(execution)
        self.last_activity = datetime.now()
    
    def update_graph_state(
        self, 
        current_node: Optional[str] = None, 
        next_nodes: Optional[List[str]] = None,
        add_to_path: Optional[str] = None
    ) -> None:
        """グラフ状態を更新"""
        if current_node is not None:
            self.graph_state.current_node = current_node
        
        if next_nodes is not None:
            self.graph_state.next_nodes = next_nodes
        
        if add_to_path is not None:
            self.graph_state.execution_path.append(add_to_path)
        
        self.last_activity = datetime.now()
    
    def increment_loop_count(self) -> bool:
        """ループカウントを増加させ、上限チェック"""
        self.graph_state.loop_count += 1
        return self.graph_state.loop_count <= self.graph_state.max_loops
    
    def record_error(self, error_message: str) -> None:
        """エラーを記録"""
        self.error_count += 1
        self.last_error = error_message
        self.last_activity = datetime.now()
    
    def increment_retry_count(self) -> bool:
        """リトライ回数を増加させ、上限チェック"""
        self.retry_count += 1
        return self.retry_count <= self.max_retries
    
    def reset_retry_count(self) -> None:
        """リトライ回数をリセット"""
        self.retry_count = 0
    
    def get_context_summary(self, max_messages: int = 5) -> Dict[str, Any]:
        """コンテキスト要約を生成（プロンプト生成用）"""
        recent_messages = self.get_recent_messages(max_messages)
        recent_tools = self.tool_executions[-5:] if len(self.tool_executions) > 5 else self.tool_executions
        
        return {
            "current_task": self.current_task,
            "recent_messages": [
                {"role": msg.role, "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content}
                for msg in recent_messages
            ],
            "active_steps": len(self.get_active_task_steps()),
            "recent_tools": [
                {"tool": te.tool_name, "success": te.error is None}
                for te in recent_tools
            ],
            "workspace_path": self.workspace.path if self.workspace else None,
            "current_file": self.workspace.current_file if self.workspace else None,
            "error_count": self.error_count,
            "last_error": self.last_error
        }
    
    def needs_memory_management(self) -> bool:
        """記憶管理が必要かどうかを判定 (ステップ2c)"""
        from ..memory.conversation_memory import conversation_memory
        return conversation_memory.should_summarize(self.conversation_history)
    
    def create_memory_summary(self) -> bool:
        """記憶要約を作成し、対話履歴を整理 (ステップ2c)"""
        try:
            from ..memory.conversation_memory import conversation_memory
            
            # 要約作成
            self.original_conversation_length = len(self.conversation_history)
            summary = conversation_memory.create_conversation_summary(
                self.conversation_history, 
                self.history_summary
            )
            
            # 履歴をトリム
            updated_summary, trimmed_messages = conversation_memory.trim_conversation_history(
                self.conversation_history, 
                summary
            )
            
            # 状態を更新
            self.history_summary = updated_summary
            self.conversation_history = trimmed_messages
            self.summary_created_at = datetime.now()
            
            return True
            
        except Exception as e:
            print(f"記憶要約作成エラー: {e}")
            return False
    
    def get_memory_context(self) -> Optional[str]:
        """記憶コンテキストを取得 (プロンプト生成用)"""
        if self.history_summary:
            context_parts = [f"**過去の対話要約:**\n{self.history_summary}"]
            
            if self.summary_created_at:
                context_parts.append(f"\n**要約作成時刻:** {self.summary_created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if self.original_conversation_length > 0:
                context_parts.append(f"**元の対話数:** {self.original_conversation_length}ターン")
            
            return "\n".join(context_parts)
        
        return None
    
    def get_memory_status(self) -> Dict[str, Any]:
        """記憶管理の状態情報を取得"""
        from ..memory.conversation_memory import conversation_memory
        
        base_status = conversation_memory.get_memory_status(
            self.conversation_history,
            self.history_summary
        )
        
        # エージェント固有の情報を追加
        base_status.update({
            "has_summary": self.history_summary is not None,
            "summary_created_at": self.summary_created_at,
            "original_length": self.original_conversation_length,
            "current_length": len(self.conversation_history)
        })
        
        return base_status
    
    # The Pecking Order 関連メソッド
    def get_pecking_order_manager(self) -> PeckingOrderManager:
        """The Pecking Order管理オブジェクトを取得する
        
        Returns:
            PeckingOrderManagerのインスタンス
        """
        if self.pecking_order_manager is None:
            self.pecking_order_manager = PeckingOrderManager(self.main_goal)
            if self.task_tree:
                self.pecking_order_manager.task_tree = self.task_tree
            if self.current_task_id:
                self.pecking_order_manager.current_task_id = self.current_task_id
        return self.pecking_order_manager
    
    def initialize_pecking_order(self, main_goal: str, root_task_description: str) -> Task:
        """The Pecking Orderを初期化する
        
        Args:
            main_goal: メインゴール
            root_task_description: ルートタスクの説明
            
        Returns:
            作成されたルートタスク
        """
        self.main_goal = main_goal
        manager = self.get_pecking_order_manager()
        manager.main_goal = main_goal
        
        root_task = manager.create_root_task(root_task_description)
        self.task_tree = root_task
        self.current_task_id = None
        
        return root_task
    
    def add_sub_task(self, parent_id: str, description: str, priority: int = 0) -> Optional[Task]:
        """サブタスクを追加する
        
        Args:
            parent_id: 親タスクのID
            description: サブタスクの説明
            priority: 優先度
            
        Returns:
            作成されたサブタスク、失敗時はNone
        """
        manager = self.get_pecking_order_manager()
        sub_task = manager.add_sub_task(parent_id, description, priority)
        
        # AgentStateの状態を同期
        if sub_task:
            self.task_tree = manager.task_tree
        
        return sub_task
    
    def start_next_task(self) -> Optional[Task]:
        """次のタスクを開始する
        
        Returns:
            開始されたタスク、ない場合はNone
        """
        manager = self.get_pecking_order_manager()
        next_task = manager.get_next_task()
        
        if next_task and manager.start_task(next_task.id):
            self.current_task_id = next_task.id
            return next_task
        
        return None
    
    def complete_current_task(self, result: Optional[str] = None) -> bool:
        """現在のタスクを完了する
        
        Args:
            result: 実行結果
            
        Returns:
            完了に成功した場合True
        """
        if not self.current_task_id:
            return False
            
        manager = self.get_pecking_order_manager()
        success = manager.complete_task(self.current_task_id, result)
        
        if success:
            # 次のタスクに自動で移行
            self.current_task_id = manager.current_task_id
        
        return success
    
    def fail_current_task(self, error: str) -> bool:
        """現在のタスクを失敗させる
        
        Args:
            error: エラーメッセージ
            
        Returns:
            失敗処理に成功した場合True
        """
        if not self.current_task_id:
            return False
            
        manager = self.get_pecking_order_manager()
        return manager.fail_task(self.current_task_id, error)
    
    def get_current_task(self) -> Optional[Task]:
        """現在実行中のタスクを取得する
        
        Returns:
            現在実行中のタスク、ない場合はNone
        """
        if not self.current_task_id:
            return None
            
        manager = self.get_pecking_order_manager()
        return manager.get_current_task()
    
    def get_pecking_order_status(self) -> Dict[str, Any]:
        """The Pecking Orderの状態サマリーを取得する
        
        Returns:
            状態サマリーの辞書
        """
        manager = self.get_pecking_order_manager()
        return manager.get_status_summary()
    
    def get_pecking_order_string(self) -> str:
        """The Pecking Orderの文字列表現を取得する
        
        Returns:
            階層構造の文字列表現
        """
        manager = self.get_pecking_order_manager()
        return manager.to_string()
    
    # Duck Pacemaker 関連メソッド
    def update_duck_vitals(
        self, 
        confidence_score: Optional[float] = None, 
        had_error: bool = False, 
        is_progress: bool = True,
        context_size: int = 0,
        user_feedback: Optional[float] = None
    ) -> None:
        """Duck Pacemakerのバイタルサインを更新
        
        Args:
            confidence_score: AIの自己評価スコア (0.0-1.0)
            had_error: エラーが発生したかどうか
            is_progress: 進歩があったかどうか
            context_size: 現在のコンテキストサイズ
            user_feedback: ユーザーからのフィードバック
        """
        if confidence_score is not None:
            self.vitals.update_mood(confidence_score, user_feedback)
        
        self.vitals.update_focus(is_progress, context_size)
        self.vitals.update_stamina(had_error)
    
    def is_duck_healthy(self) -> bool:
        """Duckの健康状態をチェック（全バイタルが基準値以上）
        
        Returns:
            健康な状態かどうか
        """
        return (
            self.vitals.mood >= 0.7 and
            self.vitals.focus >= 0.3 and
            self.vitals.stamina >= 0.1
        )
    
    def needs_duck_intervention(self) -> Dict[str, Any]:
        """Duck Pacemakerによる介入が必要かチェック
        
        Returns:
            介入の必要性と詳細情報
        """
        intervention = {
            "required": False,
            "reason": "",
            "action": "",
            "vitals_status": self.vitals.get_health_status()
        }
        
        # Stamina危険水域チェック（最優先）
        if self.vitals.stamina < 0.1:
            intervention.update({
                "required": True,
                "reason": "体力が危険水域に到達",
                "action": "HALT_AND_CONSULT",
                "priority": "CRITICAL"
            })
            return intervention
        
        # Focus低下チェック（再計画が必要）
        if self.vitals.focus < 0.3:
            intervention.update({
                "required": True,
                "reason": "集中力低下により思考が停滞",
                "action": "REPLAN",
                "priority": "HIGH"
            })
            return intervention
        
        # Mood低下チェック（相談が必要）
        if self.vitals.mood < 0.7:
            intervention.update({
                "required": True,
                "reason": "自信不足により判断が困難",
                "action": "CONSULT_USER",
                "priority": "MEDIUM"
            })
            return intervention
        
        return intervention
    
    def get_duck_status_display(self) -> str:
        """Duck Pacemakerの状態を表示用文字列で取得
        
        Returns:
            バイタル表示文字列
        """
        emojis = self.vitals.get_emoji_status()
        health_status = self.vitals.get_health_status()
        
        return f"[ Duck🦆 | Mood: {emojis['mood']}({self.vitals.mood:.2f}) | Focus: {emojis['focus']}({self.vitals.focus:.2f}) | Stamina: {emojis['stamina']}({self.vitals.stamina:.2f}) | {health_status} ]"
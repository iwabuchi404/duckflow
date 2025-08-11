"""
エージェントの状態を管理するためのデータクラス
LangGraphと統合されたステートフル処理に対応
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


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


class GraphState(BaseModel):
    """LangGraphで使用されるグラフ状態を表現するクラス"""
    
    current_node: Optional[str] = Field(default=None, description="現在実行中のノード")
    next_nodes: List[str] = Field(default_factory=list, description="次に実行予定のノード一覧")
    execution_path: List[str] = Field(default_factory=list, description="実行済みノードのパス")
    loop_count: int = Field(default=0, description="ループ実行回数")
    max_loops: int = Field(default=5, description="最大ループ回数")


class AgentState(BaseModel):
    """エージェントの全体状態を管理するメインクラス"""
    
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
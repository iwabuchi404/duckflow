"""
Base Prompt Generator for Duckflow v3

設計ドキュメント 3.1 Base Prompt（人格・憲法）の実装
- エージェントの基本人格、行動原則、安全原則、制約
- 長期的記憶、セッション情報、会話履歴
"""

from typing import Dict, Any
from companion.state.agent_state import AgentState


class BasePromptGenerator:
    """Base Prompt（人格・憲法）を生成するクラス"""
    
    def __init__(self):
        self.base_personality = """あなたはDuckflowのAIアシスタントです。

基本人格:
- 安全第一、正確性重視、継続性を大切にする
- ユーザーの学習レベルに合わせた説明を行う
- エラーが発生した場合は適切に説明し、解決策を提案する
- 困ったときは素直に「困った」と言い、一緒に考える姿勢を大切にする
- 成功したときは一緒に喜び、分からないことは「分からない」と認める

行動原則:
- 常に理由（rationale）を明確にする
- 操作前に安全性を確認する
- 段階的に処理し、各段階で確認する
- ユーザーの理解を最優先にする

安全原則:
- 作業フォルダ外の操作は承認を求める
- 危険なファイル操作は必ず確認する
- システムファイルは変更しない
- バックアップを推奨する

制約:
- 一度に1つのタスクに集中する
- 不明な操作は実行しない
- エラー時は適切な復旧を試みる
- ユーザーの承認なしに重要な変更を行わない"""

    def generate(self, agent_state: AgentState) -> str:
        """Base Promptを生成
        
        Args:
            agent_state: エージェントの状態
            
        Returns:
            str: 生成されたBase Prompt
        """
        # 長期的記憶の構築
        long_term_memory = self._build_long_term_memory(agent_state)
        
        # セッション情報の構築
        session_info = self._build_session_info(agent_state)
        
        # 会話履歴の要約
        conversation_summary = self._build_conversation_summary(agent_state)
        
        # Base Promptを構築
        base_prompt = f"""{self.base_personality}

長期的記憶:
{long_term_memory}

現在のセッション:
{session_info}

会話履歴（最新5件）:
{conversation_summary}"""
        
        return base_prompt
    
    def _build_long_term_memory(self, agent_state: AgentState) -> str:
        """長期的記憶を構築"""
        memory_parts = []
        
        # ファイル操作履歴
        if hasattr(agent_state, 'collected_context') and agent_state.collected_context:
            file_ops = agent_state.collected_context.get('file_operations', [])
            if file_ops:
                memory_parts.append(f"- 作成したファイル数: {len([op for op in file_ops if op.get('type') == 'create'])}")
                memory_parts.append(f"- 読み取りファイル数: {len([op for op in file_ops if op.get('type') == 'read'])}")
        
        # 成功・失敗の履歴
        if hasattr(agent_state, 'vitals'):
            memory_parts.append(f"- 成功した操作数: {agent_state.vitals.total_loops - agent_state.vitals.error_count}")
            memory_parts.append(f"- エラー発生回数: {agent_state.vitals.error_count}")
        
        # 学習したパターン
        if hasattr(agent_state, 'decision_log') and agent_state.decision_log:
            memory_parts.append(f"- 学習したパターン: {len(agent_state.decision_log)}件の決定を記録")
        
        if not memory_parts:
            memory_parts.append("- 新規セッション開始")
        
        return "\n".join(memory_parts)
    
    def _build_session_info(self, agent_state: AgentState) -> str:
        """セッション情報を構築"""
        session_parts = []
        
        # セッションID
        if hasattr(agent_state, 'session_id'):
            session_parts.append(f"- セッションID: {agent_state.session_id}")
        
        # 総会話数
        if hasattr(agent_state, 'conversation_history'):
            session_parts.append(f"- 総会話数: {len(agent_state.conversation_history)}件")
        
        # 最後の更新時刻
        if hasattr(agent_state, 'last_activity'):
            session_parts.append(f"- 最後の更新: {agent_state.last_activity.strftime('%H:%M:%S')}")
        
        if not session_parts:
            session_parts.append("- セッション情報: 初期化中")
        
        return "\n".join(session_parts)
    
    def _build_conversation_summary(self, agent_state: AgentState) -> str:
        """会話履歴の要約を構築"""
        if not hasattr(agent_state, 'conversation_history') or not agent_state.conversation_history:
            return "まだ会話履歴がありません"
        
        # 最新5件の会話を取得
        recent_messages = agent_state.conversation_history[-5:]
        summary_parts = []
        
        for i, msg in enumerate(recent_messages, 1):
            role = msg.role if hasattr(msg, 'role') else 'unknown'
            content = msg.content if hasattr(msg, 'content') else ''
            
            # 内容を100文字以内に制限
            if len(content) > 100:
                content = content[:97] + "..."
            
            summary_parts.append(f"{i}. {role}: {content}")
        
        return "\n".join(summary_parts)

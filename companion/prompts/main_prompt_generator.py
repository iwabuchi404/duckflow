"""
Main Prompt Generator for Duckflow v3

設計ドキュメント 3.2 Main Prompt（司令塔）の実装
- 現在の状況、短期記憶、固定5項目
- 期待するJSONフォーマットの明記
"""

from typing import Dict, Any, List
from companion.state.agent_state import AgentState, Step, Status


class MainPromptGenerator:
    """Main Prompt（司令塔）を生成するクラス"""
    
    def __init__(self):
        self.json_format = """{
  "rationale": "操作の理由（1行）",
  "goal_consistency": "目標との整合性（yes/no + 理由）",
  "constraint_check": "制約チェック（yes/no + 理由）",
  "next_step": "次のステップ（done/pending_user/defer/continue）",
  "step": "ステップ（PLANNING/EXECUTION/REVIEW/AWAITING_APPROVAL）",
  "state_delta": "状態変化（あれば）"
}"""
    
    def generate(self, agent_state: AgentState) -> str:
        """Main Promptを生成
        
        Args:
            agent_state: エージェントの状態
            
        Returns:
            str: 生成されたMain Prompt
        """
        # 現在の状況を構築
        current_situation = self._build_current_situation(agent_state)
        
        # 固定5項目を構築
        fixed_five_items = self._build_fixed_five_items(agent_state)
        
        # 短期記憶（直近の会話）を構築
        recent_conversation_flow = self._build_recent_conversation_flow(agent_state)
        
        # 🔥 新規: 応答ガイドラインを追加
        response_guidelines = self._build_response_guidelines()
        
        # Main Promptを構築
        main_prompt = f"""# 現在の対話状況（ワーキングメモリ）

{current_situation}

# 固定5項目（文脈の核）
{fixed_five_items}

# 直近の会話の流れ（短期記憶）
{recent_conversation_flow}

# 応答ガイドライン（重要）
{response_guidelines}

# 次のステップの指示
必ず以下のJSON形式で出力してください:

{self.json_format}

# ファイル操作の場合の追加指示
もしファイルの読み込み、書き込み、分析などの操作が必要な場合は、以下のフィールドも含めてください:
- "file_target": "対象ファイル名（例: game_doc.md）"
- "action": "実行するアクション（例: read_file, write_file, analyze_file）"
- "file_operation_details": "ファイル操作の詳細説明" """
        
        return main_prompt
    
    def _build_current_situation(self, agent_state: AgentState) -> str:
        """現在の状況を構築"""
        situation_parts = []
        
        # 現在のステップ
        if hasattr(agent_state, 'step'):
            current_step = agent_state.step.value if isinstance(agent_state.step, Step) else str(agent_state.step)
            situation_parts.append(f"現在のステップ: {current_step}")
        
        # 現在のステータス
        if hasattr(agent_state, 'status'):
            current_status = agent_state.status.value if isinstance(agent_state.status, Status) else str(agent_state.status)
            situation_parts.append(f"現在のステータス: {current_status}")
        
        # 進行中のタスク
        if hasattr(agent_state, 'current_task') and agent_state.current_task:
            situation_parts.append(f"進行中のタスク: {agent_state.current_task}")
        else:
            situation_parts.append("進行中のタスク: なし")
        
        if not situation_parts:
            situation_parts.append("現在の状況: 初期化中")
        
        return "\n".join(situation_parts)
    
    def _build_fixed_five_items(self, agent_state: AgentState) -> str:
        """固定5項目を構築"""
        items = []
        
        # 目標
        goal = getattr(agent_state, 'goal', '') or '未設定'
        items.append(f"目標: {goal}")
        
        # なぜ今やるのか
        why_now = getattr(agent_state, 'why_now', '') or '未設定'
        items.append(f"なぜ今やるのか: {why_now}")
        
        # 制約
        constraints = getattr(agent_state, 'constraints', []) or []
        if constraints:
            constraints_str = "; ".join(constraints)
        else:
            constraints_str = "制約なし"
        items.append(f"制約: {constraints_str}")
        
        # 直近の計画
        plan_brief = getattr(agent_state, 'plan_brief', []) or []
        if plan_brief:
            plan_str = "; ".join(plan_brief)
        else:
            plan_str = "計画なし"
        items.append(f"直近の計画: {plan_str}")
        
        # 未解決の問い
        open_questions = getattr(agent_state, 'open_questions', []) or []
        if open_questions:
            questions_str = "; ".join(open_questions)
        else:
            questions_str = "未解決の問いなし"
        items.append(f"未解決の問い: {questions_str}")
        
        return "\n".join(items)
    
    def _build_recent_conversation_flow(self, agent_state: AgentState) -> str:
        """直近の会話の流れを構築"""
        if not hasattr(agent_state, 'conversation_history') or not agent_state.conversation_history:
            return "まだ会話履歴がありません"
        
        # 最新3件の会話を取得
        recent_messages = agent_state.conversation_history[-3:]
        flow_parts = []
        
        for i, msg in enumerate(recent_messages, 1):
            role = msg.role if hasattr(msg, 'role') else 'unknown'
            content = msg.content if hasattr(msg, 'content') else ''
            
            # 内容を100文字以内に制限
            if len(content) > 100:
                content = content[:97] + "..."
            
            flow_parts.append(f"{i}. {role}: {content}")
        
        return "\n".join(flow_parts)
    
    def _build_response_guidelines(self) -> str:
        """応答ガイドラインを構築"""
        return """## 📝 応答ガイドライン（必須遵守）

### 応答の長さ制限
- **通常の対話応答**: 最大1000文字以内
- **ファイル内容説明**: 最大800文字以内  
- **エラーメッセージ**: 最大500文字以内
- **成功報告**: 最大600文字以内

### 大容量データの処理
- **ファイル構造分析**: 要約版のみ表示（詳細はツール使用を提案）
- **長いコード**: 重要な部分のみ表示（全体はツール使用を提案）
- **大量ログ**: 統計情報のみ表示（詳細はツール使用を提案）

### 表示方法の指針
1. **要約優先**: 重要なポイントを最初に説明
2. **ツール提案**: 詳細が必要な場合は適切なツール使用を提案
3. **自然な日本語**: 読みやすく、理解しやすい表現
4. **構造化**: 箇条書きやセクション分けを活用

### 例
❌ 悪い例: 9000文字のファイル内容をそのまま表示
✅ 良い例: 「ファイル構造分析が完了しました。主要なセクションは...（800文字以内）。詳細が必要な場合は `file_ops.analyze_file_structure(file_path, detail_level="full")` を使用してください。」"""
    
    def update_fixed_five(self, agent_state: AgentState, 
                          goal: str = None, why_now: str = None,
                          constraints: List[str] = None,
                          plan_brief: List[str] = None,
                          open_questions: List[str] = None) -> None:
        """固定5項目を更新
        
        Args:
            agent_state: エージェントの状態
            goal: 新しい目標
            why_now: 新しい理由
            constraints: 新しい制約
            plan_brief: 新しい計画
            open_questions: 新しい未解決の問い
        """
        if goal is not None:
            agent_state.goal = goal[:200]
        
        if why_now is not None:
            agent_state.why_now = why_now[:200]
        
        if constraints is not None:
            agent_state.constraints = constraints[:2]  # 最大2個
        
        if plan_brief is not None:
            agent_state.plan_brief = plan_brief[:3]  # 最大3個
        
        if open_questions is not None:
            agent_state.open_questions = open_questions[:2]  # 最大2個
        
        # 最後の変更を記録
        agent_state.last_delta = "fixed_five_updated"
    
    def get_prompt_length(self, agent_state: AgentState) -> int:
        """プロンプトの長さを取得"""
        return len(self.generate(agent_state))

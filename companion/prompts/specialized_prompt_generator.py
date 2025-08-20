"""
Specialized Prompt Generator for Duckflow v3

設計ドキュメント 3.3 Specialized Prompt（手順書）の実装
- PLANNING用: 計画作成の手順、品質基準、出力形式
- EXECUTION用: 実行の手順、安全性チェック、進捗管理
- REVIEW用: レビューの観点、評価基準、改善提案
"""

from typing import Dict, Any, Optional
from companion.state.agent_state import AgentState, Step


class SpecializedPromptGenerator:
    """Specialized Prompt（手順書）を生成するクラス"""
    
    def __init__(self):
        self.planning_template = """# 計画作成の専門知識・手順書

## 計画作成の手順
1. 要求の分析と分解（最大3つのステップ）
2. 必要なリソースの特定
3. リスク評価（低/中/高）
4. 成功基準の設定（具体的で測定可能）

## 出力形式
```
プラン名: [プランの名称]
目的: [達成したいこと]
ステップ:
  1. [ステップ1の詳細]
  2. [ステップ2の詳細]
  3. [ステップ3の詳細]
リスク: [想定されるリスク]
成功基準: [成功の判断基準]
```

## 品質基準
- 各ステップは具体的で実行可能
- リスクは適切に評価されている
- 成功基準は測定可能
- 制約を考慮している"""

        self.execution_template = """# 実行の専門知識・手順書

## 実行の手順
1. 計画の確認と準備
2. 安全性チェック（ファイル操作、システム影響）
3. 段階的な実行と進捗確認
4. エラーハンドリングと復旧

## 安全性チェック項目
- ファイル操作の安全性（パス、権限、バックアップ）
- システムへの影響（リソース、依存関係）
- データの整合性（入力値、出力値）

## 進捗管理
- 各ステップの完了確認
- エラー発生時の適切な処理
- ユーザーへの進捗報告

## 出力形式
```
実行結果: [成功/部分成功/失敗]
完了ステップ: [完了したステップ数/総ステップ数]
エラー: [発生したエラー（あれば）]
次のアクション: [推奨する次のアクション]
```"""

        self.review_template = """# レビューの専門知識・手順書

## レビューの観点
1. 内容の正確性（仕様との一致）
2. 安全性（リスクの評価）
3. 品質（パフォーマンス、保守性）
4. 改善点（効率化、最適化）

## 評価基準
- 良い: 仕様を満たし、安全で高品質
- 普通: 基本的な要求は満たしている
- 要改善: 問題があり、修正が必要

## 出力形式
```
評価: [良い/普通/要改善]
問題点: [発見された問題]
改善提案: [具体的な改善案]
承認可否: [承認/要修正/拒否]
```"""

    def generate(self, step: Step, agent_state: Optional[AgentState] = None) -> str:
        """Specialized Promptを生成
        
        Args:
            step: 現在のステップ
            agent_state: エージェントの状態（オプション）
            
        Returns:
            str: 生成されたSpecialized Prompt
        """
        if step == Step.PLANNING:
            return self._generate_planning_prompt(agent_state)
        elif step == Step.EXECUTION:
            return self._generate_execution_prompt(agent_state)
        elif step == Step.REVIEW:
            return self._generate_review_prompt(agent_state)
        else:
            return self._generate_generic_prompt(step, agent_state)
    
    def _generate_planning_prompt(self, agent_state: Optional[AgentState] = None) -> str:
        """PLANNING用のプロンプトを生成"""
        context_info = self._extract_context_info(agent_state, "planning")
        
        return f"""{self.planning_template}

## 現在のコンテキスト
{context_info}

## 注意事項
- 既存の制約を必ず考慮する
- リスクが高い場合は承認プロセスを含める
- ユーザーの理解レベルに合わせた説明を心がける"""
    
    def _generate_execution_prompt(self, agent_state: Optional[AgentState] = None) -> str:
        """EXECUTION用のプロンプトを生成"""
        context_info = self._extract_context_info(agent_state, "execution")
        
        return f"""{self.execution_template}

## 現在のコンテキスト
{context_info}

## 注意事項
- 安全性を最優先にする
- 各ステップで確認を取る
- エラー時は適切な復旧を試みる
- ユーザーへの進捗報告を忘れない"""
    
    def _generate_review_prompt(self, agent_state: Optional[AgentState] = None) -> str:
        """REVIEW用のプロンプトを生成"""
        context_info = self._extract_context_info(agent_state, "review")
        
        return f"""{self.review_template}

## 現在のコンテキスト
{context_info}

## 注意事項
- 客観的な評価を心がける
- 改善点は具体的に提案する
- 安全性の観点を重視する
- ユーザーの理解を促進する"""
    
    def _generate_generic_prompt(self, step: Step, agent_state: Optional[AgentState] = None) -> str:
        """汎用のプロンプトを生成"""
        context_info = self._extract_context_info(agent_state, "generic")
        
        return f"""# {step.value}用の専門知識・手順書

## 現在のステップ
{step.value}

## 基本的な手順
1. 現在の状況を確認
2. 必要な情報を収集
3. 適切な処理を実行
4. 結果を確認・報告

## 現在のコンテキスト
{context_info}

## 注意事項
- 安全性を最優先にする
- 段階的に処理する
- エラー時は適切に対応する
- ユーザーへの報告を忘れない"""
    
    def _extract_context_info(self, agent_state: Optional[AgentState], context_type: str) -> str:
        """コンテキスト情報を抽出"""
        if not agent_state:
            return "コンテキスト情報: 利用不可"
        
        context_parts = []
        
        # 基本情報
        if hasattr(agent_state, 'current_task') and agent_state.current_task:
            context_parts.append(f"現在のタスク: {agent_state.current_task}")
        
        # 固定5項目から関連情報を抽出
        if context_type == "planning":
            if hasattr(agent_state, 'goal') and agent_state.goal:
                context_parts.append(f"目標: {agent_state.goal}")
            if hasattr(agent_state, 'constraints') and agent_state.constraints:
                context_parts.append(f"制約: {'; '.join(agent_state.constraints)}")
        
        elif context_type == "execution":
            if hasattr(agent_state, 'plan_brief') and agent_state.plan_brief:
                context_parts.append(f"実行計画: {'; '.join(agent_state.plan_brief)}")
        
        elif context_type == "review":
            if hasattr(agent_state, 'plan_brief') and agent_state.plan_brief:
                context_parts.append(f"レビュー対象: {'; '.join(agent_state.plan_brief)}")
        
        # ファイル操作履歴
        if hasattr(agent_state, 'collected_context') and agent_state.collected_context:
            file_ops = agent_state.collected_context.get('file_operations', [])
            if file_ops:
                recent_ops = file_ops[-3:]  # 最新3件
                op_summaries = []
                for op in recent_ops:
                    if isinstance(op, dict):
                        op_type = op.get('type', 'unknown')
                        op_path = op.get('path', 'unknown')
                        op_summaries.append(f"{op_type}: {op_path}")
                
                if op_summaries:
                    context_parts.append(f"最近の操作: {'; '.join(op_summaries)}")
        
        if not context_parts:
            context_parts.append("コンテキスト情報: 基本情報のみ")
        
        return "\n".join(context_parts)
    
    def get_prompt_length(self, step: Step, agent_state: Optional[AgentState] = None) -> int:
        """プロンプトの長さを取得"""
        return len(self.generate(step, agent_state))

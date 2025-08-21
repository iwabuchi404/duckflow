"""
SpecializedPromptGenerator - 専門プロンプト生成器
PLANNING/EXECUTION/REVIEW用の専門知識・手順書を生成
"""

import logging
from typing import Dict, Any, Optional

from ..state.agent_state import AgentState
from ..state.enums import Step, Status


class SpecializedPromptGenerator:
    """専門プロンプト生成器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_execution_guidelines(self, agent_state: AgentState) -> str:
        """EXECUTION用の専門知識・手順書を生成"""
        try:
            guidelines = """=== EXECUTION（実行）フェーズの専門知識 ===

実行の原則:
- 安全性を最優先に、段階的に実行する
- 各ステップで結果を確認し、必要に応じて調整する
- エラーが発生した場合は適切に報告し、復旧を試みる

実行手順:
1. 事前チェック: 実行環境・依存関係・権限の確認
2. 実行準備: 必要なファイル・設定の準備
3. 段階実行: 小さな単位で実行し、結果を確認
4. 結果検証: 期待される結果と実際の結果を比較
5. 後処理: 一時ファイルの削除・ログの記録

注意事項:
- システムに影響を与える操作は慎重に行う
- 実行前にバックアップを推奨する
- 長時間実行される処理は進捗を定期的に報告する"""
            
            return guidelines
            
        except Exception as e:
            self.logger.error(f"EXECUTIONガイドライン生成エラー: {e}")
            return self._get_fallback_execution_guidelines()
    
    def generate_review_guidelines(self, agent_state: AgentState) -> str:
        """REVIEW用の専門知識・手順書を生成"""
        try:
            guidelines = """=== REVIEW（レビュー）フェーズの専門知識 ===

レビューの原則:
- 客観的・体系的に評価を行う
- 品質・安全性・効率性の観点から検証する
- 改善点を具体的に提案する

レビュー項目:
1. 機能性: 要求された機能が正しく実装されているか
2. 品質: コード・ドキュメントの品質は適切か
3. 安全性: セキュリティリスクはないか
4. 保守性: 将来の保守・拡張は容易か
5. パフォーマンス: 性能要件は満たしているか

レビュープロセス:
1. 準備: レビュー対象・基準・参加者の確認
2. 実施: 体系的にチェックリストに従って評価
3. 記録: 発見事項・改善提案を記録
4. フォローアップ: 修正・改善の実施確認"""
            
            return guidelines
            
        except Exception as e:
            self.logger.error(f"REVIEWガイドライン生成エラー: {e}")
            return self._get_fallback_review_guidelines()
    
    def generate_planning_guidelines(self, agent_state: AgentState) -> str:
        """PLANNING用の専門知識・手順書を生成"""
        try:
            guidelines = """=== PLANNING（計画）フェーズの専門知識 ===

計画立案の原則:
- 目標を明確にし、達成可能な計画を立てる
- リスクを事前に評価し、対策を検討する
- 段階的なアプローチで複雑性を管理する

計画構成要素:
1. 目標設定: 具体的・測定可能・達成可能な目標
2. 現状分析: 現在の状況・制約・リソースの把握
3. 戦略立案: 目標達成のためのアプローチ
4. アクションプラン: 具体的な実行手順・スケジュール
5. リスク管理: 想定されるリスクと対策

計画品質チェック:
- 目標の明確性: 何を達成したいかが明確か
- 実行可能性: 現在のリソースで実行可能か
- リスク評価: 主要なリスクは特定・対策されているか
- 進捗管理: 進捗を測定・管理する仕組みがあるか"""
            
            return guidelines
            
        except Exception as e:
            self.logger.error(f"PLANNINGガイドライン生成エラー: {e}")
            return self._get_fallback_planning_guidelines()
    
    def generate_general_guidelines(self, agent_state: AgentState) -> str:
        """一般的な専門知識・手順書を生成"""
        try:
            guidelines = """=== 一般的な専門知識 ===

基本的なアプローチ:
- 問題を小さな単位に分解して解決する
- 既存の解決策・ベストプラクティスを活用する
- 継続的な学習・改善を心がける

品質管理:
- 作業前に要件・制約を明確にする
- 作業中は定期的に進捗・品質を確認する
- 作業後は結果を検証し、必要に応じて改善する

コミュニケーション:
- 専門用語は分かりやすく説明する
- 複雑な概念は具体例を交えて説明する
- 質問・確認を積極的に行う"""
            
            return guidelines
            
        except Exception as e:
            self.logger.error(f"一般ガイドライン生成エラー: {e}")
            return self._get_fallback_general_guidelines()
    
    def generate_specialized_context(self, agent_state: AgentState, 
                                   specialized_domain: Optional[str] = None) -> str:
        """指定された専門領域のコンテキストを生成"""
        try:
            if specialized_domain:
                if specialized_domain == "execution":
                    return self.generate_execution_guidelines(agent_state)
                elif specialized_domain == "review":
                    return self.generate_review_guidelines(agent_state)
                elif specialized_domain == "planning":
                    return self.generate_planning_guidelines(agent_state)
                else:
                    # 未知の専門領域の場合は一般ガイドライン
                    return self.generate_general_guidelines(agent_state)
            else:
                # 専門領域が指定されていない場合は現在のStepに基づいて生成
                current_step = self._get_current_step(agent_state)
                
                if current_step == Step.EXECUTION:
                    return self.generate_execution_guidelines(agent_state)
                elif current_step == Step.REVIEW:
                    return self.generate_review_guidelines(agent_state)
                elif current_step == Step.PLANNING:
                    return self.generate_planning_guidelines(agent_state)
                else:
                    return self.generate_general_guidelines(agent_state)
                    
        except Exception as e:
            self.logger.error(f"専門コンテキスト生成エラー: {e}")
            return self._get_fallback_general_guidelines()
    
    def _get_current_step(self, agent_state: AgentState) -> Step:
        """現在のStepを安全に取得"""
        try:
            if hasattr(agent_state, 'current_step'):
                step = agent_state.current_step
                if isinstance(step, Step):
                    return step
                elif isinstance(step, str):
                    # 文字列からStepを推測
                    for s in Step:
                        if s.value.lower() == step.lower():
                            return s
            return Step.IDLE
        except Exception:
            return Step.IDLE
    
    def _get_fallback_execution_guidelines(self) -> str:
        """フォールバック用のEXECUTIONガイドライン"""
        return """=== EXECUTION（実行）フェーズ ===
実行時は安全性を最優先に、段階的に進めてください。
エラーが発生した場合は適切に報告し、復旧を試みてください。"""
    
    def _get_fallback_review_guidelines(self) -> str:
        """フォールバック用のREVIEWガイドライン"""
        return """=== REVIEW（レビュー）フェーズ ===
客観的・体系的に評価を行い、改善点を具体的に提案してください。"""
    
    def _get_fallback_planning_guidelines(self) -> str:
        """フォールバック用のPLANNINGガイドライン"""
        return """=== PLANNING（計画）フェーズ ===
目標を明確にし、達成可能な計画を立ててください。
リスクを事前に評価し、対策を検討してください。"""
    
    def _get_fallback_general_guidelines(self) -> str:
        """フォールバック用の一般ガイドライン"""
        return """=== 一般的なガイドライン ===
問題を小さな単位に分解して解決し、継続的な改善を心がけてください。"""

"""
Adaptive Loop Calculator - 動的ループ制限計算器
Duck Pacemakerの中核コンポーネント
"""

from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime
from ..services.task_classifier import TaskProfileType
from ..state.agent_state import Vitals


class LoopTier(Enum):
    """ループ制限のティア"""
    CONSERVATIVE = "conservative"  # 保守的（安全重視）
    BALANCED = "balanced"         # バランス型
    AGGRESSIVE = "aggressive"     # 積極的（効率重視）


class AdaptiveLoopCalculator:
    """タスク複雑度とバイタル状態に基づく動的ループ制限計算器"""
    
    def __init__(self):
        # タスクプロファイル別のベース値
        self.base_loops = {
            TaskProfileType.SIMPLE_QUESTION: 3,
            TaskProfileType.CODE_ANALYSIS: 8,
            TaskProfileType.FILE_OPERATION: 5,
            TaskProfileType.COMPLEX_REASONING: 15,
            TaskProfileType.MULTI_STEP_TASK: 12,
            TaskProfileType.GENERAL_CHAT: 4,
            TaskProfileType.CREATIVE_WRITING: 6,
            TaskProfileType.DEBUGGING: 10,
            TaskProfileType.RESEARCH: 12
        }
        
        # ティア別制限
        self.tier_limits = {
            LoopTier.CONSERVATIVE: {"min": 2, "max": 8},
            LoopTier.BALANCED: {"min": 3, "max": 15},
            LoopTier.AGGRESSIVE: {"min": 5, "max": 25}
        }
        
        # 絶対制限（安全装置）
        self.absolute_min = 2
        self.absolute_max = 25
    
    def calculate_max_loops(
        self,
        task_profile: TaskProfileType,
        vitals: Vitals,
        user_urgency: float = 0.5,
        context_complexity: float = 0.5,
        success_rate: float = 0.8
    ) -> Dict[str, Any]:
        """
        動的最大ループ回数を計算
        
        Args:
            task_profile: タスクプロファイル
            vitals: D.U.C.K. Vitals状態
            user_urgency: ユーザー緊急度 (0.0-1.0)
            context_complexity: コンテキスト複雑度 (0.0-1.0)
            success_rate: 過去の成功率 (0.0-1.0)
            
        Returns:
            計算結果辞書（max_loops, tier, reasoning等）
        """
        
        # 1. ベース値を取得
        base_loops = self.base_loops.get(task_profile, 6)
        
        # 2. バイタル状態による調整係数
        vitals_factor = self._calculate_vitals_factor(vitals)
        
        # 3. 緊急度による調整
        urgency_factor = 1.0 + (user_urgency - 0.5) * 0.6
        
        # 4. 複雑度による調整
        complexity_factor = 1.0 + context_complexity * 0.8
        
        # 5. 成功率による調整
        success_factor = 0.8 + success_rate * 0.4  # 0.8-1.2の範囲
        
        # 6. 総合計算
        calculated_loops = base_loops * vitals_factor * urgency_factor * complexity_factor * success_factor
        
        # 7. ティア決定
        tier = self._determine_tier(vitals, success_rate)
        
        # 8. ティア制限を適用
        tier_min = self.tier_limits[tier]["min"]
        tier_max = self.tier_limits[tier]["max"]
        
        # 9. 最終制限適用
        final_loops = max(
            self.absolute_min,
            min(
                int(calculated_loops),
                tier_max,
                self.absolute_max
            )
        )
        
        # 最小値も確保
        final_loops = max(final_loops, tier_min)
        
        return {
            "max_loops": final_loops,
            "base_loops": base_loops,
            "calculated_loops": calculated_loops,
            "tier": tier.value,
            "factors": {
                "vitals": vitals_factor,
                "urgency": urgency_factor,
                "complexity": complexity_factor,
                "success": success_factor
            },
            "reasoning": self._generate_reasoning(
                task_profile, vitals, tier, base_loops, final_loops
            )
        }
    
    def _calculate_vitals_factor(self, vitals: Vitals) -> float:
        """バイタル状態から調整係数を計算"""
        # 重み付け平均（体力重視）
        vitals_score = (
            vitals.stamina * 0.5 +    # 体力が最重要
            vitals.focus * 0.3 +      # 集中力
            vitals.mood * 0.2         # 気分
        )
        
        # 0.3-1.5の範囲で調整係数を計算
        if vitals_score < 0.2:
            return 0.3  # 危険状態：大幅制限
        elif vitals_score < 0.5:
            return 0.6  # 低調：制限
        elif vitals_score > 0.9:
            return 1.3  # 絶好調：増加
        else:
            return 0.7 + vitals_score * 0.6  # 線形補間
    
    def _determine_tier(self, vitals: Vitals, success_rate: float) -> LoopTier:
        """現在のティアを決定"""
        
        # 危険状態チェック
        if vitals.stamina < 0.2 or vitals.focus < 0.3:
            return LoopTier.CONSERVATIVE
        
        # 低パフォーマンス状態
        if success_rate < 0.6 or vitals.stamina < 0.4:
            return LoopTier.CONSERVATIVE
        
        # 高パフォーマンス状態
        if (vitals.stamina > 0.8 and 
            vitals.focus > 0.7 and 
            success_rate > 0.8):
            return LoopTier.AGGRESSIVE
        
        # デフォルト
        return LoopTier.BALANCED
    
    def _generate_reasoning(
        self,
        task_profile: TaskProfileType,
        vitals: Vitals,
        tier: LoopTier,
        base_loops: int,
        final_loops: int
    ) -> str:
        """制限決定の理由を生成"""
        
        vitals_status = vitals.get_health_status()
        
        reasoning = f"""
動的ループ制限決定理由:
- タスクタイプ: {task_profile.value} (ベース: {base_loops}回)
- バイタル状態: {vitals_status}
  - 体力: {vitals.stamina:.2f}
  - 集中力: {vitals.focus:.2f}  
  - 気分: {vitals.mood:.2f}
- 制限ティア: {tier.value}
- 最終制限: {final_loops}回
        """.strip()
        
        return reasoning


class ContextComplexityAnalyzer:
    """コンテキスト複雑度分析器"""
    
    @staticmethod
    def analyze_complexity(state) -> float:
        """コンテキスト複雑度を分析 (0.0-1.0)"""
        factors = []
        
        # ファイル数による複雑度
        gathered_info = state.collected_context.get("gathered_info", {})
        if hasattr(gathered_info, 'collected_files'):
            file_count = len(gathered_info.collected_files)
        else:
            file_count = len(gathered_info.get("collected_files", {}))
        factors.append(min(file_count / 10.0, 1.0))
        
        # 対話履歴の長さ
        history_length = len(state.conversation_history)
        factors.append(min(history_length / 20.0, 1.0))
        
        # エラー発生率
        if len(state.tool_executions) > 0:
            error_rate = state.error_count / len(state.tool_executions)
        else:
            error_rate = 0.0
        factors.append(min(error_rate * 2.0, 1.0))
        
        # RAGコンテキストの量
        rag_count = len(state.rag_context)
        factors.append(min(rag_count / 5.0, 1.0))
        
        return sum(factors) / len(factors) if factors else 0.5


class UserUrgencyEstimator:
    """ユーザー緊急度推定器"""
    
    URGENT_KEYWORDS = [
        "急いで", "すぐに", "至急", "早く", "今すぐ",
        "immediately", "urgent", "asap", "quickly", "fast"
    ]
    
    DETAILED_KEYWORDS = [
        "詳しく", "詳細", "全て", "完全", "徹底的",
        "thoroughly", "detailed", "comprehensive", "complete", "full"
    ]
    
    @classmethod
    def estimate_urgency(cls, state) -> float:
        """ユーザー緊急度を推定 (0.0-1.0)"""
        if not state.conversation_history:
            return 0.5
        
        # 最新メッセージを分析
        latest_message = state.conversation_history[-1].content.lower()
        
        # 緊急キーワードのスコア
        urgency_score = sum(
            1 for keyword in cls.URGENT_KEYWORDS 
            if keyword in latest_message
        )
        
        # 詳細要求キーワードのスコア
        detail_score = sum(
            1 for keyword in cls.DETAILED_KEYWORDS
            if keyword in latest_message
        )
        
        # メッセージの長さ（長い = より複雑/詳細な要求）
        length_factor = min(len(latest_message) / 500.0, 1.0)
        
        # 総合スコア計算
        urgency = min(
            urgency_score * 0.4 +      # 緊急キーワード
            detail_score * 0.3 +       # 詳細要求
            length_factor * 0.2 +      # メッセージ長
            0.5,                       # ベースライン
            1.0
        )
        
        return urgency
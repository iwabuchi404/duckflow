"""
Simple Loop Calculator - シンプル制限計算器
Duck Pacemakerの動的ループ制限計算の中核コンポーネント
"""

from typing import Dict, Any
from enum import Enum
import logging

from ..services.task_classifier import TaskProfileType
from ..state.agent_state import Vitals

logger = logging.getLogger(__name__)


class SimpleLoopCalculator:
    """シンプルな動的ループ制限計算器
    
    設計原則:
    - シンプル第一: 複雑な機能より確実な動作を優先
    - 設定値の分散改善: タスク特性に応じた適切な制限
    - 透明性: 制限決定理由の明確な説明
    """
    
    def __init__(self):
        """計算器を初期化"""
        
        # タスクプロファイル別ベース値（設定値の分散改善）
        self.base_loops = {
            TaskProfileType.INFORMATION_REQUEST: 5,      # 情報要求：確実な情報提供のため余裕を持たせる
            TaskProfileType.ANALYSIS_REQUEST: 12,        # 分析要求：詳細分析→問題特定→報告の多段階処理
            TaskProfileType.CREATION_REQUEST: 10,        # 作成要求：設計→実装→検証の創作プロセス
            TaskProfileType.MODIFICATION_REQUEST: 8,     # 修正要求：理解→変更→確認→検証の流れ
            TaskProfileType.SEARCH_REQUEST: 6,           # 検索要求：探索→発見→整理の流れ
            TaskProfileType.GUIDANCE_REQUEST: 7,         # ガイダンス要求：理解→手順作成→説明
            TaskProfileType.FILE_ANALYSIS: 12,           # ファイル分析：読取→構造理解→分析→報告
            TaskProfileType.CODE_EXPLANATION: 8,         # コード説明：理解→解析→説明の流れ
            TaskProfileType.PROJECT_EXPLORATION: 14,     # プロジェクト探索：全体把握→詳細調査→統合理解
            TaskProfileType.DEBUGGING_SUPPORT: 16,       # デバッグ支援：問題再現→原因特定→解決策→テスト
            TaskProfileType.IMPLEMENTATION_TASK: 18,     # 実装タスク：要求分析→設計→実装→テスト→統合
            TaskProfileType.CONSULTATION: 9,             # 相談：状況理解→分析→選択肢提示→推奨
            TaskProfileType.GENERAL_CHAT: 6              # 一般対話：理解→考慮→応答の基本パターン
        }
        
        # 制限範囲
        self.min_loops = 3
        self.max_loops = 20
        
        logger.info("SimpleLoopCalculator初期化完了")
    
    def calculate_max_loops(
        self,
        task_profile: TaskProfileType,
        vitals: Vitals,
        context_complexity: float = 0.3
    ) -> Dict[str, Any]:
        """動的制限を計算
        
        Args:
            task_profile: タスクプロファイル
            vitals: D.U.C.K. Vitals状態
            context_complexity: コンテキスト複雑度 (0.0-1.0)
            
        Returns:
            計算結果辞書（max_loops, reasoning等）
        """
        try:
            # ベース値取得
            base_loops = self.base_loops.get(task_profile, 8)
            
            # バイタル係数計算
            vitals_factor = self._calculate_vitals_factor(vitals)
            
            # 複雑度係数計算
            complexity_factor = self._calculate_complexity_factor(context_complexity)
            
            # 最終計算
            calculated = base_loops * vitals_factor * complexity_factor
            final_loops = max(self.min_loops, min(int(calculated), self.max_loops))
            
            # 詳細な理由説明を生成
            reasoning = self._generate_detailed_reasoning(
                task_profile, base_loops, vitals, vitals_factor,
                context_complexity, complexity_factor, final_loops
            )
            
            result = {
                "max_loops": final_loops,
                "base_loops": base_loops,
                "vitals_factor": vitals_factor,
                "complexity_factor": complexity_factor,
                "calculated_raw": calculated,
                "reasoning": reasoning
            }
            
            logger.info(f"動的制限計算完了: {task_profile.value} -> {final_loops}回")
            return result
            
        except Exception as e:
            logger.error(f"動的制限計算エラー: {e}")
            raise
    
    def _calculate_vitals_factor(self, vitals: Vitals) -> float:
        """バイタル係数を計算
        
        D.U.C.K. Vitalsの正しい解釈:
        - mood = AIのプランに関する自信
        - focus = AIの思考の一貫性
        - stamina = 1タスクの試行回数（消耗度）
        
        Args:
            vitals: バイタル状態
            
        Returns:
            バイタル係数 (0.7-1.2の範囲)
        """
        # シンプルな重み付け平均
        vitals_score = (
            vitals.mood * 0.4 +      # プラン自信度：重要（40%）
            vitals.focus * 0.4 +     # 思考一貫性：重要（40%）
            vitals.stamina * 0.2     # 試行回数消耗：補助（20%）
        )
        
        # シンプルな3段階調整
        if vitals_score < 0.4:
            return 0.7  # 低調：制限
        elif vitals_score > 0.8:
            return 1.2  # 好調：増加
        else:
            return 1.0  # 普通：そのまま
    
    def _calculate_complexity_factor(self, context_complexity: float) -> float:
        """複雑度係数を計算
        
        Args:
            context_complexity: コンテキスト複雑度 (0.0-1.0)
            
        Returns:
            複雑度係数 (1.0-1.4の範囲)
        """
        # タスク複雑度に応じたシンプルな調整（控えめ）
        return 1.0 + context_complexity * 0.4
    
    def _generate_detailed_reasoning(
        self,
        task_profile: TaskProfileType,
        base_loops: int,
        vitals: Vitals,
        vitals_factor: float,
        context_complexity: float,
        complexity_factor: float,
        final_loops: int
    ) -> str:
        """制限決定の詳細な理由を生成
        
        Args:
            task_profile: タスクプロファイル
            base_loops: ベースループ数
            vitals: バイタル状態
            vitals_factor: バイタル係数
            context_complexity: コンテキスト複雑度
            complexity_factor: 複雑度係数
            final_loops: 最終制限
            
        Returns:
            詳細な理由説明文
        """
        # バイタル状態の説明
        vitals_status = []
        if vitals.mood < 0.5:
            vitals_status.append("プラン自信度が低下")
        elif vitals.mood > 0.8:
            vitals_status.append("プラン自信度が高い")
        
        if vitals.focus < 0.5:
            vitals_status.append("思考一貫性が低下")
        elif vitals.focus > 0.8:
            vitals_status.append("思考一貫性が良好")
        
        if vitals.stamina < 0.5:
            vitals_status.append("試行回数による消耗あり")
        elif vitals.stamina > 0.8:
            vitals_status.append("試行回数による消耗少ない")
        
        vitals_description = "、".join(vitals_status) if vitals_status else "標準的な状態"
        
        # 複雑度の説明
        if context_complexity < 0.3:
            complexity_description = "低複雑度（シンプルなタスク）"
        elif context_complexity > 0.7:
            complexity_description = "高複雑度（多ファイル・長履歴・エラー多発）"
        else:
            complexity_description = "中程度の複雑度"
        
        # 調整の説明
        adjustment_explanation = []
        if vitals_factor < 1.0:
            adjustment_explanation.append(f"バイタル状態により{int((1-vitals_factor)*100)}%制限")
        elif vitals_factor > 1.0:
            adjustment_explanation.append(f"バイタル状態により{int((vitals_factor-1)*100)}%増加")
        
        if complexity_factor > 1.0:
            adjustment_explanation.append(f"複雑度により{int((complexity_factor-1)*100)}%増加")
        
        adjustment_text = "、".join(adjustment_explanation) if adjustment_explanation else "調整なし"
        
        return f"""
🦆 Duck Pacemaker 制限決定理由:

📋 タスク分析:
  種別: {task_profile.value}
  ベース制限: {base_loops}回

🩺 バイタル診断:
  プラン自信度: {vitals.mood:.2f}
  思考一貫性: {vitals.focus:.2f}
  試行消耗度: {vitals.stamina:.2f}
  状態: {vitals_description}

🔍 コンテキスト分析:
  複雑度: {context_complexity:.2f} ({complexity_description})

⚙️ 制限計算:
  {base_loops}回 × {vitals_factor:.1f} × {complexity_factor:.1f} = {final_loops}回
  調整内容: {adjustment_text}

🎯 最終制限: {final_loops}回 (範囲: {self.min_loops}-{self.max_loops}回)
        """.strip()
    
    def get_base_loops(self, task_profile: TaskProfileType) -> int:
        """タスクプロファイルのベース値を取得
        
        Args:
            task_profile: タスクプロファイル
            
        Returns:
            ベースループ数
        """
        return self.base_loops.get(task_profile, 8)
    
    def get_supported_task_profiles(self) -> list:
        """サポートされているタスクプロファイル一覧を取得
        
        Returns:
            サポートされているタスクプロファイルのリスト
        """
        return list(self.base_loops.keys())
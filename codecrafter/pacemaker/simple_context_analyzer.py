"""
Simple Context Analyzer - シンプルコンテキスト分析器
タスクの複雑度を分析してDuck Pacemakerの制限計算に使用
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class SimpleContextAnalyzer:
    """シンプルなコンテキスト複雑度分析器
    
    設計原則:
    - シンプルで確実な分析
    - 3つの主要要素による複雑度計算
    - 0.0-1.0の正規化されたスコア
    """
    
    @staticmethod
    def analyze_complexity(state) -> float:
        """コンテキスト複雑度を分析
        
        Args:
            state: AgentState オブジェクト
            
        Returns:
            複雑度スコア (0.0-1.0)
        """
        try:
            factors = []
            
            # ファイル数による複雑度（シンプル）
            file_complexity = SimpleContextAnalyzer._analyze_file_complexity(state)
            factors.append(file_complexity)
            
            # 対話履歴の長さ（シンプル）
            history_complexity = SimpleContextAnalyzer._analyze_history_complexity(state)
            factors.append(history_complexity)
            
            # エラー発生率（シンプル）
            error_complexity = SimpleContextAnalyzer._analyze_error_complexity(state)
            factors.append(error_complexity)
            
            # 総合複雑度スコア計算
            if factors:
                complexity_score = sum(factors) / len(factors)
            else:
                complexity_score = 0.3  # デフォルト値
            
            # 0.0-1.0の範囲に正規化
            complexity_score = max(0.0, min(complexity_score, 1.0))
            
            logger.debug(f"複雑度分析完了: {complexity_score:.2f} (ファイル: {file_complexity:.2f}, 履歴: {history_complexity:.2f}, エラー: {error_complexity:.2f})")
            
            return complexity_score
            
        except Exception as e:
            logger.error(f"複雑度分析エラー: {e}")
            return 0.3  # エラー時のデフォルト値
    
    @staticmethod
    def _analyze_file_complexity(state) -> float:
        """ファイル数による複雑度を分析
        
        Args:
            state: AgentState オブジェクト
            
        Returns:
            ファイル複雑度 (0.0-1.0)
        """
        try:
            # collected_contextからファイル情報を取得
            gathered_info = state.collected_context.get("gathered_info", {})
            
            if hasattr(gathered_info, 'collected_files'):
                # GatheredInfoオブジェクトの場合
                file_count = len(gathered_info.collected_files)
            elif isinstance(gathered_info, dict):
                # 辞書の場合
                collected_files = gathered_info.get("collected_files", {})
                file_count = len(collected_files)
            else:
                file_count = 0
            
            # 8ファイルで最大複雑度に到達
            file_complexity = min(file_count / 8.0, 1.0)
            
            logger.debug(f"ファイル複雑度: {file_count}ファイル -> {file_complexity:.2f}")
            return file_complexity
            
        except Exception as e:
            logger.warning(f"ファイル複雑度分析エラー: {e}")
            return 0.0
    
    @staticmethod
    def _analyze_history_complexity(state) -> float:
        """対話履歴の長さによる複雑度を分析
        
        Args:
            state: AgentState オブジェクト
            
        Returns:
            履歴複雑度 (0.0-1.0)
        """
        try:
            history_length = len(state.conversation_history)
            
            # 15ターンで最大複雑度に到達
            history_complexity = min(history_length / 15.0, 1.0)
            
            logger.debug(f"履歴複雑度: {history_length}ターン -> {history_complexity:.2f}")
            return history_complexity
            
        except Exception as e:
            logger.warning(f"履歴複雑度分析エラー: {e}")
            return 0.0
    
    @staticmethod
    def _analyze_error_complexity(state) -> float:
        """エラー発生率による複雑度を分析
        
        Args:
            state: AgentState オブジェクト
            
        Returns:
            エラー複雑度 (0.0-1.0)
        """
        try:
            if len(state.tool_executions) > 0:
                error_rate = state.error_count / len(state.tool_executions)
                # エラー率33%で最大複雑度に到達
                error_complexity = min(error_rate * 3.0, 1.0)
            else:
                error_complexity = 0.0
            
            logger.debug(f"エラー複雑度: {state.error_count}/{len(state.tool_executions)} -> {error_complexity:.2f}")
            return error_complexity
            
        except Exception as e:
            logger.warning(f"エラー複雑度分析エラー: {e}")
            return 0.0
    
    @staticmethod
    def get_complexity_description(complexity_score: float) -> str:
        """複雑度スコアの説明文を取得
        
        Args:
            complexity_score: 複雑度スコア (0.0-1.0)
            
        Returns:
            複雑度の説明文
        """
        if complexity_score < 0.3:
            return "低複雑度（シンプルなタスク）"
        elif complexity_score > 0.7:
            return "高複雑度（多ファイル・長履歴・エラー多発）"
        else:
            return "中程度の複雑度"
    
    @staticmethod
    def get_detailed_analysis(state) -> Dict[str, Any]:
        """詳細な複雑度分析結果を取得
        
        Args:
            state: AgentState オブジェクト
            
        Returns:
            詳細分析結果の辞書
        """
        try:
            file_complexity = SimpleContextAnalyzer._analyze_file_complexity(state)
            history_complexity = SimpleContextAnalyzer._analyze_history_complexity(state)
            error_complexity = SimpleContextAnalyzer._analyze_error_complexity(state)
            
            overall_complexity = (file_complexity + history_complexity + error_complexity) / 3
            
            return {
                "overall_complexity": overall_complexity,
                "file_complexity": file_complexity,
                "history_complexity": history_complexity,
                "error_complexity": error_complexity,
                "description": SimpleContextAnalyzer.get_complexity_description(overall_complexity),
                "factors": {
                    "file_count": len(state.collected_context.get("gathered_info", {}).get("collected_files", {})),
                    "history_length": len(state.conversation_history),
                    "error_count": state.error_count,
                    "tool_executions": len(state.tool_executions)
                }
            }
            
        except Exception as e:
            logger.error(f"詳細複雑度分析エラー: {e}")
            return {
                "overall_complexity": 0.3,
                "file_complexity": 0.0,
                "history_complexity": 0.0,
                "error_complexity": 0.0,
                "description": "分析エラー（デフォルト値使用）",
                "factors": {
                    "file_count": 0,
                    "history_length": 0,
                    "error_count": 0,
                    "tool_executions": 0
                }
            }
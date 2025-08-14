"""
Simple Fallback - シンプルフォールバック機能
動的制限計算が失敗した場合の1段階フォールバック
"""

import logging
from typing import Dict, Any, Optional

from ..services.task_classifier import TaskProfileType
from ..state.agent_state import Vitals

logger = logging.getLogger(__name__)


class SimpleFallback:
    """シンプルなフォールバック機能
    
    設計原則:
    - 1段階のシンプルなフォールバック
    - 設定ファイルからの最大値取得
    - 確実な動作を保証
    """
    
    def __init__(self):
        """フォールバック機能を初期化"""
        self.final_fallback_value = 15  # 最終フォールバック値
        logger.info("SimpleFallback初期化完了")
    
    def calculate_with_fallback(
        self,
        calculator,
        task_profile: TaskProfileType,
        vitals: Vitals,
        complexity: float
    ) -> Dict[str, Any]:
        """フォールバック付きで動的制限を計算
        
        Args:
            calculator: SimpleLoopCalculator インスタンス
            task_profile: タスクプロファイル
            vitals: バイタル状態
            complexity: コンテキスト複雑度
            
        Returns:
            計算結果辞書またはフォールバック結果
        """
        try:
            # メイン計算を試行
            result = calculator.calculate_max_loops(task_profile, vitals, complexity)
            logger.debug(f"メイン計算成功: {result['max_loops']}回")
            return result
            
        except Exception as e:
            # フォールバック実行
            logger.warning(f"動的計算失敗、フォールバック実行: {e}")
            return self._execute_fallback(task_profile)
    
    def _execute_fallback(self, task_profile: TaskProfileType) -> Dict[str, Any]:
        """フォールバック処理を実行
        
        Args:
            task_profile: タスクプロファイル
            
        Returns:
            フォールバック結果辞書
        """
        try:
            # 設定ファイルから最大値を取得
            config_max_loops = self._get_config_max_loops()
            
            if config_max_loops is not None:
                logger.info(f"設定ファイルフォールバック: {config_max_loops}回")
                return {
                    "max_loops": config_max_loops,
                    "fallback_used": "config_file",
                    "reasoning": f"動的計算失敗のため設定ファイルの最大値を使用: {config_max_loops}回"
                }
            else:
                # 最終フォールバック
                logger.warning(f"最終フォールバック: {self.final_fallback_value}回")
                return {
                    "max_loops": self.final_fallback_value,
                    "fallback_used": "final_default",
                    "reasoning": f"全ての計算が失敗したため最終デフォルト値を使用: {self.final_fallback_value}回"
                }
                
        except Exception as e:
            # 最終的な安全装置
            logger.error(f"フォールバック処理もエラー: {e}")
            return {
                "max_loops": self.final_fallback_value,
                "fallback_used": "emergency",
                "reasoning": f"緊急フォールバック: {self.final_fallback_value}回"
            }
    
    def _get_config_max_loops(self) -> Optional[int]:
        """設定ファイルから最大ループ数を取得
        
        Returns:
            設定ファイルの最大ループ数、取得失敗時はNone
        """
        try:
            from ..base.config import config_manager
            config = config_manager.load_config()
            
            # duck_pacemaker設定が存在するかチェック
            if hasattr(config, 'duck_pacemaker') and config.duck_pacemaker:
                if hasattr(config.duck_pacemaker, 'dynamic_limits') and config.duck_pacemaker.dynamic_limits:
                    max_loops = config.duck_pacemaker.dynamic_limits.max_loops
                    if isinstance(max_loops, int) and max_loops > 0:
                        return max_loops
            
            # 従来のgraph_state設定をチェック
            if hasattr(config, 'graph_state') and config.graph_state:
                max_loops = getattr(config.graph_state, 'max_loops', None)
                if isinstance(max_loops, int) and max_loops > 0:
                    return max_loops
            
            logger.debug("設定ファイルに最大ループ数の設定が見つかりません")
            return None
            
        except ImportError:
            logger.warning("config_managerのインポートに失敗")
            return None
        except Exception as e:
            logger.warning(f"設定ファイル読み込みエラー: {e}")
            return None
    
    def get_fallback_info(self) -> Dict[str, Any]:
        """フォールバック機能の情報を取得
        
        Returns:
            フォールバック機能の情報辞書
        """
        config_max = self._get_config_max_loops()
        
        return {
            "final_fallback_value": self.final_fallback_value,
            "config_max_loops": config_max,
            "fallback_available": True,
            "fallback_levels": [
                "設定ファイルの最大値",
                f"最終デフォルト値 ({self.final_fallback_value}回)"
            ]
        }
    
    def test_fallback(self) -> Dict[str, Any]:
        """フォールバック機能のテスト
        
        Returns:
            テスト結果辞書
        """
        try:
            # 設定ファイル読み込みテスト
            config_max = self._get_config_max_loops()
            config_test = "成功" if config_max is not None else "失敗（デフォルト値使用）"
            
            # フォールバック実行テスト
            fallback_result = self._execute_fallback(TaskProfileType.GENERAL_CHAT)
            fallback_test = "成功" if fallback_result["max_loops"] > 0 else "失敗"
            
            return {
                "config_file_test": config_test,
                "config_max_loops": config_max,
                "fallback_execution_test": fallback_test,
                "fallback_result": fallback_result,
                "final_fallback_value": self.final_fallback_value,
                "overall_status": "正常" if fallback_test == "成功" else "異常"
            }
            
        except Exception as e:
            logger.error(f"フォールバックテストエラー: {e}")
            return {
                "config_file_test": "エラー",
                "fallback_execution_test": "エラー",
                "error": str(e),
                "overall_status": "異常"
            }
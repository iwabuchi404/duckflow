"""
Simple Dynamic Pacemaker - シンプル動的Duck Pacemaker
確実に動作するシンプルな動的制限システム
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..services.task_classifier import TaskProfileType
from ..state.agent_state import AgentState
from .simple_loop_calculator import SimpleLoopCalculator
from .simple_context_analyzer import SimpleContextAnalyzer
from .simple_fallback import SimpleFallback

logger = logging.getLogger(__name__)


class SimpleDynamicPacemaker:
    """シンプルな動的Duck Pacemaker
    
    設計原則:
    - シンプル第一: 複雑な機能より確実な動作を優先
    - 設定値の分散改善: タスク特性に応じた適切な制限
    - 透明性: 制限決定理由の明確な説明
    """
    
    def __init__(self):
        """シンプル動的Duck Pacemakerを初期化"""
        self.calculator = SimpleLoopCalculator()
        self.fallback = SimpleFallback()
        
        # セッション管理（シンプル版）
        self.current_session_id: Optional[str] = None
        self.session_start_time: Optional[datetime] = None
        
        logger.info("SimpleDynamicPacemaker初期化完了")
    
    def start_session(
        self,
        state: AgentState,
        task_profile: TaskProfileType
    ) -> Dict[str, Any]:
        """セッション開始と動的制限設定
        
        Args:
            state: AgentState インスタンス
            task_profile: タスクプロファイル
            
        Returns:
            動的制限設定結果
        """
        try:
            self.session_start_time = datetime.now()
            self.current_session_id = f"session_{self.session_start_time.strftime('%Y%m%d_%H%M%S')}"
            
            logger.info(f"セッション開始: {self.current_session_id}, タスク: {task_profile.value}")
            
            # コンテキスト複雑度分析
            complexity = SimpleContextAnalyzer.analyze_complexity(state)
            
            # 動的制限計算（フォールバック付き）
            calculation_result = self.fallback.calculate_with_fallback(
                calculator=self.calculator,
                task_profile=task_profile,
                vitals=state.vitals,
                complexity=complexity
            )
            
            # 状態更新
            new_max_loops = calculation_result["max_loops"]
            state.graph_state.max_loops = new_max_loops
            
            # 結果の構築
            result = {
                "max_loops": new_max_loops,
                "task_profile": task_profile.value,
                "context_complexity": complexity,
                "calculation_result": calculation_result,
                "session_id": self.current_session_id,
                "timestamp": self.session_start_time.isoformat()
            }
            
            # ログ出力
            if "fallback_used" in calculation_result:
                logger.warning(f"フォールバック使用: {calculation_result['fallback_used']}, 制限: {new_max_loops}回")
            else:
                logger.info(f"動的制限設定完了: {task_profile.value}, 制限: {new_max_loops}回, 複雑度: {complexity:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"セッション開始エラー: {e}")
            # 緊急フォールバック
            emergency_loops = 10
            state.graph_state.max_loops = emergency_loops
            return {
                "max_loops": emergency_loops,
                "error": str(e),
                "emergency_fallback": True,
                "reasoning": f"セッション開始エラーのため緊急フォールバック: {emergency_loops}回"
            }
    
    def update_during_execution(
        self,
        state: AgentState,
        current_loop: int
    ) -> Dict[str, Any]:
        """実行中の動的更新
        
        Args:
            state: AgentState インスタンス
            current_loop: 現在のループ数
            
        Returns:
            更新結果辞書
        """
        try:
            # 進捗率計算
            progress_rate = current_loop / state.graph_state.max_loops if state.graph_state.max_loops > 0 else 0
            
            # バイタル状態チェック
            vitals_status = state.vitals.get_health_status()
            
            # 介入判定
            intervention = state.needs_duck_intervention()
            
            result = {
                "current_loop": current_loop,
                "max_loops": state.graph_state.max_loops,
                "progress_rate": progress_rate,
                "vitals_status": vitals_status,
                "intervention_required": intervention["required"],
                "intervention_details": intervention if intervention["required"] else None,
                "timestamp": datetime.now().isoformat()
            }
            
            # 推奨アクションの決定
            if intervention["required"]:
                result["recommendation"] = "INTERVENTION_REQUIRED"
                logger.warning(f"介入必要: {intervention['reason']}")
            elif progress_rate > 0.8 and vitals_status in ["絶好調", "普通"]:
                result["recommendation"] = "CONSIDER_COMPLETION"
                logger.info("完了検討を推奨")
            else:
                result["recommendation"] = "CONTINUE"
                logger.debug(f"継続推奨: ループ{current_loop}/{state.graph_state.max_loops}")
            
            return result
            
        except Exception as e:
            logger.error(f"実行中更新エラー: {e}")
            return {
                "current_loop": current_loop,
                "error": str(e),
                "recommendation": "CONTINUE"
            }
    
    def end_session(
        self,
        state: AgentState,
        success: bool,
        loops_used: Optional[int] = None
    ) -> Dict[str, Any]:
        """セッション終了処理
        
        Args:
            state: AgentState インスタンス
            success: 成功/失敗
            loops_used: 使用されたループ数
            
        Returns:
            セッション終了結果
        """
        try:
            if not self.current_session_id:
                logger.warning("セッションが開始されていません")
                return {"error": "セッション未開始"}
            
            end_time = datetime.now()
            execution_time = (end_time - self.session_start_time).total_seconds() if self.session_start_time else 0
            
            actual_loops_used = loops_used if loops_used is not None else state.graph_state.loop_count
            max_loops_set = state.graph_state.max_loops
            
            # 効率性計算
            efficiency = actual_loops_used / max_loops_set if max_loops_set > 0 else 0
            
            result = {
                "session_id": self.current_session_id,
                "success": success,
                "loops_used": actual_loops_used,
                "max_loops_set": max_loops_set,
                "efficiency": efficiency,
                "execution_time": execution_time,
                "final_vitals": {
                    "mood": state.vitals.mood,
                    "focus": state.vitals.focus,
                    "stamina": state.vitals.stamina
                },
                "end_time": end_time.isoformat()
            }
            
            # ログ出力
            status_text = "成功" if success else "失敗"
            logger.info(f"セッション終了: {self.current_session_id}, {status_text}, {actual_loops_used}/{max_loops_set}回使用, 効率: {efficiency:.1%}")
            
            # セッション情報をリセット
            self.current_session_id = None
            self.session_start_time = None
            
            return result
            
        except Exception as e:
            logger.error(f"セッション終了エラー: {e}")
            return {
                "error": str(e),
                "success": success
            }
    
    def get_system_info(self) -> Dict[str, Any]:
        """システム情報を取得
        
        Returns:
            システム情報辞書
        """
        try:
            return {
                "system_name": "SimpleDynamicPacemaker",
                "version": "1.0",
                "components": {
                    "calculator": "SimpleLoopCalculator",
                    "analyzer": "SimpleContextAnalyzer", 
                    "fallback": "SimpleFallback"
                },
                "supported_task_profiles": [tp.value for tp in self.calculator.get_supported_task_profiles()],
                "fallback_info": self.fallback.get_fallback_info(),
                "current_session": {
                    "active": self.current_session_id is not None,
                    "session_id": self.current_session_id,
                    "start_time": self.session_start_time.isoformat() if self.session_start_time else None
                }
            }
            
        except Exception as e:
            logger.error(f"システム情報取得エラー: {e}")
            return {
                "system_name": "SimpleDynamicPacemaker",
                "error": str(e)
            }
    
    def test_system(self) -> Dict[str, Any]:
        """システム全体のテスト
        
        Returns:
            テスト結果辞書
        """
        try:
            test_results = {}
            
            # 計算器テスト
            from ..state.agent_state import Vitals
            test_vitals = Vitals(mood=0.8, focus=0.7, stamina=0.9)
            calc_result = self.calculator.calculate_max_loops(
                TaskProfileType.GENERAL_CHAT, test_vitals, 0.5
            )
            test_results["calculator_test"] = "成功" if calc_result["max_loops"] > 0 else "失敗"
            
            # フォールバックテスト
            fallback_result = self.fallback.test_fallback()
            test_results["fallback_test"] = fallback_result["overall_status"]
            
            # 複雑度分析テスト（モックデータ）
            class MockState:
                def __init__(self):
                    self.collected_context = {"gathered_info": {"collected_files": {}}}
                    self.conversation_history = []
                    self.error_count = 0
                    self.tool_executions = []
            
            mock_state = MockState()
            complexity = SimpleContextAnalyzer.analyze_complexity(mock_state)
            test_results["analyzer_test"] = "成功" if 0 <= complexity <= 1 else "失敗"
            
            # 総合判定
            all_tests_passed = all(result == "成功" or result == "正常" for result in test_results.values())
            test_results["overall_status"] = "正常" if all_tests_passed else "異常"
            
            return test_results
            
        except Exception as e:
            logger.error(f"システムテストエラー: {e}")
            return {
                "overall_status": "異常",
                "error": str(e)
            }
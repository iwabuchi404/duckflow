"""
PromptSmith オーケストレーター

3つのAI（Tester、Target、Optimizer）を協調させて
プロンプトの自動改善サイクルを実行します。
"""

import json
import time
import statistics
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path

# 既存のDuckflowコンポーネントをインポート
try:
    from tests.sandbox.sandbox_framework import SandboxTestRunner
    from tests.sandbox.evaluation_engine import EvaluationEngine, MetricsCollector
except ImportError:
    print("Warning: Duckflow components not available. Using mock implementations.")
    SandboxTestRunner = None
    EvaluationEngine = None
    MetricsCollector = None

# PromptSmithコンポーネントをインポート
from .prompt_manager import PromptManager, PromptVersion
from .ai_roles.tester_ai import TesterAI, ChallengeScenario
from .ai_roles.optimizer_ai import OptimizerAI
from .ai_roles.conversation_analyzer import ConversationAnalyzer
from .improvement_engine import ImprovementEngine, ImprovementPlan


@dataclass
class ImprovementCycle:
    """改善サイクルの記録"""
    cycle_id: str
    start_time: datetime
    end_time: Optional[datetime]
    prompt_version_before: str
    prompt_version_after: Optional[str]
    test_scenarios: List[str]
    performance_before: Dict[str, float]
    performance_after: Optional[Dict[str, float]]
    improvements_applied: List[str]
    success: bool
    error_message: Optional[str] = None


@dataclass  
class CycleResults:
    """改善サイクルの結果"""
    cycle_info: ImprovementCycle
    scenario_results: List[Dict[str, Any]]
    analysis_results: Dict[str, Any]
    improvement_suggestions: List[Any]
    final_metrics: Dict[str, float]
    recommendations: List[str]


class PromptSmithOrchestrator:
    """3つのAIを協調させる改善サイクル制御"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        オーケストレーターの初期化
        
        Args:
            config: 設定パラメータ
        """
        self.config = config or self._get_default_config()
        
        # コンポーネント初期化
        self.prompt_manager = PromptManager()
        self.tester_ai = TesterAI()
        self.optimizer_ai = OptimizerAI()
        self.conversation_analyzer = ConversationAnalyzer()
        self.improvement_engine = ImprovementEngine()
        
        # Duckflow統合（利用可能な場合）
        self.sandbox_runner = SandboxTestRunner() if SandboxTestRunner else None
        self.evaluation_engine = EvaluationEngine() if EvaluationEngine else None
        
        # 実行履歴
        self.cycle_history: List[ImprovementCycle] = []
        self.results_storage = Path(self.config.get("results_storage", "promptsmith_results"))
        self.results_storage.mkdir(exist_ok=True)
        
        print("PromptSmith オーケストレーター初期化完了")
    
    def run_improvement_cycle(self, iterations: int = 3, 
                             difficulty: str = "medium",
                             auto_apply: bool = False) -> CycleResults:
        """
        1サイクルの改善プロセス実行
        
        Args:
            iterations: テストイテレーション数
            difficulty: テスト難易度
            auto_apply: 自動適用フラグ
            
        Returns:
            改善サイクルの結果
        """
        cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\n{'='*60}")
        print(f"PromptSmith 改善サイクル開始: {cycle_id}")
        print(f"{'='*60}")
        
        cycle = ImprovementCycle(
            cycle_id=cycle_id,
            start_time=datetime.now(),
            end_time=None,
            prompt_version_before=self._get_current_prompt_version(),
            prompt_version_after=None,
            test_scenarios=[],
            performance_before={},
            performance_after={},
            improvements_applied=[],
            success=False
        )
        
        try:
            # Phase 1: ベースライン性能測定
            print("\n[PHASE 1] ベースライン性能測定")
            baseline_performance = self._measure_baseline_performance(cycle_id)
            cycle.performance_before = baseline_performance
            print(f"ベースライン性能: {baseline_performance}")
            
            # Phase 2: 挑戦的シナリオ生成・実行
            print("\n[PHASE 2] 挑戦的シナリオ生成・実行")
            scenario_results = self._run_challenging_scenarios(iterations, difficulty, cycle_id)
            cycle.test_scenarios = [result["scenario_name"] for result in scenario_results]
            print(f"実行シナリオ: {len(scenario_results)}個")
            
            # Phase 3: 結果分析・弱点抽出
            print("\n[PHASE 3] 結果分析・弱点抽出")
            analysis_results = self._analyze_results(scenario_results, baseline_performance)
            print(f"分析完了 - 弱点パターン: {len(analysis_results.get('weakness_patterns', []))}個")
            
            # Phase 4: 改善提案生成
            print("\n[PHASE 4] 改善提案生成")
            improvement_suggestions = self._generate_improvements(analysis_results)
            print(f"改善提案: {len(improvement_suggestions)}個")
            
            # Phase 5: 改善適用
            print("\n[PHASE 5] 改善適用")
            if improvement_suggestions:
                applied_improvements = self._apply_improvements(improvement_suggestions, auto_apply)
                cycle.improvements_applied = applied_improvements
                
                if applied_improvements:
                    # Phase 6: 改善後性能測定
                    print("\n[PHASE 6] 改善後性能測定")
                    improved_performance = self._measure_improved_performance(cycle_id)
                    cycle.performance_after = improved_performance
                    cycle.prompt_version_after = self._get_current_prompt_version()
                    
                    print(f"改善後性能: {improved_performance}")
                    
                    # 改善効果の評価
                    improvement_effect = self._calculate_improvement_effect(
                        baseline_performance, improved_performance
                    )
                    print(f"改善効果: {improvement_effect}")
                    
                    cycle.success = improvement_effect.get("overall_improvement", 0) > 0
                else:
                    print("改善が適用されませんでした（承認待ちまたは安全性の問題）")
            else:
                print("改善提案が生成されませんでした")
            
            # サイクル完了
            cycle.end_time = datetime.now()
            execution_time = (cycle.end_time - cycle.start_time).total_seconds()
            
            print(f"\n[COMPLETE] 改善サイクル完了")
            print(f"実行時間: {execution_time:.2f}秒")
            print(f"成功: {'Yes' if cycle.success else 'No'}")
            
            # 結果サマリー作成
            results = CycleResults(
                cycle_info=cycle,
                scenario_results=scenario_results,
                analysis_results=analysis_results,
                improvement_suggestions=improvement_suggestions,
                final_metrics=cycle.performance_after or cycle.performance_before,
                recommendations=self._generate_recommendations(analysis_results, cycle.success)
            )
            
            # 履歴に追加・保存
            self.cycle_history.append(cycle)
            self._save_cycle_results(results)
            
            return results
            
        except Exception as e:
            cycle.end_time = datetime.now()
            cycle.error_message = str(e)
            cycle.success = False
            
            print(f"\n[ERROR] 改善サイクル中にエラーが発生: {e}")
            
            # エラー時の結果も保存
            error_results = CycleResults(
                cycle_info=cycle,
                scenario_results=[],
                analysis_results={},
                improvement_suggestions=[],
                final_metrics={},
                recommendations=[f"エラーが発生しました: {e}"]
            )
            
            self.cycle_history.append(cycle)
            return error_results
    
    def evaluate_prompt_performance(self, prompt_version: Optional[str] = None,
                                  test_count: int = 5) -> Dict[str, Any]:
        """
        プロンプトバージョンの性能評価
        
        Args:
            prompt_version: 評価するプロンプトバージョン（Noneで現行バージョン）
            test_count: テスト実行回数
            
        Returns:
            性能評価結果
        """
        print(f"\n{'='*50}")
        print(f"プロンプト性能評価開始")
        print(f"{'='*50}")
        
        # 指定バージョンに切り替え（必要な場合）
        original_version = None
        if prompt_version and prompt_version != self._get_current_prompt_version():
            original_version = self._get_current_prompt_version()
            self.prompt_manager.apply_version(prompt_version)
            print(f"プロンプトバージョン切り替え: {prompt_version}")
        
        try:
            # 標準シナリオでのテスト実行
            if self.sandbox_runner:
                print("\nDuckflow サンドボックステスト実行中...")
                sandbox_results = self.sandbox_runner.run_all_scenarios()
                
                performance_metrics = {
                    "overall_score": sandbox_results.get("average_score", 0),
                    "success_rate": sandbox_results.get("success_rate", 0),
                    "total_scenarios": sandbox_results.get("total_scenarios", 0),
                    "execution_time": sandbox_results.get("total_execution_time", 0)
                }
                
                # 詳細メトリクス
                scenario_results = sandbox_results.get("scenario_results", {})
                detailed_metrics = {}
                
                for scenario_name, result in scenario_results.items():
                    detailed_metrics[scenario_name] = {
                        "score": result.get("score", 0),
                        "passed": result.get("passed", False),
                        "execution_time": result.get("execution_time", 0)
                    }
                
                print(f"性能評価完了:")
                print(f"  総合スコア: {performance_metrics['overall_score']:.1f}")
                print(f"  成功率: {performance_metrics['success_rate']*100:.1f}%")
                print(f"  実行シナリオ数: {performance_metrics['total_scenarios']}")
                
                return {
                    "prompt_version": prompt_version or self._get_current_prompt_version(),
                    "evaluation_timestamp": datetime.now().isoformat(),
                    "performance_metrics": performance_metrics,
                    "detailed_results": detailed_metrics,
                    "test_method": "duckflow_sandbox"
                }
            else:
                # Mockテスト（Duckflowが利用不可の場合）
                print("\nMockテスト実行中...")
                mock_performance = self._run_mock_performance_test(test_count)
                
                print(f"Mock性能評価完了:")
                print(f"  総合スコア: {mock_performance['overall_score']:.1f}")
                
                return {
                    "prompt_version": prompt_version or self._get_current_prompt_version(),
                    "evaluation_timestamp": datetime.now().isoformat(),
                    "performance_metrics": mock_performance,
                    "detailed_results": {},
                    "test_method": "mock_test"
                }
                
        finally:
            # 元のバージョンに戻す（必要な場合）
            if original_version:
                self.prompt_manager.apply_version(original_version)
                print(f"プロンプトバージョン復元: {original_version}")
    
    def get_improvement_history(self, days: int = 30) -> Dict[str, Any]:
        """
        改善履歴の取得
        
        Args:
            days: 取得する日数
            
        Returns:
            改善履歴サマリー
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_cycles = [
            cycle for cycle in self.cycle_history
            if cycle.start_time > cutoff_date
        ]
        
        if not recent_cycles:
            return {
                "period_days": days,
                "total_cycles": 0,
                "successful_cycles": 0,
                "success_rate": 0.0,
                "average_improvement": 0.0,
                "trend": "no_data"
            }
        
        successful_cycles = [cycle for cycle in recent_cycles if cycle.success]
        success_rate = len(successful_cycles) / len(recent_cycles)
        
        # 改善効果の平均計算
        improvements = []
        for cycle in successful_cycles:
            if cycle.performance_before and cycle.performance_after:
                before_score = cycle.performance_before.get("overall_score", 0)
                after_score = cycle.performance_after.get("overall_score", 0)
                improvement = after_score - before_score
                improvements.append(improvement)
        
        average_improvement = statistics.mean(improvements) if improvements else 0.0
        
        # トレンド分析
        if len(recent_cycles) >= 3:
            recent_scores = [
                cycle.performance_after.get("overall_score", 0) if cycle.performance_after
                else cycle.performance_before.get("overall_score", 0)
                for cycle in recent_cycles[-3:]
            ]
            if recent_scores[-1] > recent_scores[0]:
                trend = "improving"
            elif recent_scores[-1] < recent_scores[0]:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "period_days": days,
            "total_cycles": len(recent_cycles),
            "successful_cycles": len(successful_cycles),
            "success_rate": success_rate,
            "average_improvement": average_improvement,
            "trend": trend,
            "recent_cycles": [
                {
                    "cycle_id": cycle.cycle_id,
                    "timestamp": cycle.start_time.isoformat(),
                    "success": cycle.success,
                    "improvements_applied": len(cycle.improvements_applied)
                }
                for cycle in recent_cycles[-10:]  # 最新10件
            ]
        }
    
    def _get_current_prompt_version(self) -> str:
        """現行プロンプトバージョンの取得"""
        active_version = self.prompt_manager.get_active_version()
        return active_version.version_id if active_version else "unknown"
    
    def _measure_baseline_performance(self, cycle_id: str) -> Dict[str, float]:
        """ベースライン性能測定"""
        if self.sandbox_runner:
            results = self.sandbox_runner.run_all_scenarios()
            return {
                "overall_score": results.get("average_score", 0),
                "success_rate": results.get("success_rate", 0),
                "total_execution_time": results.get("total_execution_time", 0)
            }
        else:
            # Mock実装
            return {
                "overall_score": 75.0,
                "success_rate": 0.8,
                "total_execution_time": 2.5
            }
    
    def _run_challenging_scenarios(self, iterations: int, difficulty: str, 
                                 cycle_id: str) -> List[Dict[str, Any]]:
        """挑戦的シナリオの実行"""
        scenario_results = []
        
        for i in range(iterations):
            print(f"  シナリオ {i+1}/{iterations} 実行中...")
            
            # TesterAIで挑戦的シナリオ生成
            scenario = self.tester_ai.generate_challenging_scenario(difficulty)
            
            # シナリオ実行（Sandbox使用可能な場合は実際に実行）
            if self.sandbox_runner:
                # 実際のサンドボックス実行は複雑なため、簡略化
                execution_result = {
                    "scenario_name": scenario.name,
                    "user_request": scenario.user_request,
                    "execution_success": True,
                    "performance_score": 70 + (i * 5),  # Mock値
                    "conversation_log": [
                        {"role": "user", "content": scenario.user_request},
                        {"role": "assistant", "content": f"了解しました。{scenario.name}を実行します。"}
                    ]
                }
            else:
                # Mock実行結果
                execution_result = {
                    "scenario_name": scenario.name,
                    "user_request": scenario.user_request,
                    "execution_success": i % 2 == 0,  # 50%成功率
                    "performance_score": 60 + (i * 8),
                    "conversation_log": [
                        {"role": "user", "content": scenario.user_request},
                        {"role": "assistant", "content": "実装を開始します。"}
                    ]
                }
            
            scenario_results.append(execution_result)
            
            # 短い間隔を置く
            time.sleep(0.1)
        
        return scenario_results
    
    def _analyze_results(self, scenario_results: List[Dict[str, Any]], 
                       baseline_performance: Dict[str, float]) -> Dict[str, Any]:
        """結果分析・弱点抽出"""
        analysis = {
            "baseline_performance": baseline_performance,
            "scenario_count": len(scenario_results),
            "success_rate": 0.0,
            "average_score": 0.0,
            "weakness_patterns": [],
            "conversation_analysis": {},
            "evaluation_results": {}
        }
        
        if not scenario_results:
            return analysis
        
        # 基本統計
        successful_scenarios = [r for r in scenario_results if r.get("execution_success", False)]
        analysis["success_rate"] = len(successful_scenarios) / len(scenario_results)
        analysis["average_score"] = statistics.mean([
            r.get("performance_score", 0) for r in scenario_results
        ])
        
        # 対話ログ分析（Phase 2: 拡張分析）
        all_conversations = []
        for result in scenario_results:
            conversation = result.get("conversation_log", [])
            if conversation:
                all_conversations.extend(conversation)
        
        if all_conversations:
            # 基本分析
            conversation_analysis = self.conversation_analyzer.analyze_intent_understanding(all_conversations)
            
            # Phase 2: 高度な分析機能
            sentiment_analysis = self.conversation_analyzer.analyze_sentiment_progression(all_conversations)
            complexity_analysis = self.conversation_analyzer.analyze_task_complexity_handling(all_conversations)
            efficiency_analysis = self.conversation_analyzer.measure_communication_efficiency(all_conversations)
            misalignment_analysis = self.conversation_analyzer.detect_misalignment_patterns(all_conversations)
            
            analysis["conversation_analysis"] = {
                # 基本分析
                "intent_understanding_rate": conversation_analysis,
                "confusion_points": self.conversation_analyzer.detect_confusion_points(all_conversations),
                "question_quality": self.conversation_analyzer.measure_question_quality(
                    self.conversation_analyzer._extract_questions_from_conversation(all_conversations)
                ),
                
                # Phase 2: 拡張分析
                "sentiment_analysis": sentiment_analysis,
                "complexity_analysis": complexity_analysis,
                "efficiency_analysis": efficiency_analysis,
                "misalignment_analysis": misalignment_analysis,
                
                # 統合指標
                "advanced_metrics": {
                    "overall_satisfaction": sentiment_analysis["satisfaction_score"],
                    "complexity_handling_quality": complexity_analysis["handling_quality"], 
                    "communication_efficiency": efficiency_analysis["efficiency_score"],
                    "alignment_quality": 1.0 - misalignment_analysis["misalignment_score"]
                }
            }
        
        # OptimizerAIによる弱点分析
        evaluation_results = {
            "quality_score": analysis["average_score"],
            "completeness_score": analysis["success_rate"] * 100,
            "efficiency_score": 70.0  # Mock値
        }
        analysis["evaluation_results"] = evaluation_results
        
        weakness_patterns = self.optimizer_ai.identify_weakness_patterns(evaluation_results)
        analysis["weakness_patterns"] = weakness_patterns
        
        return analysis
    
    def _generate_improvements(self, analysis_results: Dict[str, Any]) -> List[Any]:
        """改善提案生成"""
        return self.improvement_engine.generate_targeted_improvements(analysis_results)
    
    def _apply_improvements(self, improvement_suggestions: List[Any], 
                          auto_apply: bool = False) -> List[str]:
        """改善適用"""
        applied_improvements = []
        
        if not improvement_suggestions:
            return applied_improvements
        
        # 現行プロンプトを取得
        current_prompt = self.prompt_manager.load_current_prompt()
        
        # 高優先度・低リスクの改善のみ選択
        safe_improvements = [
            imp for imp in improvement_suggestions 
            if hasattr(imp, 'risk_level') and imp.risk_level == "low"
        ][:2]  # 最大2つ
        
        if not safe_improvements:
            print("  安全な改善提案がありません")
            return applied_improvements
        
        for improvement in safe_improvements:
            print(f"  改善提案: {improvement.target_section} - {improvement.improvement_type}")
            print(f"  内容: {improvement.proposed_content[:100]}...")
            print(f"  期待効果: {improvement.expected_impact}")
            
            if auto_apply:
                apply_decision = True
                print("  -> 自動適用")
            else:
                # 実際の実装では、ここでユーザーの承認を求める
                apply_decision = True  # デモでは自動承認
                print("  -> 承認（デモモード）")
            
            if apply_decision:
                # プロンプトバリエーション生成
                variations = self.improvement_engine.create_prompt_variations(
                    current_prompt, [improvement]
                )
                
                if variations:
                    improved_prompt = variations[0]["prompt"]
                    
                    # 安全性検証
                    safety_check = self.improvement_engine.validate_improvement_safety(
                        improved_prompt, current_prompt
                    )
                    
                    if safety_check["is_safe"]:
                        # 新バージョンとして保存・適用
                        changes = [improvement.rationale]
                        expected_metrics = {
                            f"expected_{metric}": value 
                            for metric, value in improvement.expected_impact.items()
                        }
                        
                        version_id = self.prompt_manager.save_new_version(
                            improved_prompt, changes, expected_metrics
                        )
                        
                        self.prompt_manager.apply_version(version_id)
                        applied_improvements.append(improvement.improvement_id)
                        current_prompt = improved_prompt  # 次の改善のベースとして使用
                        
                        print(f"  -> 適用完了: バージョン {version_id}")
                    else:
                        print(f"  -> 安全性チェック失敗: {safety_check['risk_level']}")
            else:
                print("  -> 適用見送り")
        
        return applied_improvements
    
    def _measure_improved_performance(self, cycle_id: str) -> Dict[str, float]:
        """改善後性能測定"""
        return self._measure_baseline_performance(cycle_id)  # 同じロジックを再利用
    
    def _calculate_improvement_effect(self, before: Dict[str, float], 
                                    after: Dict[str, float]) -> Dict[str, float]:
        """改善効果の計算"""
        improvement_effect = {}
        
        for metric in before.keys():
            if metric in after:
                improvement = after[metric] - before[metric]
                improvement_percent = (improvement / before[metric] * 100) if before[metric] > 0 else 0
                improvement_effect[f"{metric}_improvement"] = improvement
                improvement_effect[f"{metric}_improvement_percent"] = improvement_percent
        
        # 総合改善度
        if "overall_score" in before and "overall_score" in after:
            overall_improvement = after["overall_score"] - before["overall_score"]
            improvement_effect["overall_improvement"] = overall_improvement
        
        return improvement_effect
    
    def _generate_recommendations(self, analysis_results: Dict[str, Any], 
                                success: bool) -> List[str]:
        """推奨事項生成"""
        recommendations = []
        
        if success:
            recommendations.append("改善サイクルが成功しました。現在の改善を継続してください。")
            
            # 更なる改善の提案
            avg_score = analysis_results.get("average_score", 0)
            if avg_score < 80:
                recommendations.append("さらなる品質向上のため、追加の改善サイクルを検討してください。")
        else:
            recommendations.append("改善サイクルで期待した効果が得られませんでした。")
            
            # 具体的な改善提案
            success_rate = analysis_results.get("success_rate", 0)
            if success_rate < 0.7:
                recommendations.append("シナリオの成功率が低いです。要求理解の改善に重点を置いてください。")
            
            weakness_patterns = analysis_results.get("weakness_patterns", [])
            if len(weakness_patterns) > 3:
                recommendations.append("多くの弱点が検出されました。段階的な改善アプローチを推奨します。")
        
        # 次回サイクルの提案
        recommendations.append("次回は異なる難易度のシナリオでテストすることを推奨します。")
        
        return recommendations
    
    def _run_mock_performance_test(self, test_count: int) -> Dict[str, float]:
        """Mockパフォーマンステスト（Duckflow未使用時）"""
        # シンプルなMock実装
        scores = [75 + (i * 2) for i in range(test_count)]
        
        return {
            "overall_score": statistics.mean(scores),
            "success_rate": 0.8,
            "total_execution_time": test_count * 0.5,
            "test_count": test_count
        }
    
    def _serialize_for_json(self, obj: Any) -> Any:
        """JSON serialization用のオブジェクト変換"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, list):
            return [self._serialize_for_json(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._serialize_for_json(value) for key, value in obj.items()}
        elif hasattr(obj, '__dict__'):
            # dataclassやその他のオブジェクトを辞書に変換
            try:
                # asdictを使って変換し、再帰的にシリアライズ
                obj_dict = asdict(obj)
                return self._serialize_for_json(obj_dict)
            except:
                # asdictが失敗した場合は手動で辞書化
                return {key: self._serialize_for_json(value) for key, value in obj.__dict__.items()}
        else:
            return obj
    
    def _save_cycle_results(self, results: CycleResults) -> None:
        """サイクル結果の保存"""
        results_file = self.results_storage / f"{results.cycle_info.cycle_id}.json"
        
        # 完全なシリアライズ変換
        results_dict = {
            "cycle_info": self._serialize_for_json(results.cycle_info),
            "scenario_results": self._serialize_for_json(results.scenario_results),
            "analysis_results": self._serialize_for_json(results.analysis_results),
            "improvement_suggestions": self._serialize_for_json(results.improvement_suggestions),
            "final_metrics": self._serialize_for_json(results.final_metrics),
            "recommendations": self._serialize_for_json(results.recommendations)
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, ensure_ascii=False, indent=2)
        
        print(f"  結果保存: {results_file}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """デフォルト設定の取得"""
        return {
            "max_iterations": 5,
            "default_difficulty": "medium",
            "auto_apply_threshold": 0.1,  # 10%以上の改善で自動適用
            "safety_threshold": 0.7,
            "results_storage": "promptsmith_results",
            "backup_enabled": True
        }


# デモ実行用関数
def demo_promptsmith_orchestrator():
    """PromptSmithオーケストレーターのデモ実行"""
    print("=== PromptSmith オーケストレーター デモ実行 ===")
    
    orchestrator = PromptSmithOrchestrator()
    
    # 1. 現在のプロンプト性能評価
    print("\n1. 現在のプロンプト性能評価:")
    performance = orchestrator.evaluate_prompt_performance(test_count=3)
    print(f"評価結果: {performance['performance_metrics']}")
    
    # 2. 改善サイクル実行
    print("\n2. 改善サイクル実行:")
    results = orchestrator.run_improvement_cycle(iterations=2, difficulty="easy", auto_apply=True)
    
    print(f"\nサイクル結果:")
    print(f"  成功: {results.cycle_info.success}")
    print(f"  実行シナリオ: {len(results.scenario_results)}個")
    print(f"  改善提案: {len(results.improvement_suggestions)}個")
    print(f"  適用された改善: {len(results.cycle_info.improvements_applied)}個")
    
    # 3. 改善履歴確認
    print("\n3. 改善履歴:")
    history = orchestrator.get_improvement_history(days=1)
    print(f"  実行サイクル数: {history['total_cycles']}")
    print(f"  成功率: {history['success_rate']*100:.1f}%")
    print(f"  平均改善: {history['average_improvement']:.1f}")
    
    # 4. 推奨事項
    print(f"\n4. 推奨事項:")
    for recommendation in results.recommendations:
        print(f"  - {recommendation}")
    
    print("\n=== デモ完了 ===")


if __name__ == "__main__":
    demo_promptsmith_orchestrator()
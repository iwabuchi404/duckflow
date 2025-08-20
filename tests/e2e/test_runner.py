"""
E2ETestRunner - E2Eテストの実行制御
"""

import asyncio
import yaml
import logging
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.e2e.conversation_llm import ConversationTestLLM
from tests.e2e.evaluator import ConversationEvaluator
from tests.e2e.logger import ConversationLogger


class E2ETestRunner:
    """E2Eテストの実行制御"""
    
    def __init__(self, duckflow_system=None):
        """初期化
        
        Args:
            duckflow_system: DuckflowCompanionインスタンス（テスト用）
        """
        self.duckflow_system = duckflow_system
        self.test_llm = None
        self.evaluator = ConversationEvaluator()
        self.logger = None
        
        # ログ設定
        self.runner_logger = logging.getLogger(__name__)
        
        # 結果格納
        self.test_results = []
    
    async def run_single_test(self, scenario_file: str) -> Dict:
        """単一テストを実行
        
        Args:
            scenario_file: シナリオファイルのパス
            
        Returns:
            テスト結果
        """
        try:
            # シナリオファイルの読み込み
            scenario_config = self._load_scenario(scenario_file)
            
            self.runner_logger.info(f"Starting test: {scenario_config['name']}")
            
            # コンポーネントの初期化
            self.test_llm = ConversationTestLLM(
                scenario=scenario_config["scenario"],
                evaluation_criteria=scenario_config["evaluation_criteria"]
            )
            
            self.logger = ConversationLogger(scenario_config["name"])
            self.logger.log["test_config"] = scenario_config.get("test_config", {})
            
            # 対話実行
            conversation_result = await self._run_conversation(scenario_config)
            
            # 評価実行
            evaluation_result = self.evaluator.evaluate_conversation(
                log=self.logger.log,
                scenario=scenario_config["scenario"],
                evaluation_criteria=scenario_config["evaluation_criteria"]
            )
            
            # 結果の統合
            test_result = {
                "scenario_file": scenario_file,
                "scenario_config": scenario_config,
                "conversation_log": self.logger.log,
                "evaluation": evaluation_result,
                "success": evaluation_result.get("passed", False),
                "test_duration": conversation_result.get("duration", 0),
                "timestamp": self.logger.log.get("end_time")
            }
            
            # ログファイルの保存
            log_filepath = self.logger.save_log()
            test_result["log_file"] = log_filepath
            
            self.runner_logger.info(f"Test completed: {scenario_config['name']} - Success: {test_result['success']}")
            
            return test_result
            
        except Exception as e:
            self.runner_logger.error(f"Test execution failed: {e}")
            return self._create_error_result(scenario_file, str(e))
    
    async def _run_conversation(self, scenario_config: Dict) -> Dict:
        """実際の対話を実行
        
        Args:
            scenario_config: シナリオ設定
            
        Returns:
            対話実行結果
        """
        start_time = time.time()
        
        try:
            # テスト設定の取得
            test_config = scenario_config.get("test_config", {})
            max_exchanges = test_config.get("max_exchanges", 10)
            timeout_minutes = test_config.get("timeout_minutes", 5)
            
            # 最初のユーザー入力を生成
            user_input = self.test_llm.generate_first_input()
            
            # 対話ループ
            for exchange_num in range(max_exchanges):
                # タイムアウトチェック
                if (time.time() - start_time) > (timeout_minutes * 60):
                    self.logger.set_completion_status("timeout", "時間制限に達しました")
                    break
                
                # Duckflowに入力を送信（モック版）
                duckflow_response = await self._send_to_duckflow(user_input)
                
                # ログに記録
                self.logger.log_exchange(user_input, duckflow_response)
                
                # 終了条件チェック
                if self.test_llm.should_terminate(duckflow_response):
                    self.logger.set_completion_status("completed", "正常終了")
                    break
                
                # 次のユーザー入力を生成
                user_input = self.test_llm.generate_next_input(self.logger.log["exchanges"])
                
                # 明示的な終了要求チェック
                if "テスト完了" in user_input or "テスト中断" in user_input:
                    self.logger.set_completion_status("completed", "テスト終了要求")
                    break
            
            else:
                # ループが最大回数に達した場合
                self.logger.set_completion_status("completed", "最大対話数に達しました")
            
            duration = time.time() - start_time
            
            return {
                "duration": duration,
                "exchanges": len(self.logger.log["exchanges"]),
                "status": self.logger.log["completion_status"]
            }
            
        except Exception as e:
            self.logger.set_completion_status("failed", f"対話実行エラー: {str(e)}")
            self.logger.log_error(str(e), "conversation_execution")
            raise
    
    async def _send_to_duckflow(self, user_input: str) -> str:
        """Duckflowに入力を送信（現在はモック版）
        
        Args:
            user_input: ユーザー入力
            
        Returns:
            Duckflowの応答
        """
        # TODO: 実際のDuckflowシステムとの統合
        # 現在はモック応答を返す
        
        await asyncio.sleep(0.5)  # 処理時間をシミュレート
        
        # 簡単なパターンマッチング応答
        if "hello.py" in user_input.lower() and "作" in user_input:
            return "hello.pyファイルを作成します。以下の内容で作成してよろしいですか？\\n\\n```python\\nprint('Hello World')\\n```\\n\\n承認してください。"
        
        elif "はい" in user_input or "ok" in user_input.lower() or "進めて" in user_input:
            # ファイル操作をログに記録
            self.logger.log_file_operation("create", "hello.py", "print('Hello World')")
            return "hello.pyファイルを作成しました。ファイルにはHello Worldを出力するコードが含まれています。"
        
        elif "ファイル" in user_input and "確認" in user_input:
            return "hello.pyファイルの内容:\\n```python\\nprint('Hello World')\\n```\\n\\nファイルは正常に作成されています。"
        
        elif "テスト完了" in user_input:
            return "テストが完了しました。お疲れさまでした。"
        
        else:
            return f"申し訳ありませんが、「{user_input}」についてはよく理解できませんでした。もう少し具体的に教えてください。"
    
    def _load_scenario(self, scenario_file: str) -> Dict:
        """シナリオファイルを読み込み
        
        Args:
            scenario_file: シナリオファイルのパス
            
        Returns:
            シナリオ設定
        """
        try:
            with open(scenario_file, 'r', encoding='utf-8') as f:
                scenario_config = yaml.safe_load(f)
            
            # 必須フィールドの検証
            required_fields = ["name", "scenario", "evaluation_criteria"]
            for field in required_fields:
                if field not in scenario_config:
                    raise ValueError(f"Required field '{field}' missing in scenario file")
            
            return scenario_config
            
        except Exception as e:
            self.runner_logger.error(f"Failed to load scenario file {scenario_file}: {e}")
            raise
    
    async def run_test_suite(self, scenario_pattern: str = "tests/scenarios/level1/*.yaml") -> Dict:
        """テストスイートを実行
        
        Args:
            scenario_pattern: シナリオファイルのパターン
            
        Returns:
            テストスイート結果
        """
        # シナリオファイルの検索
        scenario_files = list(Path(".").glob(scenario_pattern))
        
        if not scenario_files:
            self.runner_logger.warning(f"No scenario files found for pattern: {scenario_pattern}")
            return {"results": [], "summary": {"total": 0, "passed": 0, "failed": 0}}
        
        results = []
        
        # 各シナリオの実行
        for scenario_file in scenario_files:
            try:
                result = await self.run_single_test(str(scenario_file))
                results.append(result)
                
            except Exception as e:
                self.runner_logger.error(f"Failed to run scenario {scenario_file}: {e}")
                results.append(self._create_error_result(str(scenario_file), str(e)))
        
        # サマリーの作成
        summary = self._create_test_summary(results)
        
        return {
            "results": results,
            "summary": summary,
            "execution_time": sum(r.get("test_duration", 0) for r in results)
        }
    
    def _create_test_summary(self, results: List[Dict]) -> Dict:
        """テスト結果のサマリーを作成
        
        Args:
            results: テスト結果のリスト
            
        Returns:
            サマリー
        """
        total = len(results)
        passed = sum(1 for r in results if r.get("success", False))
        failed = total - passed
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / total * 100) if total > 0 else 0,
            "average_score": self._calculate_average_score(results)
        }
    
    def _calculate_average_score(self, results: List[Dict]) -> float:
        """平均スコアを計算
        
        Args:
            results: テスト結果のリスト
            
        Returns:
            平均スコア
        """
        scores = []
        for result in results:
            evaluation = result.get("evaluation", {}).get("evaluation", {})
            overall_score = evaluation.get("overall_score", {}).get("score", 0)
            scores.append(overall_score)
        
        return sum(scores) / len(scores) if scores else 0
    
    def _create_error_result(self, scenario_file: str, error_message: str) -> Dict:
        """エラー結果を作成
        
        Args:
            scenario_file: シナリオファイルパス
            error_message: エラーメッセージ
            
        Returns:
            エラー結果
        """
        return {
            "scenario_file": scenario_file,
            "scenario_config": {"name": "Error", "scenario": "Failed to load"},
            "conversation_log": {"error": error_message},
            "evaluation": {"passed": False, "error": error_message},
            "success": False,
            "test_duration": 0,
            "error": error_message
        }
    
    def generate_report(self, results: List[Dict]) -> str:
        """テスト結果レポートを生成
        
        Args:
            results: テスト結果のリスト
            
        Returns:
            レポート文字列
        """
        summary = self._create_test_summary(results)
        
        report_lines = [
            "# E2Eテスト結果レポート",
            "",
            f"## サマリー",
            f"- 総テスト数: {summary['total']}",
            f"- 成功: {summary['passed']}",
            f"- 失敗: {summary['failed']}",
            f"- 成功率: {summary['pass_rate']:.1f}%",
            f"- 平均スコア: {summary['average_score']:.2f}/5.0",
            "",
            "## 個別結果"
        ]
        
        for result in results:
            name = result.get("scenario_config", {}).get("name", "Unknown")
            success = "✅" if result.get("success", False) else "❌"
            
            evaluation = result.get("evaluation", {}).get("evaluation", {})
            score = evaluation.get("overall_score", {}).get("score", 0)
            
            report_lines.append(f"- {success} {name}: {score}/5.0")
        
        return "\n".join(report_lines)
"""
PromptSmith ファイル内容解析の統合テスト
シナリオ生成、実行、評価の全体的な統合テスト
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

from codecrafter.promptsmith.ai_roles.file_analysis_scenarios import (
    FileAnalysisScenarioGenerator, 
    FileAnalysisScenario
)
from codecrafter.promptsmith.evaluation.file_analysis_evaluator import (
    FileAnalysisEvaluator,
    AnalysisEvaluationResult
)

class TestFileAnalysisIntegration:
    """ファイル分析統合テスト"""
    
    def setup_method(self):
        """テスト前の初期化"""
        self.generator = FileAnalysisScenarioGenerator()
        self.evaluator = FileAnalysisEvaluator()
    
    def test_scenario_generation(self):
        """シナリオ生成のテスト"""
        
        # 各レベルのシナリオ生成
        for level in [1, 2, 3]:
            scenario = self.generator.generate_scenario(level=level)
            
            assert isinstance(scenario, FileAnalysisScenario)
            assert scenario.level == level
            assert scenario.scenario_id is not None
            assert len(scenario.user_request) > 0
            assert len(scenario.expected_analysis_points) > 0
            assert len(scenario.evaluation_criteria) > 0
            assert Path(scenario.file_path).exists()
    
    def test_batch_scenario_generation(self):
        """バッチシナリオ生成のテスト"""
        
        batch = self.generator.create_scenario_batch(batch_size=6)
        
        assert batch["total_scenarios"] == 6
        assert len(batch["scenarios"]) == 6
        assert "batch_id" in batch
        assert "level_distribution" in batch
        
        # レベル分布確認
        levels = [s.level for s in batch["scenarios"]]
        assert 1 in levels
        assert 2 in levels
        assert 3 in levels
    
    def test_evaluation_system(self):
        """評価システムのテスト"""
        
        # テスト用シナリオ
        scenario = self.generator.generate_scenario(level=2, category="bug_detection")
        
        # サンプル回答
        test_response = """
        このコードを分析した結果、以下の問題を発見しました：
        
        1. エラーハンドリングの欠如
           - JSON.parseで例外処理がされていません
           - try-catch文の追加が必要です
        
        2. null/undefinedチェック不足
           - userオブジェクトのnullチェックが不十分です
           
        3. セキュリティ上の問題
           - SQLインジェクション脆弱性が存在します
        
        修正提案：
        - 適切な例外処理の実装
        - 入力値検証の強化
        - パラメータ化クエリの使用
        """
        
        # 評価実行
        evaluation = self.evaluator.evaluate_analysis(scenario, test_response)
        
        assert isinstance(evaluation, AnalysisEvaluationResult)
        assert evaluation.scenario_id == scenario.scenario_id
        assert 0 <= evaluation.total_score <= 1
        assert len(evaluation.category_scores) > 0
        assert len(evaluation.detailed_feedback) > 0
    
    def test_low_quality_response_evaluation(self):
        """低品質回答の評価テスト"""
        
        scenario = self.generator.generate_scenario(level=1)
        
        # 低品質な回答
        poor_response = "このファイルは何かをするコードです。"
        
        evaluation = self.evaluator.evaluate_analysis(scenario, poor_response)
        
        # 低品質回答は低スコアを受けるべき
        assert evaluation.total_score < 0.5
        assert len(evaluation.improvement_suggestions) > 0
        assert len(evaluation.weaknesses) > 0
    
    def test_high_quality_response_evaluation(self):
        """高品質回答の評価テスト"""
        
        scenario = self.generator.generate_scenario(level=2)
        
        # 高品質な回答
        high_quality_response = """
        ## コード構造分析
        
        このPythonファイルは以下の要素で構成されています：
        
        ### クラス定義
        1. **DataProcessor**（基底クラス）
           - 抽象基底クラス (ABC)
           - process()抽象メソッド: データ処理の契約を定義
           - validate_data(): データ妥当性検証（Dict型の必須キー確認）
           
        2. **TextProcessor**（継承クラス）
           - DataProcessorを継承したテキスト処理実装
           - コンストラクタ引数: name(str), max_length(int, default=1000)
           - process()メソッド: テキストクリーニングと単語数カウント
        
        ### 主要メソッドの詳細分析
        
        **process()メソッド**:
        - 引数: data (Dict) - id, content, timestampキーが必須
        - 戻り値: Dict - 処理結果（processed_content, word_count等）
        - 処理フロー: 検証 → クリーニング → 統計計算 → 結果返却
        
        **_clean_text()メソッド**:
        - プライベートメソッド：テキスト正規化処理
        - ストップワード除去機能
        - 小文字変換とトリム処理
        
        ### 設計パターンと特徴
        - **Template Method Pattern**: 基底クラスで処理フレームワークを定義
        - **Strategy Pattern的な継承**: 処理種類別の実装分離
        - **型安全性**: type hintsによる引数・戻り値の型保証
        
        ### 品質評価
        **強み:**
        - 抽象化設計による拡張性
        - 適切なエラーハンドリング（ValueError）
        - ログ出力による実行可視性
        
        **改善提案:**
        - より詳細な例外タイプの定義
        - テキスト処理のパフォーマンス最適化
        - 設定の外部化（ストップワードリスト等）
        """
        
        evaluation = self.evaluator.evaluate_analysis(scenario, high_quality_response)
        
        # 高品質回答は高スコアを受けるべき
        assert evaluation.total_score > 0.7
        assert len(evaluation.strengths) > len(evaluation.weaknesses)
    
    def test_batch_evaluation(self):
        """バッチ評価のテスト"""
        
        # テスト用シナリオとレスポンスの準備
        scenarios = []
        responses = []
        
        for level in [1, 2]:
            scenario = self.generator.generate_scenario(level=level)
            scenarios.append(scenario)
            
            # レベル別のサンプル回答
            if level == 1:
                response = "このファイルには calculate_area 関数があり、幅と高さを引数として面積を返します。"
            else:
                response = """
                コード分析結果:
                1. クラス構造: 継承関係のある複雑な設計
                2. 問題点: エラーハンドリング不足
                3. 改善案: 例外処理の追加とログ改善
                """
            
            responses.append(response)
        
        scenarios_and_responses = list(zip(scenarios, responses))
        
        # バッチ評価実行
        batch_result = self.evaluator.batch_evaluate(scenarios_and_responses)
        
        assert "batch_id" in batch_result
        assert batch_result["statistics"]["total_evaluations"] == 2
        assert "average_score" in batch_result["statistics"]
        assert "score_distribution" in batch_result["statistics"]
        assert len(batch_result["individual_results"]) == 2
    
    def test_challenge_scenario_generation(self):
        """挑戦的シナリオ生成のテスト"""
        
        challenge_scenarios = self.generator.generate_challenge_scenarios(count=3)
        
        assert len(challenge_scenarios) == 3
        
        # 各シナリオの基本検証
        for scenario in challenge_scenarios:
            assert isinstance(scenario, FileAnalysisScenario)
            assert scenario.level in [1, 2, 3]
            assert len(scenario.difficulty_factors) > 0
            assert len(scenario.expected_analysis_points) > 0
    
    def test_ambiguous_request_handling(self):
        """曖昧な要求への対応テスト"""
        
        # レベル3で曖昧なシナリオを生成
        scenario = self.generator.generate_scenario(level=3, category="ambiguous_analysis")
        
        # 曖昧な要求に対する適切な回答例
        good_ambiguous_response = """
        ご要求について、より具体的にお手伝いするために確認させてください：
        
        ## 確認事項
        1. **改善の観点**: どの観点での改善をお求めでしょうか？
           - 性能・パフォーマンス
           - コードの可読性・保守性
           - セキュリティ
           - バグ修正
        
        2. **優先度**: 最も重要な改善点はどちらでしょうか？
        
        3. **制約条件**: 改善時に考慮すべき制約はありますか？
        
        ## 現時点での包括的分析
        とりあえず、以下の観点で分析いたします：
        
        **コード構造**: [構造分析結果]
        **潜在的問題**: [問題点の列挙]
        **改善候補**: [優先度付きの改善提案]
        """
        
        evaluation = self.evaluator.evaluate_analysis(scenario, good_ambiguous_response)
        
        # 曖昧な要求に対する適切な対応は高く評価されるべき
        if scenario.category == "ambiguous_analysis":
            assert evaluation.category_scores.get("ambiguous_analysis", 0) > 0.6
    
    def test_edge_case_files(self):
        """エッジケースファイルのテスト"""
        
        # 各種特殊ファイルでのシナリオ生成テスト
        for _ in range(5):
            scenario = self.generator.generate_scenario()
            
            # ファイルが存在することを確認
            assert Path(scenario.file_path).exists()
            
            # シナリオが適切に生成されていることを確認
            assert scenario.user_request is not None
            assert len(scenario.expected_analysis_points) > 0
            assert scenario.level in [1, 2, 3]

class TestFileAnalysisWorkflow:
    """ファイル分析ワークフロー全体のテスト"""
    
    def test_end_to_end_workflow(self):
        """エンドツーエンドワークフローのテスト"""
        
        # 1. シナリオ生成
        generator = FileAnalysisScenarioGenerator()
        batch = generator.create_scenario_batch(batch_size=3)
        
        # 2. 模擬AI応答生成
        mock_responses = [
            # レベル1相当の回答
            "このファイルは簡単な関数を定義しています。calculate_areaという関数があります。",
            
            # レベル2相当の回答  
            """
            コード分析：
            - 複数のクラス定義あり
            - 継承関係を使用
            - 問題: エラーハンドリング不足
            - 改善案: try-catch追加
            """,
            
            # レベル3相当の回答
            """
            包括的分析結果：
            1. アーキテクチャ評価: オブジェクト指向設計
            2. 問題特定: 5つの主要問題を発見
            3. 改善ロードマップ: 段階的実装計画
            4. 質問: 具体的な改善優先度は？
            """
        ]
        
        # 3. 評価実行
        evaluator = FileAnalysisEvaluator()
        scenarios_and_responses = list(zip(batch["scenarios"], mock_responses))
        evaluation_result = evaluator.batch_evaluate(scenarios_and_responses)
        
        # 4. 結果検証
        assert evaluation_result["statistics"]["total_evaluations"] == 3
        assert "average_score" in evaluation_result["statistics"]
        
        # スコアが妥当な範囲内
        avg_score = evaluation_result["statistics"]["average_score"]
        assert 0 <= avg_score <= 1
        
        # 個別結果の検証
        for result in evaluation_result["individual_results"]:
            assert isinstance(result, AnalysisEvaluationResult)
            assert result.total_score >= 0
            assert len(result.category_scores) > 0
    
    def test_json_serialization(self):
        """JSON シリアライゼーションのテスト"""
        
        # シナリオ生成と評価
        generator = FileAnalysisScenarioGenerator()
        evaluator = FileAnalysisEvaluator()
        
        scenario = generator.generate_scenario()
        response = "テスト回答: このファイルは関数を含んでいます。"
        evaluation = evaluator.evaluate_analysis(scenario, response)
        
        # JSON シリアライゼーション
        try:
            # asdict を使用してシリアライズ可能な形式に変換
            from dataclasses import asdict
            evaluation_dict = asdict(evaluation)
            json_str = json.dumps(evaluation_dict, ensure_ascii=False, default=str)
            
            # デシリアライゼーション
            parsed = json.loads(json_str)
            
            assert parsed["scenario_id"] == evaluation.scenario_id
            assert parsed["total_score"] == evaluation.total_score
            
        except Exception as e:
            pytest.fail(f"JSON serialization failed: {e}")

if __name__ == "__main__":
    # 手動テスト実行
    test_instance = TestFileAnalysisIntegration()
    test_instance.setup_method()
    
    print("=== PromptSmith ファイル解析統合テスト ===")
    
    try:
        test_instance.test_scenario_generation()
        print("✅ シナリオ生成テスト: 成功")
        
        test_instance.test_evaluation_system()  
        print("✅ 評価システムテスト: 成功")
        
        test_instance.test_batch_evaluation()
        print("✅ バッチ評価テスト: 成功")
        
        workflow_test = TestFileAnalysisWorkflow()
        workflow_test.test_end_to_end_workflow()
        print("✅ エンドツーエンドワークフローテスト: 成功")
        
        print("\n🎉 全テストが正常に完了しました！")
        
    except Exception as e:
        print(f"❌ テスト失敗: {e}")
        raise
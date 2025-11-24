#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PromptSmith ファイル解析システム デモンストレーション
使用方法の例とサンプル実行
"""

import sys
from pathlib import Path

# プロジェクトパスを追加
sys.path.append(str(Path(__file__).parent))

from codecrafter.promptsmith.ai_roles.file_analysis_scenarios import FileAnalysisScenarioGenerator
from codecrafter.promptsmith.evaluation.file_analysis_evaluator import FileAnalysisEvaluator

def main():
    """メイン実行関数"""
    
    print("🔍 PromptSmith ファイル解析システム デモ")
    print("=" * 50)
    
    # システム初期化
    generator = FileAnalysisScenarioGenerator()
    evaluator = FileAnalysisEvaluator()
    
    print("\n📋 Step 1: シナリオ生成")
    print("-" * 25)
    
    # 各レベルのシナリオを生成
    scenarios = []
    for level in [1, 2, 3]:
        scenario = generator.generate_scenario(level=level)
        scenarios.append(scenario)
        
        print(f"\n【レベル {level}】{scenario.title}")
        print(f"ファイル: {Path(scenario.file_path).name}")
        print(f"ユーザー要求: {scenario.user_request}")
        print(f"期待ポイント: {', '.join(scenario.expected_analysis_points[:2])}...")
        print(f"困難要因: {', '.join(scenario.difficulty_factors)}")
    
    print(f"\n🧪 Step 2: AI応答シミュレーション")
    print("-" * 30)
    
    # 各レベルに応じたサンプル応答
    sample_responses = [
        # レベル1: 基本的な応答
        """
        このMarkdownファイルは「FileAnalyzer プロジェクト」の説明文書です。

        ## 主要セクション
        - 概要: ファイル内容を分析して品質評価するツール
        - インストール: pip install file-analyzer
        - 使用方法: 基本的な使用例とコマンドライン操作
        - サポート対象: Python, JavaScript, JSON, YAMLファイル

        このREADMEファイルは、プロジェクトの目的と使い方を説明する標準的なドキュメントです。
        """,
        
        # レベル2: 中級の応答（問題検出）
        """
        このPythonファイルを詳細分析した結果、以下の問題を特定しました:

        ## 検出された問題
        1. **エラーハンドリング不足**
           - JSON.loads()でJSONDecodeError処理なし
           - ファイル操作でIOError処理なし
           
        2. **セキュリティリスク**
           - SQLインジェクション脆弱性 (line 45)
           - ユーザー情報のログ出力 (line 23)
           
        3. **パフォーマンス問題**
           - O(n²)の非効率アルゴリズム (calculate_discount関数)
           - mutable default argument問題 (UserManager.add_user)

        ## 修正提案
        - try-except文による例外処理追加
        - パラメータ化クエリの使用
        - アルゴリズム最適化 (dict使用で O(1) 検索)
        """,
        
        # レベル3: 高級の応答（曖昧な要求への対応）
        """
        ご要求の「改善」について、より具体的にお手伝いするため確認させてください:

        ## 確認事項
        1. **改善の観点**: どの面での改善をお求めですか？
           - パフォーマンス最適化
           - コード品質・可読性向上
           - セキュリティ強化
           - 保守性・拡張性改善

        2. **優先度**: 最も重要な改善ポイントは？

        ## 現時点での包括的分析

        **アーキテクチャ評価**:
        - Python 2時代の古い記法を使用
        - グローバル変数への過度な依存
        - 非Pythonic実装パターン

        **現代化提案**:
        1. **Python 3対応**: print文→print関数、type hints追加
        2. **セキュリティ強化**: SQL文のパラメータ化、入力検証
        3. **設計改善**: グローバル変数削減、クラス設計見直し

        具体的な改善計画を立案いたしますので、優先事項をお教えください。
        """
    ]
    
    print("\n📊 Step 3: 自動評価実行")
    print("-" * 25)
    
    # 各応答を評価
    evaluations = []
    for i, (scenario, response) in enumerate(zip(scenarios, sample_responses)):
        print(f"\n【レベル {i+1} 評価結果】")
        
        evaluation = evaluator.evaluate_analysis(scenario, response)
        evaluations.append(evaluation)
        
        print(f"総合スコア: {evaluation.total_score:.3f}")
        print(f"カテゴリ別スコア:")
        for category, score in evaluation.category_scores.items():
            print(f"  - {category}: {score:.3f}")
        
        if evaluation.strengths:
            print(f"強み: {evaluation.strengths[0]}")
        if evaluation.improvement_suggestions:
            print(f"改善提案: {evaluation.improvement_suggestions[0]}")
    
    print(f"\n🏆 Step 4: バッチ評価と統計")
    print("-" * 28)
    
    # バッチ評価実行
    scenarios_and_responses = list(zip(scenarios, sample_responses))
    batch_result = evaluator.batch_evaluate(scenarios_and_responses)
    
    stats = batch_result["statistics"]
    print(f"評価件数: {stats['total_evaluations']}")
    print(f"平均スコア: {stats['average_score']:.3f}")
    print(f"最高スコア: {stats['max_score']:.3f}")
    print(f"スコア分布:")
    for level, count in stats["score_distribution"].items():
        print(f"  - {level}: {count}件")
    
    print(f"\n🎯 Step 5: 挑戦的シナリオ")
    print("-" * 23)
    
    # 挑戦的シナリオ生成
    challenge_scenarios = generator.generate_challenge_scenarios(count=2)
    
    for i, scenario in enumerate(challenge_scenarios, 1):
        print(f"\n【挑戦シナリオ {i}】")
        print(f"レベル: {scenario.level}")
        print(f"カテゴリ: {scenario.category}")
        print(f"要求: {scenario.user_request}")
        print(f"困難要因: {', '.join(scenario.difficulty_factors)}")
    
    print(f"\n✨ システム概要")
    print("-" * 15)
    print("📁 テストファイル: 10種類 (Python/JS/JSON/YAML/MD)")
    print("🎚️  難易度レベル: 3段階 (基本→中級→高級)")
    print("🏷️  評価カテゴリ: 6種類 (構造分析/バグ検出/性能/セキュリティ等)")
    print("📊 評価指標: 多次元スコアリング + 自動フィードバック")
    print("🤖 応用: PromptSmith自動改善サイクルに統合可能")
    
    print(f"\n🎉 デモンストレーション完了!")
    print("このシステムをPromptSmithの改善サイクルで活用し、")
    print("Duckflowのファイル解析能力を継続的に向上させることができます。")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLMベースTaskProfile分類システム デモンストレーション

実装したハイブリッド分類システムの動作確認
"""

import sys
import os
from pathlib import Path

# プロジェクトルートを追加
sys.path.insert(0, str(Path(__file__).parent))

from codecrafter.services.classification_manager import TaskProfileClassificationManager, ClassificationMode
from codecrafter.services.hybrid_task_classifier import hybrid_task_classifier
from codecrafter.services.llm_service import llm_service


def demo_classification_comparison():
    """分類システムの比較デモ"""
    print("🦆 LLMベースTaskProfile分類システム デモ")
    print("=" * 60)
    
    # テストケース
    test_cases = [
        {
            "input": "README.mdの内容を教えて",
            "description": "シンプルな情報要求"
        },
        {
            "input": "README.mdをレビューして品質を評価して",
            "description": "レビュー・評価要求（分析）"
        },
        {
            "input": "README.mdを改善して読みやすくして",
            "description": "改善・修正要求"
        },
        {
            "input": "main.pyとconfig.pyを比較して違いを教えて",
            "description": "複数ファイル比較（分析）"
        },
        {
            "input": "Pythonでログ機能を実装して",
            "description": "新規機能実装要求"
        },
        {
            "input": "バグを探して修正して",
            "description": "複合要求（検索+修正）"
        }
    ]
    
    # 分類マネージャー初期化
    manager = TaskProfileClassificationManager()
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n【テストケース {i}】{case['description']}")
        print(f"入力: \"{case['input']}\"")
        print("-" * 40)
        
        try:
            # ルールベース分類
            rule_result = manager.classify(case["input"], force_mode=ClassificationMode.RULE_ONLY)
            
            # ハイブリッド分類（実験モード）
            hybrid_result = manager.classify(case["input"], force_mode=ClassificationMode.HYBRID_EXPERIMENTAL)
            
            # 結果比較表示
            print(f"📝 ルールベース: {rule_result.profile_type.value} (信頼度: {rule_result.confidence:.2f})")
            print(f"🧠 ハイブリッド : {hybrid_result.profile_type.value} (信頼度: {hybrid_result.confidence:.2f})")
            
            # 一致判定
            if rule_result.profile_type == hybrid_result.profile_type:
                print("✅ 結果一致")
            else:
                print("⚠️ 結果相違 - ハイブリッドの改善効果")
                
        except Exception as e:
            print(f"❌ エラー: {e}")


def demo_guardrail_system():
    """ガードレールシステムのデモ"""
    print("\n" + "=" * 60)
    print("🛡️ ガードレールシステム デモ")
    print("=" * 60)
    
    from codecrafter.services.task_profile_guardrail import task_profile_guardrail
    
    # 誤分類を修正するテストケース
    test_corrections = [
        {
            "input": "ファイルを作成して新しい機能を実装して",
            "wrong_llm_result": {
                "profile_type": "INFORMATION_REQUEST",  # 誤分類
                "confidence": 0.7,
                "reasoning": "テスト用の意図的誤分類"
            },
            "description": "作成要求の誤分類修正"
        },
        {
            "input": "README.mdの内容だけ見たい",
            "wrong_llm_result": {
                "profile_type": "MODIFICATION_REQUEST",  # 誤分類
                "confidence": 0.6,
                "reasoning": "テスト用の意図的誤分類"
            },
            "description": "読み取り専用要求の修正"
        }
    ]
    
    for i, case in enumerate(test_corrections, 1):
        print(f"\n【ガードレールテスト {i}】{case['description']}")
        print(f"入力: \"{case['input']}\"")
        print(f"誤分類: {case['wrong_llm_result']['profile_type']}")
        
        try:
            corrected = task_profile_guardrail.validate_and_correct(
                case["input"], 
                case["wrong_llm_result"], 
                {}
            )
            
            print(f"修正後: {corrected['profile_type']}")
            
            if "guardrail_corrections" in corrected:
                print("🔧 適用された修正:")
                for correction in corrected["guardrail_corrections"]:
                    print(f"  - {correction['type']}: {correction['reason']}")
            else:
                print("修正不要")
                
        except Exception as e:
            print(f"❌ ガードレールエラー: {e}")


def demo_context_awareness():
    """コンテキスト認識デモ"""
    print("\n" + "=" * 60)
    print("🧭 コンテキスト認識デモ")
    print("=" * 60)
    
    test_request = "ファイルの内容を分析して問題を特定して"
    
    # 異なるコンテキストでテスト
    contexts = [
        {
            "name": "コンテキストなし",
            "context": {}
        },
        {
            "name": "単一ファイル", 
            "context": {
                "detected_files": ["main.py"]
            }
        },
        {
            "name": "複数ファイル",
            "context": {
                "detected_files": ["main.py", "config.py", "tests.py"]
            }
        },
        {
            "name": "リッチコンテキスト",
            "context": {
                "detected_files": ["app.py", "models.py"],
                "recent_messages": [
                    {"role": "user", "content": "プロジェクトの構造を教えて"}
                ],
                "workspace_manifest": {
                    "project_type": "Python Web Application"
                }
            }
        }
    ]
    
    print(f"テスト要求: \"{test_request}\"")
    print()
    
    for context_case in contexts:
        print(f"【{context_case['name']}】")
        
        try:
            result = hybrid_task_classifier.classify(test_request, context_case["context"])
            
            print(f"分類: {result.profile_type.value}")
            print(f"信頼度: {result.confidence:.2f}")
            print(f"方法: {result.classification_method}")
            print()
            
        except Exception as e:
            print(f"❌ エラー: {e}\n")


def demo_system_statistics():
    """システム統計情報のデモ"""
    print("\n" + "=" * 60)
    print("📊 システム統計情報デモ")
    print("=" * 60)
    
    manager = TaskProfileClassificationManager()
    
    # いくつかの分類を実行して統計を蓄積
    sample_requests = [
        "ファイルを作成して",
        "内容を確認して", 
        "問題を分析して",
        "設定を変更して",
        "テストを実行して"
    ]
    
    print("サンプル分類実行中...")
    for request in sample_requests:
        try:
            manager.classify(request, {})
        except:
            pass  # エラーは無視
    
    # 統計情報表示
    stats = manager.get_classification_statistics()
    print("\n📈 分類統計:")
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for sub_key, sub_value in value.items():
                print(f"    {sub_key}: {sub_value}")
        else:
            print(f"  {key}: {value}")
    
    # ヘルスチェック
    print("\n🏥 システムヘルスチェック:")
    health = manager.health_check()
    print(f"全体ステータス: {health['status']}")
    
    if "components" in health:
        for component, status in health["components"].items():
            health_icon = "✅" if status.get("healthy") else "❌"
            print(f"  {component}: {health_icon}")


def interactive_demo():
    """インタラクティブデモ"""
    print("\n" + "=" * 60)
    print("🎮 インタラクティブデモ")
    print("=" * 60)
    print("任意のタスク要求を入力してください（'quit'で終了）")
    
    manager = TaskProfileClassificationManager()
    
    while True:
        try:
            user_input = input("\n📝 要求を入力: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 デモを終了します")
                break
                
            if not user_input:
                continue
            
            # 分類実行
            result = manager.classify(user_input, {})
            
            print(f"📋 分類結果:")
            print(f"  TaskProfile: {result.profile_type.value}")
            print(f"  信頼度: {result.confidence:.2f}")
            print(f"  推論: {result.reasoning[:100]}...")
            
        except KeyboardInterrupt:
            print("\n👋 デモを終了します")
            break
        except Exception as e:
            print(f"❌ エラー: {e}")


def main():
    """メインデモ実行"""
    print("🚀 LLMベースTaskProfile分類システム 総合デモ")
    
    try:
        # 各デモを順次実行
        demo_classification_comparison()
        demo_guardrail_system() 
        demo_context_awareness()
        demo_system_statistics()
        
        # インタラクティブデモの選択
        print("\n" + "=" * 60)
        choice = input("インタラクティブデモを実行しますか？ (y/N): ").strip().lower()
        if choice in ['y', 'yes']:
            interactive_demo()
        
        print("\n🎉 デモ完了！")
        print("\n📚 実装内容:")
        print("  ✅ LLMService.classify_task_profile() メソッド")
        print("  ✅ Few-Shot Learning プロンプトシステム")
        print("  ✅ TaskProfileGuardrail 修正システム")
        print("  ✅ HybridTaskProfileClassifier 統合システム") 
        print("  ✅ TaskProfileClassificationManager 管理システム")
        print("  ✅ 設定ベース段階的移行機能")
        
    except Exception as e:
        print(f"❌ デモ実行エラー: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
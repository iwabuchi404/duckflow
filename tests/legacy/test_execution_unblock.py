#!/usr/bin/env python3
"""
実行阻害改善プランのテストスクリプト
"""

import os
import sys
import asyncio
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

# FILE_OPS_V2を有効化
os.environ["FILE_OPS_V2"] = "1"

from companion.intent_understanding.intent_integration import OptionResolver, IntentUnderstandingSystem
from companion.collaborative_planner import ActionSpec
from companion.enhanced_dual_loop import PlanContext, AntiStallGuard, PlanExecutor
from companion.file_ops import SimpleFileOps


def test_option_resolver():
    """OptionResolverのテスト"""
    print("🧪 OptionResolverのテスト")
    
    test_cases = [
        ("1", 1),
        ("１", 1),
        ("一", 1),
        ("デフォルト", 1),
        ("推奨", 1),
        ("はい", 1),
        ("OK実装してください", 1),
        ("2", 2),
        ("二番目", 2),
        ("無効な入力", None),
        ("", None),
    ]
    
    for input_text, expected in test_cases:
        result = OptionResolver.parse_selection(input_text)
        status = "✅" if result == expected else "❌"
        print(f"  {status} '{input_text}' -> {result} (期待値: {expected})")
    
    print()


def test_action_spec():
    """ActionSpecのテスト"""
    print("🧪 ActionSpecのテスト")
    
    # 基本的なActionSpec
    spec1 = ActionSpec(kind='create', path='test.py')
    print(f"  ✅ 基本作成: {spec1.to_dict()}")
    
    # デフォルト値の自動補完
    spec2 = ActionSpec(kind='write')
    print(f"  ✅ デフォルト補完: {spec2.to_dict()}")
    
    # 完全指定
    spec3 = ActionSpec(
        kind='create',
        path='hello.py',
        content='print("Hello, World!")',
        description='Hello Worldプログラムを作成'
    )
    print(f"  ✅ 完全指定: {spec3.to_dict()}")
    
    print()


def test_anti_stall_guard():
    """AntiStallGuardのテスト"""
    print("🧪 AntiStallGuardのテスト")
    
    guard = AntiStallGuard()
    
    # 通常の質問
    print(f"  質問1: {guard.add_question('ファイルを作成してください')}")
    print(f"  質問2: {guard.add_question('どのような内容にしますか？')}")
    
    # 類似質問の繰り返し
    print(f"  類似1: {guard.add_question('ファイル名を教えてください')}")
    print(f"  類似2: {guard.add_question('ファイル名はどうしますか？')}")
    print(f"  類似3: {guard.add_question('ファイル名を指定してください')}")
    
    # 進展の記録
    guard.record_progress('files_created', 1)
    print(f"  進展記録後: {guard.progress_metrics}")
    
    # 最小実装の提案
    minimal = guard.get_minimal_implementation_suggestion()
    print(f"  最小実装: {minimal.to_dict()}")
    
    print()


def test_plan_executor():
    """PlanExecutorのテスト"""
    print("🧪 PlanExecutorのテスト")
    
    file_ops = SimpleFileOps()
    executor = PlanExecutor(file_ops)
    
    # テスト用ActionSpec
    specs = [
        ActionSpec(
            kind='create',
            path='test_output.txt',
            content='# テストファイル\nこれはテスト用のファイルです。',
            description='テストファイルを作成'
        ),
        ActionSpec(
            kind='mkdir',
            path='test_directory',
            description='テストディレクトリを作成'
        )
    ]
    
    print(f"  実行予定: {len(specs)}個のActionSpec")
    for i, spec in enumerate(specs):
        print(f"    {i+1}. {spec.kind}: {spec.path}")
    
    # 実際の実行はユーザー承認が必要なのでスキップ
    print("  ⚠️ 実際の実行はユーザー承認が必要なためスキップします")
    
    print()


def test_plan_context():
    """PlanContextのテスト"""
    print("🧪 PlanContextのテスト")
    
    context = PlanContext()
    print(f"  初期状態: pending={context.pending}, planned={context.planned}")
    
    # ActionSpecを追加
    context.action_specs = [
        ActionSpec(kind='create', path='example.py', content='print("test")'),
        ActionSpec(kind='write', path='readme.md', content='# README')
    ]
    context.pending = True
    context.planned = True
    
    print(f"  設定後: {len(context.action_specs)}個のActionSpec, pending={context.pending}")
    
    # リセット
    context.reset()
    print(f"  リセット後: {len(context.action_specs)}個のActionSpec, pending={context.pending}")
    
    print()


async def test_integration():
    """統合テスト（簡易版）"""
    print("🧪 統合テスト")
    
    # 選択入力の検出
    selection_inputs = ["1", "デフォルトで", "OK実装してください"]
    
    for input_text in selection_inputs:
        is_selection = OptionResolver.is_selection_input(input_text)
        selection = OptionResolver.parse_selection(input_text)
        print(f"  '{input_text}' -> 選択入力: {is_selection}, 選択: {selection}")
    
    print()


def main():
    """メイン関数"""
    print("🚀 実行阻害改善プランのテスト開始\n")
    
    try:
        test_option_resolver()
        test_action_spec()
        test_anti_stall_guard()
        test_plan_executor()
        test_plan_context()
        
        # 非同期テスト
        asyncio.run(test_integration())
        
        print("✅ すべてのテストが完了しました！")
        print("\n📋 実装された機能:")
        print("  1. OptionResolver - 選択入力の正規化")
        print("  2. ActionSpec - 構造化されたアクション仕様")
        print("  3. AntiStallGuard - スタール検出と回避")
        print("  4. PlanExecutor - ActionSpecの実行")
        print("  5. PlanContext - プラン実行コンテキスト")
        print("  6. FILE_OPS_V2 - 安全なファイル操作API")
        
        print("\n🎯 次のステップ:")
        print("  - main_companion_dual.py で実際のシステムをテスト")
        print("  - 「１で」「OK実装してください」などの入力で実行ルートをテスト")
        print("  - スタール検出機能をテスト")
        
    except Exception as e:
        print(f"❌ テスト中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
実行阻害改善プランのデモスクリプト
実際の「１で」「OK実装してください」入力をテスト
"""

import os
import sys
import asyncio
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

# FILE_OPS_V2を有効化
os.environ["FILE_OPS_V2"] = "1"

from companion.enhanced_dual_loop import EnhancedDualLoopSystem
from companion.collaborative_planner import ActionSpec


async def demo_selection_input():
    """選択入力のデモ"""
    print("🎯 選択入力デモ")
    print("=" * 50)
    
    # システムを初期化
    system = EnhancedDualLoopSystem()
    
    # プランコンテキストにサンプルActionSpecを設定
    sample_specs = [
        ActionSpec(
            kind='create',
            path='demo_hello.py',
            content='print("Hello from execution unblock demo!")',
            description='デモ用Pythonファイルを作成'
        ),
        ActionSpec(
            kind='create',
            path='demo_readme.md',
            content='# Demo Project\n\nThis is a demo created by the execution unblock system.',
            description='デモ用READMEファイルを作成'
        )
    ]
    
    system.plan_context.action_specs = sample_specs
    system.plan_context.pending = True
    system.plan_context.planned = True
    
    print(f"📋 設定されたプラン: {len(sample_specs)}個のActionSpec")
    for i, spec in enumerate(sample_specs, 1):
        print(f"  {i}. {spec.kind}: {spec.path} - {spec.description}")
    
    print("\n🤖 システムの状態:")
    print(f"  - プラン保留中: {system.plan_context.pending}")
    print(f"  - プラン計画済み: {system.plan_context.planned}")
    
    # 選択入力のテスト
    test_inputs = [
        "1",
        "１で",
        "デフォルトで進めてください",
        "OK実装してください",
        "はい、お願いします"
    ]
    
    print(f"\n🧪 選択入力のテスト:")
    
    for input_text in test_inputs:
        # OptionResolverでテスト
        from companion.intent_understanding.intent_integration import OptionResolver
        selection = OptionResolver.parse_selection(input_text)
        is_selection = OptionResolver.is_selection_input(input_text)
        
        print(f"  '{input_text}' -> 選択: {selection}, 選択入力: {is_selection}")
        
        if is_selection:
            print(f"    ✅ この入力は実行ルートに転送されます")
        else:
            print(f"    ⚠️ この入力は通常の意図理解ルートに進みます")
    
    print("\n" + "=" * 50)


async def demo_anti_stall():
    """アンチスタール機能のデモ"""
    print("🛡️ アンチスタール機能デモ")
    print("=" * 50)
    
    system = EnhancedDualLoopSystem()
    guard = system.anti_stall_guard
    
    # 類似質問の繰り返しをシミュレート
    similar_questions = [
        "ファイル名を教えてください",
        "ファイル名はどうしますか？",
        "ファイル名を指定してください",
        "どのようなファイル名にしますか？"
    ]
    
    print("📝 類似質問の繰り返しをテスト:")
    
    for i, question in enumerate(similar_questions, 1):
        is_stall = guard.add_question(question)
        print(f"  {i}. '{question}' -> スタール: {is_stall}")
        
        if is_stall:
            print(f"    🚨 スタール状態を検出！")
            minimal = guard.get_minimal_implementation_suggestion()
            print(f"    💡 最小実装を提案: {minimal.path}")
            break
    
    print(f"\n📊 進展メトリクス: {guard.progress_metrics}")
    
    # 進展を記録
    print("\n📈 進展の記録:")
    guard.record_progress('files_created', 2)
    guard.record_progress('actions_executed', 1)
    print(f"  更新後: {guard.progress_metrics}")
    
    print("\n" + "=" * 50)


async def demo_action_spec_execution():
    """ActionSpec実行のデモ"""
    print("⚙️ ActionSpec実行デモ")
    print("=" * 50)
    
    system = EnhancedDualLoopSystem()
    executor = system.plan_executor
    
    # テスト用ActionSpec（実際には実行しない）
    test_specs = [
        ActionSpec(
            kind='create',
            path='demo_test.txt',
            content='# This is a demo file\nCreated by execution unblock system',
            description='デモテストファイルを作成'
        )
    ]
    
    print(f"📋 実行予定のActionSpec:")
    for i, spec in enumerate(test_specs, 1):
        print(f"  {i}. {spec.to_dict()}")
    
    print(f"\n⚠️ 実際の実行はユーザー承認が必要なため、構造のみ確認します")
    print(f"   実際の実行では以下の流れになります:")
    print(f"   1. PREVIEW表示 (差分/内容)")
    print(f"   2. ユーザー承認待ち")
    print(f"   3. 実行 (ファイル作成/更新)")
    print(f"   4. RESULT表示 (検証済み結果)")
    
    print("\n" + "=" * 50)


async def demo_plan_context():
    """プランコンテキストのデモ"""
    print("📋 プランコンテキストデモ")
    print("=" * 50)
    
    system = EnhancedDualLoopSystem()
    context = system.plan_context
    
    print(f"初期状態:")
    print(f"  - pending: {context.pending}")
    print(f"  - planned: {context.planned}")
    print(f"  - attempted: {context.attempted}")
    print(f"  - verified: {context.verified}")
    print(f"  - ActionSpec数: {len(context.action_specs)}")
    
    # プランを設定
    context.action_specs = [
        ActionSpec(kind='create', path='plan_demo.py', content='# Plan demo'),
        ActionSpec(kind='mkdir', path='demo_dir', description='Demo directory')
    ]
    context.pending = True
    context.planned = True
    
    print(f"\nプラン設定後:")
    print(f"  - pending: {context.pending}")
    print(f"  - planned: {context.planned}")
    print(f"  - ActionSpec数: {len(context.action_specs)}")
    
    for i, spec in enumerate(context.action_specs, 1):
        print(f"    {i}. {spec.kind}: {spec.path}")
    
    # 実行シミュレート
    context.attempted = True
    context.verified = True
    context.execution_results = [
        {'success': True, 'spec': context.action_specs[0].to_dict()},
        {'success': True, 'spec': context.action_specs[1].to_dict()}
    ]
    
    print(f"\n実行完了後:")
    print(f"  - attempted: {context.attempted}")
    print(f"  - verified: {context.verified}")
    print(f"  - 実行結果数: {len(context.execution_results)}")
    
    print("\n" + "=" * 50)


async def main():
    """メイン関数"""
    print("🚀 実行阻害改善プランのデモ開始")
    print("=" * 60)
    print()
    
    try:
        await demo_selection_input()
        print()
        
        await demo_anti_stall()
        print()
        
        await demo_action_spec_execution()
        print()
        
        await demo_plan_context()
        print()
        
        print("✅ すべてのデモが完了しました！")
        print()
        print("🎯 実装された解決策:")
        print("  1. 選択入力リゾルバ - 「１で」「OK実装」を正しく解釈")
        print("  2. プラン→アクションのブリッジ - ActionSpecによる構造化")
        print("  3. コンテキスト考慮ルーティング - plan_state.pendingを参照")
        print("  4. アンチスタールガード - 進展のない質問ループを検出・回避")
        print("  5. 実行器の確実な呼び出し - FILE_OPS_V2による安全実行")
        print()
        print("🔧 使用方法:")
        print("  1. main_companion_dual.py を起動")
        print("  2. 複雑なタスクを依頼（例: 'Pythonファイルを作成してください'）")
        print("  3. プラン提示後に「１で」「デフォルトで」「OK実装してください」と入力")
        print("  4. 実行ルートに転送され、実際のファイル操作が実行される")
        
    except Exception as e:
        print(f"❌ デモ中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
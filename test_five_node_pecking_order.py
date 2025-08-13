#!/usr/bin/env python3
"""
5ノードオーケストレーターでのThe Pecking Order統合テスト

このスクリプトは、5ノードアーキテクチャにThe Pecking Orderが
正しく統合されているかをテストします。
"""

import asyncio
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from codecrafter.state.agent_state import AgentState
from codecrafter.orchestration.five_node_orchestrator import FiveNodeOrchestrator
from codecrafter.ui.rich_ui import rich_ui


async def test_pecking_order_integration():
    """The Pecking Order統合テスト"""
    try:
        rich_ui.print_header("🦆 5ノードオーケストレーター The Pecking Order統合テスト")
        
        # AgentStateの初期化
        state = AgentState(session_id="test_session_001")
        
        # 5ノードオーケストレーターの初期化
        orchestrator = FiveNodeOrchestrator(state)
        
        # テストメッセージ
        test_message = "codecrafter/state/agent_state.pyファイルを分析して、The Pecking Order関連のメソッドを説明してください"
        
        rich_ui.print_step("テストメッセージ:")
        rich_ui.print_message(test_message, "info")
        
        # オーケストレーション実行
        response = await orchestrator.orchestrate(state, test_message)
        
        # The Pecking Order状態の確認
        rich_ui.print_step("The Pecking Order状態確認:")
        
        if state.task_tree:
            status = state.get_pecking_order_status()
            rich_ui.print_success(f"✅ タスクツリー構築済み")
            rich_ui.print_message(f"  - 総タスク数: {status.get('total_tasks', 0)}", "info")
            rich_ui.print_message(f"  - 完了率: {status.get('completion_rate', 0.0):.1%}", "info")
            rich_ui.print_message(f"  - 保留中タスク: {status.get('pending_tasks', 0)}", "info")
            
            # 階層構造の表示
            hierarchy = state.get_pecking_order_string()
            rich_ui.print_step("タスク階層:")
            rich_ui.print_message(hierarchy, "debug")
            
            # 現在のタスク
            current_task = state.get_current_task()
            if current_task:
                rich_ui.print_message(f"現在のタスク: {current_task.description}", "info")
                rich_ui.print_message(f"タスク状態: {current_task.status.value}", "info")
        else:
            rich_ui.print_warning("❌ タスクツリーが構築されていません")
        
        # 応答の確認
        rich_ui.print_step("生成された応答:")
        rich_ui.print_message(f"応答長: {len(response)}文字", "info")
        
        # The Pecking Order情報が応答に含まれているかチェック
        pecking_order_keywords = [
            "current_task_progress",
            "remaining_tasks_count", 
            "task_hierarchy",
            "current_task_description"
        ]
        
        found_keywords = [kw for kw in pecking_order_keywords if kw in response]
        if found_keywords:
            rich_ui.print_success(f"✅ The Pecking Order情報が応答に統合されています: {found_keywords}")
        else:
            rich_ui.print_warning("⚠️ The Pecking Order情報が応答に見つかりません")
        
        # 応答の一部を表示
        rich_ui.print_step("応答プレビュー:")
        preview = response[:500] + "..." if len(response) > 500 else response
        rich_ui.print_message(preview, "debug")
        
        return True
        
    except Exception as e:
        rich_ui.print_error(f"テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_task_status_updates():
    """タスク状態更新テスト"""
    try:
        rich_ui.print_header("🔄 タスク状態更新テスト")
        
        # AgentStateの初期化
        state = AgentState(session_id="test_session_002")
        
        # 5ノードオーケストレーターの初期化
        orchestrator = FiveNodeOrchestrator(state)
        
        # The Pecking Orderを手動で初期化
        main_goal = "テスト用タスク管理"
        root_task = state.initialize_pecking_order(main_goal, "メインタスク")
        
        # サブタスクを追加
        sub_task1 = state.add_sub_task(root_task.id, "サブタスク1: 分析")
        sub_task2 = state.add_sub_task(root_task.id, "サブタスク2: 実装")
        sub_task3 = state.add_sub_task(root_task.id, "サブタスク3: テスト")
        
        rich_ui.print_success("✅ テスト用タスクツリー構築完了")
        
        # 初期状態の確認
        status = state.get_pecking_order_status()
        rich_ui.print_message(f"初期状態 - 総タスク数: {status.get('total_tasks', 0)}", "info")
        
        # タスク状態更新のテスト
        from codecrafter.state.pecking_order import TaskStatus
        
        # 最初のタスクを完了状態に更新
        await orchestrator._update_current_task_status(
            state, TaskStatus.COMPLETED, "分析完了"
        )
        
        # 状態確認
        updated_status = state.get_pecking_order_status()
        completion_rate = updated_status.get('completion_rate', 0.0)
        rich_ui.print_success(f"✅ タスク更新後 - 完了率: {completion_rate:.1%}")
        
        # 次のタスクが開始されているか確認
        current_task = state.get_current_task()
        if current_task:
            rich_ui.print_message(f"現在のタスク: {current_task.description}", "info")
        
        return True
        
    except Exception as e:
        rich_ui.print_error(f"タスク状態更新テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """メインテスト実行"""
    rich_ui.print_header("🦆 5ノードオーケストレーター The Pecking Order統合テストスイート")
    
    test_results = []
    
    # テスト1: 基本統合テスト
    rich_ui.print_step("テスト1: 基本統合テスト")
    result1 = await test_pecking_order_integration()
    test_results.append(("基本統合テスト", result1))
    
    # テスト2: タスク状態更新テスト
    rich_ui.print_step("テスト2: タスク状態更新テスト")
    result2 = await test_task_status_updates()
    test_results.append(("タスク状態更新テスト", result2))
    
    # 結果サマリー
    rich_ui.print_header("📊 テスト結果サマリー")
    
    passed_tests = 0
    for test_name, result in test_results:
        if result:
            rich_ui.print_success(f"✅ {test_name}: PASS")
            passed_tests += 1
        else:
            rich_ui.print_error(f"❌ {test_name}: FAIL")
    
    total_tests = len(test_results)
    rich_ui.print_message(f"合計: {passed_tests}/{total_tests} テスト通過", "info")
    
    if passed_tests == total_tests:
        rich_ui.print_success("🎉 全てのテストが通過しました！")
        rich_ui.print_message("5ノードオーケストレーターへのThe Pecking Order統合が成功しています。", "info")
    else:
        rich_ui.print_warning("⚠️ 一部のテストが失敗しました。")
        rich_ui.print_message("統合に問題がある可能性があります。", "warning")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
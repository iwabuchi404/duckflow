#!/usr/bin/env python3
"""
簡単なThe Pecking Order統合テスト
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from codecrafter.state.agent_state import AgentState
from codecrafter.ui.rich_ui import rich_ui


def test_basic_pecking_order():
    """基本的なThe Pecking Order機能テスト"""
    try:
        rich_ui.print_header("🦆 基本的なThe Pecking Order機能テスト")
        
        # AgentStateの初期化
        state = AgentState(session_id="test_basic")
        
        # The Pecking Orderの初期化
        main_goal = "テストプロジェクトの分析"
        root_task = state.initialize_pecking_order(main_goal, "プロジェクト全体の分析を行う")
        
        rich_ui.print_success(f"✅ ルートタスク作成: {root_task.description}")
        
        # サブタスクの追加
        sub_tasks = [
            "ファイル構造の分析",
            "依存関係の確認", 
            "コード品質の評価",
            "ドキュメントの確認"
        ]
        
        for i, task_desc in enumerate(sub_tasks):
            sub_task = state.add_sub_task(root_task.id, task_desc, priority=i)
            if sub_task:
                rich_ui.print_message(f"  └─ サブタスク追加: {task_desc}", "info")
        
        # 状態確認
        status = state.get_pecking_order_status()
        rich_ui.print_step("The Pecking Order状態:")
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
        
        # タスク完了のテスト
        from codecrafter.state.pecking_order import TaskStatus
        
        if current_task:
            # 現在のタスクを完了状態に更新
            current_task.update_status(TaskStatus.COMPLETED, "分析完了")
            rich_ui.print_success(f"✅ タスク完了: {current_task.description}")
            
            # 次のタスクを開始
            next_task = state.start_next_task()
            if next_task:
                rich_ui.print_message(f"次のタスク開始: {next_task.description}", "info")
            
            # 更新後の状態確認
            updated_status = state.get_pecking_order_status()
            completion_rate = updated_status.get('completion_rate', 0.0)
            rich_ui.print_message(f"更新後の完了率: {completion_rate:.1%}", "info")
        
        rich_ui.print_success("🎉 基本的なThe Pecking Order機能テスト完了")
        return True
        
    except Exception as e:
        rich_ui.print_error(f"テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_basic_pecking_order()
    sys.exit(0 if success else 1)
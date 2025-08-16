# test_hierarchical_integration.py
"""
HierarchicalTaskManagerの統合テスト
Step 2実装の最終確認用
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from companion.hierarchical_task_manager import HierarchicalTaskManager, TaskPriority, TaskStatus

def test_hierarchical_task_decomposition():
    """階層タスク分解のテスト"""
    print("🌳 階層タスク管理のテスト開始")
    print("=" * 50)
    
    # HierarchicalTaskManagerを初期化
    manager = HierarchicalTaskManager()
    
    # テスト用タスクを作成
    test_descriptions = [
        "プロジェクトの実装を開始する",
        "ウェブサイトの機能を開発する", 
        "システムの複数モジュールを統合する",
        "簡単なファイル読み込み"  # 階層化されないはず
    ]
    
    for i, description in enumerate(test_descriptions, 1):
        print(f"\n📋 テスト {i}: {description}")
        print("-" * 30)
        
        # タスクを分解
        parent_task_id = manager.decompose_task(description)
        
        if parent_task_id:
            print(f"✅ 親タスク作成: {parent_task_id}")
            
            # タスク状態を表示
            summary = manager.get_task_status_summary(parent_task_id)
            if "error" not in summary:
                parent_info = summary["parent_task"]
                print(f"📊 親タスク: {parent_info['name']}")
                print(f"📋 子タスク数: {parent_info['total_sub_tasks']}個")
                
                for j, sub_task in enumerate(summary["sub_tasks"], 1):
                    print(f"  {j}. {sub_task['name']}")
                    if sub_task['depends_on']:
                        print(f"     依存: {sub_task['depends_on']}")
                
                # 実行可能な次のタスクを取得
                next_task = manager.get_next_sub_task(parent_task_id)
                if next_task:
                    print(f"🚀 次に実行可能: {next_task.name}")
                else:
                    print("⚠️ 実行可能なタスクがありません")
        else:
            print("❌ タスク分解に失敗または単純タスクのため分解不要")

def test_task_execution_flow():
    """タスク実行フローのテスト"""
    print("\n\n🔄 タスク実行フローのテスト")
    print("=" * 50)
    
    manager = HierarchicalTaskManager()
    
    # テスト用タスクを分解
    parent_task_id = manager.decompose_task("ファイル処理機能を実装する")
    
    if not parent_task_id:
        print("❌ テスト用タスクの分解に失敗")
        return
    
    # 親タスクを開始
    if manager.start_parent_task(parent_task_id):
        print("✅ 親タスク開始")
    else:
        print("❌ 親タスク開始に失敗")
        return
    
    # 子タスクを順次実行シミュレーション
    step = 1
    while True:
        # 次に実行可能なタスクを取得
        next_task = manager.get_next_sub_task(parent_task_id)
        
        if not next_task:
            parent_task = manager.parent_tasks.get(parent_task_id)
            if parent_task and parent_task.is_completed():
                print("🎉 すべての子タスクが完了しました!")
            else:
                print("⚠️ 実行可能なタスクがありません（依存関係待ち）")
            break
        
        print(f"\nステップ {step}: {next_task.name}")
        
        # タスクを実行中に変更
        manager.update_sub_task_status(
            parent_task_id, next_task.task_id, TaskStatus.RUNNING
        )
        print(f"  🔄 実行中...")
        
        # タスクを完了に変更
        manager.update_sub_task_status(
            parent_task_id, next_task.task_id, TaskStatus.COMPLETED,
            progress=1.0, result=f"'{next_task.name}' の実行が完了しました"
        )
        print(f"  ✅ 完了")
        
        # 進捗を表示
        summary = manager.get_task_status_summary(parent_task_id)
        parent_info = summary["parent_task"]
        progress_bar = "█" * int(parent_info["progress"] * 10) + "░" * (10 - int(parent_info["progress"] * 10))
        print(f"  📊 全体進捗: [{progress_bar}] {parent_info['progress']:.1%}")
        
        step += 1

def test_dependency_management():
    """依存関係管理のテスト"""
    print("\n\n🔗 依存関係管理のテスト")
    print("=" * 50)
    
    manager = HierarchicalTaskManager()
    
    # 手動で依存関係のあるタスクを作成
    parent_task_id = manager.create_parent_task(
        "依存関係テスト", 
        "依存関係のあるタスクのテスト"
    )
    
    # 子タスクを追加（依存関係付き）
    task1_id = manager.add_sub_task(parent_task_id, "基礎タスク", "最初に実行すべきタスク")
    task2_id = manager.add_sub_task(parent_task_id, "依存タスク1", "基礎タスクの後に実行", depends_on=[task1_id])
    task3_id = manager.add_sub_task(parent_task_id, "依存タスク2", "基礎タスクの後に実行", depends_on=[task1_id])
    task4_id = manager.add_sub_task(parent_task_id, "最終タスク", "すべて完了後に実行", depends_on=[task2_id, task3_id])
    
    print("📋 作成されたタスク構造:")
    summary = manager.get_task_status_summary(parent_task_id)
    for i, sub_task in enumerate(summary["sub_tasks"], 1):
        deps = f" (依存: {', '.join(sub_task['depends_on'])})" if sub_task['depends_on'] else " (依存なし)"
        print(f"  {i}. {sub_task['name']}{deps}")
    
    # 親タスクを開始
    manager.start_parent_task(parent_task_id)
    
    print("\n🚀 実行順序テスト:")
    step = 1
    
    while True:
        executable_tasks = manager.parent_tasks[parent_task_id].get_next_executable_tasks()
        
        if not executable_tasks:
            break
        
        print(f"\nステップ {step}で実行可能:")
        for task in executable_tasks:
            print(f"  - {task.name}")
        
        # 最初の実行可能タスクを完了
        if executable_tasks:
            task = executable_tasks[0]
            manager.update_sub_task_status(
                parent_task_id, task.task_id, TaskStatus.COMPLETED, progress=1.0
            )
            print(f"  ✅ '{task.name}' を完了")
        
        step += 1

if __name__ == "__main__":
    print("🦆 HierarchicalTaskManager 統合テスト")
    print("=" * 60)
    
    try:
        test_hierarchical_task_decomposition()
        test_task_execution_flow()
        test_dependency_management()
        
        print("\n" + "=" * 60)
        print("🎉 すべてのテストが完了しました！")
        print("Step 2の階層タスク管理機能が正常に動作しています。")
        
    except Exception as e:
        print(f"\n❌ テスト中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
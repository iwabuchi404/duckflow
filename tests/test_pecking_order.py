"""
The Pecking Order システムのテスト
"""

import pytest
from datetime import datetime
from codecrafter.state.pecking_order import Task, TaskStatus, PeckingOrderManager


class TestTask:
    """Taskクラスのテスト"""
    
    def test_task_creation(self):
        """タスクの基本作成テスト"""
        task = Task(description="テストタスク")
        
        assert task.description == "テストタスク"
        assert task.status == TaskStatus.PENDING
        assert task.parent_id is None
        assert len(task.sub_tasks) == 0
        assert task.result is None
        assert task.error is None
        assert isinstance(task.created_at, datetime)
        assert task.started_at is None
        assert task.completed_at is None
        
    def test_add_sub_task(self):
        """サブタスクの追加テスト"""
        parent = Task(description="親タスク")
        child = Task(description="子タスク")
        
        parent.add_sub_task(child)
        
        assert len(parent.sub_tasks) == 1
        assert parent.sub_tasks[0] == child
        assert child.parent_id == parent.id
        
    def test_remove_sub_task(self):
        """サブタスクの削除テスト"""
        parent = Task(description="親タスク")
        child = Task(description="子タスク")
        
        parent.add_sub_task(child)
        assert len(parent.sub_tasks) == 1
        
        # 正しいIDで削除
        success = parent.remove_sub_task(child.id)
        assert success
        assert len(parent.sub_tasks) == 0
        
        # 存在しないIDで削除
        success = parent.remove_sub_task("non_existent_id")
        assert not success
        
    def test_find_task_by_id(self):
        """ID検索テスト"""
        root = Task(description="ルート")
        child1 = Task(description="子1")
        child2 = Task(description="子2")
        grandchild = Task(description="孫")
        
        root.add_sub_task(child1)
        root.add_sub_task(child2)
        child1.add_sub_task(grandchild)
        
        # 自分自身を検索
        found = root.find_task_by_id(root.id)
        assert found == root
        
        # 子タスクを検索
        found = root.find_task_by_id(child1.id)
        assert found == child1
        
        # 孫タスクを検索
        found = root.find_task_by_id(grandchild.id)
        assert found == grandchild
        
        # 存在しないIDを検索
        found = root.find_task_by_id("non_existent")
        assert found is None
        
    def test_get_next_pending_task(self):
        """次のPENDINGタスク取得テスト"""
        root = Task(description="ルート")
        child1 = Task(description="子1")
        child2 = Task(description="子2")
        grandchild = Task(description="孫")
        
        root.add_sub_task(child1)
        root.add_sub_task(child2)
        child1.add_sub_task(grandchild)
        
        # 全てPENDINGの場合、最初の孫タスクが返される
        next_task = root.get_next_pending_task()
        assert next_task == grandchild
        
        # 孫タスクをCOMPLETED にすると、次の子タスクが返される
        grandchild.update_status(TaskStatus.COMPLETED)
        next_task = root.get_next_pending_task()
        assert next_task == child1
        
        # 子1もCOMPLETEDにすると、child2が返される
        child1.update_status(TaskStatus.COMPLETED)
        next_task = root.get_next_pending_task()
        assert next_task == child2
        
        # 全ての子がCOMPLETEDになると、ルートが返される
        child2.update_status(TaskStatus.COMPLETED)
        next_task = root.get_next_pending_task()
        assert next_task == root
        
        # ルートもCOMPLETEDにすると、Noneが返される
        root.update_status(TaskStatus.COMPLETED)
        next_task = root.get_next_pending_task()
        assert next_task is None
        
    def test_update_status(self):
        """ステータス更新テスト"""
        task = Task(description="テストタスク")
        
        # PENDING -> IN_PROGRESS
        task.update_status(TaskStatus.IN_PROGRESS)
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None
        assert task.completed_at is None
        
        # IN_PROGRESS -> COMPLETED
        task.update_status(TaskStatus.COMPLETED, result="完了しました")
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "完了しました"
        assert task.completed_at is not None
        
        # エラーでFAILED
        failed_task = Task(description="失敗タスク")
        failed_task.update_status(TaskStatus.FAILED, error="エラーが発生")
        assert failed_task.status == TaskStatus.FAILED
        assert failed_task.error == "エラーが発生"
        
    def test_get_completion_rate(self):
        """完了率計算テスト"""
        root = Task(description="ルート")
        child1 = Task(description="子1")
        child2 = Task(description="子2")
        
        root.add_sub_task(child1)
        root.add_sub_task(child2)
        
        # 最初は0%
        assert root.get_completion_rate() == 0.0
        
        # 子1を完了 -> 50%
        child1.update_status(TaskStatus.COMPLETED)
        assert root.get_completion_rate() == 0.5
        
        # 子2も完了 -> 100%
        child2.update_status(TaskStatus.COMPLETED)
        assert root.get_completion_rate() == 1.0
        
    def test_get_all_tasks_flat(self):
        """平坦化テスト"""
        root = Task(description="ルート")
        child1 = Task(description="子1")
        child2 = Task(description="子2")
        grandchild = Task(description="孫")
        
        root.add_sub_task(child1)
        root.add_sub_task(child2)
        child1.add_sub_task(grandchild)
        
        all_tasks = root.get_all_tasks_flat()
        
        assert len(all_tasks) == 4
        assert root in all_tasks
        assert child1 in all_tasks
        assert child2 in all_tasks
        assert grandchild in all_tasks
        
    def test_get_status_summary(self):
        """ステータスサマリーテスト"""
        root = Task(description="ルート")
        child1 = Task(description="子1")
        child2 = Task(description="子2")
        
        root.add_sub_task(child1)
        root.add_sub_task(child2)
        
        child1.update_status(TaskStatus.COMPLETED)
        child2.update_status(TaskStatus.FAILED)
        
        summary = root.get_status_summary()
        
        assert summary["total_tasks"] == 3
        assert summary["completion_rate"] == 0.5  # 1/2の子タスクが完了
        assert summary["status_breakdown"]["PENDING"] == 1  # ルート
        assert summary["status_breakdown"]["COMPLETED"] == 1  # 子1
        assert summary["status_breakdown"]["FAILED"] == 1  # 子2
        assert summary["root_task"]["description"] == "ルート"
        
    def test_to_hierarchical_string(self):
        """階層文字列表現テスト"""
        root = Task(description="ルートタスク")
        child = Task(description="子タスク")
        
        root.add_sub_task(child)
        child.update_status(TaskStatus.COMPLETED)
        
        hierarchy_str = root.to_hierarchical_string()
        
        assert "ルートタスク" in hierarchy_str
        assert "子タスク" in hierarchy_str
        assert "⏳" in hierarchy_str  # PENDING のルート
        assert "✅" in hierarchy_str  # COMPLETED の子


class TestPeckingOrderManager:
    """PeckingOrderManagerクラスのテスト"""
    
    def test_create_root_task(self):
        """ルートタスク作成テスト"""
        manager = PeckingOrderManager("テストゴール")
        
        root = manager.create_root_task("ルートタスク")
        
        assert root is not None
        assert root.description == "ルートタスク"
        assert manager.task_tree == root
        assert manager.main_goal == "テストゴール"
        
    def test_add_sub_task(self):
        """サブタスク追加テスト"""
        manager = PeckingOrderManager("テストゴール")
        root = manager.create_root_task("ルートタスク")
        
        sub_task = manager.add_sub_task(root.id, "サブタスク", priority=1)
        
        assert sub_task is not None
        assert sub_task.description == "サブタスク"
        assert sub_task.priority == 1
        assert len(root.sub_tasks) == 1
        assert root.sub_tasks[0] == sub_task
        
        # 存在しない親IDの場合
        non_existent_sub = manager.add_sub_task("non_existent", "失敗タスク")
        assert non_existent_sub is None
        
    def test_get_next_task(self):
        """次タスク取得テスト"""
        manager = PeckingOrderManager("テストゴール")
        root = manager.create_root_task("ルートタスク")
        sub1 = manager.add_sub_task(root.id, "サブタスク1")
        sub2 = manager.add_sub_task(root.id, "サブタスク2")
        
        # 最初のサブタスクが返される
        next_task = manager.get_next_task()
        assert next_task == sub1
        
        # サブタスク1を完了すると、サブタスク2が返される
        sub1.update_status(TaskStatus.COMPLETED)
        next_task = manager.get_next_task()
        assert next_task == sub2
        
    def test_start_task(self):
        """タスク開始テスト"""
        manager = PeckingOrderManager("テストゴール")
        root = manager.create_root_task("ルートタスク")
        sub_task = manager.add_sub_task(root.id, "サブタスク")
        
        # タスク開始
        success = manager.start_task(sub_task.id)
        
        assert success
        assert sub_task.status == TaskStatus.IN_PROGRESS
        assert manager.current_task_id == sub_task.id
        
        # 既に開始済みのタスクを再開始（失敗する）
        success = manager.start_task(sub_task.id)
        assert not success
        
        # 存在しないタスクの開始（失敗する）
        success = manager.start_task("non_existent")
        assert not success
        
    def test_complete_task(self):
        """タスク完了テスト"""
        manager = PeckingOrderManager("テストゴール")
        root = manager.create_root_task("ルートタスク")
        sub1 = manager.add_sub_task(root.id, "サブタスク1")
        sub2 = manager.add_sub_task(root.id, "サブタスク2")
        
        manager.start_task(sub1.id)
        
        # タスク完了
        success = manager.complete_task(sub1.id, "完了結果")
        
        assert success
        assert sub1.status == TaskStatus.COMPLETED
        assert sub1.result == "完了結果"
        assert manager.current_task_id == sub2.id  # 自動的に次のタスクに移行
        
    def test_fail_task(self):
        """タスク失敗テスト"""
        manager = PeckingOrderManager("テストゴール")
        root = manager.create_root_task("ルートタスク")
        sub_task = manager.add_sub_task(root.id, "サブタスク")
        
        # タスクを失敗させる
        success = manager.fail_task(sub_task.id, "エラーが発生しました")
        
        assert success
        assert sub_task.status == TaskStatus.FAILED
        assert sub_task.error == "エラーが発生しました"
        
    def test_get_status_summary(self):
        """ステータスサマリー取得テスト"""
        manager = PeckingOrderManager("テストゴール")
        
        # タスクツリーがない場合
        summary = manager.get_status_summary()
        assert summary["main_goal"] == "テストゴール"
        assert summary["task_tree"] is None
        assert summary["total_tasks"] == 0
        
        # タスクツリーがある場合
        root = manager.create_root_task("ルートタスク")
        sub_task = manager.add_sub_task(root.id, "サブタスク")
        
        summary = manager.get_status_summary()
        assert summary["main_goal"] == "テストゴール"
        assert summary["total_tasks"] == 2
        assert summary["completion_rate"] == 0.0
        
    def test_to_string(self):
        """文字列表現テスト"""
        manager = PeckingOrderManager("テストゴール")
        
        # タスクツリーがない場合
        string_repr = manager.to_string()
        assert "テストゴール" in string_repr
        assert "No tasks defined" in string_repr
        
        # タスクツリーがある場合
        root = manager.create_root_task("ルートタスク")
        manager.add_sub_task(root.id, "サブタスク")
        
        string_repr = manager.to_string()
        assert "テストゴール" in string_repr
        assert "ルートタスク" in string_repr
        assert "サブタスク" in string_repr


if __name__ == "__main__":
    pytest.main([__file__])
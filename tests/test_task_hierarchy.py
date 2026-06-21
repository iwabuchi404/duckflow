"""
Tests for companion/task_management/task_hierarchy.py

TaskNode and TaskHierarchy provide hierarchical task data structures.
The module depends on companion.intent_understanding.task_profile_classifier
which does not exist yet, so we mock it at import time.
"""

import sys
import types
from enum import Enum  # noqa: E402

# ------------------------------------------------------------------
# Stub the missing intent_understanding package before importing
# ------------------------------------------------------------------
_iu_pkg = types.ModuleType("companion.intent_understanding")
_iu_mod = types.ModuleType("companion.intent_understanding.task_profile_classifier")


class _TaskProfileType(Enum):
    CREATION_REQUEST = "creation_request"
    ANALYSIS_REQUEST = "analysis_request"
    MODIFICATION_REQUEST = "modification_request"
    SEARCH_REQUEST = "search_request"
    GUIDANCE_REQUEST = "guidance_request"
    INFORMATION_REQUEST = "information_request"


class _TaskProfileResult:
    def __init__(self, profile_type, confidence=0.9, complexity_assessment="moderate"):
        self.profile_type = profile_type
        self.confidence = confidence
        self.complexity_assessment = complexity_assessment


_iu_mod.TaskProfileType = _TaskProfileType  # type: ignore[attr-defined]
_iu_mod.TaskProfileResult = _TaskProfileResult  # type: ignore[attr-defined]
_iu_pkg.task_profile_classifier = _iu_mod  # type: ignore[attr-defined]

sys.modules["companion.intent_understanding"] = _iu_pkg
sys.modules["companion.intent_understanding.task_profile_classifier"] = _iu_mod

# Now we can import the real module
from companion.task_management.task_hierarchy import (  # noqa: E402
    TaskHierarchy,
    TaskNode,
    TaskPriority,
    TaskStatus,
)

# ============================================================
# TaskNode tests
# ============================================================


class TestTaskNodeBasic:
    def test_default_fields(self) -> None:
        node = TaskNode(title="Test")
        assert node.title == "Test"
        assert node.status == TaskStatus.PENDING
        assert node.priority == TaskPriority.MEDIUM
        assert node.children == []
        assert node.parent_id is None
        assert node.metadata == {}

    def test_add_child(self) -> None:
        node = TaskNode(title="Parent")
        node.add_child("child-1")
        assert "child-1" in node.children

    def test_add_child_idempotent(self) -> None:
        node = TaskNode(title="Parent")
        node.add_child("child-1")
        node.add_child("child-1")
        assert node.children.count("child-1") == 1

    def test_remove_child(self) -> None:
        node = TaskNode(title="Parent")
        node.add_child("child-1")
        node.remove_child("child-1")
        assert "child-1" not in node.children

    def test_remove_nonexistent_child_is_noop(self) -> None:
        node = TaskNode(title="Parent")
        node.remove_child("nope")  # should not raise

    def test_is_leaf(self) -> None:
        node = TaskNode(title="Leaf")
        assert node.is_leaf()
        node.add_child("c")
        assert not node.is_leaf()

    def test_is_root(self) -> None:
        root = TaskNode(title="Root")
        assert root.is_root()
        child = TaskNode(title="Child", parent_id="some-parent")
        assert not child.is_root()


class TestTaskNodeProgress:
    def test_completed_returns_1(self) -> None:
        node = TaskNode(status=TaskStatus.COMPLETED)
        assert node.get_progress() == 1.0

    def test_in_progress_returns_half(self) -> None:
        node = TaskNode(status=TaskStatus.IN_PROGRESS)
        assert node.get_progress() == 0.5

    def test_pending_returns_0(self) -> None:
        node = TaskNode(status=TaskStatus.PENDING)
        assert node.get_progress() == 0.0

    def test_failed_returns_0(self) -> None:
        node = TaskNode(status=TaskStatus.FAILED)
        assert node.get_progress() == 0.0

    def test_cancelled_returns_0(self) -> None:
        node = TaskNode(status=TaskStatus.CANCELLED)
        assert node.get_progress() == 0.0


class TestTaskNodeSerialization:
    def test_to_dict_roundtrip(self) -> None:
        node = TaskNode(
            title="Test Task",
            description="Description",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            complexity="complex",
            metadata={"key": "val"},
        )
        d = node.to_dict()
        assert d["title"] == "Test Task"
        assert d["status"] == "in_progress"
        assert d["priority"] == "high"

        restored = TaskNode.from_dict(d)
        assert restored.title == node.title
        assert restored.status == node.status
        assert restored.priority == node.priority

    def test_from_dict_with_missing_fields(self) -> None:
        d = {"title": "Minimal"}
        node = TaskNode.from_dict(d)
        assert node.title == "Minimal"
        assert node.status == TaskStatus.PENDING
        assert node.priority == TaskPriority.MEDIUM

    def test_from_dict_invalid_datetime_uses_now(self) -> None:
        d = {"created_at": "not-a-date"}
        node = TaskNode.from_dict(d)
        assert node.created_at is not None

    def test_from_dict_invalid_started_at_ignored(self) -> None:
        d = {"started_at": "bad"}
        node = TaskNode.from_dict(d)
        assert node.started_at is None

    def test_from_dict_invalid_task_profile_ignored(self) -> None:
        d = {"task_profile": "nonexistent_type"}
        node = TaskNode.from_dict(d)
        assert node.task_profile is None


class TestTaskNodeDepth:
    def test_root_depth_is_zero(self) -> None:
        h = TaskHierarchy()
        root = TaskNode(title="Root")
        h.add_task(root)
        assert root.get_depth(h) == 0

    def test_child_depth_is_one(self) -> None:
        h = TaskHierarchy()
        root = TaskNode(title="Root")
        h.add_task(root)
        child = TaskNode(title="Child", parent_id=root.id)
        h.add_task(child)
        assert child.get_depth(h) == 1

    def test_grandchild_depth_is_two(self) -> None:
        h = TaskHierarchy()
        root = TaskNode(title="Root")
        h.add_task(root)
        child = TaskNode(title="Child", parent_id=root.id)
        h.add_task(child)
        grandchild = TaskNode(title="GC", parent_id=child.id)
        h.add_task(grandchild)
        assert grandchild.get_depth(h) == 2


class TestTaskNodeDescendants:
    def test_leaf_has_no_descendants(self) -> None:
        h = TaskHierarchy()
        leaf = TaskNode(title="Leaf")
        h.add_task(leaf)
        assert leaf.get_all_descendants(h) == []

    def test_descendants_includes_all_levels(self) -> None:
        h = TaskHierarchy()
        root = TaskNode(title="Root")
        h.add_task(root)
        child = TaskNode(title="Child", parent_id=root.id)
        h.add_task(child)
        grandchild = TaskNode(title="GC", parent_id=child.id)
        h.add_task(grandchild)
        desc = root.get_all_descendants(h)
        assert child.id in desc
        assert grandchild.id in desc


# ============================================================
# TaskHierarchy tests
# ============================================================


class TestTaskHierarchyAddRemove:
    def test_add_root_task(self) -> None:
        h = TaskHierarchy()
        t = TaskNode(title="Root")
        h.add_task(t)
        assert h.get_task_count() == 1
        assert t.id in h.root_tasks

    def test_add_child_task(self) -> None:
        h = TaskHierarchy()
        root = TaskNode(title="Root")
        h.add_task(root)
        child = TaskNode(title="Child", parent_id=root.id)
        h.add_task(child)
        assert h.get_task_count() == 2
        assert child.id in root.children
        assert child.id not in h.root_tasks

    def test_remove_root_task(self) -> None:
        h = TaskHierarchy()
        t = TaskNode(title="Root")
        h.add_task(t)
        assert h.remove_task(t.id)
        assert h.get_task_count() == 0
        assert t.id not in h.root_tasks

    def test_remove_nonexistent_returns_false(self) -> None:
        h = TaskHierarchy()
        assert not h.remove_task("fake-id")

    def test_remove_cascades_to_children(self) -> None:
        h = TaskHierarchy()
        root = TaskNode(title="Root")
        h.add_task(root)
        child = TaskNode(title="Child", parent_id=root.id)
        h.add_task(child)
        h.remove_task(root.id)
        assert h.get_task_count() == 0

    def test_remove_child_updates_parent(self) -> None:
        h = TaskHierarchy()
        root = TaskNode(title="Root")
        h.add_task(root)
        child = TaskNode(title="Child", parent_id=root.id)
        h.add_task(child)
        h.remove_task(child.id)
        assert child.id not in root.children


class TestTaskHierarchyQueries:
    def _build(self) -> TaskHierarchy:
        h = TaskHierarchy()
        t1 = TaskNode(
            title="A", status=TaskStatus.COMPLETED, priority=TaskPriority.HIGH
        )
        t2 = TaskNode(title="B", status=TaskStatus.PENDING, priority=TaskPriority.LOW)
        t3 = TaskNode(
            title="C", status=TaskStatus.IN_PROGRESS, priority=TaskPriority.MEDIUM
        )
        h.add_task(t1)
        h.add_task(t2)
        h.add_task(t3)
        return h

    def test_get_root_tasks(self) -> None:
        h = self._build()
        roots = h.get_root_tasks()
        assert len(roots) == 3

    def test_get_leaf_tasks(self) -> None:
        h = self._build()
        leaves = h.get_leaf_tasks()
        assert len(leaves) == 3  # all are leaves (no children)

    def test_get_tasks_by_status(self) -> None:
        h = self._build()
        completed = h.get_tasks_by_status(TaskStatus.COMPLETED)
        assert len(completed) == 1

    def test_get_tasks_by_priority(self) -> None:
        h = self._build()
        high = h.get_tasks_by_priority(TaskPriority.HIGH)
        assert len(high) == 1

    def test_get_completed_task_count(self) -> None:
        h = self._build()
        assert h.get_completed_task_count() == 1

    def test_get_children_nonexistent(self) -> None:
        h = TaskHierarchy()
        assert h.get_children("nope") == []

    def test_get_parent_of_root(self) -> None:
        h = TaskHierarchy()
        root = TaskNode(title="Root")
        h.add_task(root)
        assert h.get_parent(root.id) is None

    def test_get_parent_of_child(self) -> None:
        h = TaskHierarchy()
        root = TaskNode(title="Root")
        h.add_task(root)
        child = TaskNode(title="Child", parent_id=root.id)
        h.add_task(child)
        parent = h.get_parent(child.id)
        assert parent is not None
        assert parent.id == root.id


class TestTaskHierarchyProgress:
    def test_empty_hierarchy_progress(self) -> None:
        h = TaskHierarchy()
        assert h.get_overall_progress() == 0.0

    def test_all_completed(self) -> None:
        h = TaskHierarchy()
        for _ in range(3):
            h.add_task(TaskNode(status=TaskStatus.COMPLETED))
        assert h.get_overall_progress() == 1.0

    def test_mixed_progress(self) -> None:
        h = TaskHierarchy()
        h.add_task(TaskNode(status=TaskStatus.COMPLETED))  # 1.0
        h.add_task(TaskNode(status=TaskStatus.PENDING))  # 0.0
        assert h.get_overall_progress() == 0.5


class TestTaskHierarchyCriticalPath:
    def test_returns_critical_tasks_first(self) -> None:
        h = TaskHierarchy()
        h.add_task(TaskNode(title="Med", priority=TaskPriority.MEDIUM))
        h.add_task(TaskNode(title="Crit", priority=TaskPriority.CRITICAL))
        path = h.get_critical_path()
        assert len(path) == 1
        assert path[0].title == "Crit"

    def test_falls_back_to_high(self) -> None:
        h = TaskHierarchy()
        h.add_task(TaskNode(title="Med", priority=TaskPriority.MEDIUM))
        h.add_task(TaskNode(title="High", priority=TaskPriority.HIGH))
        path = h.get_critical_path()
        assert path[0].title == "High"

    def test_falls_back_to_medium(self) -> None:
        h = TaskHierarchy()
        h.add_task(TaskNode(title="Med", priority=TaskPriority.MEDIUM))
        h.add_task(TaskNode(title="Low", priority=TaskPriority.LOW))
        path = h.get_critical_path()
        assert path[0].title == "Med"


class TestTaskHierarchyValidation:
    def test_valid_hierarchy_no_errors(self) -> None:
        h = TaskHierarchy()
        root = TaskNode(title="Root")
        h.add_task(root)
        child = TaskNode(title="Child", parent_id=root.id)
        h.add_task(child)
        assert h.validate_hierarchy() == []

    def test_orphan_parent_detected(self) -> None:
        h = TaskHierarchy()
        orphan = TaskNode(title="Orphan", parent_id="missing-parent")
        h.tasks[orphan.id] = orphan  # bypass add_task to create inconsistency
        errors = h.validate_hierarchy()
        assert len(errors) > 0
        assert "存在しません" in errors[0]


class TestTaskHierarchySerialization:
    def test_to_dict_from_dict_roundtrip(self) -> None:
        h = TaskHierarchy()
        root = TaskNode(title="Root")
        h.add_task(root)
        child = TaskNode(title="Child", parent_id=root.id)
        h.add_task(child)

        d = h.to_dict()
        h2 = TaskHierarchy.from_dict(d)
        assert h2.get_task_count() == 2
        assert root.id in h2.root_tasks


class TestTaskHierarchyPrintHierarchy:
    def test_print_does_not_raise(self, capsys) -> None:
        h = TaskHierarchy()
        root = TaskNode(title="Root")
        h.add_task(root)
        child = TaskNode(title="Child", parent_id=root.id)
        h.add_task(child)
        h.print_hierarchy()
        captured = capsys.readouterr()
        assert "Root" in captured.out
        assert "Child" in captured.out

    def test_print_nonexistent_task_is_noop(self) -> None:
        h = TaskHierarchy()
        h.print_hierarchy("nonexistent")  # should not raise

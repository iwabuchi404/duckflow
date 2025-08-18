"""
PlanTool テストスイート
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock

from companion.plan_tool import (
    PlanTool, MessageRef, SpecSelection, PlanStatus, RiskLevel,
    ActionSpecExt, Plan, PlanState, ValidationReport, ExecutionResult
)
from companion.collaborative_planner import ActionSpec


class TestPlanTool:
    """PlanTool基本機能テスト"""
    
    def setup_method(self):
        """テスト前準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.plan_tool = PlanTool(logs_dir=self.temp_dir, allow_external_paths=True)
    
    def teardown_method(self):
        """テスト後クリーンアップ"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_propose_plan(self):
        """プラン提案テスト"""
        # プラン提案
        plan_id = self.plan_tool.propose(
            content="# テストプラン\n- ファイル作成\n- テスト実行",
            sources=[MessageRef("msg1", "2025-01-01T00:00:00")],
            rationale="テスト目的",
            tags=["test", "demo"]
        )
        
        # 結果確認
        assert plan_id is not None
        assert len(plan_id) > 0
        
        # 現在のプランとして設定されているか
        current = self.plan_tool.get_current()
        assert current is not None
        assert current['id'] == plan_id
        assert current['title'] == "テストプラン"
        assert current['status'] == PlanStatus.PROPOSED.value
        
        # プラン一覧に含まれているか
        plans = self.plan_tool.list()
        assert len(plans) == 1
        assert plans[0]['id'] == plan_id
    
    def test_set_action_specs_valid(self):
        """有効なActionSpec設定テスト"""
        # プラン作成
        plan_id = self.plan_tool.propose(
            content="テストプラン",
            sources=[],
            rationale="テスト",
            tags=[]
        )
        
        # ActionSpec設定
        specs = [
            ActionSpec(kind='create', path='test.txt', content='Hello World'),
            ActionSpec(kind='mkdir', path='test_dir'),
            ActionSpec(kind='read', path='existing.txt')
        ]
        
        result = self.plan_tool.set_action_specs(plan_id, specs)
        
        # バリデーション成功確認
        assert result.ok is True
        assert len(result.issues) == 0
        assert len(result.normalized) == 3
        
        # 状態確認
        state = self.plan_tool.get_state(plan_id)
        assert state['state']['status'] == PlanStatus.PENDING_REVIEW.value
        assert state['state']['action_count'] == 3
    
    def test_set_action_specs_invalid_path(self):
        """無効なパスのActionSpecテスト"""
        plan_id = self.plan_tool.propose("テスト", [], "テスト", [])
        
        # 危険なパスを含むActionSpec
        specs = [
            ActionSpec(kind='create', path='../outside.txt', content='危険'),
            ActionSpec(kind='write', path='/etc/passwd', content='システムファイル')
        ]
        
        result = self.plan_tool.set_action_specs(plan_id, specs)
        
        # バリデーション失敗確認
        assert result.ok is False
        assert len(result.issues) > 0
        assert any("相対パス" in issue for issue in result.issues)
    
    def test_risk_assessment(self):
        """リスク評価テスト"""
        plan_id = self.plan_tool.propose("テスト", [], "テスト", [])
        
        specs = [
            ActionSpec(kind='create', path='normal.txt', content='通常'),  # LOW
            ActionSpec(kind='write', path='.env', content='重要ファイル'),  # HIGH
            ActionSpec(kind='run', path=None, content='rm -rf /')  # HIGH
        ]
        
        result = self.plan_tool.set_action_specs(plan_id, specs)
        
        # リスクレベル確認
        risks = [spec.risk for spec in result.normalized]
        assert RiskLevel.LOW in risks
        assert RiskLevel.HIGH in risks
    
    def test_preview_plan(self):
        """プランプレビューテスト"""
        plan_id = self.plan_tool.propose("テスト", [], "テスト", [])
        
        specs = [
            ActionSpec(kind='create', path='file1.txt', content='内容1'),
            ActionSpec(kind='create', path='file2.txt', content='内容2')
        ]
        
        self.plan_tool.set_action_specs(plan_id, specs)
        
        # プレビュー取得
        preview = self.plan_tool.preview(plan_id)
        
        assert len(preview.files) == 2
        assert 'file1.txt' in preview.files
        assert 'file2.txt' in preview.files
        assert preview.risk_score >= 0.0
        assert preview.risk_score <= 1.0
    
    def test_approval_workflow(self):
        """承認ワークフローテスト"""
        plan_id = self.plan_tool.propose("テスト", [], "テスト", [])
        
        specs = [ActionSpec(kind='create', path='test.txt', content='テスト')]
        self.plan_tool.set_action_specs(plan_id, specs)
        
        # 承認要求
        selection = SpecSelection(all=True)
        approval_id = self.plan_tool.request_approval(plan_id, selection)
        assert approval_id is not None
        
        # 承認実行
        approved = self.plan_tool.approve(plan_id, "test_user", selection)
        assert approved['plan_id'] == plan_id
        assert approved['approver'] == "test_user"
        
        # 状態確認
        state = self.plan_tool.get_state(plan_id)
        assert state['state']['status'] == PlanStatus.APPROVED.value
        assert state['state']['approved_count'] == 1
    
    def test_execution_workflow(self):
        """実行ワークフローテスト"""
        plan_id = self.plan_tool.propose("テスト", [], "テスト", [])
        
        # テストファイル作成用のActionSpec
        test_file = Path(self.temp_dir) / "test_output.txt"
        specs = [
            ActionSpec(kind='create', path=str(test_file), content='テスト内容')
        ]
        
        self.plan_tool.set_action_specs(plan_id, specs)
        
        # 承認
        selection = SpecSelection(all=True)
        self.plan_tool.request_approval(plan_id, selection)
        self.plan_tool.approve(plan_id, "test_user", selection)
        
        # 実行
        result = self.plan_tool.execute(plan_id)
        
        # 結果確認
        assert isinstance(result, ExecutionResult)
        print(f"実行結果: {result}")
        print(f"結果詳細: {result.results}")
        assert len(result.results) == 1
        assert result.started_at is not None
        assert result.finished_at is not None
        
        # ファイルが実際に作成されたか確認
        print(f"テストファイルパス: {test_file}")
        print(f"ファイル存在: {test_file.exists()}")
        assert test_file.exists()
        assert test_file.read_text(encoding='utf-8') == 'テスト内容'
        
        # 状態確認
        state = self.plan_tool.get_state(plan_id)
        assert state['state']['status'] == PlanStatus.COMPLETED.value
    
    def test_execution_without_approval(self):
        """未承認実行エラーテスト"""
        plan_id = self.plan_tool.propose("テスト", [], "テスト", [])
        
        specs = [ActionSpec(kind='create', path='test.txt', content='テスト')]
        self.plan_tool.set_action_specs(plan_id, specs)
        
        # 承認なしで実行を試行
        with pytest.raises(ValueError, match="未承認のプランは実行できません"):
            self.plan_tool.execute(plan_id)
    
    def test_partial_selection(self):
        """部分選択テスト"""
        plan_id = self.plan_tool.propose("テスト", [], "テスト", [])
        
        specs = [
            ActionSpec(kind='create', path='file1.txt', content='内容1'),
            ActionSpec(kind='create', path='file2.txt', content='内容2'),
            ActionSpec(kind='create', path='file3.txt', content='内容3')
        ]
        
        result = self.plan_tool.set_action_specs(plan_id, specs)
        
        # 最初の2つのActionSpecのIDを取得
        selected_ids = [spec.id for spec in result.normalized[:2]]
        
        # 部分選択で承認
        selection = SpecSelection(all=False, ids=selected_ids)
        self.plan_tool.request_approval(plan_id, selection)
        self.plan_tool.approve(plan_id, "test_user", selection)
        
        # 実行（選択された分のみ）
        execution_result = self.plan_tool.execute(plan_id)
        
        # 2つのActionSpecのみ実行されたか確認
        assert len(execution_result.results) == 2
    
    def test_persistence(self):
        """永続化テスト"""
        # プラン作成
        plan_id = self.plan_tool.propose("永続化テスト", [], "テスト", ["persistence"])
        
        specs = [ActionSpec(kind='create', path='persistent.txt', content='永続化')]
        self.plan_tool.set_action_specs(plan_id, specs)
        
        # 新しいPlanToolインスタンスで読み込み
        new_plan_tool = PlanTool(logs_dir=self.temp_dir)
        
        # データが復元されているか確認
        current = new_plan_tool.get_current()
        assert current is not None
        assert current['id'] == plan_id
        assert current['title'] == "永続化テスト"
        
        plans = new_plan_tool.list()
        assert len(plans) == 1
        assert plans[0]['id'] == plan_id
        
        state = new_plan_tool.get_state(plan_id)
        assert state['state']['action_count'] == 1


class TestPlanToolIntegration:
    """PlanTool統合テスト"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.plan_tool = PlanTool(logs_dir=self.temp_dir, allow_external_paths=True)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_complete_workflow(self):
        """完全なワークフローテスト"""
        # 1. プラン提案
        plan_id = self.plan_tool.propose(
            content="# 完全テストプラン\n- ディレクトリ作成\n- ファイル作成\n- 内容確認",
            sources=[MessageRef("workflow_test", "2025-01-01T00:00:00")],
            rationale="完全なワークフローをテスト",
            tags=["integration", "complete"]
        )
        
        # 2. ActionSpec設定
        test_dir = Path(self.temp_dir) / "workflow_test"
        test_file = test_dir / "result.txt"
        
        specs = [
            ActionSpec(kind='mkdir', path=str(test_dir)),
            ActionSpec(kind='create', path=str(test_file), content='ワークフロー成功'),
            ActionSpec(kind='read', path=str(test_file))
        ]
        
        validation = self.plan_tool.set_action_specs(plan_id, specs)
        assert validation.ok
        
        # 3. プレビュー
        preview = self.plan_tool.preview(plan_id)
        assert len(preview.files) == 2  # mkdir は files に含まれない
        
        # 4. 承認要求・承認
        selection = SpecSelection(all=True)
        approval_id = self.plan_tool.request_approval(plan_id, selection)
        approved = self.plan_tool.approve(plan_id, "integration_tester", selection)
        
        # 5. 実行
        result = self.plan_tool.execute(plan_id)
        
        # 6. 結果確認
        assert result.overall_success
        assert len(result.results) == 3
        
        # 実際のファイルシステム確認
        assert test_dir.exists()
        assert test_file.exists()
        assert test_file.read_text(encoding='utf-8') == 'ワークフロー成功'
        
        # 最終状態確認
        final_state = self.plan_tool.get_state(plan_id)
        assert final_state['state']['status'] == PlanStatus.COMPLETED.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
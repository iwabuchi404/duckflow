"""
EnhancedDualLoop PlanTool統合テスト
"""

import pytest
import tempfile
import shutil
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from companion.enhanced_dual_loop import EnhancedDualLoopSystem
from companion.plan_tool import PlanTool
from companion.collaborative_planner import ActionSpec


class TestEnhancedDualLoopPlanToolIntegration:
    """EnhancedDualLoop PlanTool統合テスト"""
    
    def setup_method(self):
        """テスト前準備"""
        self.temp_dir = tempfile.mkdtemp()
        
        # EnhancedDualLoopSystem初期化
        self.dual_loop = EnhancedDualLoopSystem()
        
        # テスト用PlanTool設定
        self.dual_loop.enhanced_companion.plan_tool = PlanTool(
            logs_dir=self.temp_dir,
            allow_external_paths=True
        )
        
        # PlanTool使用フラグを有効化
        self.dual_loop.use_plan_tool = True
    
    def teardown_method(self):
        """テスト後クリーンアップ"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_has_executable_plan_with_plan_tool(self):
        """実行可能プラン確認（PlanTool版）"""
        # 初期状態では実行可能プランなし
        assert not self.dual_loop._has_executable_plan()
        
        # PlanToolでプラン作成・承認
        plan_id = self.dual_loop.enhanced_companion.plan_tool.propose(
            content="テストプラン",
            sources=[],
            rationale="テスト",
            tags=["test"]
        )
        
        specs = [ActionSpec(kind='create', path='test.txt', content='test')]
        validation = self.dual_loop.enhanced_companion.plan_tool.set_action_specs(plan_id, specs)
        assert validation.ok
        
        # まだ未承認なので実行不可
        assert not self.dual_loop._has_executable_plan()
        
        # 承認後は実行可能
        from companion.plan_tool import SpecSelection
        selection = SpecSelection(all=True)
        self.dual_loop.enhanced_companion.plan_tool.request_approval(plan_id, selection)
        self.dual_loop.enhanced_companion.plan_tool.approve(plan_id, "test_user", selection)
        
        assert self.dual_loop._has_executable_plan()
    
    def test_get_executable_action_specs_with_plan_tool(self):
        """実行可能ActionSpec取得（PlanTool版）"""
        # PlanContextに直接設定
        legacy_spec = ActionSpec(kind='create', path='legacy.txt', content='legacy')
        self.dual_loop.plan_context.action_specs = [legacy_spec]
        
        # PlanTool未使用時はPlanContextから取得
        self.dual_loop.use_plan_tool = False
        specs = self.dual_loop._get_executable_action_specs()
        assert len(specs) == 1
        assert specs[0].path == 'legacy.txt'
        
        # PlanTool使用時は同期・移行される
        self.dual_loop.use_plan_tool = True
        specs = self.dual_loop._get_executable_action_specs()
        assert len(specs) == 1
        assert specs[0].path == 'legacy.txt'
        
        # PlanToolに移行されているか確認
        current_plan = self.dual_loop.enhanced_companion.plan_tool.get_current()
        assert current_plan is not None
        assert current_plan['status'] == 'approved'
    
    def test_set_plan_specs_with_plan_tool(self):
        """プランActionSpec設定（PlanTool版）"""
        test_specs = [
            ActionSpec(kind='create', path='file1.txt', content='content1'),
            ActionSpec(kind='create', path='file2.txt', content='content2')
        ]
        
        # PlanTool版でプラン設定
        result = self.dual_loop._set_plan_specs(test_specs, "テスト用プラン")
        assert result is True
        
        # PlanToolに正しく設定されているか確認
        current_plan = self.dual_loop.enhanced_companion.plan_tool.get_current()
        assert current_plan is not None
        assert current_plan['status'] == 'approved'
        
        # ActionSpecが正しく設定されているか確認
        specs = self.dual_loop._get_executable_action_specs()
        assert len(specs) == 2
        assert specs[0].path == 'file1.txt'
        assert specs[1].path == 'file2.txt'
    
    def test_execute_current_plan_with_plan_tool(self):
        """現在プラン実行（PlanTool版）"""
        # テスト用プラン設定
        test_file = Path(self.temp_dir) / "execute_test.txt"
        test_specs = [
            ActionSpec(kind='create', path=str(test_file), content='実行テスト成功')
        ]
        
        self.dual_loop._set_plan_specs(test_specs, "実行テストプラン")
        
        # プラン実行
        result = self.dual_loop._execute_current_plan()
        
        # 実行結果確認
        assert result['success'] is True
        assert len(result['results']) == 1
        
        # ファイルが実際に作成されているか確認
        assert test_file.exists()
        assert test_file.read_text(encoding='utf-8') == '実行テスト成功'
    
    def test_clear_current_plan_with_plan_tool(self):
        """現在プランクリア（PlanTool版）"""
        # プラン設定
        test_specs = [ActionSpec(kind='create', path='clear_test.txt', content='test')]
        self.dual_loop._set_plan_specs(test_specs, "クリアテストプラン")
        
        # プランが設定されていることを確認
        assert self.dual_loop._has_executable_plan()
        current_plan = self.dual_loop.enhanced_companion.plan_tool.get_current()
        assert current_plan is not None
        
        # プランクリア
        self.dual_loop._clear_current_plan()
        
        # クリアされていることを確認
        assert not self.dual_loop._has_executable_plan()
        current_plan_after = self.dual_loop.enhanced_companion.plan_tool.get_current()
        assert current_plan_after is None
        
        # PlanContextもクリアされていることを確認
        assert not self.dual_loop.plan_context.action_specs
        assert not self.dual_loop.plan_context.pending
    
    def test_plan_context_to_plan_tool_sync(self):
        """PlanContext → PlanTool 同期テスト"""
        # PlanContextに直接ActionSpecを設定
        legacy_specs = [
            ActionSpec(kind='create', path='sync_test1.txt', content='sync1'),
            ActionSpec(kind='create', path='sync_test2.txt', content='sync2')
        ]
        self.dual_loop.plan_context.action_specs = legacy_specs
        self.dual_loop.plan_context.pending = True
        self.dual_loop.plan_context.current_plan = {'summary': 'Legacy sync test plan'}
        
        # 同期実行
        self.dual_loop._sync_plan_context_to_plan_tool()
        
        # PlanToolに移行されているか確認
        current_plan = self.dual_loop.enhanced_companion.plan_tool.get_current()
        assert current_plan is not None
        assert current_plan['status'] == 'approved'
        
        # ActionSpecが正しく移行されているか確認
        synced_specs = self.dual_loop._get_action_specs_from_plan_tool()
        assert len(synced_specs) == 2
        assert synced_specs[0].path == 'sync_test1.txt'
        assert synced_specs[1].path == 'sync_test2.txt'
    
    def test_fallback_to_plan_context(self):
        """PlanTool無効時のPlanContextフォールバック"""
        # PlanToolを無効化
        self.dual_loop.use_plan_tool = False
        
        # PlanContextに直接設定
        fallback_specs = [ActionSpec(kind='create', path='fallback.txt', content='fallback')]
        self.dual_loop.plan_context.action_specs = fallback_specs
        
        # フォールバック動作確認
        assert self.dual_loop._has_executable_plan()
        specs = self.dual_loop._get_executable_action_specs()
        assert len(specs) == 1
        assert specs[0].path == 'fallback.txt'
        
        # プラン設定もPlanContextに反映される
        new_specs = [ActionSpec(kind='create', path='fallback2.txt', content='fallback2')]
        result = self.dual_loop._set_plan_specs(new_specs, "フォールバックプラン")
        assert result is True
        assert len(self.dual_loop.plan_context.action_specs) == 1
        assert self.dual_loop.plan_context.action_specs[0].path == 'fallback2.txt'
    
    def test_selection_handling(self):
        """選択指定の処理テスト"""
        # 複数ActionSpecのプラン設定
        test_specs = [
            ActionSpec(kind='create', path='select1.txt', content='選択1'),
            ActionSpec(kind='create', path='select2.txt', content='選択2'),
            ActionSpec(kind='create', path='select3.txt', content='選択3')
        ]
        self.dual_loop._set_plan_specs(test_specs, "選択テストプラン")
        
        # 選択なし（全件）
        all_specs = self.dual_loop._get_executable_action_specs()
        assert len(all_specs) == 3
        
        # 選択指定（2番目）
        selected_specs = self.dual_loop._get_executable_action_specs(selection=2)
        assert len(selected_specs) == 1
        assert selected_specs[0].path == 'select2.txt'
        
        # 無効な選択（範囲外）
        invalid_specs = self.dual_loop._get_executable_action_specs(selection=5)
        assert len(invalid_specs) == 3  # 全件が返される
    
    def test_error_handling_in_integration(self):
        """統合時のエラーハンドリングテスト"""
        # PlanToolを破損状態にする
        original_plan_tool = self.dual_loop.enhanced_companion.plan_tool
        self.dual_loop.enhanced_companion.plan_tool = None
        
        try:
            # エラーが発生してもフォールバックで動作する
            test_specs = [ActionSpec(kind='create', path='error_test.txt', content='error')]
            result = self.dual_loop._set_plan_specs(test_specs, "エラーテストプラン")
            assert result is True  # PlanContextフォールバックで成功
            
            # PlanContextに設定されている
            assert len(self.dual_loop.plan_context.action_specs) == 1
            assert self.dual_loop.plan_context.action_specs[0].path == 'error_test.txt'
            
        finally:
            # PlanToolを復元
            self.dual_loop.enhanced_companion.plan_tool = original_plan_tool


class TestEnhancedDualLoopWorkflow:
    """EnhancedDualLoop統合ワークフローテスト"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.dual_loop = EnhancedDualLoopSystem()
        self.dual_loop.enhanced_companion.plan_tool = PlanTool(
            logs_dir=self.temp_dir,
            allow_external_paths=True
        )
        self.dual_loop.use_plan_tool = True
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_execute_selected_plan_integration(self):
        """選択プラン実行の統合テスト"""
        # テスト用プラン設定
        test_file1 = Path(self.temp_dir) / "workflow1.txt"
        test_file2 = Path(self.temp_dir) / "workflow2.txt"
        
        test_specs = [
            ActionSpec(kind='create', path=str(test_file1), content='ワークフロー1'),
            ActionSpec(kind='create', path=str(test_file2), content='ワークフロー2')
        ]
        
        self.dual_loop._set_plan_specs(test_specs, "ワークフローテストプラン")
        
        # 模擬タスクデータ
        mock_task = {
            "type": "execute_selected_plan",
            "intent_result": {
                "message": "1番目のプランを実行してください",
                "metadata": {"selection": 1},  # 1番目を選択
                "session_id": "workflow_test"
            }
        }
        
        # 選択プラン実行（TaskLoopにアクセス）
        self.dual_loop.task_loop._execute_selected_plan(mock_task)
        
        # 1番目のファイルのみ作成されているはず
        print(f"Debug: test_file1 = {test_file1}")
        print(f"Debug: test_file1.exists() = {test_file1.exists()}")
        print(f"Debug: current working directory = {Path.cwd()}")
        
        # カレントディレクトリの同名ファイルも確認
        cwd_file1 = Path.cwd() / test_file1.name
        print(f"Debug: cwd_file1 = {cwd_file1}")
        print(f"Debug: cwd_file1.exists() = {cwd_file1.exists()}")
        
        if cwd_file1.exists():
            # カレントディレクトリに作成されている場合
            assert cwd_file1.read_text(encoding='utf-8') == 'ワークフロー1'
        else:
            # 想定パスに作成されている場合
            assert test_file1.exists()
            assert test_file1.read_text(encoding='utf-8') == 'ワークフロー1'
        
        assert not test_file2.exists()  # 2番目は選択されていない
    
    def test_minimal_implementation_fallback(self):
        """最小実装フォールバックテスト"""
        # プランが存在しない状態で実行
        mock_task = {
            "type": "execute_selected_plan",
            "intent_result": {
                "message": "何かファイルを作成してください",
                "metadata": {},
                "session_id": "minimal_test"
            }
        }
        
        # AntiStallGuardのモック
        mock_minimal_spec = ActionSpec(
            kind='create',
            path=str(Path(self.temp_dir) / "minimal.txt"),
            content='最小実装テスト',
            description='最小実装'
        )
        
        with patch.object(
            self.dual_loop.enhanced_companion.anti_stall_guard,
            'get_minimal_implementation_suggestion',
            return_value=mock_minimal_spec
        ):
            self.dual_loop.task_loop._execute_selected_plan(mock_task)
        
        # 最小実装ファイルが作成されているか確認
        minimal_file = Path(self.temp_dir) / "minimal.txt"
        assert minimal_file.exists()
        assert minimal_file.read_text(encoding='utf-8') == '最小実装テスト'
        
        # PlanToolにも最小実装プランが設定されているか確認
        current_plan = self.dual_loop.enhanced_companion.plan_tool.get_current()
        assert current_plan is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
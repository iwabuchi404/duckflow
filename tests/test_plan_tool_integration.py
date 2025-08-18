"""
PlanTool統合テスト - EnhancedCoreとの統合
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from companion.enhanced_core import EnhancedCompanionCore
from companion.plan_tool import PlanTool, MessageRef
from companion.collaborative_planner import ActionSpec


class TestPlanToolIntegration:
    """PlanTool統合テスト"""
    
    def setup_method(self):
        """テスト前準備"""
        self.temp_dir = tempfile.mkdtemp()
        
        # EnhancedCoreを初期化（PlanToolも含む）
        self.enhanced_core = EnhancedCompanionCore()
        
        # テスト用にPlanToolを一時ディレクトリに設定
        self.enhanced_core.plan_tool = PlanTool(
            logs_dir=self.temp_dir, 
            allow_external_paths=True
        )
    
    def teardown_method(self):
        """テスト後クリーンアップ"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_enhanced_core_plan_proposal(self):
        """EnhancedCore経由でのプラン提案テスト"""
        # プラン提案
        plan_id = self.enhanced_core.propose_plan(
            content="# テスト統合プラン\n- ファイル作成\n- テスト実行",
            rationale="統合テスト用",
            tags=["integration", "test"]
        )
        
        # プランが作成されたか確認
        assert plan_id is not None
        
        # 現在のプランとして設定されているか
        current = self.enhanced_core.get_current_plan()
        assert current is not None
        assert current['id'] == plan_id
        
        # プラン一覧に含まれているか
        plans = self.enhanced_core.list_plans()
        assert len(plans) == 1
        assert plans[0]['id'] == plan_id
    
    def test_enhanced_core_action_spec_workflow(self):
        """EnhancedCore経由でのActionSpecワークフローテスト"""
        # プラン提案
        plan_id = self.enhanced_core.propose_plan(
            content="統合テストプラン",
            rationale="ActionSpecテスト"
        )
        
        # ActionSpec設定
        test_file = Path(self.temp_dir) / "integration_test.txt"
        specs = [
            {
                'kind': 'create',
                'path': str(test_file),
                'content': '統合テスト成功',
                'description': '統合テスト用ファイル作成'
            }
        ]
        
        result = self.enhanced_core.set_plan_action_specs(plan_id, specs)
        assert result['ok'] is True
        assert result['action_count'] == 1
        
        # プレビュー
        preview = self.enhanced_core.preview_plan(plan_id)
        assert len(preview['files']) == 1
        assert str(test_file) in preview['files']
        
        # 承認
        approval_result = self.enhanced_core.approve_plan(plan_id, "integration_tester")
        assert approval_result['plan_id'] == plan_id
        
        # 実行
        execution_result = self.enhanced_core.execute_plan(plan_id)
        assert execution_result['success'] is True
        assert len(execution_result['results']) == 1
        
        # ファイルが実際に作成されたか確認
        assert test_file.exists()
        assert test_file.read_text(encoding='utf-8') == '統合テスト成功'
    
    def test_legacy_compatibility(self):
        """従来のset_plan_stateとの互換性テスト"""
        # 従来のset_plan_stateを使用
        plan_content = "# 互換性テストプラン\n- レガシー機能テスト"
        self.enhanced_core.set_plan_state(plan_content, "compatibility_test")
        
        # 従来の状態が設定されているか確認
        plan_state = self.enhanced_core.get_plan_state()
        assert plan_state['pending'] is True
        assert plan_state['plan_content'] == plan_content
        assert plan_state['plan_type'] == "compatibility_test"
        
        # PlanToolにもプランが作成されているか確認
        assert 'plan_id' in plan_state
        
        current_plan = self.enhanced_core.get_current_plan()
        assert current_plan is not None
        assert current_plan['id'] == plan_state['plan_id']
        
        # プラン状態クリア
        self.enhanced_core.clear_plan_state()
        
        # 状態がクリアされているか確認
        cleared_state = self.enhanced_core.get_plan_state()
        assert cleared_state['pending'] is False
        assert cleared_state['plan_content'] is None
        
        # PlanToolの現在のプランもクリアされているか確認
        current_after_clear = self.enhanced_core.get_current_plan()
        assert current_after_clear is None
    
    def test_error_handling(self):
        """エラーハンドリングテスト"""
        # 存在しないプランIDでの操作
        with pytest.raises(ValueError):
            self.enhanced_core.preview_plan("non_existent_plan")
        
        # 無効なActionSpecでの設定
        plan_id = self.enhanced_core.propose_plan("エラーテスト", "エラーハンドリング")
        
        invalid_specs = [
            {
                'kind': 'create',
                'path': '../dangerous_path.txt',  # 危険なパス
                'content': 'test'
            }
        ]
        
        result = self.enhanced_core.set_plan_action_specs(plan_id, invalid_specs)
        assert result['ok'] is False
        assert len(result['issues']) > 0
    
    def test_plan_tool_fallback(self):
        """PlanToolエラー時のフォールバック動作テスト"""
        # PlanToolを無効化してエラーを発生させる
        original_plan_tool = self.enhanced_core.plan_tool
        self.enhanced_core.plan_tool = None
        
        try:
            # set_plan_stateがフォールバックモードで動作するか確認
            self.enhanced_core.set_plan_state("フォールバックテスト", "fallback_test")
            
            plan_state = self.enhanced_core.get_plan_state()
            assert plan_state['pending'] is True
            assert plan_state['plan_content'] == "フォールバックテスト"
            # plan_idは設定されていないはず
            assert 'plan_id' not in plan_state or plan_state['plan_id'] is None
            
        finally:
            # PlanToolを復元
            self.enhanced_core.plan_tool = original_plan_tool


class TestPlanToolDualLoopIntegration:
    """PlanTool DualLoop統合テスト"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('companion.enhanced_dual_loop.llm_manager')
    def test_dual_loop_plan_tool_sync(self, mock_llm):
        """DualLoopでのPlanTool同期テスト"""
        from companion.enhanced_dual_loop import EnhancedDualLoopSystem
        
        # モックLLMの設定
        mock_llm.generate_response.return_value = "テスト応答"
        
        # DualLoopシステム初期化
        dual_loop = EnhancedDualLoopSystem()
        dual_loop.enhanced_companion.plan_tool = PlanTool(
            logs_dir=self.temp_dir,
            allow_external_paths=True
        )
        
        # PlanContextにActionSpecを設定
        from companion.collaborative_planner import ActionSpec
        test_spec = ActionSpec(
            kind='create',
            path=str(Path(self.temp_dir) / "dual_loop_test.txt"),
            content='DualLoop統合テスト',
            description='DualLoop統合テスト用ファイル'
        )
        
        dual_loop.plan_context.action_specs = [test_spec]
        dual_loop.plan_context.pending = True
        
        # PlanContextからPlanToolへの同期をテスト
        dual_loop._sync_plan_context_to_plan_tool()
        
        # PlanToolにプランが作成されているか確認
        current_plan = dual_loop.enhanced_companion.plan_tool.get_current()
        assert current_plan is not None
        assert current_plan['status'] == 'approved'  # 自動承認されているはず
        
        # ActionSpecが正しく移行されているか確認
        action_specs = dual_loop._get_action_specs_from_plan_tool()
        assert len(action_specs) == 1
        assert action_specs[0].kind == 'create'
        assert action_specs[0].content == 'DualLoop統合テスト'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
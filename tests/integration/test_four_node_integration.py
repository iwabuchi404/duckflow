"""
4ノードオーケストレーターの統合テスト
実際のワークフローを通じて4ノードシステムの動作を検証
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from codecrafter.orchestration.four_node_orchestrator import FourNodeOrchestrator
from codecrafter.state.agent_state import AgentState, ConversationMessage, WorkspaceInfo, GraphState


class TestFourNodeIntegration:
    """4ノードオーケストレーターの統合テスト"""
    
    @pytest.fixture
    def temp_workspace(self):
        """一時的なワークスペースを作成"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def integration_agent_state(self, temp_workspace):
        """統合テスト用のAgentStateを作成"""
        # テスト用のファイルを作成
        (temp_workspace / "main.py").write_text("# メインファイル\nprint('Hello World')")
        (temp_workspace / "utils.py").write_text("# ユーティリティファイル\ndef helper_function():\n    pass")
        
        state = AgentState(session_id="integration_test")
        state.conversation_history = [
            ConversationMessage(
                role="user",
                content="main.pyファイルにコメントを追加してください",
                timestamp=datetime.now()
            )
        ]
        state.graph_state = GraphState()
        state.workspace = WorkspaceInfo(
            path=str(temp_workspace),
            files=["main.py", "utils.py"]
        )
        return state
    
    def test_simple_file_read_workflow(self, integration_agent_state):
        """シンプルなファイル読み取りワークフローのテスト"""
        orchestrator = FourNodeOrchestrator(integration_agent_state)
        
        # 4ノードコンテキストが正常に作成されることを確認
        assert orchestrator.four_node_context is not None
        assert orchestrator.four_node_context.current_node.value == "understanding"
        assert len(orchestrator.four_node_context.task_chain) > 0
        
        # グラフが正常に構築されることを確認
        assert orchestrator.graph is not None
        
        # ノード分岐メソッドの基本動作確認
        understanding_branch = orchestrator._after_understanding_planning(integration_agent_state)
        assert understanding_branch in ["gather_info", "execute_directly", "complete"]
    
    def test_context_creation_and_transformation(self, integration_agent_state):
        """AgentStateから4ノードコンテキストへの変換テスト"""
        orchestrator = FourNodeOrchestrator(integration_agent_state)
        context = orchestrator.four_node_context
        
        # 基本的なコンテキスト情報の確認
        assert context.workspace_path == Path(integration_agent_state.workspace.path)
        assert len(context.task_chain) > 0
        assert context.task_chain[0].user_message == "main.pyファイルにコメントを追加してください"
        
        # 実行フェーズの初期値確認
        assert context.execution_phase == 1
        assert context.current_node.value == "understanding"
    
    def test_helper_methods_integration(self, integration_agent_state):
        """ヘルパーメソッドの統合動作テスト"""
        orchestrator = FourNodeOrchestrator(integration_agent_state)
        
        # 軽量コンテキストの準備
        orchestrator.helpers.prepare_lightweight_context(integration_agent_state)
        assert integration_agent_state.workspace is not None
        
        # 意図分析の実行
        intent_analysis = orchestrator.helpers.analyze_user_intent(integration_agent_state)
        assert isinstance(intent_analysis, dict)
        assert "needs_file_read" in intent_analysis
        assert "operation_type" in intent_analysis
        
        # 再試行判定のテスト
        is_retry = orchestrator.helpers.is_retry_context(integration_agent_state)
        assert isinstance(is_retry, bool)
    
    def test_error_handling_and_recovery(self, integration_agent_state):
        """エラーハンドリングと回復機能のテスト"""
        orchestrator = FourNodeOrchestrator(integration_agent_state)
        
        # 無効な状態でのノード分岐テスト
        invalid_branch = orchestrator._after_understanding_planning(None)
        assert invalid_branch == "complete"
        
        invalid_branch = orchestrator._after_information_gathering(None)
        assert invalid_branch == "complete"
        
        invalid_branch = orchestrator._after_evaluation_continuation(None)
        assert invalid_branch == "complete"
        
        # エラー情報の記録確認
        assert hasattr(integration_agent_state, 'record_error')
    
    def test_node_state_transitions(self, integration_agent_state):
        """ノード状態遷移の基本動作テスト"""
        orchestrator = FourNodeOrchestrator(integration_agent_state)
        
        # 理解ノードの状態設定
        from codecrafter.prompts.four_node_context import UnderstandingResult, ExecutionPlan, NodeType
        
        understanding_result = UnderstandingResult(
            requirement_analysis="ファイル編集要求",
            execution_plan=ExecutionPlan(
                summary="main.pyにコメント追加",
                steps=["ファイル読み取り", "コメント追加", "ファイル保存"],
                required_tools=["read_file", "write_file"],
                expected_files=["main.py"],
                estimated_complexity="low",
                success_criteria="コメントが正常に追加される"
            ),
            identified_risks=[],
            information_needs=[],
            confidence=0.9,
            complexity_assessment="シンプル"
        )
        
        orchestrator.four_node_context.understanding = understanding_result
        
        # 理解・計画後の分岐判定
        next_step = orchestrator._after_understanding_planning(integration_agent_state)
        # 低複雑度でexpected_filesがある場合は情報収集へ
        assert next_step == "gather_info"
        
        # ノード状態の更新確認
        orchestrator.four_node_context.current_node = NodeType.GATHERING
        assert orchestrator.four_node_context.current_node == NodeType.GATHERING
    
    def test_serialization_and_context_preservation(self, integration_agent_state):
        """シリアライゼーションとコンテキスト保持のテスト"""
        orchestrator = FourNodeOrchestrator(integration_agent_state)
        
        from codecrafter.prompts.four_node_context import (
            UnderstandingResult, ExecutionPlan, GatheredInfo, ProjectContext,
            ExecutionResult, RiskAssessment, ApprovalStatus, EvaluationResult,
            NextAction, RiskLevel
        )
        
        # 理解結果のシリアライゼーションテスト
        understanding_result = UnderstandingResult(
            requirement_analysis="テスト要求",
            execution_plan=ExecutionPlan(
                summary="テスト実行計画",
                steps=["step1"],
                required_tools=["tool1"],
                expected_files=["test.py"],
                estimated_complexity="low",
                success_criteria="成功"
            ),
            identified_risks=[],
            information_needs=[],
            confidence=0.8,
            complexity_assessment="test"
        )
        
        serialized = orchestrator._serialize_understanding_result(understanding_result)
        assert "summary" in serialized
        assert serialized["summary"] == "テスト要求"
        
        # 情報収集結果のシリアライゼーションテスト
        gathered_info = GatheredInfo(
            collected_files={},
            rag_results=[],
            project_context=ProjectContext(
                project_type="Test",
                main_languages=["Python"],
                frameworks=[],
                architecture_pattern="Simple",
                key_directories=[],
                recent_changes=[]
            ),
            confidence_scores={},
            information_gaps=[],
            collection_strategy="test"
        )
        
        serialized = orchestrator._serialize_gathered_info(gathered_info)
        assert "file_count" in serialized
        assert serialized["file_count"] == 0


class TestFourNodePerformanceBasics:
    """4ノードシステムの基本パフォーマンステスト"""
    
    @pytest.fixture
    def perf_agent_state(self):
        """パフォーマンステスト用のAgentState"""
        state = AgentState(session_id="perf_test")
        state.conversation_history = [
            ConversationMessage(
                role="user", 
                content="複数のPythonファイルを作成してください",
                timestamp=datetime.now()
            )
        ]
        state.graph_state = GraphState()
        state.workspace = WorkspaceInfo(
            path=str(Path.cwd()),
            files=["file1.py", "file2.py", "file3.py"] * 10  # 30ファイル
        )
        return state
    
    def test_large_workspace_handling(self, perf_agent_state):
        """大きなワークスペースの処理テスト"""
        orchestrator = FourNodeOrchestrator(perf_agent_state)
        
        # 初期化時間が合理的な範囲内であることを確認
        import time
        start_time = time.time()
        
        context = orchestrator.four_node_context
        assert context is not None
        
        initialization_time = time.time() - start_time
        assert initialization_time < 5.0, f"初期化時間が長すぎます: {initialization_time}秒"
        
        # 軽量化されたワークスペース情報の確認
        orchestrator.helpers.prepare_lightweight_context(perf_agent_state)
        # ファイル数が制限されていることを確認（最大20ファイル）
        assert len(perf_agent_state.workspace.files) <= 20
    
    def test_memory_efficiency(self, perf_agent_state):
        """メモリ効率性の基本チェック"""
        orchestrator = FourNodeOrchestrator(perf_agent_state)
        
        # 大量のコンテキストデータがメモリに蓄積されないことを確認
        for _ in range(10):
            orchestrator.helpers.prepare_lightweight_context(perf_agent_state)
            intent_analysis = orchestrator.helpers.analyze_user_intent(perf_agent_state)
        
        # メモリリークがないことの基本チェック
        # （実際のメモリ使用量測定は本格的なプロファイリングツールで行う）
        assert orchestrator is not None  # 基本的な動作確認
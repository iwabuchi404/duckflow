"""
FourNodeOrchestrator のテスト
"""

import pytest
from datetime import datetime
from pathlib import Path
from codecrafter.orchestration.four_node_orchestrator import FourNodeOrchestrator
from codecrafter.state.agent_state import AgentState, ConversationMessage, GraphState, WorkspaceInfo


class TestFourNodeOrchestrator:
    """FourNodeOrchestrator の基本テスト"""
    
    @pytest.fixture
    def sample_agent_state(self):
        """サンプルのAgentStateを作成"""
        state = AgentState(session_id="test_session")
        state.conversation_history = [
            ConversationMessage(
                role="user",
                content="test.pyファイルを作成してください",
                timestamp=datetime.now()
            )
        ]
        state.graph_state = GraphState()
        state.workspace = WorkspaceInfo(
            path=str(Path.cwd()),
            files=["test.py", "main.py"]
        )
        return state
    
    @pytest.fixture
    def four_node_orchestrator(self, sample_agent_state):
        """FourNodeOrchestratorを作成"""
        return FourNodeOrchestrator(sample_agent_state)
    
    def test_orchestrator_initialization(self, four_node_orchestrator):
        """オーケストレーターの初期化テスト"""
        orchestrator = four_node_orchestrator
        
        assert orchestrator is not None
        assert orchestrator.state is not None
        assert orchestrator.routing_engine is not None
        assert orchestrator.prompt_compiler is not None
        assert orchestrator.helpers is not None
        assert orchestrator.four_node_context is not None
        assert orchestrator.graph is not None
    
    def test_four_node_context_creation(self, four_node_orchestrator):
        """4ノードコンテキストの作成テスト"""
        context = four_node_orchestrator.four_node_context
        
        assert context is not None
        assert context.current_node.value == "understanding"
        assert context.execution_phase == 1
        assert context.workspace_path is not None
        assert len(context.task_chain) > 0
        assert context.task_chain[0].user_message == "test.pyファイルを作成してください"
    
    def test_graph_structure(self, four_node_orchestrator):
        """グラフ構造のテスト"""
        graph = four_node_orchestrator.graph
        
        # グラフが正常にコンパイルされていることを確認
        assert graph is not None
        
        # ノード名が正しく設定されていることを確認（LangGraphの内部構造にアクセス）
        # 注意: これはLangGraphの実装詳細に依存するため、将来変更される可能性あり
        if hasattr(graph, 'nodes'):
            expected_nodes = {"理解・計画", "情報収集", "安全実行", "評価・継続"}
            assert expected_nodes.issubset(set(graph.nodes.keys()))
    
    def test_conditional_edges_after_understanding_planning(self, four_node_orchestrator):
        """理解・計画後の条件分岐テスト"""
        orchestrator = four_node_orchestrator
        
        # 理解結果を設定
        from codecrafter.prompts.four_node_context import UnderstandingResult, ExecutionPlan
        understanding_result = UnderstandingResult(
            requirement_analysis="ファイル作成要求",
            execution_plan=ExecutionPlan(
                summary="test.pyファイルを作成",
                steps=["ファイル作成"],
                required_tools=["write_file"],
                expected_files=["test.py"],
                estimated_complexity="low",
                success_criteria="ファイルが正常に作成される"
            ),
            identified_risks=[],
            information_needs=[],
            confidence=0.9,
            complexity_assessment="シンプル"
        )
        orchestrator.four_node_context.understanding = understanding_result
        
        # 分岐判定をテスト
        result = orchestrator._after_understanding_planning(orchestrator.state)
        
        # 情報収集が必要ないシンプルなケースでは直接実行
        assert result in ["gather_info", "execute_directly"]
    
    def test_conditional_edges_after_information_gathering(self, four_node_orchestrator):
        """情報収集後の条件分岐テスト"""
        orchestrator = four_node_orchestrator
        
        # 収集情報を設定
        from codecrafter.prompts.four_node_context import GatheredInfo, ProjectContext
        gathered_info = GatheredInfo(
            collected_files={},
            rag_results=[],
            project_context=ProjectContext(
                project_type="Python",
                main_languages=["Python"],
                frameworks=[],
                architecture_pattern="Simple",
                key_directories=[],
                recent_changes=[]
            ),
            confidence_scores={},
            information_gaps=[],
            collection_strategy="minimal"
        )
        orchestrator.four_node_context.gathered_info = gathered_info
        
        # 分岐判定をテスト
        result = orchestrator._after_information_gathering(orchestrator.state)
        
        # 通常は実行に進む
        assert result == "execute"
    
    def test_conditional_edges_after_evaluation_continuation(self, four_node_orchestrator):
        """評価・継続後の条件分岐テスト"""
        orchestrator = four_node_orchestrator
        
        # 評価結果を設定
        from codecrafter.prompts.four_node_context import EvaluationResult, NextAction
        evaluation_result = EvaluationResult(
            success_status=True,
            completion_percentage=1.0,
            next_action=NextAction.COMPLETE,
            quality_assessment="良好",
            user_satisfaction_prediction=0.9
        )
        orchestrator.four_node_context.evaluation = evaluation_result
        
        # 分岐判定をテスト
        result = orchestrator._after_evaluation_continuation(orchestrator.state)
        
        # 完了ケースでは終了
        assert result == "complete"
    
    def test_serialization_methods(self, four_node_orchestrator):
        """シリアライゼーションメソッドのテスト"""
        orchestrator = four_node_orchestrator
        
        from codecrafter.prompts.four_node_context import (
            UnderstandingResult, ExecutionPlan, GatheredInfo, ExecutionResult, 
            EvaluationResult, NextAction, RiskAssessment, ApprovalStatus, RiskLevel,
            ProjectContext
        )
        
        # UnderstandingResult のシリアライゼーション
        understanding_result = UnderstandingResult(
            requirement_analysis="テスト要求",
            execution_plan=ExecutionPlan(
                summary="テスト計画",
                steps=["ステップ1"],
                required_tools=["tool1"],
                expected_files=["test.py"],
                estimated_complexity="low",
                success_criteria="成功"
            ),
            identified_risks=[],
            information_needs=[],
            confidence=0.8,
            complexity_assessment="シンプル"
        )
        
        serialized = orchestrator._serialize_understanding_result(understanding_result)
        assert "summary" in serialized
        assert serialized["summary"] == "テスト要求"
        
        # GatheredInfo のシリアライゼーション
        gathered_info = GatheredInfo(
            collected_files={"test.py": None, "main.py": None},
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
        assert serialized["file_count"] == 2
    
    def test_error_handling(self, four_node_orchestrator):
        """エラーハンドリングのテスト"""
        orchestrator = four_node_orchestrator
        
        # 無効な状態でのメソッド呼び出しをテスト
        result = orchestrator._after_understanding_planning(None)
        assert result == "complete"  # エラー時はcompleteで終了
        
        result = orchestrator._after_information_gathering(None)
        assert result == "complete"
        
        result = orchestrator._after_evaluation_continuation(None)
        assert result == "complete"


class TestFourNodeOrchestratorHelpers:
    """FourNodeOrchestrator のヘルパーメソッドテスト"""
    
    @pytest.fixture
    def sample_agent_state(self):
        """サンプルのAgentStateを作成"""
        state = AgentState(session_id="test_session_helpers")
        state.conversation_history = [
            ConversationMessage(
                role="user",
                content="プロジェクトの概要を教えてください",
                timestamp=datetime.now()
            )
        ]
        return state
    
    @pytest.fixture
    def four_node_orchestrator(self, sample_agent_state):
        """FourNodeOrchestratorを作成"""
        return FourNodeOrchestrator(sample_agent_state)
    
    def test_evaluate_information_quality(self, four_node_orchestrator):
        """情報品質評価のテスト"""
        from codecrafter.prompts.four_node_context import FileContent
        
        collected_files = {
            "test1.py": FileContent(
                path="test1.py", 
                content="test", 
                encoding="utf-8", 
                size=4,
                last_modified=datetime.now()
            ),
            "test2.py": FileContent(
                path="test2.py", 
                content="test", 
                encoding="utf-8", 
                size=4,
                last_modified=datetime.now()
            )
        }
        rag_results = [{"query": "test", "results": []}]
        
        quality = four_node_orchestrator._evaluate_information_quality(collected_files, rag_results)
        
        assert "file_coverage" in quality
        assert "rag_relevance" in quality
        assert quality["file_coverage"] == 1.0  # 2/2 = 1.0
        assert quality["rag_relevance"] == 1/3  # 1/3
    
    def test_identify_information_gaps(self, four_node_orchestrator):
        """情報ギャップ特定のテスト"""
        from codecrafter.prompts.four_node_context import UnderstandingResult, ExecutionPlan, FileContent
        
        understanding_result = UnderstandingResult(
            requirement_analysis="テスト",
            execution_plan=ExecutionPlan(
                summary="テスト",
                steps=["ステップ1"],
                required_tools=["tool1"],
                expected_files=["missing.py", "exists.py"],
                estimated_complexity="low",
                success_criteria="成功"
            ),
            identified_risks=[],
            information_needs=[],
            confidence=0.8,
            complexity_assessment="シンプル"
        )
        
        collected_files = {
            "exists.py": FileContent(
                path="exists.py", 
                content="test", 
                encoding="utf-8", 
                size=4,
                last_modified=datetime.now()
            )
        }
        
        gaps = four_node_orchestrator._identify_information_gaps(understanding_result, collected_files)
        
        assert len(gaps) == 1
        assert "missing.py" in gaps[0]
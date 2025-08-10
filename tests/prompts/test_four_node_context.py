"""
FourNodePromptContext とデータクラスのユニットテスト
"""

import pytest
from datetime import datetime
from pathlib import Path
from codecrafter.prompts.four_node_context import (
    FourNodePromptContext, NodeType, NextAction, RiskLevel,
    ExecutionPlan, UnderstandingResult, GatheredInfo, ExecutionResult, EvaluationResult,
    FileContent, ProjectContext, RiskAssessment, ApprovalStatus, ToolResult,
    ExecutionError, ErrorAnalysis, TaskStep, RetryContext
)
from codecrafter.state.agent_state import ConversationMessage


class TestNodeType:
    """NodeType enumのテスト"""
    
    def test_node_type_values(self):
        """NodeTypeの値が正しいことを確認"""
        assert NodeType.UNDERSTANDING.value == "understanding"
        assert NodeType.GATHERING.value == "gathering"
        assert NodeType.EXECUTION.value == "execution"
        assert NodeType.EVALUATION.value == "evaluation"
    
    def test_node_type_count(self):
        """NodeTypeが4つの値を持つことを確認"""
        assert len(list(NodeType)) == 4


class TestExecutionPlan:
    """ExecutionPlan データクラスのテスト"""
    
    def test_basic_creation(self):
        """基本的な作成テスト"""
        plan = ExecutionPlan(
            summary="テスト計画",
            steps=["ステップ1", "ステップ2"],
            required_tools=["read_file", "write_file"],
            expected_files=["test.py"],
            estimated_complexity="medium",
            success_criteria="ファイルが正しく作成される"
        )
        
        assert plan.summary == "テスト計画"
        assert len(plan.steps) == 2
        assert "read_file" in plan.required_tools
        assert plan.estimated_complexity == "medium"


class TestFourNodePromptContext:
    """FourNodePromptContext のテスト"""
    
    @pytest.fixture
    def sample_context(self):
        """サンプルのPromptContextを作成"""
        return FourNodePromptContext(
            current_node=NodeType.UNDERSTANDING,
            execution_phase=1,
            workspace_path=Path("/test/workspace")
        )
    
    def test_basic_creation(self, sample_context):
        """基本的な作成テスト"""
        assert sample_context.current_node == NodeType.UNDERSTANDING
        assert sample_context.execution_phase == 1
        assert sample_context.workspace_path == Path("/test/workspace")
        assert sample_context.token_budget == 6000
    
    def test_get_current_phase_info(self, sample_context):
        """現在のフェーズ情報取得テスト"""
        phase_info = sample_context.get_current_phase_info()
        assert "要求理解・計画立案" in phase_info
        assert "Phase 1" in phase_info
        
        # 他のノードタイプもテスト
        sample_context.current_node = NodeType.GATHERING
        phase_info = sample_context.get_current_phase_info()
        assert "情報収集・文脈構築" in phase_info
    
    def test_has_previous_results(self, sample_context):
        """前段階結果の存在確認テスト"""
        # 初期状態では何も結果がない
        assert not sample_context.has_previous_results(NodeType.UNDERSTANDING)
        assert not sample_context.has_previous_results(NodeType.GATHERING)
        
        # UnderstandingResultを追加
        sample_context.understanding = UnderstandingResult(
            requirement_analysis="テスト分析",
            execution_plan=ExecutionPlan(
                summary="テスト",
                steps=["step1"],
                required_tools=["tool1"],
                expected_files=["file1"],
                estimated_complexity="low",
                success_criteria="成功"
            ),
            identified_risks=["risk1"],
            information_needs=["info1"],
            confidence=0.9,
            complexity_assessment="低"
        )
        
        assert sample_context.has_previous_results(NodeType.UNDERSTANDING)
        assert not sample_context.has_previous_results(NodeType.GATHERING)
    
    def test_get_token_allocation(self, sample_context):
        """トークン配分計算テスト"""
        allocation = sample_context.get_token_allocation()
        
        # 基本配分の確認
        assert allocation["understanding"] == 6000 // 4  # 1500
        assert allocation["gathering"] == 6000 // 2     # 3000
        assert allocation["execution"] == 6000 // 6     # 1000
        assert allocation["evaluation"] == 6000 // 12   # 500
        
        # 合計がtoken_budget以下であることを確認
        total_allocated = sum(allocation.values())
        assert total_allocated <= sample_context.token_budget
    
    def test_get_token_allocation_with_priorities(self, sample_context):
        """優先度付きトークン配分テスト"""
        sample_context.node_priorities = {
            "understanding": 1.5,  # 150%
            "gathering": 0.8       # 80%
        }
        
        allocation = sample_context.get_token_allocation()
        
        # 優先度が反映されることを確認
        base_understanding = 6000 // 4
        base_gathering = 6000 // 2
        
        assert allocation["understanding"] == int(base_understanding * 1.5)
        assert allocation["gathering"] == int(base_gathering * 0.8)
    
    def test_should_request_approval(self, sample_context):
        """承認必要性判定テスト"""
        # 初期状態では承認不要
        assert not sample_context.should_request_approval()
        
        # 低リスクの場合は承認不要
        sample_context.execution_result = ExecutionResult(
            risk_assessment=RiskAssessment(
                overall_risk=RiskLevel.LOW,
                risk_factors=[],
                mitigation_measures=[],
                approval_required=False,
                reasoning="低リスク"
            ),
            approval_status=ApprovalStatus(
                requested=False,
                granted=False,
                timestamp=datetime.now(),
                approval_message=""
            ),
            tool_results=[],
            execution_errors=[],
            partial_success=False
        )
        
        assert not sample_context.should_request_approval()
        
        # 高リスクの場合は承認必要
        sample_context.execution_result.risk_assessment.overall_risk = RiskLevel.HIGH
        assert sample_context.should_request_approval()
        
        # 中リスクの場合も承認必要
        sample_context.execution_result.risk_assessment.overall_risk = RiskLevel.MEDIUM
        assert sample_context.should_request_approval()
    
    def test_get_execution_summary(self, sample_context):
        """実行サマリー取得テスト"""
        summary = sample_context.get_execution_summary()
        
        # 基本情報の確認
        assert "phase" in summary
        assert "completed_nodes" in summary
        assert "retry_count" in summary
        assert "total_executions" in summary
        assert "token_usage" in summary
        assert "safety_status" in summary
        
        # 初期状態の値確認
        assert summary["retry_count"] == 0
        assert summary["total_executions"] == 0
        assert len(summary["completed_nodes"]) == 0
        
        # UnderstandingResultを追加して再確認
        sample_context.understanding = UnderstandingResult(
            requirement_analysis="テスト",
            execution_plan=ExecutionPlan(
                summary="テスト",
                steps=["step1"],
                required_tools=["tool1"],
                expected_files=["file1"],
                estimated_complexity="low",
                success_criteria="成功"
            ),
            identified_risks=[],
            information_needs=[],
            confidence=0.9,
            complexity_assessment="低"
        )
        
        summary = sample_context.get_execution_summary()
        assert "understanding" in summary["completed_nodes"]


class TestDataClassesIntegration:
    """データクラス間の統合テスト"""
    
    def test_full_workflow_context(self):
        """完全なワークフロー文脈のテスト"""
        # 初期コンテキスト作成
        context = FourNodePromptContext(
            current_node=NodeType.UNDERSTANDING,
            execution_phase=1,
            workspace_path=Path("/test/project")
        )
        
        # タスクチェーンを追加
        task = TaskStep(
            step_id="task_1",
            user_message="ファイルを作成してください",
            timestamp=datetime.now()
        )
        context.task_chain.append(task)
        
        # 理解結果を追加
        context.understanding = UnderstandingResult(
            requirement_analysis="ユーザーはファイル作成を要求している",
            execution_plan=ExecutionPlan(
                summary="新しいファイルを作成する",
                steps=["ファイル内容を決定", "ファイルを作成"],
                required_tools=["write_file"],
                expected_files=["new_file.py"],
                estimated_complexity="low",
                success_criteria="ファイルが正しく作成される"
            ),
            identified_risks=["ファイル上書きのリスク"],
            information_needs=["ファイル内容の詳細"],
            confidence=0.85,
            complexity_assessment="シンプルなファイル作成タスク"
        )
        
        # 情報収集結果を追加
        context.gathered_info = GatheredInfo(
            collected_files={
                "example.py": FileContent(
                    path="example.py",
                    content="# サンプルファイル",
                    encoding="utf-8",
                    size=100,
                    last_modified=datetime.now()
                )
            },
            rag_results=[],
            project_context=ProjectContext(
                project_type="Python",
                main_languages=["Python"],
                frameworks=["pytest"],
                architecture_pattern="MVC",
                key_directories=["src", "tests"],
                recent_changes=[]
            ),
            confidence_scores={"file_analysis": 0.9},
            information_gaps=[],
            collection_strategy="focused"
        )
        
        # 実行結果を追加
        context.execution_result = ExecutionResult(
            risk_assessment=RiskAssessment(
                overall_risk=RiskLevel.LOW,
                risk_factors=[],
                mitigation_measures=[],
                approval_required=False,
                reasoning="シンプルなファイル作成"
            ),
            approval_status=ApprovalStatus(
                requested=False,
                granted=True,
                timestamp=datetime.now(),
                approval_message="自動承認"
            ),
            tool_results=[
                ToolResult(
                    tool_name="write_file",
                    success=True,
                    output="ファイルが正常に作成されました"
                )
            ],
            execution_errors=[],
            partial_success=False
        )
        
        # 評価結果を追加
        context.evaluation = EvaluationResult(
            success_status=True,
            completion_percentage=1.0,
            next_action=NextAction.COMPLETE,
            quality_assessment="高品質",
            user_satisfaction_prediction=0.95
        )
        
        # 統合テスト
        assert context.has_previous_results(NodeType.UNDERSTANDING)
        assert context.has_previous_results(NodeType.GATHERING)
        assert context.has_previous_results(NodeType.EXECUTION)
        assert context.has_previous_results(NodeType.EVALUATION)
        
        summary = context.get_execution_summary()
        assert len(summary["completed_nodes"]) == 4
        assert not context.should_request_approval()  # 低リスク
    
    def test_retry_context_workflow(self):
        """再試行コンテキストのワークフローテスト"""
        # 再試行コンテキストを持つPromptContextを作成
        error = ExecutionError(
            error_type="FileNotFoundError",
            message="ファイルが見つかりません",
            file_path="missing_file.py"
        )
        
        error_analysis = ErrorAnalysis(
            root_cause="指定されたファイルが存在しない",
            suggested_fixes=["ファイルパスを確認", "ファイルを作成"],
            confidence=0.9,
            similar_patterns=["典型的なファイル不存在エラー"],
            prevention_measures=["事前のファイル存在確認"]
        )
        
        retry_context = RetryContext(
            retry_count=1,
            previous_errors=[error],
            failure_analysis=error_analysis
        )
        
        context = FourNodePromptContext(
            current_node=NodeType.UNDERSTANDING,
            execution_phase=2,  # 再試行なので2回目
            workspace_path=Path("/test/project"),
            retry_context=retry_context
        )
        
        # 再試行の場合の動作を確認
        phase_info = context.get_current_phase_info()
        assert "Phase 2" in phase_info
        
        summary = context.get_execution_summary()
        assert summary["retry_count"] == 1
        assert summary["phase"] == phase_info
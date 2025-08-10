"""
FourNodePromptCompiler のユニットテスト
"""

import pytest
from pathlib import Path
from datetime import datetime
from codecrafter.prompts.four_node_compiler import FourNodePromptCompiler
from codecrafter.prompts.four_node_context import (
    FourNodePromptContext, NodeType, NextAction, RiskLevel,
    ExecutionPlan, UnderstandingResult, GatheredInfo, ExecutionResult, EvaluationResult,
    FileContent, ProjectContext, RiskAssessment, ApprovalStatus, ToolResult,
    ExecutionError, ErrorAnalysis, TaskStep, RetryContext
)


class TestFourNodePromptCompiler:
    """FourNodePromptCompiler のテスト"""
    
    @pytest.fixture
    def compiler(self):
        """テスト用のコンパイラを作成"""
        # テンプレートファイルのパスを設定（実際のファイルが存在する場合）
        templates_path = Path(__file__).parent.parent.parent / "codecrafter" / "prompts" / "system_prompts" / "four_node_templates.yaml"
        
        # テンプレートファイルが存在しない場合はモックテンプレートを作成
        if not templates_path.exists():
            compiler = FourNodePromptCompiler.__new__(FourNodePromptCompiler)
            compiler.templates_path = templates_path
            compiler.templates = {
                "understanding_fresh": "Role: {user_message} Workspace: {workspace_path}",
                "understanding_retry": "Retry: {user_message} Failure: {previous_failure}",
                "gathering_focused": "Gather: {execution_plan} Info: {information_needs}",
                "gathering_retry": "ReGather: {previous_collected_files}",
                "execution_safe": "Execute: {execution_plan} Context: {collected_context_summary}",
                "execution_rollback": "Rollback: {error_type} {error_message}",
                "evaluation_comprehensive": "Evaluate: {original_plan} Results: {execution_results_summary}",
                "evaluation_error_analysis": "Error Analysis: {error_type} {error_message}"
            }
            return compiler
        else:
            return FourNodePromptCompiler(templates_path)
    
    @pytest.fixture
    def sample_understanding_context(self):
        """理解ノード用のサンプルコンテキスト"""
        context = FourNodePromptContext(
            current_node=NodeType.UNDERSTANDING,
            execution_phase=1,
            workspace_path=Path("/test/workspace")
        )
        
        # タスクチェーンを追加
        task = TaskStep(
            step_id="task_1",
            user_message="Pythonファイルを作成してください",
            timestamp=datetime.now()
        )
        context.task_chain.append(task)
        
        return context
    
    @pytest.fixture
    def sample_gathering_context(self, sample_understanding_context):
        """情報収集ノード用のサンプルコンテキスト"""
        context = sample_understanding_context
        context.current_node = NodeType.GATHERING
        
        # 理解結果を追加
        context.understanding = UnderstandingResult(
            requirement_analysis="ユーザーはPythonファイルの作成を要求",
            execution_plan=ExecutionPlan(
                summary="新しいPythonファイルを作成",
                steps=["ファイル内容を決定", "ファイルを作成"],
                required_tools=["write_file"],
                expected_files=["new_file.py"],
                estimated_complexity="low",
                success_criteria="ファイルが正しく作成される"
            ),
            identified_risks=["ファイル上書きリスク"],
            information_needs=["ファイル内容仕様", "プロジェクト構造"],
            confidence=0.85,
            complexity_assessment="シンプル"
        )
        
        return context
    
    def test_compiler_initialization(self, compiler):
        """コンパイラの初期化テスト"""
        assert isinstance(compiler, FourNodePromptCompiler)
        assert hasattr(compiler, 'templates')
        assert isinstance(compiler.templates, dict)
    
    def test_compile_understanding_fresh_prompt(self, compiler, sample_understanding_context):
        """理解ノード（新規）のプロンプト生成テスト"""
        prompt = compiler.compile_node_prompt(sample_understanding_context)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        
        # 基本的な内容が含まれていることを確認
        assert "Pythonファイルを作成してください" in prompt or "user_message" in prompt
        assert "/test/workspace" in prompt or "workspace_path" in prompt
    
    def test_compile_understanding_retry_prompt(self, compiler):
        """理解ノード（再試行）のプロンプト生成テスト"""
        # 再試行コンテキストを持つPromptContextを作成
        error = ExecutionError(
            error_type="FileNotFoundError",
            message="ファイルが見つかりません"
        )
        
        error_analysis = ErrorAnalysis(
            root_cause="指定パスが不正",
            suggested_fixes=["パスを修正"],
            confidence=0.9,
            similar_patterns=[],
            prevention_measures=[]
        )
        
        retry_context = RetryContext(
            retry_count=1,
            previous_errors=[error],
            failure_analysis=error_analysis
        )
        
        context = FourNodePromptContext(
            current_node=NodeType.UNDERSTANDING,
            execution_phase=2,
            workspace_path=Path("/test/workspace"),
            retry_context=retry_context
        )
        
        task = TaskStep(
            step_id="retry_task",
            user_message="再度ファイルを作成してください",
            timestamp=datetime.now()
        )
        context.task_chain.append(task)
        
        prompt = compiler.compile_node_prompt(context)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # 再試行関連の内容が含まれていることを確認（モックの場合）
        if "Retry:" in compiler.templates.get("understanding_retry", ""):
            assert "再度ファイルを作成してください" in prompt
    
    def test_compile_gathering_prompt(self, compiler, sample_gathering_context):
        """情報収集ノードのプロンプト生成テスト"""
        prompt = compiler.compile_node_prompt(sample_gathering_context)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        
        # 実行計画関連の情報が含まれていることを確認
        if "execution_plan" in prompt.lower():
            assert "新しいPythonファイルを作成" in prompt or "execution_plan" in prompt
    
    def test_compile_execution_prompt(self, compiler, sample_gathering_context):
        """実行ノードのプロンプト生成テスト"""
        context = sample_gathering_context
        context.current_node = NodeType.EXECUTION
        
        # 情報収集結果を追加
        context.gathered_info = GatheredInfo(
            collected_files={
                "example.py": FileContent(
                    path="example.py",
                    content="# Example",
                    encoding="utf-8",
                    size=10,
                    last_modified=datetime.now()
                )
            },
            rag_results=[],
            project_context=ProjectContext(
                project_type="Python",
                main_languages=["Python"],
                frameworks=[],
                architecture_pattern="Simple",
                key_directories=["src"],
                recent_changes=[]
            ),
            confidence_scores={},
            information_gaps=[],
            collection_strategy="focused"
        )
        
        prompt = compiler.compile_node_prompt(context)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
    
    def test_compile_evaluation_prompt(self, compiler, sample_gathering_context):
        """評価ノードのプロンプト生成テスト"""
        context = sample_gathering_context
        context.current_node = NodeType.EVALUATION
        
        # 実行結果を追加
        context.execution_result = ExecutionResult(
            risk_assessment=RiskAssessment(
                overall_risk=RiskLevel.LOW,
                risk_factors=[],
                mitigation_measures=[],
                approval_required=False,
                reasoning="低リスク"
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
                    output="ファイル作成完了"
                )
            ],
            execution_errors=[],
            partial_success=False
        )
        
        prompt = compiler.compile_node_prompt(context)
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
    
    def test_invalid_node_type(self, compiler):
        """無効なノードタイプのテスト"""
        context = FourNodePromptContext(
            current_node=None,  # 無効なノード
            execution_phase=1,
            workspace_path=Path("/test")
        )
        
        with pytest.raises((ValueError, AttributeError)):
            compiler.compile_node_prompt(context)
    
    def test_missing_prerequisites_gathering(self, compiler):
        """前提条件不足時のエラーテスト（情報収集ノード）"""
        context = FourNodePromptContext(
            current_node=NodeType.GATHERING,
            execution_phase=1,
            workspace_path=Path("/test")
        )
        # understanding結果がない状態
        
        with pytest.raises(ValueError, match="理解ノードの結果が必要"):
            compiler.compile_node_prompt(context)
    
    def test_missing_prerequisites_execution(self, compiler):
        """前提条件不足時のエラーテスト（実行ノード）"""
        context = FourNodePromptContext(
            current_node=NodeType.EXECUTION,
            execution_phase=1,
            workspace_path=Path("/test")
        )
        # understanding, gathered_info結果がない状態
        
        with pytest.raises(ValueError, match="理解・収集ノードの結果が必要"):
            compiler.compile_node_prompt(context)
    
    def test_missing_prerequisites_evaluation(self, compiler):
        """前提条件不足時のエラーテスト（評価ノード）"""
        context = FourNodePromptContext(
            current_node=NodeType.EVALUATION,
            execution_phase=1,
            workspace_path=Path("/test")
        )
        # understanding, execution_result結果がない状態
        
        with pytest.raises(ValueError, match="理解・実行ノードの結果が必要"):
            compiler.compile_node_prompt(context)


class TestTemplateHelperMethods:
    """テンプレートヘルパーメソッドのテスト"""
    
    @pytest.fixture
    def compiler(self):
        """テスト用のコンパイラを作成（モック）"""
        compiler = FourNodePromptCompiler.__new__(FourNodePromptCompiler)
        compiler.templates = {"test_template": "Test: {test_var}"}
        return compiler
    
    def test_format_template_variables_dict(self, compiler):
        """辞書形式変数のフォーマットテスト"""
        variables = {
            "test_dict": {"key1": "value1", "key2": ["item1", "item2"]},
            "test_list": ["item1", "item2", "item3"],
            "test_string": "simple_string"
        }
        
        formatted = compiler._format_template_variables(variables)
        
        assert isinstance(formatted, dict)
        assert "test_dict" in formatted
        assert "test_list" in formatted
        assert "test_string" in formatted
        
        # リストが改行区切りになることを確認
        assert "- item1" in formatted["test_list"]
        assert "- item2" in formatted["test_list"]
        
        # 文字列はそのまま
        assert formatted["test_string"] == "simple_string"
    
    def test_format_dict_for_template(self, compiler):
        """辞書のテンプレート用フォーマットテスト"""
        test_dict = {
            "summary": "テスト計画",
            "tools": ["tool1", "tool2"],
            "complexity": "medium"
        }
        
        result = compiler._format_dict_for_template(test_dict)
        
        assert isinstance(result, str)
        assert "- **summary**: テスト計画" in result
        assert "- **tools**: tool1, tool2" in result
        assert "- **complexity**: medium" in result
    
    def test_render_template_success(self, compiler):
        """テンプレートレンダリング成功テスト"""
        variables = {"test_var": "test_value"}
        result = compiler._render_template("test_template", variables)
        
        assert result == "Test: test_value"
    
    def test_render_template_missing_variable(self, compiler):
        """テンプレート変数不足時のエラーテスト"""
        variables = {}  # test_varが不足
        
        with pytest.raises(ValueError, match="テンプレート変数が不足"):
            compiler._render_template("test_template", variables)
    
    def test_render_template_missing_template(self, compiler):
        """存在しないテンプレートのエラーテスト"""
        variables = {"test_var": "value"}
        
        with pytest.raises(ValueError, match="テンプレートが見つかりません"):
            compiler._render_template("nonexistent_template", variables)


class TestWorkspaceHelperMethods:
    """ワークスペースヘルパーメソッドのテスト"""
    
    @pytest.fixture
    def compiler(self):
        """テスト用のコンパイラを作成"""
        compiler = FourNodePromptCompiler.__new__(FourNodePromptCompiler)
        return compiler
    
    def test_get_workspace_summary_with_project_context(self, compiler):
        """プロジェクト文脈ありでのワークスペース要約テスト"""
        context = FourNodePromptContext(
            current_node=NodeType.UNDERSTANDING,
            execution_phase=1,
            workspace_path=Path("/test/my_project")
        )
        
        # プロジェクト文脈を追加
        context.gathered_info = GatheredInfo(
            collected_files={},
            rag_results=[],
            project_context=ProjectContext(
                project_type="Web Application",
                main_languages=["Python", "JavaScript"],
                frameworks=["Django", "React"],
                architecture_pattern="MVC",
                key_directories=["backend", "frontend"],
                recent_changes=[]
            ),
            confidence_scores={},
            information_gaps=[],
            collection_strategy="comprehensive"
        )
        
        summary = compiler._get_workspace_summary(context)
        
        assert "Web Application" in summary
        assert "Python" in summary and "JavaScript" in summary
    
    def test_get_workspace_summary_without_project_context(self, compiler):
        """プロジェクト文脈なしでのワークスペース要約テスト"""
        context = FourNodePromptContext(
            current_node=NodeType.UNDERSTANDING,
            execution_phase=1,
            workspace_path=Path("/test/my_project")
        )
        
        summary = compiler._get_workspace_summary(context)
        
        assert "my_project" in summary
        assert "プロジェクト:" in summary
    
    def test_get_current_files(self, compiler):
        """現在のファイル状況取得テスト"""
        context = FourNodePromptContext(
            current_node=NodeType.GATHERING,
            execution_phase=1,
            workspace_path=Path("/test")
        )
        
        # ファイル情報がない場合
        files_info = compiler._get_current_files(context)
        assert "ファイル情報を収集中" in files_info
        
        # ファイル情報がある場合
        context.gathered_info = GatheredInfo(
            collected_files={
                "file1.py": FileContent(
                    path="file1.py",
                    content="",
                    encoding="utf-8",
                    size=0,
                    last_modified=datetime.now()
                ),
                "file2.py": FileContent(
                    path="file2.py", 
                    content="",
                    encoding="utf-8",
                    size=0,
                    last_modified=datetime.now()
                )
            },
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
            collection_strategy="focused"
        )
        
        files_info = compiler._get_current_files(context)
        assert "- file1.py" in files_info
        assert "- file2.py" in files_info
"""
4ノード統合アーキテクチャ専用のPromptCompiler

このモジュールは、各ノードの役割に特化したプロンプト生成を行います。
従来の静的なテンプレート選択から、動的で文脈継承対応のコンパイラに進化。
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from .four_node_context import (
    FourNodePromptContext, NodeType, ExecutionPlan, 
    UnderstandingResult, GatheredInfo, ExecutionResult, EvaluationResult
)


class FourNodePromptCompiler:
    """4ノード特化型プロンプトコンパイラ"""
    
    def __init__(self, templates_path: Optional[Path] = None):
        """
        初期化
        
        Args:
            templates_path: テンプレートファイルのパス（Noneの場合はデフォルト）
        """
        if templates_path is None:
            templates_path = Path(__file__).parent / "system_prompts" / "four_node_templates.yaml"
        
        self.templates_path = templates_path
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, str]:
        """テンプレートファイルを読み込み"""
        try:
            with open(self.templates_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"テンプレートファイルが見つかりません: {self.templates_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"テンプレートファイルの解析に失敗しました: {e}")
    
    def compile_node_prompt(self, context: FourNodePromptContext) -> str:
        """
        ノードごとの最適化プロンプトを生成
        
        Args:
            context: 4ノード対応のPromptContext
            
        Returns:
            生成されたプロンプト文字列
            
        Raises:
            ValueError: 不正なノードタイプまたは必要な情報が不足
        """
        match context.current_node:
            case NodeType.UNDERSTANDING:
                return self._compile_understanding_prompt(context)
            case NodeType.GATHERING:
                return self._compile_gathering_prompt(context)
            case NodeType.EXECUTION:
                return self._compile_execution_prompt(context)
            case NodeType.EVALUATION:
                return self._compile_evaluation_prompt(context)
            case _:
                raise ValueError(f"未対応のノードタイプ: {context.current_node}")
    
    def _compile_understanding_prompt(self, context: FourNodePromptContext) -> str:
        """理解・計画ノード専用プロンプト生成"""
        
        # 継続タスクか新規タスクかで分岐
        if context.retry_context:
            template_name = "understanding_retry"
            template_vars = self._prepare_retry_variables(context)
        else:
            template_name = "understanding_fresh"
            template_vars = self._prepare_fresh_variables(context)
        
        # 共通変数の追加
        template_vars.update({
            "workspace_path": str(context.workspace_path),
            "workspace_overview": self._get_workspace_summary(context),
            "token_limit": context.get_token_allocation()[NodeType.UNDERSTANDING.value]
        })
        
        return self._render_template(template_name, template_vars)
    
    def _compile_gathering_prompt(self, context: FourNodePromptContext) -> str:
        """情報収集ノード専用プロンプト生成"""
        
        understanding = context.understanding
        if not understanding:
            raise ValueError("理解ノードの結果が必要です")
        
        # 再収集か初回収集かで分岐
        if context.gathered_info and context.gathered_info.information_gaps:
            template_name = "gathering_retry"
            template_vars = self._prepare_regathering_variables(context)
        else:
            template_name = "gathering_focused"
            template_vars = self._prepare_gathering_variables(context, understanding)
        
        return self._render_template(template_name, template_vars)
    
    def _compile_execution_prompt(self, context: FourNodePromptContext) -> str:
        """安全実行ノード専用プロンプト生成"""
        
        understanding = context.understanding
        gathered_info = context.gathered_info
        if not (understanding and gathered_info):
            raise ValueError("理解・収集ノードの結果が必要です")
        
        # エラー復旧かロールバックか通常実行かで分岐
        if context.execution_result and context.execution_result.execution_errors:
            template_name = "execution_rollback"
            template_vars = self._prepare_rollback_variables(context)
        else:
            template_name = "execution_safe"
            template_vars = self._prepare_execution_variables(context, understanding, gathered_info)
        
        return self._render_template(template_name, template_vars)
    
    def _compile_evaluation_prompt(self, context: FourNodePromptContext) -> str:
        """評価・継続ノード専用プロンプト生成"""
        
        understanding = context.understanding
        execution_result = context.execution_result
        if not (understanding and execution_result):
            raise ValueError("理解・実行ノードの結果が必要です")
        
        # エラー分析か通常評価かで分岐
        if execution_result.execution_errors:
            template_name = "evaluation_error_analysis"
            template_vars = self._prepare_error_analysis_variables(context)
        else:
            template_name = "evaluation_comprehensive"
            template_vars = self._prepare_evaluation_variables(context, understanding, execution_result)
        
        return self._render_template(template_name, template_vars)
    
    def _prepare_fresh_variables(self, context: FourNodePromptContext) -> Dict[str, str]:
        """新規タスク用の変数を準備"""
        if not context.task_chain:
            raise ValueError("タスクチェーンが空です")
        
        current_task = context.task_chain[-1]
        return {
            "user_message": current_task.user_message,
            "execution_phase": str(context.execution_phase)
        }
    
    def _prepare_retry_variables(self, context: FourNodePromptContext) -> Dict[str, str]:
        """再試行用の変数を準備"""
        if not context.retry_context:
            raise ValueError("再試行コンテキストが必要です")
        
        retry_ctx = context.retry_context
        current_task = context.task_chain[-1] if context.task_chain else None
        
        vars_dict = {
            "user_message": current_task.user_message if current_task else "継続タスク",
            "retry_count": str(retry_ctx.retry_count),
            "execution_phase": str(context.execution_phase)
        }
        
        # 前回の失敗分析を展開
        if retry_ctx.failure_analysis:
            vars_dict.update({
                "previous_failure": {
                    "root_cause": retry_ctx.failure_analysis.root_cause,
                    "message": ", ".join(retry_ctx.previous_errors[0].message if retry_ctx.previous_errors else []),
                    "suggested_fixes": retry_ctx.failure_analysis.suggested_fixes
                }
            })
        
        return vars_dict
    
    def _prepare_gathering_variables(self, context: FourNodePromptContext, understanding: UnderstandingResult) -> Dict[str, str]:
        """情報収集用の変数を準備"""
        return {
            "execution_plan": {
                "summary": understanding.execution_plan.summary,
                "expected_files": understanding.execution_plan.expected_files,
                "required_tools": understanding.execution_plan.required_tools
            },
            "information_needs": understanding.information_needs,
            "current_workspace": self._get_current_files(context),
            "rag_hints": self._prepare_rag_hints(understanding),
            "token_limit": context.get_token_allocation()[NodeType.GATHERING.value]
        }
    
    def _prepare_regathering_variables(self, context: FourNodePromptContext) -> Dict[str, str]:
        """再収集用の変数を準備"""
        gathered_info = context.gathered_info
        understanding = context.understanding
        
        if not (gathered_info and understanding):
            raise ValueError("収集・理解ノードの結果が必要です")
        
        return {
            "previous_collected_files": list(gathered_info.collected_files.keys()),
            "information_gaps": gathered_info.information_gaps,
            "previous_collection_strategy": gathered_info.collection_strategy,
            "execution_plan": {
                "summary": understanding.execution_plan.summary
            },
            "information_needs": understanding.information_needs
        }
    
    def _prepare_execution_variables(self, context: FourNodePromptContext, 
                                   understanding: UnderstandingResult, 
                                   gathered_info: GatheredInfo) -> Dict[str, str]:
        """実行用の変数を準備"""
        return {
            "execution_plan": {
                "summary": understanding.execution_plan.summary,
                "steps": understanding.execution_plan.steps
            },
            "collected_context_summary": self._summarize_collected_context(gathered_info),
            "project_context": {
                "project_type": gathered_info.project_context.project_type,
                "main_languages": gathered_info.project_context.main_languages,
                "architecture_pattern": gathered_info.project_context.architecture_pattern
            },
            "risk_factors": understanding.identified_risks,
            "token_limit": context.get_token_allocation()[NodeType.EXECUTION.value]
        }
    
    def _prepare_rollback_variables(self, context: FourNodePromptContext) -> Dict[str, str]:
        """ロールバック用の変数を準備"""
        execution_result = context.execution_result
        if not execution_result or not execution_result.execution_errors:
            raise ValueError("実行エラー情報が必要です")
        
        error = execution_result.execution_errors[0]  # 最初のエラーを使用
        return {
            "error_type": error.error_type,
            "error_message": error.message,
            "error_location": f"{error.file_path}:{error.line_number}" if error.file_path else "不明",
            "rollback_info": execution_result.rollback_info or {}
        }
    
    def _prepare_evaluation_variables(self, context: FourNodePromptContext,
                                    understanding: UnderstandingResult,
                                    execution_result: ExecutionResult) -> Dict[str, str]:
        """評価用の変数を準備"""
        return {
            "original_plan": {
                "summary": understanding.execution_plan.summary,
                "success_criteria": understanding.execution_plan.success_criteria
            },
            "expected_outcome": understanding.requirement_analysis,
            "execution_results_summary": self._summarize_execution_results(execution_result),
            "error_context": self._format_error_context(execution_result.execution_errors) if execution_result.execution_errors else "エラーなし"
        }
    
    def _prepare_error_analysis_variables(self, context: FourNodePromptContext) -> Dict[str, str]:
        """エラー分析用の変数を準備"""
        execution_result = context.execution_result
        understanding = context.understanding
        
        if not (execution_result and understanding):
            raise ValueError("実行・理解ノードの結果が必要です")
        
        error = execution_result.execution_errors[0] if execution_result.execution_errors else None
        if not error:
            raise ValueError("エラー情報が必要です")
        
        return {
            "error_type": error.error_type,
            "error_message": error.message,
            "error_file": error.file_path or "不明",
            "error_line": str(error.line_number) if error.line_number else "不明",
            "stack_trace": error.stack_trace or "不明",
            "original_plan": understanding.execution_plan.summary,
            "failed_step": self._identify_failed_step(context, error),
            "used_tools": [tr.tool_name for tr in execution_result.tool_results]
        }
    
    def _render_template(self, template_name: str, variables: Dict[str, Any]) -> str:
        """
        テンプレートをレンダリング
        
        Args:
            template_name: テンプレート名
            variables: テンプレート変数
            
        Returns:
            レンダリング済みプロンプト
        """
        if template_name not in self.templates:
            raise ValueError(f"テンプレートが見つかりません: {template_name}")
        
        template = self.templates[template_name]
        
        try:
            # 辞書形式の変数を適切にフォーマット
            formatted_vars = self._format_template_variables(variables)
            return template.format(**formatted_vars)
        except KeyError as e:
            raise ValueError(f"テンプレート変数が不足しています: {e}")
        except Exception as e:
            raise ValueError(f"テンプレートレンダリングに失敗しました: {e}")
    
    def _format_template_variables(self, variables: Dict[str, Any]) -> Dict[str, str]:
        """テンプレート変数を文字列形式に変換"""
        formatted = {}
        
        for key, value in variables.items():
            if isinstance(value, dict):
                # 辞書の場合、JSONまたは改行区切りで展開
                if key in ['execution_plan', 'project_context', 'previous_failure']:
                    formatted[key] = self._format_dict_for_template(value)
                else:
                    formatted[key] = json.dumps(value, ensure_ascii=False, indent=2)
            elif isinstance(value, list):
                # リストの場合、改行区切りで展開
                formatted[key] = '\n'.join([f"- {item}" for item in value])
            else:
                formatted[key] = str(value)
        
        return formatted
    
    def _format_dict_for_template(self, data: Dict[str, Any]) -> str:
        """辞書をテンプレート用にフォーマット"""
        lines = []
        for key, value in data.items():
            if isinstance(value, list):
                value_str = ', '.join(map(str, value))
            else:
                value_str = str(value)
            lines.append(f"- **{key}**: {value_str}")
        return '\n'.join(lines)
    
    def _get_workspace_summary(self, context: FourNodePromptContext) -> str:
        """ワークスペースの概要を取得"""
        # 簡易的な実装（実際はproject_contextがあればそれを使用）
        if context.gathered_info and context.gathered_info.project_context:
            pc = context.gathered_info.project_context
            return f"{pc.project_type} プロジェクト（{', '.join(pc.main_languages)}）"
        
        return f"プロジェクト: {context.workspace_path.name}"
    
    def _get_current_files(self, context: FourNodePromptContext) -> str:
        """現在のファイル状況を取得"""
        if context.gathered_info and context.gathered_info.collected_files:
            files = list(context.gathered_info.collected_files.keys())[:10]  # 最初の10ファイル
            return '\n'.join([f"- {file}" for file in files])
        
        return "ファイル情報を収集中..."
    
    def _prepare_rag_hints(self, understanding: UnderstandingResult) -> str:
        """RAG検索ヒントを準備"""
        hints = []
        
        # 実行計画から検索キーワードを抽出
        plan = understanding.execution_plan
        if plan.required_tools:
            hints.append(f"使用ツール関連: {', '.join(plan.required_tools)}")
        
        # 要求分析から重要キーワードを抽出
        analysis = understanding.requirement_analysis
        if "API" in analysis:
            hints.append("API関連の実装を検索")
        if "データベース" in analysis or "DB" in analysis:
            hints.append("データベース接続を検索")
        if "テスト" in analysis:
            hints.append("テスト関連のコードを検索")
        
        return '\n'.join([f"- {hint}" for hint in hints]) if hints else "特定のヒントなし"
    
    def _summarize_collected_context(self, gathered_info: GatheredInfo) -> str:
        """収集された文脈を要約"""
        summary_parts = []
        
        if gathered_info.collected_files:
            file_count = len(gathered_info.collected_files)
            summary_parts.append(f"収集ファイル数: {file_count}個")
        
        if gathered_info.rag_results:
            rag_count = len(gathered_info.rag_results)
            summary_parts.append(f"RAG検索結果: {rag_count}件")
        
        if gathered_info.project_context:
            pc = gathered_info.project_context
            summary_parts.append(f"プロジェクトタイプ: {pc.project_type}")
        
        return ', '.join(summary_parts) if summary_parts else "文脈情報なし"
    
    def _summarize_execution_results(self, execution_result: ExecutionResult) -> str:
        """実行結果を要約"""
        summary_parts = []
        
        if execution_result.tool_results:
            success_count = sum(1 for tr in execution_result.tool_results if tr.success)
            total_count = len(execution_result.tool_results)
            summary_parts.append(f"ツール実行: {success_count}/{total_count} 成功")
        
        if execution_result.execution_errors:
            error_count = len(execution_result.execution_errors)
            summary_parts.append(f"エラー: {error_count}件")
        
        if execution_result.partial_success:
            summary_parts.append("部分的成功")
        
        return ', '.join(summary_parts) if summary_parts else "実行結果なし"
    
    def _format_error_context(self, errors: List) -> str:
        """エラー文脈をフォーマット"""
        if not errors:
            return "エラーなし"
        
        error_summaries = []
        for error in errors[:3]:  # 最初の3つのエラー
            summary = f"{error.error_type}: {error.message[:100]}"
            if error.file_path:
                summary += f" ({error.file_path})"
            error_summaries.append(summary)
        
        return '\n'.join([f"- {summary}" for summary in error_summaries])
    
    def _identify_failed_step(self, context: FourNodePromptContext, error) -> str:
        """失敗したステップを特定"""
        if context.understanding and context.understanding.execution_plan:
            steps = context.understanding.execution_plan.steps
            # エラーメッセージから関連ステップを推定（簡易的な実装）
            for i, step in enumerate(steps):
                if any(keyword in error.message for keyword in step.split()[:3]):
                    return f"ステップ{i+1}: {step}"
        
        return "不明なステップ"
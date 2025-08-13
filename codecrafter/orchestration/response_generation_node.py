"""
応答生成ノード (Response Generation Node)

5ノードアーキテクチャの最終ノード
TaskProfileテンプレートに基づいて決定論的にレポートを生成
LLM呼び出しを行わない機械的な処理のみ
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass

from ..templates import TaskProfileType, get_template, validate_template_data
from ..state.agent_state import AgentState
from ..prompts.four_node_context import GatheredInfo, ExecutionResult
from ..ui.rich_ui import rich_ui


@dataclass
class ResponseResult:
    """応答生成結果"""
    final_response: str
    template_used: str
    data_completeness: float
    generation_method: str = "deterministic"


class ResponseGenerationNode:
    """応答生成ノード
    
    収集された全情報とTaskProfileテンプレートから
    最終的なユーザー向けレポートを決定論的に生成
    """
    
    def __init__(self):
        """ノードを初期化"""
        self.data_extractors = self._build_data_extractors()
    
    def generate_response(
        self, 
        state: AgentState, 
        gathered_info: Optional[GatheredInfo] = None, 
        execution_result: Optional[ExecutionResult] = None, 
        task_profile_type: Optional[TaskProfileType] = None
    ) -> ResponseResult:
        """最終応答を生成 (5ノードアーキテクチャ対応)
        
        Args:
            state: エージェント状態
            gathered_info: 情報収集結果 (オプション)
            execution_result: 実行結果 (オプション)
            task_profile_type: TaskProfile分類 (オプション)
            
        Returns:
            応答生成結果オブジェクト
        """
        try:
            rich_ui.print_step("[応答生成] フェーズ開始")
            
            # TaskProfileの取得 (パラメータ優先、フォールバック処理)
            if not task_profile_type:
                task_profile_type = self._extract_task_profile(state)
            if not task_profile_type:
                error_response = self._generate_error_response("TaskProfileの特定に失敗しました")
                return ResponseResult(
                    final_response=error_response,
                    template_used="error_template",
                    data_completeness=0.0
                )
            
            rich_ui.print_message(f"TaskProfile: {task_profile_type.value}", "info")
            
            # テンプレートの取得
            template = get_template(task_profile_type)
            
            # データ抽出 (渡されたパラメータを活用)
            extracted_data = self._extract_data_for_template(state, template, gathered_info, execution_result)
            
            # データ検証
            data_completeness = 1.0 if validate_template_data(task_profile_type, extracted_data) else 0.6
            if data_completeness < 1.0:
                rich_ui.print_warning("必須データが不足しています - フォールバック値を使用")
            
            # テンプレートにデータを埋め込み
            final_report = self._fill_template(template, extracted_data)
            
            # Markdown整形
            formatted_report = self._format_markdown(final_report)
            
            rich_ui.print_success("[応答生成] 完了")
            
            return ResponseResult(
                final_response=formatted_report,
                template_used=task_profile_type.value,
                data_completeness=data_completeness
            )
            
        except Exception as e:
            rich_ui.print_error(f"応答生成エラー: {e}")
            error_response = self._generate_error_response(f"応答生成中にエラーが発生しました: {str(e)}")
            return ResponseResult(
                final_response=error_response,
                template_used="error_template",
                data_completeness=0.0,
                generation_method="error_fallback"
            )
    
    def _extract_task_profile(self, state: AgentState) -> Optional[TaskProfileType]:
        """AgentStateからTaskProfileTypeを抽出
        
        Args:
            state: エージェント状態
            
        Returns:
            TaskProfileType、取得できない場合はNone
        """
        try:
            # four_node_contextから取得を試行
            if hasattr(state, 'four_node_context') and state.four_node_context:
                if hasattr(state.four_node_context, 'task_profile_type'):
                    return state.four_node_context.task_profile_type
            
            # current_taskから取得を試行
            if hasattr(state, 'current_task') and state.current_task:
                if hasattr(state.current_task, 'task_profile_type'):
                    return state.current_task.task_profile_type
            
            # conversation_historyから推測（フォールバック）
            if hasattr(state, 'conversation_history') and state.conversation_history:
                last_user_message = None
                for msg in reversed(state.conversation_history):
                    if msg.role == 'user':
                        last_user_message = msg.content
                        break
                
                if last_user_message:
                    from ..services.task_classifier import task_classifier
                    classification = task_classifier.classify(last_user_message)
                    return classification.profile_type
            
            return None
            
        except Exception as e:
            rich_ui.print_warning(f"TaskProfile抽出エラー: {e}")
            return None
    
    def _extract_data_for_template(
        self, 
        state: AgentState, 
        template, 
        gathered_info: Optional[GatheredInfo] = None, 
        execution_result: Optional[ExecutionResult] = None
    ) -> Dict[str, str]:
        """テンプレート用データを抽出 (5ノードアーキテクチャ対応)
        
        Args:
            state: エージェント状態
            template: TaskProfileTemplate
            gathered_info: 情報収集結果 (オプション)
            execution_result: 実行結果 (オプション)
            
        Returns:
            テンプレート変数をキーとした辞書
        """
        extracted_data = {}
        
        try:
            # gathered_info を複数のソースから取得を試行 (パラメータ優先)
            consolidated_gathered_info = {}
            
            # 1. パラメータから渡されたgathered_infoを優先
            if gathered_info and hasattr(gathered_info, 'collected_files'):
                consolidated_gathered_info['collected_files'] = gathered_info.collected_files
                print(f"[RESPONSE_DEBUG] パラメータからgathered_info取得: {len(gathered_info.collected_files)}ファイル")
            
            # 2. collected_contextからフォールバック
            if hasattr(state, 'collected_context') and state.collected_context:
                context = state.collected_context
                print(f"[RESPONSE_DEBUG] collected_context keys: {list(context.keys())}")
                
                # gathered_infoオブジェクトを直接取得
                if 'gathered_info' in context:
                    gathered_obj = context['gathered_info']
                    if hasattr(gathered_obj, 'collected_files'):
                        consolidated_gathered_info['collected_files'] = gathered_obj.collected_files
                        print(f"[RESPONSE_DEBUG] collected_contextからgathered_info取得: {len(gathered_obj.collected_files)}ファイル")
                
                # その他のコンテキストも統合
                consolidated_gathered_info.update(context)
            
            # 3. gathered_info_detailed から（修正版）
            if 'gathered_info_detailed' in consolidated_gathered_info:
                detailed = consolidated_gathered_info['gathered_info_detailed']
                if 'collected_files' in detailed:
                    consolidated_gathered_info['collected_files'] = detailed['collected_files']
                    print(f"[RESPONSE_DEBUG] gathered_info_detailedから取得")
            
            # 4. conversation_historyから情報収集結果を復元
            self._restore_gathered_info_from_history(state, consolidated_gathered_info)
            
            print(f"[RESPONSE_DEBUG] consolidated_gathered_info keys: {list(consolidated_gathered_info.keys())}")
            if 'collected_files' in consolidated_gathered_info:
                print(f"[RESPONSE_DEBUG] collected_files count: {len(consolidated_gathered_info['collected_files'])}")
            
            # data_mappingに基づいてデータを抽出
            for template_var, data_source in template.data_mapping.items():
                value = self._extract_specific_data(state, data_source, consolidated_gathered_info)
                extracted_data[template_var] = value or template.fallback_values.get(template_var, "情報が利用できません")
                print(f"[RESPONSE_DEBUG] {template_var} = {len(str(value))}文字")
            
            # 【追加】The Pecking Order情報を統合
            self._integrate_pecking_order_info(state, extracted_data)
            
            return extracted_data
            
        except Exception as e:
            rich_ui.print_warning(f"データ抽出エラー: {e}")
            # フォールバック値で全て埋める
            return {var: template.fallback_values.get(var, "データ取得エラー") 
                   for var in template.data_mapping.keys()}
    
    def _extract_specific_data(self, state: AgentState, data_source: str, gathered_info: Dict) -> Optional[str]:
        """特定のデータソースから値を抽出
        
        Args:
            state: エージェント状態
            data_source: データソース名
            gathered_info: 収集済み情報
            
        Returns:
            抽出された値、取得できない場合はNone
        """
        try:
            extractor = self.data_extractors.get(data_source)
            if extractor:
                return extractor(state, gathered_info)
            
            # フォールバック: gathered_infoから直接取得を試行
            return gathered_info.get(data_source)
            
        except Exception as e:
            rich_ui.print_warning(f"データ抽出エラー ({data_source}): {e}")
            return None
    
    def _restore_gathered_info_from_history(self, state: AgentState, gathered_info: Dict) -> None:
        """対話履歴から収集情報を復元"""
        try:
            # 最近のメッセージから情報収集の痕跡を探す
            if hasattr(state, 'conversation_history'):
                for msg in reversed(state.conversation_history[-10:]):  # 直近10メッセージ
                    if msg.role == 'assistant' and '[OK] ファイル読み取り完了:' in msg.content:
                        # ファイル読み取り成功の痕跡から推測...（簡易実装）
                        pass
        except Exception as e:
            print(f"[RESPONSE_DEBUG] 履歴復元エラー: {e}")
    
    def _build_data_extractors(self) -> Dict[str, Any]:
        """データ抽出関数の辞書を構築
        
        Returns:
            データソース名をキーとした抽出関数の辞書
        """
        return {
            "target_filename": self._extract_target_filename,
            "file_content_analysis": self._extract_file_content_analysis,
            "file_metadata_summary": self._extract_file_metadata_summary,
            "dependencies_summary": self._extract_dependencies_summary,
            "usage_examples": self._extract_usage_examples,
            "analysis_target": self._extract_analysis_target,
            "quality_metrics": self._extract_quality_metrics,
            "identified_issues": self._extract_identified_issues,
            "improvement_suggestions": self._extract_improvement_suggestions,
            "risk_priority_summary": self._extract_risk_priority_summary,
            "target_name": self._extract_target_name,
            "creation_approach": self._extract_creation_approach,
            "implementation_details": self._extract_implementation_details,
            "risk_considerations": self._extract_risk_considerations,
            "follow_up_actions": self._extract_follow_up_actions,
            "modification_target": self._extract_modification_target,
            "affected_files_list": self._extract_affected_files_list,
            "modification_details": self._extract_modification_details,
            "change_impact_summary": self._extract_change_impact_summary,
            "backup_and_safety_info": self._extract_backup_and_safety_info,
            "search_term": self._extract_search_term,
            "discovered_files_list": self._extract_discovered_files_list,
            "code_snippets": self._extract_code_snippets,
            "search_statistics": self._extract_search_statistics,
            "additional_findings": self._extract_additional_findings,
            "guidance_topic": self._extract_guidance_topic,
            "requirement_list": self._extract_requirement_list,
            "step_by_step_guide": self._extract_step_by_step_guide,
            "troubleshooting_info": self._extract_troubleshooting_info,
            "best_practices": self._extract_best_practices
        }
    
    # ===== データ抽出メソッド群 =====
    
    def _extract_target_filename(self, state: AgentState, gathered_info: Dict) -> str:
        """対象ファイル名を抽出"""
        # collected_filesから最初のファイル名を取得
        if 'collected_files' in gathered_info and gathered_info['collected_files']:
            file_paths = list(gathered_info['collected_files'].keys())
            if file_paths:
                # パスからファイル名のみを抽出
                import os
                return os.path.basename(file_paths[0])
        
        # conversation_historyから推測
        if hasattr(state, 'conversation_history') and state.conversation_history:
            for msg in reversed(state.conversation_history):
                if msg.role == 'user':
                    # ファイル名らしきパターンを検索
                    import re
                    file_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z]{1,4})'
                    matches = re.findall(file_pattern, msg.content)
                    if matches:
                        return matches[0]
        
        return "特定のファイル"
    
    def _extract_file_content_analysis(self, state: AgentState, gathered_info: Dict) -> str:
        """ファイル内容の分析を抽出（詳細なコード内容を含む）"""
        print(f"[FILE_ANALYSIS_DEBUG] gathered_info keys: {list(gathered_info.keys())}")
        
        if 'collected_files' in gathered_info and gathered_info['collected_files']:
            files_info = gathered_info['collected_files']
            print(f"[FILE_ANALYSIS_DEBUG] collected_files type: {type(files_info)}")
            print(f"[FILE_ANALYSIS_DEBUG] collected_files count: {len(files_info)}")
            
            analysis_parts = []
            for file_path, file_content in files_info.items():
                print(f"[FILE_ANALYSIS_DEBUG] Processing file: {file_path}, type: {type(file_content)}")
                
                # ファイル内容の取得（複数の形式に対応）
                if hasattr(file_content, 'content'):
                    content = file_content.content
                    print(f"[FILE_ANALYSIS_DEBUG] Content from .content: {len(content)}文字")
                elif hasattr(file_content, 'file_content'):
                    content = file_content.file_content
                    print(f"[FILE_ANALYSIS_DEBUG] Content from .file_content: {len(content)}文字")
                elif isinstance(file_content, str):
                    content = file_content
                    print(f"[FILE_ANALYSIS_DEBUG] Content as string: {len(content)}文字")
                else:
                    content = str(file_content)
                    print(f"[FILE_ANALYSIS_DEBUG] Content as str(): {len(content)}文字")
                
                # 空の内容をスキップ
                if not content or content.strip() == "":
                    print(f"[FILE_ANALYSIS_DEBUG] Skipping empty file: {file_path}")
                    continue
                
                # 基本情報の分析
                lines_count = len(content.split('\n'))
                chars_count = len(content)
                
                # ファイル名から拡張子を取得
                import os
                _, ext = os.path.splitext(file_path)
                
                if ext == '.md':
                    # Markdownファイルの分析
                    header_matches = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)
                    
                    analysis_parts.append(f"""## {os.path.basename(file_path)}

### 📊 ドキュメント概要
- **行数**: {lines_count}行
- **文字数**: {chars_count:,}文字
- **見出し数**: {len(header_matches)}個

### 📋 主要見出し
{chr(10).join([f"- {header}" for header in header_matches[:10]]) if header_matches else "- なし"}

### 📝 内容プレビュー
```markdown
{content[:2000]}{'...[残り' + str(max(0, len(content) - 2000)) + '文字]' if len(content) > 2000 else ''}
```""")
                
                elif ext == '.py':
                    # Pythonファイルの詳細分析
                    import_matches = re.findall(r'^(?:import\s+(\w+)|from\s+([\w.]+)\s+import)', content, re.MULTILINE)
                    imports = [m[0] or m[1] for m in import_matches]
                    
                    class_matches = re.findall(r'^class\s+(\w+)', content, re.MULTILINE)
                    function_matches = re.findall(r'^(?:def|async def)\s+(\w+)', content, re.MULTILINE)
                    
                    analysis_parts.append(f"""## {os.path.basename(file_path)}

### 📊 ファイル概要
- **行数**: {lines_count}行
- **文字数**: {chars_count:,}文字  
- **インポート**: {len(imports)}個
- **クラス**: {len(class_matches)}個
- **関数**: {len(function_matches)}個

### 📦 インポート一覧
{chr(10).join([f"- `{imp}`" for imp in imports[:10]]) if imports else "- なし"}

### 🏗️ クラス一覧  
{chr(10).join([f"- `{cls}`" for cls in class_matches]) if class_matches else "- なし"}

### ⚙️ 関数一覧
{chr(10).join([f"- `{func}()`" for func in function_matches]) if function_matches else "- なし"}

### 📝 コード内容
```python
{content[:1500]}{'...[残り' + str(max(0, len(content) - 1500)) + '文字]' if len(content) > 1500 else ''}
```""")
                
                else:
                    # その他のファイル
                    analysis_parts.append(f"""## {os.path.basename(file_path)}

### 📊 ファイル概要
- **行数**: {lines_count}行
- **文字数**: {chars_count:,}文字
- **ファイル種別**: {ext or 'テキストファイル'}

### 📝 内容プレビュー
```
{content[:1000]}{'...[残り' + str(max(0, len(content) - 1000)) + '文字]' if len(content) > 1000 else ''}
```""")
            
            if analysis_parts:
                return "\n\n".join(analysis_parts)
            else:
                return "ファイル内容は取得されましたが、分析可能な内容がありませんでした"
        
        return "ファイル内容の分析データが利用できません"
    
    def _extract_file_metadata_summary(self, state: AgentState, gathered_info: Dict) -> str:
        """ファイルメタデータの要約を抽出"""
        if 'collected_files' in gathered_info and gathered_info['collected_files']:
            files_info = gathered_info['collected_files']
            
            metadata_parts = []
            for file_path, file_content in files_info.items():
                # ファイル拡張子から種別を判定
                import os
                _, ext = os.path.splitext(file_path)
                file_type = self._get_file_type_description(ext)
                
                # サイズ情報
                if hasattr(file_content, 'size'):
                    size_info = f"{file_content.size} bytes"
                else:
                    size_info = "サイズ不明"
                
                metadata_parts.append(f"- **{os.path.basename(file_path)}**: {file_type} ({size_info})")
            
            return "\n".join(metadata_parts)
        
        return "ファイルメタデータが利用できません"
    
    def _get_file_type_description(self, ext: str) -> str:
        """ファイル拡張子から種別説明を取得"""
        type_map = {
            '.py': 'Pythonスクリプト',
            '.js': 'JavaScriptファイル',
            '.ts': 'TypeScriptファイル',
            '.md': 'Markdownドキュメント',
            '.json': 'JSON設定ファイル',
            '.yaml': 'YAML設定ファイル',
            '.yml': 'YAML設定ファイル',
            '.txt': 'テキストファイル',
            '.html': 'HTMLファイル',
            '.css': 'CSSスタイルシート'
        }
        return type_map.get(ext.lower(), 'ファイル')
    
    # 他のデータ抽出メソッドは簡略実装（必要に応じて拡張）
    def _extract_dependencies_summary(self, state: AgentState, gathered_info: Dict) -> str:
        return "依存関係の分析は現在実装中です"
    
    def _extract_usage_examples(self, state: AgentState, gathered_info: Dict) -> str:
        return "使用例の生成は現在実装中です"
    
    def _extract_analysis_target(self, state: AgentState, gathered_info: Dict) -> str:
        return self._extract_target_filename(state, gathered_info)
    
    def _extract_quality_metrics(self, state: AgentState, gathered_info: Dict) -> str:
        """品質メトリクスを抽出"""
        if 'collected_files' in gathered_info and gathered_info['collected_files']:
            files_info = gathered_info['collected_files']
            total_files = len(files_info)
            total_size = 0
            total_lines = 0
            
            for file_path, file_content in files_info.items():
                # ファイル内容の取得
                content = self._get_file_content(file_content)
                if content:
                    total_size += len(content)
                    total_lines += len(content.split('\n'))
            
            return f"""**ファイル数**: {total_files}個
**総文字数**: {total_size:,}文字
**総行数**: {total_lines:,}行
**平均ファイルサイズ**: {total_size // total_files if total_files > 0 else 0:,}文字"""
        
        return "ファイル情報が取得できませんでした"
    
    def _extract_identified_issues(self, state: AgentState, gathered_info: Dict) -> str:
        """特定された問題を抽出"""
        if 'collected_files' in gathered_info and gathered_info['collected_files']:
            issues = []
            
            for file_path, file_content in gathered_info['collected_files'].items():
                content = self._get_file_content(file_content)
                if content:
                    # 簡単な問題検出
                    if len(content) > 10000:
                        issues.append(f"- {file_path}: ファイルサイズが大きい ({len(content):,}文字)")
                    
                    # Markdownファイルの場合の簡単なチェック
                    if file_path.endswith('.md'):
                        if not content.strip().startswith('#'):
                            issues.append(f"- {file_path}: 見出しで始まっていない")
                        
                        # 長い行のチェック
                        long_lines = [i+1 for i, line in enumerate(content.split('\n')) if len(line) > 100]
                        if long_lines:
                            issues.append(f"- {file_path}: 長い行が存在 (行番号: {', '.join(map(str, long_lines[:3]))}{'...' if len(long_lines) > 3 else ''})")
            
            return '\n'.join(issues) if issues else "特筆すべき問題は見つかりませんでした"
        
        return "ファイル分析ができませんでした"
    
    def _extract_improvement_suggestions(self, state: AgentState, gathered_info: Dict) -> str:
        """改善提案を抽出"""
        if 'collected_files' in gathered_info and gathered_info['collected_files']:
            suggestions = []
            
            for file_path, file_content in gathered_info['collected_files'].items():
                content = self._get_file_content(file_content)
                if content and file_path.endswith('.md'):
                    # Markdownファイルの改善提案
                    if len(content.split('\n')) < 10:
                        suggestions.append(f"- {file_path}: 内容を充実させることを推奨")
                    
                    if '```' not in content:
                        suggestions.append(f"- {file_path}: コード例の追加を検討")
                    
                    headers = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)
                    if len(headers) < 3:
                        suggestions.append(f"- {file_path}: 構造化のため見出しを追加")
            
            return '\n'.join(suggestions) if suggestions else "現時点で特別な改善提案はありません"
        
        return "改善提案の生成ができませんでした"
    
    def _extract_risk_priority_summary(self, state: AgentState, gathered_info: Dict) -> str:
        """リスク優先度評価を抽出"""
        if 'collected_files' in gathered_info and gathered_info['collected_files']:
            high_priority = []
            medium_priority = []
            low_priority = []
            
            for file_path, file_content in gathered_info['collected_files'].items():
                content = self._get_file_content(file_content)
                if content:
                    # ファイルサイズベースの優先度
                    if len(content) > 5000:
                        high_priority.append(f"大きなファイル: {file_path}")
                    elif len(content) > 1000:
                        medium_priority.append(f"中サイズファイル: {file_path}")
                    else:
                        low_priority.append(f"小さなファイル: {file_path}")
            
            priority_summary = []
            if high_priority:
                priority_summary.append(f"**高優先度** ({len(high_priority)}件): {', '.join(high_priority[:2])}{'...' if len(high_priority) > 2 else ''}")
            if medium_priority:
                priority_summary.append(f"**中優先度** ({len(medium_priority)}件): {', '.join(medium_priority[:2])}{'...' if len(medium_priority) > 2 else ''}")
            if low_priority:
                priority_summary.append(f"**低優先度** ({len(low_priority)}件): {', '.join(low_priority[:2])}{'...' if len(low_priority) > 2 else ''}")
            
            return '\n'.join(priority_summary) if priority_summary else "優先度の評価ができませんでした"
        
        return "リスク評価のためのデータが不足しています"
    
    def _extract_target_name(self, state: AgentState, gathered_info: Dict) -> str:
        return self._extract_target_filename(state, gathered_info)
    
    def _get_file_content(self, file_content) -> str:
        """ファイル内容を統一的に取得するヘルパーメソッド"""
        if hasattr(file_content, 'content'):
            return file_content.content
        elif hasattr(file_content, 'file_content'):
            return file_content.file_content
        elif isinstance(file_content, str):
            return file_content
        else:
            return str(file_content)
    
    def _extract_creation_approach(self, state: AgentState, gathered_info: Dict) -> str:
        return "作成アプローチの決定は現在実装中です"
    
    def _extract_implementation_details(self, state: AgentState, gathered_info: Dict) -> str:
        return "実装詳細の生成は現在実装中です"
    
    def _extract_risk_considerations(self, state: AgentState, gathered_info: Dict) -> str:
        return "リスク考慮事項の分析は現在実装中です"
    
    def _extract_follow_up_actions(self, state: AgentState, gathered_info: Dict) -> str:
        return "フォローアップアクションの提案は現在実装中です"
    
    def _extract_modification_target(self, state: AgentState, gathered_info: Dict) -> str:
        return self._extract_target_filename(state, gathered_info)
    
    def _extract_affected_files_list(self, state: AgentState, gathered_info: Dict) -> str:
        return "影響ファイルの特定は現在実装中です"
    
    def _extract_modification_details(self, state: AgentState, gathered_info: Dict) -> str:
        return "変更詳細の分析は現在実装中です"
    
    def _extract_change_impact_summary(self, state: AgentState, gathered_info: Dict) -> str:
        return "変更影響の分析は現在実装中です"
    
    def _extract_backup_and_safety_info(self, state: AgentState, gathered_info: Dict) -> str:
        return "バックアップと安全対策の情報は現在実装中です"
    
    def _extract_search_term(self, state: AgentState, gathered_info: Dict) -> str:
        return "検索クエリの抽出は現在実装中です"
    
    def _extract_discovered_files_list(self, state: AgentState, gathered_info: Dict) -> str:
        return "発見ファイルのリスト生成は現在実装中です"
    
    def _extract_code_snippets(self, state: AgentState, gathered_info: Dict) -> str:
        return "コードスニペットの抽出は現在実装中です"
    
    def _extract_search_statistics(self, state: AgentState, gathered_info: Dict) -> str:
        return "検索統計の生成は現在実装中です"
    
    def _extract_additional_findings(self, state: AgentState, gathered_info: Dict) -> str:
        return "追加発見事項は現在実装中です"
    
    def _extract_guidance_topic(self, state: AgentState, gathered_info: Dict) -> str:
        return "ガイダンストピックの抽出は現在実装中です"
    
    def _extract_requirement_list(self, state: AgentState, gathered_info: Dict) -> str:
        return "前提条件の抽出は現在実装中です"
    
    def _extract_step_by_step_guide(self, state: AgentState, gathered_info: Dict) -> str:
        return "ステップバイステップガイドの生成は現在実装中です"
    
    def _extract_troubleshooting_info(self, state: AgentState, gathered_info: Dict) -> str:
        return "トラブルシューティング情報は現在実装中です"
    
    def _extract_best_practices(self, state: AgentState, gathered_info: Dict) -> str:
        return "ベストプラクティスの提案は現在実装中です"
    
    def _fill_template(self, template, data: Dict[str, str]) -> str:
        """テンプレートにデータを埋め込み
        
        Args:
            template: TaskProfileTemplate
            data: 埋め込むデータの辞書
            
        Returns:
            データが埋め込まれたテキスト
        """
        result = template.structure
        
        for placeholder, value in data.items():
            pattern = "{" + placeholder + "}"
            result = result.replace(pattern, str(value))
        
        return result
    
    def _format_markdown(self, content: str) -> str:
        """Markdownの整形
        
        Args:
            content: 整形前のMarkdown
            
        Returns:
            整形後のMarkdown
        """
        # 空行の統一
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # 先頭と末尾の空白を除去
        content = content.strip()
        
        # 生成日時を追加
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        footer = f"\n\n---\n*Generated by Duckflow at {timestamp}*"
        
        return content + footer
    
    def _integrate_pecking_order_info(self, state: AgentState, extracted_data: Dict[str, str]) -> None:
        """The Pecking Order情報を応答データに統合する
        
        Args:
            state: AgentState
            extracted_data: 抽出済みデータ辞書（変更される）
        """
        try:
            # The Pecking Order情報を取得
            pecking_order_status = state.get_pecking_order_status()
            current_task = state.get_current_task()
            
            if pecking_order_status:
                # 進捗情報を統合
                completion_rate = pecking_order_status.get('completion_rate', 0.0)
                total_tasks = pecking_order_status.get('total_tasks', 0)
                remaining_tasks = pecking_order_status.get('pending_tasks', 0)
                
                # 既存のデータに進捗情報を追加
                extracted_data['current_task_progress'] = f"{completion_rate:.1%}"
                extracted_data['remaining_tasks_count'] = str(remaining_tasks)
                extracted_data['total_tasks_count'] = str(total_tasks)
                
                # タスク階層情報を追加
                if state.task_tree:
                    hierarchy_str = state.get_pecking_order_string()
                    extracted_data['task_hierarchy'] = hierarchy_str
                
                # 現在のタスク情報を追加
                if current_task:
                    extracted_data['current_task_description'] = current_task.description
                    extracted_data['current_task_status'] = current_task.status.value
                
                rich_ui.print_message(f"[RESPONSE] The Pecking Order情報を統合: {completion_rate:.1%}完了", "info")
            
        except Exception as e:
            rich_ui.print_warning(f"The Pecking Order情報統合エラー: {e}")
            # エラーが発生してもフォールバック値を設定
            extracted_data['current_task_progress'] = "0.0%"
            extracted_data['remaining_tasks_count'] = "0"
            extracted_data['total_tasks_count'] = "0"
            extracted_data['task_hierarchy'] = "タスク階層情報が利用できません"
    
    def _generate_error_response(self, error_message: str) -> str:
        """エラー時のフォールバック応答を生成
        
        Args:
            error_message: エラーメッセージ
            
        Returns:
            エラー応答のMarkdown
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return f"""## ❌ 処理エラー

申し訳ございません。処理中にエラーが発生しました。

### エラー詳細
{error_message}

### 対処方法
1. 要求を再度確認してください
2. 対象ファイルが存在することを確認してください  
3. エラーが継続する場合は、より具体的な指示をお試しください

---
*Generated by Duckflow at {timestamp}*"""


# グローバルインスタンス
response_generation_node = ResponseGenerationNode()
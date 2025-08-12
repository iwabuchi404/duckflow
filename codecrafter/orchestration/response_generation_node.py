"""
応答生成ノード (Response Generation Node)

5ノードアーキテクチャの最終ノード
TaskProfileテンプレートに基づいて決定論的にレポートを生成
LLM呼び出しを行わない機械的な処理のみ
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..templates import TaskProfileType, get_template, validate_template_data
from ..state.agent_state import AgentState
from ..prompts.four_node_context import GatheredInfo, ExecutionResult
from ..ui.rich_ui import rich_ui


class ResponseGenerationNode:
    """応答生成ノード
    
    収集された全情報とTaskProfileテンプレートから
    最終的なユーザー向けレポートを決定論的に生成
    """
    
    def __init__(self):
        """ノードを初期化"""
        self.data_extractors = self._build_data_extractors()
    
    def generate_response(self, state: AgentState) -> str:
        """最終応答を生成
        
        Args:
            state: エージェント状態（全ての収集情報を含む）
            
        Returns:
            ユーザー向けの最終レポート（Markdown形式）
        """
        try:
            rich_ui.print_step("[応答生成] フェーズ開始")
            
            # TaskProfileの取得
            task_profile_type = self._extract_task_profile(state)
            if not task_profile_type:
                return self._generate_error_response("TaskProfileの特定に失敗しました")
            
            rich_ui.print_message(f"TaskProfile: {task_profile_type.value}", "info")
            
            # テンプレートの取得
            template = get_template(task_profile_type)
            
            # データ抽出
            extracted_data = self._extract_data_for_template(state, template)
            
            # データ検証
            if not validate_template_data(task_profile_type, extracted_data):
                rich_ui.print_warning("必須データが不足しています - フォールバック値を使用")
            
            # テンプレートにデータを埋め込み
            final_report = self._fill_template(template, extracted_data)
            
            # Markdown整形
            formatted_report = self._format_markdown(final_report)
            
            rich_ui.print_success("[応答生成] 完了")
            
            return formatted_report
            
        except Exception as e:
            rich_ui.print_error(f"応答生成エラー: {e}")
            return self._generate_error_response(f"応答生成中にエラーが発生しました: {str(e)}")
    
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
    
    def _extract_data_for_template(self, state: AgentState, template) -> Dict[str, str]:
        """テンプレート用データを抽出
        
        Args:
            state: エージェント状態
            template: TaskProfileTemplate
            
        Returns:
            テンプレート変数をキーとした辞書
        """
        extracted_data = {}
        
        try:
            # gathered_info を複数のソースから取得を試行
            gathered_info = {}
            
            # 1. collected_contextから
            if hasattr(state, 'collected_context') and state.collected_context:
                gathered_info.update(state.collected_context)
            
            # 2. gathered_info_detailed から（修正版）
            if 'gathered_info_detailed' in gathered_info:
                detailed = gathered_info['gathered_info_detailed']
                if 'collected_files' in detailed:
                    gathered_info['collected_files'] = detailed['collected_files']
            
            # 3. conversation_historyから情報収集結果を復元
            self._restore_gathered_info_from_history(state, gathered_info)
            
            print(f"[RESPONSE_DEBUG] gathered_info keys: {list(gathered_info.keys())}")
            if 'collected_files' in gathered_info:
                print(f"[RESPONSE_DEBUG] collected_files count: {len(gathered_info['collected_files'])}")
            
            # data_mappingに基づいてデータを抽出
            for template_var, data_source in template.data_mapping.items():
                value = self._extract_specific_data(state, data_source, gathered_info)
                extracted_data[template_var] = value or template.fallback_values.get(template_var, "情報が利用できません")
                print(f"[RESPONSE_DEBUG] {template_var} = {len(str(value))}文字")
            
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
        if 'collected_files' in gathered_info and gathered_info['collected_files']:
            files_info = gathered_info['collected_files']
            
            analysis_parts = []
            for file_path, file_content in files_info.items():
                if hasattr(file_content, 'content'):
                    content = file_content.content
                else:
                    content = str(file_content)
                
                # 基本情報の分析
                lines_count = len(content.split('\n'))
                chars_count = len(content)
                
                # ターゲットファイル（test_step2d_graphなど）は詳細に分析
                is_target_file = any(pattern in file_path.lower() for pattern in ['test_step2d_graph', 'target', 'main'])
                
                if is_target_file and file_path.endswith('.py'):
                    # Python詳細分析
                    import_matches = re.findall(r'^(?:import\s+(\w+)|from\s+([\w.]+)\s+import)', content, re.MULTILINE)
                    imports = [m[0] or m[1] for m in import_matches]
                    
                    class_matches = re.findall(r'^class\s+(\w+)', content, re.MULTILINE)
                    function_matches = re.findall(r'^(?:def|async def)\s+(\w+)', content, re.MULTILINE)
                    
                    analysis_parts.append(f"""## {file_path}

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
{content[:3000]}{'...[残り' + str(max(0, len(content) - 3000)) + '文字]' if len(content) > 3000 else ''}
```""")
                
                elif file_path.endswith('.py'):
                    # 通常のPythonファイル（簡易版）
                    import_count = len(re.findall(r'^import\s+|^from\s+', content, re.MULTILINE))
                    class_count = len(re.findall(r'^class\s+\w+', content, re.MULTILINE))
                    function_count = len(re.findall(r'^def\s+\w+', content, re.MULTILINE))
                    
                    analysis_parts.append(f"""**{file_path}**
- 行数: {lines_count}行
- 文字数: {chars_count}文字  
- インポート: {import_count}個
- クラス: {class_count}個
- 関数: {function_count}個

```python
{content[:500]}{'...[省略]' if len(content) > 500 else ''}
```""")
                else:
                    # 非Pythonファイル
                    analysis_parts.append(f"""**{file_path}**
- 行数: {lines_count}行
- 文字数: {chars_count}文字""")
            
            return "\n\n".join(analysis_parts)
        
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
        return "品質メトリクスの分析は現在実装中です"
    
    def _extract_identified_issues(self, state: AgentState, gathered_info: Dict) -> str:
        return "問題の特定は現在実装中です"
    
    def _extract_improvement_suggestions(self, state: AgentState, gathered_info: Dict) -> str:
        return "改善提案の生成は現在実装中です"
    
    def _extract_risk_priority_summary(self, state: AgentState, gathered_info: Dict) -> str:
        return "リスク優先度の評価は現在実装中です"
    
    def _extract_target_name(self, state: AgentState, gathered_info: Dict) -> str:
        return self._extract_target_filename(state, gathered_info)
    
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
response_generator = ResponseGenerationNode()
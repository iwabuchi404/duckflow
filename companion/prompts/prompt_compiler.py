#!/usr/bin/env python3
"""
プロンプトコンパイラ - プロンプトの最適化とコンパイル

codecrafterから分離し、companion内で完結するように調整
3層構造（Base/Main/Specialized）と記憶注入機能を統合
"""

import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .memory_context_extractor import MemoryContextExtractor
from ..state.agent_state import AgentState


@dataclass
class PromptTemplate:
    """プロンプトテンプレート"""
    name: str
    content: str
    variables: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'name': self.name,
            'content': self.content,
            'variables': self.variables,
            'metadata': self.metadata
        }


class PromptCompiler:
    """プロンプトコンパイラ - 3層構造と記憶注入機能を統合"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.templates: Dict[str, PromptTemplate] = {}
        self.compilation_cache: Dict[str, str] = {}
        
        # 記憶注入機能の初期化
        self.memory_extractor = MemoryContextExtractor()
        
        # 3層構造の設定
        self.layer_configs = {
            "base_specialized": {
                "description": "軽量版: Base + Specializedのみ",
                "token_limit": 2000,
                "layers": ["base", "specialized"]
            },
            "base_main": {
                "description": "標準版: Base + Main",
                "token_limit": 4000,
                "layers": ["base", "main"]
            },
            "base_main_specialized": {
                "description": "完全版: Base + Main + Specialized",
                "token_limit": 6000,
                "layers": ["base", "main", "specialized"]
            }
        }
        
        self.logger.info("PromptCompiler初期化完了（3層構造 + 記憶注入対応）")
    
    def add_template(self, name: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """テンプレートを追加"""
        try:
            # 変数を抽出
            variables = self._extract_variables(content)
            
            template = PromptTemplate(
                name=name,
                content=content,
                variables=variables,
                metadata=metadata or {}
            )
            
            self.templates[name] = template
            self.logger.info(f"テンプレート追加: {name} (変数: {len(variables)}件)")
            return True
            
        except Exception as e:
            self.logger.error(f"テンプレート追加エラー: {e}")
            return False
    
    def _extract_variables(self, content: str) -> List[str]:
        """テンプレートから変数を抽出"""
        variables = []
        
        # {{variable}} 形式の変数を検索
        pattern = r'\{\{(\w+)\}\}'
        matches = re.findall(pattern, content)
        
        for match in matches:
            if match not in variables:
                variables.append(match)
        
        return variables
    
    def compile_prompt(self, template_name: str, variables: Dict[str, Any]) -> str:
        """プロンプトをコンパイル"""
        try:
            if template_name not in self.templates:
                raise ValueError(f"テンプレートが見つかりません: {template_name}")
            
            template = self.templates[template_name]
            
            # キャッシュキーを生成
            cache_key = f"{template_name}:{hash(str(sorted(variables.items())))}"
            
            if cache_key in self.compilation_cache:
                self.logger.debug(f"キャッシュからプロンプトを取得: {template_name}")
                return self.compilation_cache[cache_key]
            
            # プロンプトをコンパイル
            compiled_content = template.content
            
            for var_name, var_value in variables.items():
                placeholder = f"{{{{{var_name}}}}}"
                if placeholder in compiled_content:
                    compiled_content = compiled_content.replace(placeholder, str(var_value))
            
            # 未使用の変数を警告
            unused_vars = [var for var in template.variables if f"{{{{{var}}}}}" in compiled_content]
            if unused_vars:
                self.logger.warning(f"未使用の変数: {unused_vars}")
            
            # キャッシュに保存
            self.compilation_cache[cache_key] = compiled_content
            
            self.logger.debug(f"プロンプトコンパイル完了: {template_name}")
            return compiled_content
            
        except Exception as e:
            self.logger.error(f"プロンプトコンパイルエラー: {e}")
            return f"プロンプトコンパイルエラー: {str(e)}"
    
    def compile_with_memory(self, pattern: str, base_context: str, 
                           main_context: str = "", specialized_context: str = "",
                           agent_state: Optional[AgentState] = None, 
                           target_file: Optional[str] = None) -> str:
        """記憶データを統合した3層プロンプトを合成
        
        Args:
            pattern: プロンプトパターン（base_specialized, base_main, base_main_specialized）
            base_context: Base層のコンテキスト
            main_context: Main層のコンテキスト（オプション）
            specialized_context: Specialized層のコンテキスト（オプション）
            agent_state: エージェント状態（記憶データ抽出用）
            target_file: 対象ファイル（オプション）
            
        Returns:
            記憶データが統合されたプロンプト
        """
        try:
            self.logger.info(f"記憶統合プロンプトコンパイル開始: pattern={pattern}")
            
            # パターンの検証
            if pattern not in self.layer_configs:
                self.logger.warning(f"未知のパターン: {pattern}, デフォルト使用")
                pattern = "base_main"
            
            # 記憶データの抽出
            memory_data = {}
            if agent_state:
                memory_data = self.memory_extractor.extract_for_pattern(
                    pattern, agent_state, target_file
                )
            
            # Main層の会話履歴統合状況をログ出力
            if agent_state and agent_state.conversation_history:
                self.logger.info(f"会話履歴統合確認: {len(agent_state.conversation_history)}件の履歴をMain層に統合")
                self.logger.debug(f"Main層内容（最初の300文字）: {main_context[:300] if main_context else '空'}...")
            else:
                self.logger.warning("会話履歴が存在しません")
            
            # パターンに基づいて記憶データを各層に注入
            if pattern == "base_specialized":
                enhanced_base = self._inject_memory_to_base(base_context, memory_data)
                enhanced_specialized = self._inject_memory_to_specialized(
                    specialized_context, memory_data
                )
                result = self._compile_base_specialized(enhanced_base, enhanced_specialized)
                
            elif pattern == "base_main":
                enhanced_base = self._inject_memory_to_base(base_context, memory_data)
                enhanced_main = self._inject_memory_to_main(main_context, memory_data)
                result = self._compile_base_main(enhanced_base, enhanced_main)
                
            elif pattern == "base_main_specialized":
                enhanced_base = self._inject_memory_to_base(base_context, memory_data)
                enhanced_main = self._inject_memory_to_main(main_context, memory_data)
                enhanced_specialized = self._inject_memory_to_specialized(
                    specialized_context, memory_data
                )
                result = self._compile_base_main_specialized(
                    enhanced_base, enhanced_main, enhanced_specialized
                )
            
            # トークン制限の適用
            result = self._apply_token_limit(result, pattern)
            
            self.logger.info(f"記憶統合プロンプトコンパイル完了: pattern={pattern}, 長さ={len(result)}")
            return result
            
        except Exception as e:
            self.logger.error(f"記憶統合プロンプトコンパイルエラー: {e}")
            # エラー時は基本コンテキストのみを返す
            return base_context
    
    def _inject_memory_to_base(self, base_context: str, memory_data: Dict[str, Any]) -> str:
        """Base層に基本記憶データを注入"""
        try:
            base_memory = memory_data.get('base_memory', {})
            
            if not base_memory or 'error' in base_memory:
                return base_context
            
            # セッション情報
            session_info = base_memory.get('session_info', {})
            session_text = f"""
セッションID: {session_info.get('session_id', '不明')}
開始時刻: {session_info.get('start_time', '不明')}
継続時間: {session_info.get('duration', '不明')}"""
            
            # 作業ディレクトリ
            work_dir = base_memory.get('work_dir', './work')
            
            # 現在の状態
            current_state = base_memory.get('current_state', {})
            state_text = f"""
現在のステップ: {current_state.get('step', 'UNKNOWN')}
現在のステータス: {current_state.get('status', 'UNKNOWN')}
リトライ回数: {current_state.get('retry_count', 0)}"""
            
            # バイタル情報
            vitals = base_memory.get('vitals', {})
            vitals_text = self._format_vitals(vitals)
            
            # 記憶データを統合
            enhanced_base = f"""{base_context}

--- 基本記憶 ---
{session_text}
作業ディレクトリ: {work_dir}
{state_text}
{vitals_text}"""
            
            return enhanced_base
            
        except Exception as e:
            self.logger.warning(f"Base層記憶注入エラー: {e}")
            return base_context
    
    def _inject_memory_to_main(self, main_context: str, memory_data: Dict[str, Any]) -> str:
        """Main層に主要記憶データを注入"""
        try:
            main_memory = memory_data.get('main_memory', {})
            
            if not main_memory or 'error' in main_memory:
                return main_context
            
            # 最近のファイル操作
            recent_file_ops = main_memory.get('recent_file_ops', [])
            file_ops_text = self._format_file_operations(recent_file_ops)
            
            # 会話履歴の要約
            conversation_summary = main_memory.get('conversation_summary', {})
            conv_text = self._format_conversation_summary(conversation_summary)
            
            # 処理履歴
            operation_history = main_memory.get('operation_history', [])
            ops_text = self._format_operation_history(operation_history)
            
            # ツール実行履歴
            tool_execution_history = main_memory.get('tool_execution_history', [])
            tool_text = self._format_tool_execution_history(tool_execution_history)
            
            # 記憶データを統合
            enhanced_main = f"""{main_context}

--- 主要記憶 ---
{file_ops_text}
{conv_text}
{ops_text}
{tool_text}"""
            
            return enhanced_main
            
        except Exception as e:
            self.logger.warning(f"Main層記憶注入エラー: {e}")
            return main_context
    
    def _inject_memory_to_specialized(self, specialized_context: str, 
                                     memory_data: Dict[str, Any]) -> str:
        """Specialized層に専門記憶データを注入"""
        try:
            specialized_memory = memory_data.get('specialized_memory', {})
            
            if not specialized_memory or 'error' in specialized_memory:
                return specialized_context
            
            # ファイル内容キャッシュ
            file_cache = specialized_memory.get('file_cache', {})
            cache_text = self._format_file_cache(file_cache)
            
            # 要約履歴
            summary_history = specialized_memory.get('summary_history', [])
            summary_text = self._format_summary_history(summary_history)
            
            # プラン履歴
            plan_history = specialized_memory.get('plan_history', [])
            plan_text = self._format_plan_history(plan_history)
            
            # 記憶データを統合
            enhanced_specialized = f"""{specialized_context}

--- 専門記憶 ---
{cache_text}
{summary_text}
{plan_text}"""
            
            return enhanced_specialized
            
        except Exception as e:
            self.logger.warning(f"Specialized層記憶注入エラー: {e}")
            return specialized_context
    
    def _compile_base_specialized(self, base_context: str, specialized_context: str) -> str:
        """Base + Specializedの合成"""
        return f"{base_context}\n\n{specialized_context}"
    
    def _compile_base_main(self, base_context: str, main_context: str) -> str:
        """Base + Mainの合成"""
        return f"{base_context}\n\n{main_context}"
    
    def _compile_base_main_specialized(self, base_context: str, main_context: str, 
                                      specialized_context: str) -> str:
        """Base + Main + Specializedの合成"""
        return f"{base_context}\n\n{main_context}\n\n{specialized_context}"
    
    def _apply_token_limit(self, prompt: str, pattern: str) -> str:
        """トークン制限を適用"""
        try:
            config = self.layer_configs.get(pattern, {})
            token_limit = config.get('token_limit', 4000)
            
            # 簡易的な文字数制限（実際のトークン数はより正確な計算が必要）
            char_limit = token_limit * 4  # 概算: 1トークン ≈ 4文字
            
            if len(prompt) > char_limit:
                self.logger.warning(f"プロンプトが長すぎます: {len(prompt)}文字 > {char_limit}文字制限")
                # 長すぎる場合は要約版を生成
                return self._truncate_prompt(prompt, char_limit)
            
            return prompt
            
        except Exception as e:
            self.logger.warning(f"トークン制限適用エラー: {e}")
            return prompt
    
    def _truncate_prompt(self, prompt: str, char_limit: int) -> str:
        """プロンプトを制限内に切り詰める"""
        try:
            if len(prompt) <= char_limit:
                return prompt
            
            # Base層は保持し、他の層を要約
            lines = prompt.split('\n')
            base_end = 0
            
            # Base層の終端を特定
            for i, line in enumerate(lines):
                if line.strip() == "--- 基本記憶 ---":
                    base_end = i
                    break
            
            if base_end > 0:
                base_content = '\n'.join(lines[:base_end + 1])
                remaining_chars = char_limit - len(base_content) - 100  # 余裕を持たせる
                
                if remaining_chars > 0:
                    # 残りの内容を要約
                    summary = f"\n\n--- 要約された記憶 ---\nプロンプトが長すぎるため、詳細な記憶データは省略されています。"
                    return base_content + summary
            
            # 最後の手段: 最初の部分のみを保持
            return prompt[:char_limit - 100] + "\n\n... (プロンプトが長すぎるため省略) ..."
            
        except Exception as e:
            self.logger.warning(f"プロンプト切り詰めエラー: {e}")
            return prompt[:char_limit] if len(prompt) > char_limit else prompt
    
    def _format_file_operations(self, file_ops: List[Dict[str, Any]]) -> str:
        """ファイル操作履歴をフォーマット"""
        if not file_ops:
            return "最近のファイル操作: なし"
        
        formatted_ops = []
        for op in file_ops[:3]:  # 最新3件
            op_type = op.get('operation', '不明')
            file_path = op.get('file_path', '不明')
            content_length = op.get('content_length', 0)
            timestamp = op.get('timestamp', '不明')[:19] if op.get('timestamp') else '不明'  # 短縮
            
            # ファイル操作の詳細情報を追加
            if content_length > 0:
                formatted_ops.append(f"- {op_type}: {file_path} ({content_length}文字, {timestamp})")
            else:
                formatted_ops.append(f"- {op_type}: {file_path} ({timestamp})")
        
        return f"最近のファイル操作:\n" + "\n".join(formatted_ops)
    
    def _format_conversation_summary(self, conv_summary: Dict[str, Any]) -> str:
        """会話履歴要約をフォーマット"""
        if not conv_summary or 'error' in conv_summary:
            return "会話履歴: なし"
        
        total = conv_summary.get('total_messages', 0)
        summary = conv_summary.get('summary', '要約なし')
        recent_topics = conv_summary.get('recent_topics', [])
        
        # 最新トピックを含める
        topics_text = ", ".join(recent_topics[:3]) if recent_topics else "なし"
        
        return f"会話履歴: {total}件のメッセージ\n最新トピック: {topics_text}\n要約: {summary[:200]}..." if len(summary) > 200 else f"会話履歴: {total}件のメッセージ\n最新トピック: {topics_text}\n要約: {summary}"
    
    def _format_operation_history(self, operations: List[Dict[str, Any]]) -> str:
        """処理履歴をフォーマット"""
        if not operations:
            return "処理履歴: なし"
        
        formatted_ops = []
        for op in operations[:3]:  # 最新3件
            operation = op.get('operation', '不明')
            success = op.get('success', False)
            timestamp = op.get('timestamp', '不明')[:19] if op.get('timestamp') else '不明'
            
            status_icon = "✅" if success else "❌"
            formatted_ops.append(f"- {status_icon} {operation} ({timestamp})")
        
        return f"処理履歴:\n" + "\n".join(formatted_ops)
    
    def _format_file_cache(self, file_cache: Dict[str, Any]) -> str:
        """ファイルキャッシュをフォーマット"""
        if not file_cache or 'error' in file_cache:
            return "ファイルキャッシュ: なし"
        
        if 'target_file' in file_cache:
            # 特定ファイルのキャッシュ
            target = file_cache.get('target_file', '不明')
            content_length = file_cache.get('content_length', 0)
            timestamp = file_cache.get('cache_timestamp', '不明')[:19] if file_cache.get('cache_timestamp') else '不明'
            
            if content_length > 0:
                return f"対象ファイルキャッシュ: {target} ({content_length}文字, {timestamp})"
            else:
                return f"対象ファイルキャッシュ: {target} (空, {timestamp})"
        else:
            # 全ファイルキャッシュの概要
            cached_files = file_cache.get('cached_files', [])
            total = file_cache.get('total_cached_files', 0)
            files_list = ', '.join(cached_files[:3])
            if len(cached_files) > 3:
                files_list += f"他{len(cached_files) - 3}件"
            return f"ファイルキャッシュ: {total}件\nキャッシュ済み: {files_list}"
    
    def _format_summary_history(self, summaries: List[Dict[str, Any]]) -> str:
        """要約履歴をフォーマット"""
        if not summaries:
            return "要約履歴: なし"
        
        formatted_summaries = []
        for summary in summaries[:3]:  # 最新3件
            summary_type = summary.get('type', '不明')
            timestamp = summary.get('timestamp', '不明')
            formatted_summaries.append(f"- {summary_type} ({timestamp})")
        
        return f"要約履歴:\n" + "\n".join(formatted_summaries)
    
    def _format_plan_history(self, plans: List[Dict[str, Any]]) -> str:
        """プラン履歴をフォーマット"""
        if not plans:
            return "プラン履歴: なし"
        
        formatted_plans = []
        for plan in plans[:3]:  # 最新3件
            plan_name = plan.get('name', '不明')
            goal = plan.get('goal', '')
            status = plan.get('status', '不明')
            steps_count = plan.get('steps_count', 0)
            completed_steps = plan.get('completed_steps', 0)
            
            # 進捗情報を追加
            progress = f"({completed_steps}/{steps_count}ステップ完了)"
            formatted_plans.append(f"- {plan_name}: {status} {progress}")
            if goal and len(goal) < 100:
                formatted_plans.append(f"  目標: {goal}")
        
        return f"プラン履歴:\n" + "\n".join(formatted_plans)
    
    def _format_vitals(self, vitals: Dict[str, Any]) -> str:
        """バイタル情報をフォーマット"""
        if not vitals:
            return "エージェント状態: 情報なし"
        
        mood = vitals.get('mood', 1.0)
        focus = vitals.get('focus', 1.0)
        stamina = vitals.get('stamina', 1.0)
        total_loops = vitals.get('total_loops', 0)
        error_count = vitals.get('error_count', 0)
        
        # 状態の評価
        mood_status = "良好" if mood > 0.7 else "普通" if mood > 0.4 else "不調"
        focus_status = "集中" if focus > 0.7 else "普通" if focus > 0.4 else "散漫"
        stamina_status = "十分" if stamina > 0.7 else "普通" if stamina > 0.4 else "疲労"
        
        return f"""エージェント状態:
気分: {mood:.2f} ({mood_status})
集中力: {focus:.2f} ({focus_status})
体力: {stamina:.2f} ({stamina_status})
処理回数: {total_loops}回, エラー: {error_count}回"""
    
    def _format_tool_execution_history(self, tool_executions: List[Dict[str, Any]]) -> str:
        """ツール実行履歴をフォーマット"""
        if not tool_executions:
            return "ツール実行履歴: なし"
        
        formatted_executions = []
        for execution in tool_executions[:5]:  # 最新5件
            tool_name = execution.get('tool_name', '不明')
            success = execution.get('success', False)
            execution_time = execution.get('execution_time', 0)
            timestamp = execution.get('timestamp', '不明')[:19] if execution.get('timestamp') else '不明'
            
            status_icon = "✅" if success else "❌"
            time_str = f"{execution_time:.3f}s" if execution_time < 1 else f"{execution_time:.1f}s"
            
            formatted_executions.append(f"- {status_icon} {tool_name} ({time_str}, {timestamp})")
            
            # エラーがある場合は表示
            if not success and execution.get('error'):
                error_msg = execution['error'][:50] + "..." if len(execution['error']) > 50 else execution['error']
                formatted_executions.append(f"  エラー: {error_msg}")
        
        return f"ツール実行履歴:\n" + "\n".join(formatted_executions)
    
    def get_pattern_info(self, pattern: str) -> Dict[str, Any]:
        """パターン情報を取得"""
        return self.layer_configs.get(pattern, {})
    
    def list_patterns(self) -> List[str]:
        """利用可能なパターン一覧を取得"""
        return list(self.layer_configs.keys())
    
    def get_memory_statistics(self, agent_state: Optional[AgentState] = None) -> Dict[str, Any]:
        """記憶データの統計情報を取得"""
        if not agent_state:
            return {"error": "AgentStateが提供されていません"}
        
        try:
            stats = self.memory_extractor.get_memory_statistics(agent_state)
            stats['available_patterns'] = self.list_patterns()
            return stats
            
        except Exception as e:
            self.logger.error(f"記憶統計情報取得エラー: {e}")
            return {"error": f"記憶統計情報取得エラー: {str(e)}"}
    
    # 既存のメソッド（互換性のため保持）
    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """テンプレートを取得"""
        return self.templates.get(name)
    
    def list_templates(self) -> List[str]:
        """テンプレート一覧を取得"""
        return list(self.templates.keys())
    
    def remove_template(self, name: str) -> bool:
        """テンプレートを削除"""
        try:
            if name in self.templates:
                del self.templates[name]
                self.logger.info(f"テンプレート削除: {name}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"テンプレート削除エラー: {e}")
            return False
    
    def clear_cache(self):
        """コンパイルキャッシュをクリア"""
        self.compilation_cache.clear()
        self.logger.info("コンパイルキャッシュをクリアしました")
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return {
            'total_templates': len(self.templates),
            'cache_size': len(self.compilation_cache),
            'template_names': list(self.templates.keys()),
            'available_patterns': self.list_patterns(),
            'layer_configs': self.layer_configs
        }
    
    def compile_system_prompt_dto(self, prompt_data: Any) -> str:
        """システムプロンプトDTOをコンパイル
        - dict/str いずれの入力にも対応
        """
        try:
            if isinstance(prompt_data, str):
                return prompt_data
            if not isinstance(prompt_data, dict):
                return str(prompt_data)

            # システムプロンプトの基本構造
            system_prompt = prompt_data.get('system_prompt', '')
            user_context = prompt_data.get('user_context', '')
            task_description = prompt_data.get('task_description', '')

            # プロンプトを構築
            compiled_prompt = f"""システムプロンプト:
{system_prompt}

ユーザーコンテキスト:
{user_context}

タスク説明:
{task_description}

上記の情報に基づいて、適切な応答を生成してください。"""

            self.logger.info("システムプロンプトDTOコンパイル完了")
            return compiled_prompt

        except Exception as e:
            self.logger.error(f"システムプロンプトDTOコンパイルエラー: {e}")
            return f"システムプロンプトコンパイルエラー: {str(e)}"
    
    def compile_with_context(self, template_name: str, context: Dict[str, Any]) -> str:
        """コンテキスト付きでプロンプトをコンパイル"""
        try:
            if template_name not in self.templates:
                raise ValueError(f"テンプレートが見つかりません: {template_name}")
            
            template = self.templates[template_name]
            
            # コンテキスト情報を追加
            context_variables = {
                **context,
                'timestamp': context.get('timestamp', ''),
                'session_id': context.get('session_id', ''),
                'user_id': context.get('user_id', '')
            }
            
            return self.compile_prompt(template_name, context_variables)
            
        except Exception as e:
            self.logger.error(f"コンテキスト付きコンパイルエラー: {e}")
            return f"コンパイルエラー: {str(e)}"
    
    def to_dict(self) -> Dict[str, Any]:
        """オブジェクトの状態を辞書形式で取得"""
        return {
            'templates': {name: template.to_dict() for name, template in self.templates.items()},
            'statistics': self.get_statistics()
        }


# グローバルインスタンス
prompt_compiler = PromptCompiler()


# 便利な関数
def add_template(name: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """テンプレートを追加"""
    return prompt_compiler.add_template(name, content, metadata)


def compile_prompt(template_name: str, variables: Dict[str, Any]) -> str:
    """プロンプトをコンパイル"""
    return prompt_compiler.compile_prompt(template_name, variables)


def compile_with_memory(pattern: str, base_context: str, main_context: str = "",
                        specialized_context: str = "", agent_state: Optional[AgentState] = None,
                        target_file: Optional[str] = None) -> str:
    """記憶データを統合した3層プロンプトを合成"""
    return prompt_compiler.compile_with_memory(
        pattern, base_context, main_context, specialized_context, agent_state, target_file
    )


def get_template(name: str) -> Optional[PromptTemplate]:
    """テンプレートを取得"""
    return prompt_compiler.get_template(name)


def list_templates() -> List[str]:
    """テンプレート一覧を取得"""
    return prompt_compiler.list_templates()


def list_patterns() -> List[str]:
    """利用可能なパターン一覧を取得"""
    return prompt_compiler.list_patterns()


def get_pattern_info(pattern: str) -> Dict[str, Any]:
    """パターン情報を取得"""
    return prompt_compiler.get_pattern_info(pattern)

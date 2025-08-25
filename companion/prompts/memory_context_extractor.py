#!/usr/bin/env python3
"""
記憶コンテキスト抽出器 - 3層プロンプト構造に適した記憶データの抽出・管理

PromptCompilerの3層構造（Base/Main/Specialized）に適した記憶データを
AgentStateから抽出し、適切な形式で提供する
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from ..state.agent_state import AgentState
from ..state.enums import Step, Status


class MemoryContextExtractor:
    """3層プロンプト構造に適した記憶データを抽出するクラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 記憶データの分類設定
        self.memory_categories = {
            "base": ["session_info", "work_dir", "current_state"],
            "main": ["recent_file_ops", "conversation_summary", "operation_history"],
            "specialized": ["file_cache", "summary_history", "plan_history"]
        }
    
    def extract_for_pattern(self, pattern: str, agent_state: AgentState, 
                           target_file: Optional[str] = None) -> Dict[str, Any]:
        """パターンに基づいて記憶データを抽出
        
        Args:
            pattern: プロンプトパターン（base_specialized, base_main, base_main_specialized）
            agent_state: エージェント状態
            target_file: 対象ファイル（オプション）
            
        Returns:
            抽出された記憶データの辞書
        """
        try:
            self.logger.debug(f"記憶データ抽出開始: pattern={pattern}, target_file={target_file}")
            
            # 基本記憶データを抽出
            base_memory = self._extract_base_memory(agent_state)
            main_memory = self._extract_main_memory(agent_state)
            specialized_memory = self._extract_specialized_memory(agent_state, target_file)
            
            # パターンに基づいて記憶データを統合
            if pattern == "base_specialized":
                return {
                    "base_memory": base_memory,
                    "specialized_memory": specialized_memory
                }
            elif pattern == "base_main":
                return {
                    "base_memory": base_memory,
                    "main_memory": main_memory
                }
            elif pattern == "base_main_specialized":
                return {
                    "base_memory": base_memory,
                    "main_memory": main_memory,
                    "specialized_memory": specialized_memory
                }
            else:
                # デフォルト: base_main
                self.logger.warning(f"未知のパターン: {pattern}, デフォルト使用")
                return {
                    "base_memory": base_memory,
                    "main_memory": main_memory
                }
                
        except Exception as e:
            self.logger.error(f"記憶データ抽出エラー: {e}")
            return {"error": f"記憶データ抽出エラー: {str(e)}"}
    
    def _extract_base_memory(self, agent_state: AgentState) -> Dict[str, Any]:
        """基本記憶データを抽出（Base層用）"""
        try:
            # セッション情報
            session_info = {
                "session_id": agent_state.session_id,
                "start_time": getattr(agent_state, 'session_start_time', None),
                "duration": self._calculate_session_duration(getattr(agent_state, 'session_start_time', None))
            }
            
            # セッション開始時間が存在しない場合は現在時刻を使用
            if session_info["start_time"]:
                session_info["start_time"] = session_info["start_time"].isoformat()
            else:
                session_info["start_time"] = "不明"
            
            # 作業ディレクトリ情報
            work_dir = agent_state.workspace.get('work_dir', './work') if agent_state.workspace else './work'
            
            # 現在の状態
            current_state = {
                "step": agent_state.step.value if agent_state.step else "UNKNOWN",
                "status": agent_state.status.value if agent_state.status else "UNKNOWN",
                "retry_count": agent_state.retry_count
            }
            
            # バイタル情報
            vitals_info = {
                "mood": agent_state.vitals.mood,
                "focus": agent_state.vitals.focus,
                "stamina": agent_state.vitals.stamina,
                "total_loops": agent_state.vitals.total_loops,
                "error_count": agent_state.vitals.error_count
            }
            
            return {
                "session_info": session_info,
                "work_dir": work_dir,
                "current_state": current_state,
                "vitals": vitals_info
            }
            
        except Exception as e:
            self.logger.error(f"基本記憶データ抽出エラー: {e}")
            return {"error": f"基本記憶データ抽出エラー: {str(e)}"}
    
    def _extract_main_memory(self, agent_state: AgentState) -> Dict[str, Any]:
        """主要記憶データを抽出（Main層用）"""
        try:
            # 最近のファイル操作
            recent_file_ops = self._extract_recent_file_operations(agent_state)
            
            # 会話履歴の要約
            conversation_summary = self._extract_conversation_summary(agent_state)
            
            # 処理履歴
            operation_history = self._extract_operation_history(agent_state)
            
            # ツール実行履歴
            tool_execution_history = self._extract_tool_execution_history(agent_state)
            
            return {
                "recent_file_ops": recent_file_ops,
                "conversation_summary": conversation_summary,
                "operation_history": operation_history,
                "tool_execution_history": tool_execution_history
            }
            
        except Exception as e:
            self.logger.error(f"主要記憶データ抽出エラー: {e}")
            return {"error": f"主要記憶データ抽出エラー: {str(e)}"}
    
    def _extract_specialized_memory(self, agent_state: AgentState, 
                                   target_file: Optional[str] = None) -> Dict[str, Any]:
        """専門記憶データを抽出（Specialized層用）"""
        try:
            # ファイル内容キャッシュ
            file_cache = self._extract_file_cache(agent_state, target_file)
            
            # 要約履歴
            summary_history = self._extract_summary_history(agent_state)
            
            # プラン履歴
            plan_history = self._extract_plan_history(agent_state)
            
            return {
                "file_cache": file_cache,
                "summary_history": summary_history,
                "plan_history": plan_history
            }
            
        except Exception as e:
            self.logger.error(f"専門記憶データ抽出エラー: {e}")
            return {"error": f"専門記憶データ抽出エラー: {str(e)}"}
    
    def _calculate_session_duration(self, start_time: Optional[datetime]) -> str:
        """セッション時間を計算"""
        if not start_time:
            return "不明"
        
        duration = datetime.now() - start_time
        minutes = int(duration.total_seconds() / 60)
        
        if minutes < 60:
            return f"{minutes}分"
        else:
            hours = minutes // 60
            remaining_minutes = minutes % 60
            return f"{hours}時間{remaining_minutes}分"
    
    def _extract_recent_file_operations(self, agent_state: AgentState) -> List[Dict[str, Any]]:
        """最近のファイル操作を抽出"""
        try:
            # 短期記憶からファイル操作履歴を取得
            file_ops = agent_state.short_term_memory.get('file_operations', [])
            
            # 最新5件を返す
            recent_ops = sorted(file_ops, key=lambda x: x.get('timestamp', ''), reverse=True)[:5]
            
            return recent_ops
            
        except Exception as e:
            self.logger.warning(f"ファイル操作履歴抽出エラー: {e}")
            return []
    
    def _extract_conversation_summary(self, agent_state: AgentState) -> Dict[str, Any]:
        """会話履歴の要約を抽出"""
        try:
            conversation_history = agent_state.conversation_history
            
            if not conversation_history:
                return {"total_messages": 0, "recent_topics": [], "summary": "会話履歴なし"}
            
            # 最新の会話内容を分析
            recent_messages = conversation_history[-5:]  # 最新5件
            
            # トピックを抽出（簡単なキーワード抽出）
            topics = self._extract_conversation_topics(recent_messages)
            
            # 要約を生成
            summary = self._generate_conversation_summary(recent_messages)
            
            return {
                "total_messages": len(conversation_history),
                "recent_topics": topics,
                "summary": summary,
                "last_message_time": getattr(recent_messages[-1], 'timestamp', '不明') if recent_messages else '不明'
            }
            
        except Exception as e:
            self.logger.warning(f"会話履歴要約抽出エラー: {e}")
            return {"error": f"会話履歴要約抽出エラー: {str(e)}"}
    
    def _extract_operation_history(self, agent_state: AgentState) -> List[Dict[str, Any]]:
        """処理履歴を抽出"""
        try:
            # 短期記憶から処理履歴を取得
            operations = agent_state.short_term_memory.get('operations', [])
            
            # 最新10件を返す
            recent_ops = sorted(operations, key=lambda x: x.get('timestamp', ''), reverse=True)[:10]
            
            return recent_ops
            
        except Exception as e:
            self.logger.warning(f"処理履歴抽出エラー: {e}")
            return []
    
    def _extract_tool_execution_history(self, agent_state: AgentState) -> List[Dict[str, Any]]:
        """ツール実行履歴を抽出"""
        try:
            # tool_executionsから最新情報を取得
            tool_executions = agent_state.tool_executions
            
            # 最新10件のツール実行情報を変換
            recent_executions = []
            for execution in tool_executions[-10:]:  # 最新10件
                execution_info = {
                    'tool_name': execution.tool_name,
                    'success': execution.error is None,
                    'execution_time': execution.execution_time,
                    'timestamp': execution.timestamp.isoformat()
                }
                
                # エラーがある場合はエラー情報も含める
                if execution.error:
                    execution_info['error'] = execution.error[:100] + "..." if len(execution.error) > 100 else execution.error
                
                recent_executions.append(execution_info)
            
            return recent_executions
            
        except Exception as e:
            self.logger.warning(f"ツール実行履歴抽出エラー: {e}")
            return []
    
    def _extract_file_cache(self, agent_state: AgentState, target_file: Optional[str] = None) -> Dict[str, Any]:
        """ファイル内容キャッシュを抽出"""
        try:
            file_cache = agent_state.short_term_memory.get('file_cache', {})
            
            if target_file and target_file in file_cache:
                # 特定ファイルのキャッシュ
                return {
                    "target_file": target_file,
                    "cached_content": file_cache[target_file],
                    "cache_timestamp": file_cache.get(f"{target_file}_timestamp", "不明")
                }
            else:
                # 全ファイルキャッシュの概要
                return {
                    "cached_files": list(file_cache.keys()),
                    "total_cached_files": len(file_cache),
                    "cache_summary": "ファイル内容キャッシュあり"
                }
                
        except Exception as e:
            self.logger.warning(f"ファイルキャッシュ抽出エラー: {e}")
            return {"error": f"ファイルキャッシュ抽出エラー: {str(e)}"}
    
    def _extract_summary_history(self, agent_state: AgentState) -> List[Dict[str, Any]]:
        """要約履歴を抽出"""
        try:
            # 短期記憶から要約履歴を取得
            summaries = agent_state.short_term_memory.get('summaries', [])
            
            # 最新5件を返す
            recent_summaries = sorted(summaries, key=lambda x: x.get('timestamp', ''), reverse=True)[:5]
            
            return recent_summaries
            
        except Exception as e:
            self.logger.warning(f"要約履歴抽出エラー: {e}")
            return []
    
    def _extract_plan_history(self, agent_state: AgentState) -> List[Dict[str, Any]]:
        """プラン履歴を抽出"""
        try:
            # AgentStateのplansから情報を取得
            plans = agent_state.plans
            
            # 最新5件のプラン情報を変換
            plan_info = []
            for plan in plans[-5:]:  # 最新5件
                plan_info.append({
                    'plan_id': plan.plan_id,
                    'name': plan.name,
                    'goal': plan.goal,
                    'status': plan.status,
                    'steps_count': len(plan.steps),
                    'completed_steps': sum(1 for s in plan.steps if s.status == 'completed')
                })
            
            return plan_info
            
        except Exception as e:
            self.logger.warning(f"プラン履歴抽出エラー: {e}")
            return []
    
    def _extract_conversation_topics(self, messages: List[Any]) -> List[str]:
        """会話からトピックを抽出"""
        try:
            topics = []
            
            for message in messages:
                content = getattr(message, 'content', '')
                if content:
                    # 簡単なキーワード抽出（実際の実装ではより高度な処理が必要）
                    words = content.split()
                    if len(words) > 3:
                        topics.append(f"{words[0]}...{words[-1]}")
            
            return topics[:3]  # 最大3件
            
        except Exception as e:
            self.logger.warning(f"トピック抽出エラー: {e}")
            return []
    
    def _generate_conversation_summary(self, messages: List[Any]) -> str:
        """会話の要約を生成"""
        try:
            if not messages:
                return "会話履歴なし"
            
            # 最新の会話内容を要約
            recent_content = " ".join([getattr(msg, 'content', '') for msg in messages[-3:]])
            
            if len(recent_content) > 100:
                return f"{recent_content[:100]}..."
            else:
                return recent_content
                
        except Exception as e:
            self.logger.warning(f"会話要約生成エラー: {e}")
            return "会話要約生成エラー"
    
    def get_memory_statistics(self, agent_state: AgentState) -> Dict[str, Any]:
        """記憶データの統計情報を取得"""
        try:
            return {
                "total_conversations": len(agent_state.conversation_history),
                "short_term_memory_size": len(agent_state.short_term_memory),
                "session_duration": self._calculate_session_duration(getattr(agent_state, 'session_start_time', None)),
                "current_step": agent_state.step.value if agent_state.step else "UNKNOWN",
                "current_status": agent_state.status.value if agent_state.status else "UNKNOWN"
            }
            
        except Exception as e:
            self.logger.error(f"記憶統計情報取得エラー: {e}")
            return {"error": f"記憶統計情報取得エラー: {str(e)}"}

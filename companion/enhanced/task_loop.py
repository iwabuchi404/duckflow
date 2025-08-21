"""
Enhanced TaskLoop - Enhanced v2.0専用版

v4.0 Final版の機能を移植し、AgentStateを直接参照する設計。
状態管理はAgentStateに統一し、StateMachineへの依存を完全に排除。
"""

import queue
import time
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from companion.state.enums import Step, Status


class TaskType(Enum):
    """タスクタイプの定義（v3a: 型安全性向上）"""
    PROCESS_ENHANCED_INTENT = "process_enhanced_intent"
    UPDATE_AGENT_STATE = "update_agent_state"
    FILE_OPERATION = "file_operation"


class StatusType(Enum):
    """ステータスタイプの定義（v3a: 型安全性向上）"""
    TASK_COMPLETED = "task_completed"
    TASK_ERROR = "task_error"
    STATE_UPDATED = "state_updated"
    ERROR = "error"


class EnhancedTaskLoop:
    """Enhanced v2.0専用TaskLoop - AgentState直接参照版"""
    
    def __init__(self, task_queue: queue.Queue, status_queue: queue.Queue, 
                 enhanced_companion, dual_loop_system):
        self.task_queue = task_queue
        self.status_queue = status_queue
        self.enhanced_companion = enhanced_companion
        self.dual_loop_system = dual_loop_system
        
        # parent_system参照を追加（v3a）
        self.parent_system = dual_loop_system
        
        # AgentStateを直接参照（StateMachine不要）
        self.agent_state = dual_loop_system.agent_state
        
        self.running = False
        self.logger = logging.getLogger(__name__)
        # デバッグ用にログレベルを調整
        self.logger.setLevel(logging.DEBUG)
        
        self.logger.info("EnhancedTaskLoop initialized with AgentState direct reference")

    def run(self):
        """Enhanced v2.0専用の実行ループ開始"""
        self.running = True
        self.logger.info("EnhancedTaskLoop を開始しました")
        
        while self.running:
            try:
                task_data = self.task_queue.get(timeout=1)  # タイムアウト付きで待機
                self._execute_enhanced_task(task_data)
                
            except queue.Empty:
                continue  # タイムアウト時はループを継続
                
            except Exception as e:
                self.logger.error(f"EnhancedTaskLoopで予期せぬエラー: {e}", exc_info=True)
                self._send_enhanced_status({'type': StatusType.ERROR.value, 'message': str(e)})

    def _execute_enhanced_task(self, task_data: Dict[str, Any]):
        """Enhanced v2.0専用のタスク実行"""
        task_type = task_data.get('type')
        self.logger.info(f"Enhancedタスク受信: {task_type}")
        
        try:
            if task_type == TaskType.PROCESS_ENHANCED_INTENT.value:
                self._process_enhanced_intent(task_data)
            elif task_type == TaskType.UPDATE_AGENT_STATE.value:
                self._update_agent_state(task_data)
            elif task_type == TaskType.FILE_OPERATION.value:
                self._execute_file_operation(task_data)
            else:
                self.logger.warning(f"不明なEnhancedタスクタイプをスキップしました: {task_type}")
                
        except Exception as e:
            self.logger.error(f"Enhancedタスク実行中にエラー: {e}", exc_info=True)
            self._send_enhanced_status({'type': StatusType.TASK_ERROR.value, 'message': str(e)})
        
        finally:
            self.task_queue.task_done()

    def _process_enhanced_intent(self, task_data: Dict[str, Any]):
        """Enhanced v2.0専用の意図処理"""
        try:
            intent_result = task_data.get('intent_result')
            user_input = task_data.get('user_input', '')
            
            if not intent_result:
                self.logger.warning("intent_resultが含まれていないEnhancedタスクをスキップしました。")
                return
            
            # AgentStateの状態を更新（PLANNING → EXECUTION）
            self.parent_system.update_state(Step.EXECUTION, Status.IN_PROGRESS, "task_execution_start")
            
            # 非同期メソッドの安全な実行
            try:
                # 新しいイベントループで実行
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(
                        self.enhanced_companion.process_with_intent_result(intent_result)
                    )
                finally:
                    loop.close()
                
                # 成功時の状態更新
                self.parent_system.update_state(Step.REVIEW, Status.SUCCESS, "task_execution_success")
                
                # タスク結果をAgentStateに直接書き込み（v3a）
                self.logger.info(f"タスク結果をAgentStateに設定: {result[:100] if result else 'None'}...")
                self.logger.debug(f"AgentState参照確認: {self.agent_state is not None}")
                self.logger.debug(f"AgentStateの型: {type(self.agent_state)}")
                
                self.agent_state.set_task_result({
                    'type': StatusType.TASK_COMPLETED.value,
                    'message': result,
                    'step': 'EXECUTION',
                    'status': 'SUCCESS',
                    'timestamp': datetime.now().isoformat()
                })
                
                # 設定後の確認
                self.logger.debug(f"設定後のlast_task_result: {self.agent_state.last_task_result is not None}")
                if self.agent_state.last_task_result:
                    self.logger.debug(f"設定された結果の内容: {self.agent_state.last_task_result}")
                
                self.logger.info("タスク結果の設定完了")
                
                # 状態更新の通知のみ送信
                self._send_enhanced_status({
                    'type': StatusType.STATE_UPDATED.value,
                    'message': 'タスク完了: 結果がAgentStateに保存されました',
                    'step': 'EXECUTION',
                    'status': 'SUCCESS'
                })
                
            except Exception as e:
                # エラー時の状態更新
                self.parent_system.update_state(Step.EXECUTION, Status.ERROR, "task_execution_error")
                
                self.logger.error(f"process_with_intent_resultの実行中にエラー: {e}", exc_info=True)
                # タスク結果をAgentStateに直接書き込み（v3a）
                self.agent_state.set_task_result({
                    'type': StatusType.TASK_ERROR.value,
                    'message': str(e),
                    'step': 'EXECUTION',
                    'status': 'ERROR',
                    'timestamp': datetime.now().isoformat()
                })
                
                # 状態更新の通知のみ送信
                self._send_enhanced_status({
                    'type': StatusType.STATE_UPDATED.value,
                    'message': 'タスクエラー: 結果がAgentStateに保存されました',
                    'step': 'EXECUTION',
                    'status': 'ERROR'
                })
                
        except Exception as e:
            self.logger.error(f"Enhanced意図処理中にエラー: {e}", exc_info=True)
            self._send_enhanced_status({'type': StatusType.TASK_ERROR.value, 'message': str(e)})

    def _update_agent_state(self, task_data: Dict[str, Any]):
        """AgentStateの更新タスク（v3a: 単純化）"""
        try:
            step = task_data.get('step')
            status = task_data.get('status')
            
            if step and status:
                self.parent_system.update_state(step, status, "agent_state_update")
                self.logger.info(f"状態更新完了: {step.value if hasattr(step, 'value') else step}.{status.value if hasattr(status, 'value') else status}")
            
        except Exception as e:
            self.logger.error(f"AgentState更新中にエラー: {e}", exc_info=True)
            self._send_enhanced_status({'type': StatusType.TASK_ERROR.value, 'message': str(e)})

    def _execute_file_operation(self, task_data: Dict[str, Any]):
        """ファイル操作タスクの実行"""
        try:
            operation = task_data.get('operation')
            file_path = task_data.get('file_path')
            content = task_data.get('content')
            
            if operation == 'read':
                # ファイル読み込み（依存関係の安全な確認）
                if hasattr(self.enhanced_companion, 'file_ops') and self.enhanced_companion.file_ops:
                    result = self.enhanced_companion.file_ops.read_file(file_path)
                else:
                    self.logger.warning("file_ops が利用できません")
                    result = None
                self._send_enhanced_status({
                    'type': StatusType.STATE_UPDATED.value,
                    'message': f"ファイル読み込み完了: {file_path}",
                    'content_length': len(result) if result else 0
                })
                
            elif operation == 'write':
                # ファイル書き込み（依存関係の安全な確認）
                if hasattr(self.enhanced_companion, 'file_ops') and self.enhanced_companion.file_ops:
                    success = self.enhanced_companion.file_ops.write_file(file_path, content)
                else:
                    self.logger.warning("file_ops が利用できません")
                    success = False
                if success:
                    self._send_enhanced_status({
                        'type': StatusType.STATE_UPDATED.value,
                        'message': f"ファイル書き込み完了: {file_path}"
                    })
                else:
                    self._send_enhanced_status({
                        'type': StatusType.TASK_ERROR.value,
                        'message': f"ファイル書き込み失敗: {file_path}"
                    })
                    
        except Exception as e:
            self.logger.error(f"ファイル操作中にエラー: {e}", exc_info=True)
            self._send_enhanced_status({'type': StatusType.TASK_ERROR.value, 'message': str(e)})



    def _send_enhanced_status(self, status_data: Dict[str, Any]):
        """Enhanced v2.0専用の状態更新通知"""
        try:
            # タイムスタンプを追加
            status_data['timestamp'] = time.time()
            status_data['agent_state_step'] = self.agent_state.step.value if self.agent_state and self.agent_state.step else 'UNKNOWN'
            status_data['agent_state_status'] = self.agent_state.status.value if self.agent_state and self.agent_state.status else 'UNKNOWN'
            
            self.status_queue.put(status_data)
            
        except Exception as e:
            self.logger.error(f"Enhanced状態キューへの通知エラー: {e}")

    def stop(self):
        """Enhanced v2.0専用の停止処理"""
        self.running = False
        self.logger.info("EnhancedTaskLoop を停止しました")

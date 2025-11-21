#!/usr/bin/env python3
"""
タスク管理ツール - LLMが呼び出せるタスク操作
"""

import logging
from datetime import datetime
from typing import Dict, Any, List


class TaskManagementTool:
    """タスク管理ツール - LLMが呼び出せる"""
    
    def __init__(self, agent_state):
        self.agent_state = agent_state
        self.logger = logging.getLogger(__name__)
    
    async def start_task(self, title: str, description: str) -> Dict[str, Any]:
        """新しいタスクを開始"""
        try:
            task_id = f"task_{datetime.now().strftime('%H%M%S')}"
            task_data = {
                "task_id": task_id,
                "title": title,
                "description": description,
                "status": "active",
                "created_at": datetime.now().isoformat(),
                "results": []
            }
            
            # AgentStateに保存
            if not hasattr(self.agent_state, 'tasks'):
                self.agent_state.tasks = []
            self.agent_state.tasks.append(task_data)
            
            self.logger.info(f"タスク開始: {title} (ID: {task_id})")
            return {"success": True, "task_id": task_id, "message": f"タスク開始: {title}"}
        except Exception as e:
            self.logger.error(f"タスク開始エラー: {e}")
            return {"success": False, "error": str(e)}
    
    async def complete_task(self, task_id: str, summary: str) -> Dict[str, Any]:
        """タスクを完了"""
        try:
            if not hasattr(self.agent_state, 'tasks'):
                return {"success": False, "error": "タスクが存在しません"}
            
            for task in self.agent_state.tasks:
                if task["task_id"] == task_id:
                    task["status"] = "completed"
                    task["completed_at"] = datetime.now().isoformat()
                    task["summary"] = summary
                    self.logger.info(f"タスク完了: {task['title']} (ID: {task_id})")
                    return {"success": True, "message": f"タスク完了: {task['title']}"}
            
            return {"success": False, "error": "タスクIDが見つかりません"}
        except Exception as e:
            self.logger.error(f"タスク完了エラー: {e}")
            return {"success": False, "error": str(e)}
    
    async def add_task_result(self, task_id: str, result: str) -> Dict[str, Any]:
        """タスクに結果を追加"""
        try:
            if not hasattr(self.agent_state, 'tasks'):
                return {"success": False, "error": "タスクが存在しません"}
            
            for task in self.agent_state.tasks:
                if task["task_id"] == task_id:
                    task["results"].append({
                        "content": result,
                        "timestamp": datetime.now().isoformat()
                    })
                    self.logger.info(f"タスク結果追加: {task['title']} (ID: {task_id})")
                    return {"success": True, "message": "結果を追加しました"}
            
            return {"success": False, "error": "タスクIDが見つかりません"}
        except Exception as e:
            self.logger.error(f"タスク結果追加エラー: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """タスクの状態を取得"""
        try:
            if not hasattr(self.agent_state, 'tasks'):
                return {"success": False, "error": "タスクが存在しません"}
            
            for task in self.agent_state.tasks:
                if task["task_id"] == task_id:
                    return {"success": True, "task": task}
            
            return {"success": False, "error": "タスクIDが見つかりません"}
        except Exception as e:
            self.logger.error(f"タスク状態取得エラー: {e}")
            return {"success": False, "error": str(e)}
    
    async def list_tasks(self) -> Dict[str, Any]:
        """全タスクの一覧を取得"""
        try:
            if not hasattr(self.agent_state, 'tasks'):
                return {"success": True, "tasks": []}
            
            return {"success": True, "tasks": self.agent_state.tasks.copy()}
        except Exception as e:
            self.logger.error(f"タスク一覧取得エラー: {e}")
            return {"success": False, "error": str(e)}

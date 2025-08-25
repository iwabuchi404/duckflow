#!/usr/bin/env python3
"""
ToolRegistry - LLMが呼び出せるToolの登録管理

ActionPlanToolとUserResponseToolを登録し、LLMが直接呼び出せるようにする
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ToolDefinition:
    """Toolの定義"""
    name: str
    description: str
    parameters: Dict[str, Any]
    required_params: List[str]
    tool_class: str
    method_name: str


class ToolRegistry:
    """LLMが呼び出せるToolの登録管理"""
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self.logger = logging.getLogger(__name__)
        self._register_default_tools()
    
    def _register_default_tools(self):
        """デフォルトのToolを登録"""
        # ActionPlanToolの登録
        self.register_tool("action_plan_tool", {
            "name": "decompose_task",
            "description": "ユーザー要求を分析し、実行可能なサブタスクに分解する",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_input": {
                        "type": "string",
                        "description": "ユーザーの要求"
                    },
                    "task_profile": {
                        "type": "string",
                        "description": "タスクプロファイルタイプ（general, file_analysis, code_generation等）",
                        "enum": ["general", "file_analysis", "code_generation", "planning", "execution"]
                    },
                    "complexity": {
                        "type": "string",
                        "description": "タスクの複雑度",
                        "enum": ["low", "medium", "high"]
                    }
                },
                "required": ["user_input"]
            },
            "tool_class": "ActionPlanTool",
            "method_name": "decompose_task"
        })
        
        # UserResponseToolの登録
        self.register_tool("user_response_tool", {
            "name": "generate_response",
            "description": "アクション実行結果からユーザーへの応答を生成する",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_results": {
                        "type": "array",
                        "description": "実行されたアクションの結果リスト",
                        "items": {
                            "type": "object",
                            "properties": {
                                "operation": {"type": "string"},
                                "success": {"type": "boolean"},
                                "data": {"type": "string"},
                                "error_message": {"type": "string"}
                            }
                        }
                    },
                    "user_input": {
                        "type": "string",
                        "description": "ユーザーの元の要求"
                    },
                    "agent_state": {
                        "type": "object",
                        "description": "エージェントの現在の状態（オプション）"
                    }
                },
                "required": ["action_results", "user_input"]
            },
            "tool_class": "UserResponseTool",
            "method_name": "generate_response"
        })
        
        self.logger.info("デフォルトTool登録完了: action_plan_tool, user_response_tool")
    
    def register_tool(self, tool_id: str, tool_info: Dict[str, Any]) -> bool:
        """Toolを登録"""
        try:
            # 必須フィールドの検証
            required_fields = ["name", "description", "parameters", "tool_class", "method_name"]
            for field in required_fields:
                if field not in tool_info:
                    self.logger.error(f"Tool登録エラー: 必須フィールド '{field}' が不足")
                    return False
            
            # パラメータの検証
            if "required" not in tool_info["parameters"]:
                self.logger.error(f"Tool登録エラー: パラメータ定義に 'required' が不足")
                return False
            
            # ToolDefinitionを作成
            tool_def = ToolDefinition(
                name=tool_info["name"],
                description=tool_info["description"],
                parameters=tool_info["parameters"],
                required_params=tool_info["parameters"]["required"],
                tool_class=tool_info["tool_class"],
                method_name=tool_info["method_name"]
            )
            
            self.tools[tool_id] = tool_def
            self.logger.info(f"Tool登録完了: {tool_id} ({tool_info['name']})")
            return True
            
        except Exception as e:
            self.logger.error(f"Tool登録エラー: {e}")
            return False
    
    def get_tool(self, tool_id: str) -> Optional[ToolDefinition]:
        """Toolの定義を取得"""
        return self.tools.get(tool_id)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """登録されているToolの一覧を取得"""
        tool_list = []
        for tool_id, tool_def in self.tools.items():
            tool_list.append({
                "id": tool_id,
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": tool_def.parameters,
                "tool_class": tool_def.tool_class,
                "method_name": tool_def.method_name
            })
        return tool_list
    
    def get_tool_schema(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Toolのスキーマを取得（LLM用）"""
        tool_def = self.get_tool(tool_id)
        if not tool_def:
            return None
        
        return {
            "type": "function",
            "function": {
                "name": f"{tool_id}.{tool_def.method_name}",
                "description": tool_def.description,
                "parameters": tool_def.parameters
            }
        }
    
    def get_all_tool_schemas(self) -> List[Dict[str, Any]]:
        """すべてのToolのスキーマを取得（LLM用）"""
        schemas = []
        for tool_id in self.tools.keys():
            schema = self.get_tool_schema(tool_id)
            if schema:
                schemas.append(schema)
        return schemas
    
    def validate_tool_call(self, tool_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Tool呼び出しのパラメータを検証"""
        tool_def = self.get_tool(tool_id)
        if not tool_def:
            return {
                "valid": False,
                "error": f"Tool '{tool_id}' が見つかりません"
            }
        
        # 必須パラメータの検証
        missing_params = []
        for param in tool_def.required_params:
            if param not in parameters:
                missing_params.append(param)
        
        if missing_params:
            return {
                "valid": False,
                "error": f"必須パラメータが不足: {missing_params}"
            }
        
        # パラメータ型の検証（基本的な検証）
        for param_name, param_value in parameters.items():
            param_schema = tool_def.parameters["properties"].get(param_name, {})
            expected_type = param_schema.get("type")
            
            if expected_type == "string" and not isinstance(param_value, str):
                return {
                    "valid": False,
                    "error": f"パラメータ '{param_name}' は文字列である必要があります"
                }
            elif expected_type == "boolean" and not isinstance(param_value, bool):
                return {
                    "valid": False,
                    "error": f"パラメータ '{param_name}' は真偽値である必要があります"
                }
            elif expected_type == "array" and not isinstance(param_value, list):
                return {
                    "valid": False,
                    "error": f"パラメータ '{param_name}' は配列である必要があります"
                }
        
        return {
            "valid": True,
            "tool_def": tool_def
        }
    
    def remove_tool(self, tool_id: str) -> bool:
        """Toolを削除"""
        if tool_id in self.tools:
            del self.tools[tool_id]
            self.logger.info(f"Tool削除完了: {tool_id}")
            return True
        else:
            self.logger.warning(f"Tool削除失敗: {tool_id} は存在しません")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Tool登録状況の統計を取得"""
        return {
            "total_tools": len(self.tools),
            "tool_ids": list(self.tools.keys()),
            "tool_classes": list(set(tool_def.tool_class for tool_def in self.tools.values()))
        }

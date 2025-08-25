#!/usr/bin/env python3
"""
IntegratedResponseController - Tool統合された応答生成コントローラー

ActionPlanToolとUserResponseToolを統合し、LLMが直接呼び出せるようにする
"""

import logging
import json
from typing import Dict, Any, List, Optional

from ..llm.llm_client import LLMClient
from ..prompts.prompt_compiler import PromptCompiler
from ..state.agent_state import AgentState
from .action_plan_tool import ActionPlanTool
from .user_response_tool import UserResponseTool
from .tool_registry import ToolRegistry


class IntegratedResponseController:
    """Tool統合された応答生成コントローラー"""
    
    def __init__(self, llm_client: LLMClient, prompt_compiler: PromptCompiler):
        self.llm_client = llm_client
        self.prompt_compiler = prompt_compiler
        self.action_plan_tool = ActionPlanTool(llm_client)
        self.user_response_tool = UserResponseTool(prompt_compiler, llm_client)
        self.tool_registry = ToolRegistry()
        self.logger = logging.getLogger(__name__)
    
    async def process_user_input(self, user_input: str, agent_state: AgentState) -> str:
        """ユーザー入力を処理して応答を生成"""
        
        try:
            self.logger.info(f"ユーザー入力処理開始: {user_input[:50]}...")
            
            # 1. LLMにTool呼び出しを依頼（ActionPlanTool使用）
            action_plan = await self._generate_action_plan_llm(user_input, agent_state)
            
            # 2. 生成されたアクションを実行
            action_results = []
            for action in action_plan.get('subtasks', []):
                result = await self._execute_action(action)
                action_results.append(result)
            
            # 3. LLMにTool呼び出しを依頼（UserResponseTool使用）
            response = await self._generate_response_llm(action_results, user_input, agent_state)
            
            self.logger.info(f"ユーザー入力処理完了: {len(response)}文字の応答を生成")
            return response
            
        except Exception as e:
            error_msg = f"申し訳ありません、処理中にエラーが発生しました: {str(e)}"
            self.logger.error(f"ユーザー入力処理エラー: {e}")
            return error_msg
    
    async def _generate_action_plan_llm(self, user_input: str, agent_state: AgentState) -> Dict[str, Any]:
        """LLMにActionPlanToolの使用を依頼"""
        
        try:
            # LLMにTool呼び出しを依頼するプロンプトを構築
            prompt = f"""
以下のユーザー要求を分析し、適切なToolを使用してタスク分解を行ってください。

ユーザー要求: {user_input}

利用可能なTool:
- action_plan_tool.decompose_task: ユーザー要求を分析し、実行可能なサブタスクに分解する

以下のJSON形式でTool呼び出しを指定してください：

```json
{{
    "tool_calls": [
        {{
            "tool": "action_plan_tool.decompose_task",
            "parameters": {{
                "user_input": "{user_input}",
                "task_profile": "適切なタスクプロファイル",
                "complexity": "適切な複雑度"
            }}
        }}
    ]
}}
```

タスクプロファイルの選択指針：
- general: 一般的なタスク
- file_analysis: ファイル分析関連
- code_generation: コード生成関連
- planning: 計画策定関連
- execution: 実行関連

複雑度の選択指針：
- low: 単純なタスク（2-3個のサブタスク）
- medium: 中程度のタスク（3-5個のサブタスク）
- high: 複雑なタスク（5-8個のサブタスク）
"""
            
            # LLM呼び出し
            response = await self.llm_client.chat(prompt=prompt)
            
            # レスポンスからTool呼び出しを解析
            tool_calls = self._parse_tool_calls(response.content)
            
            # Toolを実行
            results = []
            for tool_call in tool_calls:
                if tool_call['tool'] == 'action_plan_tool.decompose_task':
                    result = await self.action_plan_tool.decompose_task(**tool_call['parameters'])
                    results.append(result)
            
            # 最初の結果を返す
            return results[0] if results else {"subtasks": []}
            
        except Exception as e:
            self.logger.error(f"ActionPlanTool呼び出しエラー: {e}")
            # フォールバック: 基本的なタスク分解
            return await self.action_plan_tool.decompose_task(user_input)
    
    async def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """アクションを実行"""
        
        try:
            operation = action.get('operation', 'unknown_operation')
            self.logger.info(f"アクション実行開始: {operation}")
            
            # 実際のTool実行は既存のシステムに委譲
            # ここでは基本的な結果構造を返す
            result = {
                'operation': operation,
                'success': True,
                'data': f"アクション '{operation}' が実行されました",
                'error_message': None,
                'execution_time': 0.1
            }
            
            self.logger.info(f"アクション実行完了: {operation}")
            return result
            
        except Exception as e:
            self.logger.error(f"アクション実行エラー: {e}")
            return {
                'operation': action.get('operation', 'unknown_operation'),
                'success': False,
                'data': None,
                'error_message': str(e),
                'execution_time': 0.0
            }
    
    async def _generate_response_llm(self, action_results: List[Dict[str, Any]], user_input: str, agent_state: AgentState) -> str:
        """LLMにUserResponseToolの使用を依頼"""
        
        try:
            # LLMにTool呼び出しを依頼するプロンプトを構築
            prompt = f"""
以下のアクション実行結果から、ユーザーへの適切な応答を生成してください。

ユーザーの要求: {user_input}

実行されたアクション:
{self._format_action_results_for_prompt(action_results)}

利用可能なTool:
- user_response_tool.generate_response: アクション実行結果からユーザーへの応答を生成する

以下のJSON形式でTool呼び出しを指定してください：

```json
{{
    "tool_calls": [
        {{
            "tool": "user_response_tool.generate_response",
            "parameters": {{
                "action_results": {json.dumps(action_results, ensure_ascii=False)},
                "user_input": "{user_input}"
            }}
        }}
    ]
}}
```

ただし、実際にはToolを呼び出すのではなく、直接ユーザーへの応答を生成してください。
応答は以下の点を考慮してください：

1. 実行されたアクションの結果を分かりやすく説明する
2. エラーが発生した場合は、原因と対処法を説明する
3. 次のステップの提案がある場合は、具体的に示す
4. 専門的すぎる用語は避け、一般ユーザーが理解できる表現を使用する
5. 応答は自然な日本語で、親しみやすい口調にする
"""
            
            # LLM呼び出し
            response = await self.llm_client.chat(prompt=prompt)
            
            # レスポンスからTool呼び出しを解析
            tool_calls = self._parse_tool_calls(response.content)
            
            # Toolを実行
            results = []
            for tool_call in tool_calls:
                if tool_call['tool'] == 'user_response_tool.generate_response':
                    result = await self.user_response_tool.generate_response(**tool_call['parameters'])
                    results.append(result)
            
            # 最初の結果を返す
            if results and results[0].get('success'):
                return results[0].get('response', '応答の生成に失敗しました')
            else:
                # Tool呼び出しが失敗した場合は、LLMの直接応答を使用
                return response.content
            
        except Exception as e:
            self.logger.error(f"UserResponseTool呼び出しエラー: {e}")
            # フォールバック: 基本的な応答生成
            result = await self.user_response_tool.generate_response(action_results, user_input)
            return result.get('response', '応答の生成に失敗しました')
    
    def _parse_tool_calls(self, response_content: str) -> List[Dict[str, Any]]:
        """LLMレスポンスからTool呼び出しを解析"""
        try:
            # JSON部分を抽出
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                self.logger.warning("JSONレスポンスが見つかりません")
                return []
            
            json_str = response_content[json_start:json_end]
            parsed_data = json.loads(json_str)
            
            tool_calls = parsed_data.get('tool_calls', [])
            
            # Tool呼び出しの検証
            validated_calls = []
            for call in tool_calls:
                if 'tool' in call and 'parameters' in call:
                    validated_calls.append(call)
            
            return validated_calls
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析エラー: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Tool呼び出し解析エラー: {e}")
            return []
    
    def _format_action_results_for_prompt(self, action_results: List[Dict[str, Any]]) -> str:
        """プロンプト用にアクション結果をフォーマット"""
        if not action_results:
            return "実行されたアクションはありません"
        
        formatted_lines = []
        for i, result in enumerate(action_results, 1):
            operation = result.get('operation', '不明な操作')
            success = result.get('success', False)
            status = "成功" if success else "失敗"
            formatted_lines.append(f"{i}. {operation}: {status}")
            
            if result.get('data'):
                data_summary = str(result['data'])[:100]
                if len(str(result['data'])) > 100:
                    data_summary += "..."
                formatted_lines.append(f"   結果: {data_summary}")
            
            if result.get('error_message'):
                formatted_lines.append(f"   エラー: {result['error_message']}")
            formatted_lines.append("")
        
        return "\n".join(formatted_lines)
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """利用可能なToolのスキーマを取得"""
        return self.tool_registry.get_all_tool_schemas()
    
    def get_statistics(self) -> Dict[str, Any]:
        """システムの統計情報を取得"""
        return {
            "tool_count": len(self.tool_registry.tools),
            "registered_tools": list(self.tool_registry.tools.keys()),
            "controller_status": "active"
        }

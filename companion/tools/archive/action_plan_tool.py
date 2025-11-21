#!/usr/bin/env python3
"""
ActionPlanTool - LLMが直接呼び出せるタスク分解・サブタスク生成Tool

既存のPecking Orderシステムと連携し、LLMベースのタスク分解を実現
"""

import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..llm.llm_client import LLMClient


@dataclass
class TaskDecompositionResult:
    """タスク分解結果"""
    success: bool
    main_task: str
    subtasks: List[Dict[str, Any]]
    total_count: int
    decomposition_method: str
    error: Optional[str] = None
    fallback_subtasks: Optional[List[Dict[str, Any]]] = None


class ActionPlanTool:
    """LLMが直接呼び出せるタスク分解・サブタスク生成Tool"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
    
    async def decompose_task(self, user_input: str, task_profile: str = "general", complexity: str = "medium") -> Dict[str, Any]:
        """
        ユーザー要求を分析し、実行可能なサブタスクに分解する
        
        Args:
            user_input: ユーザーの要求
            task_profile: タスクプロファイルタイプ
            complexity: タスクの複雑度
            
        Returns:
            タスク分解結果の辞書
        """
        try:
            self.logger.info(f"タスク分解開始: {user_input[:50]}...")
            
            # LLMプロンプトの構築
            prompt = self._build_decomposition_prompt(user_input, task_profile, complexity)
            
            # LLM呼び出し
            response = await self.llm_client.chat(
                prompt=prompt,
                tools=False,  # ツール使用を無効化
                tool_choice="none"  # ツール選択を無効化
            )
            
            # レスポンスからサブタスクを解析
            subtasks = self._parse_decomposition_response(response.content)
            
            result = TaskDecompositionResult(
                success=True,
                main_task=user_input,
                subtasks=subtasks,
                total_count=len(subtasks),
                decomposition_method="llm_based"
            )
            
            self.logger.info(f"タスク分解完了: {len(subtasks)}個のサブタスクを生成")
            return result.__dict__
            
        except Exception as e:
            self.logger.error(f"タスク分解エラー: {e}")
            fallback_subtasks = self._generate_fallback_subtasks(user_input)
            
            result = TaskDecompositionResult(
                success=False,
                main_task=user_input,
                subtasks=fallback_subtasks,
                total_count=len(fallback_subtasks),
                decomposition_method="fallback",
                error=str(e),
                fallback_subtasks=fallback_subtasks
            )
            
            return result.__dict__
    
    def _build_decomposition_prompt(self, user_input: str, task_profile: str, complexity: str) -> str:
        """タスク分解用のLLMプロンプトを構築"""
        
        prompt = f"""
あなたはDuckflowのタスク分析エキスパートです。
以下のユーザー要求を分析し、実行可能なサブタスクに分解してください。

ユーザー要求: {user_input}
タスクプロファイル: {task_profile}
複雑度: {complexity}

以下のルールに従ってサブタスクを生成してください：

1. 各サブタスクは具体的で実行可能であること
2. サブタスクの順序は論理的であること
3. 依存関係を考慮すること
4. 各サブタスクの説明は簡潔で分かりやすいこと

以下のJSON形式で回答してください：

```json
{{
    "subtasks": [
        {{
            "id": "task_1",
            "title": "サブタスクのタイトル",
            "description": "サブタスクの詳細説明",
            "operation": "実行する操作名",
            "dependencies": ["依存するタスクID"],
            "estimated_time": "推定実行時間",
            "priority": "優先度（high/medium/low）"
        }}
    ]
}}
```

サブタスクの数は複雑度に応じて調整してください：
- 低複雑度: 2-3個
- 中複雑度: 3-5個  
- 高複雑度: 5-8個
"""
        
        return prompt
    
    def _parse_decomposition_response(self, response_content: str) -> List[Dict[str, Any]]:
        """LLMレスポンスからサブタスクを解析"""
        try:
            # JSON部分を抽出
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                self.logger.warning("JSONレスポンスが見つかりません")
                return self._generate_fallback_subtasks("JSON解析失敗")
            
            json_str = response_content[json_start:json_end]
            parsed_data = json.loads(json_str)
            
            subtasks = parsed_data.get('subtasks', [])
            
            # サブタスクの検証
            validated_subtasks = []
            for i, subtask in enumerate(subtasks):
                validated_subtask = {
                    'id': subtask.get('id', f'task_{i+1}'),
                    'title': subtask.get('title', f'サブタスク {i+1}'),
                    'description': subtask.get('description', '説明なし'),
                    'operation': subtask.get('operation', 'unknown_operation'),
                    'dependencies': subtask.get('dependencies', []),
                    'estimated_time': subtask.get('estimated_time', '不明'),
                    'priority': subtask.get('priority', 'medium')
                }
                validated_subtasks.append(validated_subtask)
            
            return validated_subtasks
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析エラー: {e}")
            return self._generate_fallback_subtasks("JSON解析失敗")
        except Exception as e:
            self.logger.error(f"サブタスク解析エラー: {e}")
            return self._generate_fallback_subtasks("解析失敗")
    
    def _generate_fallback_subtasks(self, user_input: str) -> List[Dict[str, Any]]:
        """フォールバック用のサブタスクを生成"""
        self.logger.info("フォールバックサブタスクを生成")
        
        # 基本的なサブタスク構造
        fallback_subtasks = [
            {
                'id': 'task_1',
                'title': '要求の分析',
                'description': f'ユーザー要求「{user_input}」を分析する',
                'operation': 'analyze_request',
                'dependencies': [],
                'estimated_time': '1分',
                'priority': 'high'
            },
            {
                'id': 'task_2',
                'title': '実行計画の策定',
                'description': '分析結果に基づいて実行計画を策定する',
                'operation': 'create_execution_plan',
                'dependencies': ['task_1'],
                'estimated_time': '2分',
                'priority': 'medium'
            },
            {
                'id': 'task_3',
                'title': '計画の実行',
                'description': '策定された計画を実行する',
                'operation': 'execute_plan',
                'dependencies': ['task_2'],
                'estimated_time': '5分',
                'priority': 'medium'
            }
        ]
        
        return fallback_subtasks

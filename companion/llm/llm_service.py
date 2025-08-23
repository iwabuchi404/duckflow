"""
Companion LLM Service

LLMベースの高度なサービス機能
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .llm_client import LLMClient, LLMResponse, LLMProvider


@dataclass
class ContentPlan:
    """コンテンツ作成計画"""
    title: str
    outline: List[str]
    key_points: List[str]
    estimated_length: str
    target_audience: str
    tone: str
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TaskExecutionPlan:
    """タスク実行計画"""
    main_goal: str
    steps: List[str]
    prerequisites: List[str]
    estimated_duration: str
    required_resources: List[str]
    success_criteria: List[str]
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SatisfactionEvaluation:
    """満足度評価"""
    overall_score: float
    criteria_scores: Dict[str, float]
    improvement_suggestions: List[str]
    user_feedback: str
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class RequirementItem:
    """要件項目"""
    category: str
    description: str
    priority: str
    status: str
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class MissingInfoAnalysis:
    """不足情報分析"""
    missing_items: List[str]
    impact_level: str
    suggested_sources: List[str]
    priority: str
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TaskContext:
    """タスクコンテキスト"""
    project_info: str
    user_preferences: Dict[str, Any]
    technical_constraints: List[str]
    available_resources: List[str]
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class LLMService:
    """LLMベースの高度なサービス"""
    
    def __init__(self, llm_client: LLMClient):
        """LLMサービスを初期化"""
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
        
        # サービス設定
        self.config = self._load_service_config()
    
    def _load_service_config(self) -> Dict[str, Any]:
        """サービス設定の読み込み"""
        return {
            "max_retry_attempts": 3,
            "default_temperature": 0.1,
            "default_max_tokens": 1000,
            "enable_fallback": True,
            "log_requests": True
        }
    
    async def generate_content_plan(
        self, 
        topic: str, 
        requirements: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> ContentPlan:
        """
        コンテンツ作成計画の生成
        
        Args:
            topic: トピック
            requirements: 要件リスト
            context: 追加コンテキスト
            
        Returns:
            コンテンツ作成計画
        """
        try:
            prompt = f"""
トピック: {topic}

要件:
{chr(10).join(f"- {req}" for req in requirements)}

上記のトピックと要件に基づいて、コンテンツ作成計画を立ててください。
以下のJSON形式で回答してください：

```json
{{
    "title": "タイトル",
    "outline": ["アウトライン1", "アウトライン2"],
    "key_points": ["重要ポイント1", "重要ポイント2"],
    "estimated_length": "推定長さ",
    "target_audience": "ターゲット読者",
    "tone": "トーン・文体"
}}
```
"""
            
            response = await self.llm_client.chat(
                prompt=prompt,
                max_tokens=800,
                temperature=0.2
            )
            
            return self._parse_content_plan(response, topic)
            
        except Exception as e:
            self.logger.error(f"コンテンツ計画生成エラー: {e}")
            return self._create_fallback_content_plan(topic, requirements)
    
    def _parse_content_plan(self, response: LLMResponse, topic: str) -> ContentPlan:
        """LLM応答からコンテンツ計画をパース"""
        try:
            import json
            
            # JSON部分を抽出
            content = response.content
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("JSON形式の応答が見つかりません")
            
            json_str = content[json_start:json_end]
            parsed_data = json.loads(json_str)
            
            return ContentPlan(
                title=parsed_data.get("title", f"{topic}の計画"),
                outline=parsed_data.get("outline", ["基本的なアウトライン"]),
                key_points=parsed_data.get("key_points", ["重要なポイント"]),
                estimated_length=parsed_data.get("estimated_length", "中程度"),
                target_audience=parsed_data.get("target_audience", "一般"),
                tone=parsed_data.get("tone", "専門的"),
                metadata={
                    "llm_provider": response.provider.value,
                    "llm_model": response.model
                }
            )
            
        except Exception as e:
            self.logger.error(f"コンテンツ計画パースエラー: {e}")
            return self._create_fallback_content_plan(topic, [])
    
    def _create_fallback_content_plan(self, topic: str, requirements: List[str]) -> ContentPlan:
        """フォールバック用のコンテンツ計画"""
        return ContentPlan(
            title=f"{topic}の基本計画",
            outline=["概要", "詳細", "まとめ"],
            key_points=["主要なポイント"],
            estimated_length="中程度",
            target_audience="一般",
            tone="標準的",
            metadata={"fallback": True}
        )
    
    async def plan_task_execution(
        self, 
        task_description: str,
        constraints: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> TaskExecutionPlan:
        """
        タスク実行計画の生成
        
        Args:
            task_description: タスクの説明
            constraints: 制約条件
            context: 追加コンテキスト
            
        Returns:
            タスク実行計画
        """
        try:
            prompt = f"""
タスク: {task_description}

制約条件:
{chr(10).join(f"- {constraint}" for constraint in constraints)}

上記のタスクと制約条件に基づいて、実行計画を立ててください。
以下のJSON形式で回答してください：

```json
{{
    "main_goal": "主要目標",
    "steps": ["ステップ1", "ステップ2"],
    "prerequisites": ["前提条件1", "前提条件2"],
    "estimated_duration": "推定所要時間",
    "required_resources": ["必要なリソース1", "必要なリソース2"],
    "success_criteria": ["成功基準1", "成功基準2"]
}}
```
"""
            
            response = await self.llm_client.chat(
                prompt=prompt,
                max_tokens=800,
                temperature=0.1
            )
            
            return self._parse_task_execution_plan(response, task_description)
            
        except Exception as e:
            self.logger.error(f"タスク実行計画生成エラー: {e}")
            return self._create_fallback_task_plan(task_description, constraints)
    
    def _parse_task_execution_plan(self, response: LLMResponse, task_description: str) -> TaskExecutionPlan:
        """LLM応答からタスク実行計画をパース"""
        try:
            import json
            
            # JSON部分を抽出
            content = response.content
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("JSON形式の応答が見つかりません")
            
            json_str = content[json_start:json_end]
            parsed_data = json.loads(json_str)
            
            return TaskExecutionPlan(
                main_goal=parsed_data.get("main_goal", f"{task_description}の完了"),
                steps=parsed_data.get("steps", ["基本的なステップ"]),
                prerequisites=parsed_data.get("prerequisites", ["基本的な前提条件"]),
                estimated_duration=parsed_data.get("estimated_duration", "中程度"),
                required_resources=parsed_data.get("required_resources", ["基本的なリソース"]),
                success_criteria=parsed_data.get("success_criteria", ["基本的な成功基準"]),
                metadata={
                    "llm_provider": response.provider.value,
                    "llm_model": response.model
                }
            )
            
        except Exception as e:
            self.logger.error(f"タスク実行計画パースエラー: {e}")
            return self._create_fallback_task_plan(task_description, [])
    
    def _create_fallback_task_plan(self, task_description: str, constraints: List[str]) -> TaskExecutionPlan:
        """フォールバック用のタスク実行計画"""
        return TaskExecutionPlan(
            main_goal=f"{task_description}の完了",
            steps=["計画", "実行", "確認"],
            prerequisites=["基本的な準備"],
            estimated_duration="中程度",
            required_resources=["基本的なリソース"],
            success_criteria=["タスク完了"],
            metadata={"fallback": True}
        )
    
    async def evaluate_task_satisfaction(
        self, 
        task_result: str,
        original_requirements: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> SatisfactionEvaluation:
        """
        タスク満足度の評価
        
        Args:
            task_result: タスク結果
            original_requirements: 元の要件
            context: 追加コンテキスト
            
        Returns:
            満足度評価
        """
        try:
            prompt = f"""
タスク結果: {task_result}

元の要件:
{chr(10).join(f"- {req}" for req in original_requirements)}

上記のタスク結果が元の要件をどの程度満たしているか評価してください。
以下のJSON形式で回答してください：

```json
{{
    "overall_score": 0.85,
    "criteria_scores": {{
        "要件1": 0.9,
        "要件2": 0.8
    }},
    "improvement_suggestions": ["改善提案1", "改善提案2"],
    "user_feedback": "全体的な評価コメント"
}}
```
"""
            
            response = await self.llm_client.chat(
                prompt=prompt,
                max_tokens=600,
                temperature=0.1
            )
            
            return self._parse_satisfaction_evaluation(response)
            
        except Exception as e:
            self.logger.error(f"満足度評価エラー: {e}")
            return self._create_fallback_satisfaction_evaluation()
    
    def _parse_satisfaction_evaluation(self, response: LLMResponse) -> SatisfactionEvaluation:
        """LLM応答から満足度評価をパース"""
        try:
            import json
            
            # JSON部分を抽出
            content = response.content
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("JSON形式の応答が見つかりません")
            
            json_str = content[json_start:json_end]
            parsed_data = json.loads(json_str)
            
            return SatisfactionEvaluation(
                overall_score=float(parsed_data.get("overall_score", 0.7)),
                criteria_scores=parsed_data.get("criteria_scores", {"基本要件": 0.7}),
                improvement_suggestions=parsed_data.get("improvement_suggestions", ["基本的な改善"]),
                user_feedback=parsed_data.get("user_feedback", "基本的な評価"),
                metadata={
                    "llm_provider": response.provider.value,
                    "llm_model": response.model
                }
            )
            
        except Exception as e:
            self.logger.error(f"満足度評価パースエラー: {e}")
            return self._create_fallback_satisfaction_evaluation()
    
    def _create_fallback_satisfaction_evaluation(self) -> SatisfactionEvaluation:
        """フォールバック用の満足度評価"""
        return SatisfactionEvaluation(
            overall_score=0.7,
            criteria_scores={"基本要件": 0.7},
            improvement_suggestions=["基本的な改善"],
            user_feedback="基本的な評価",
            metadata={"fallback": True}
        )
    
    async def prioritize_files_for_task(
        self, 
        task_description: str,
        available_files: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        タスク用ファイルの優先順位付け
        
        Args:
            task_description: タスクの説明
            available_files: 利用可能なファイル
            context: 追加コンテキスト
            
        Returns:
            優先順位付けされたファイルリスト
        """
        try:
            prompt = f"""
タスク: {task_description}

利用可能なファイル:
{chr(10).join(f"- {file}" for file in available_files)}

上記のタスクを実行するために、ファイルを優先順位順に並べてください。
最も関連性の高いファイルから順番に、ファイル名のみをリストで回答してください。
"""
            
            response = await self.llm_client.chat(
                prompt=prompt,
                max_tokens=400,
                temperature=0.1
            )
            
            return self._parse_file_prioritization(response, available_files)
            
        except Exception as e:
            self.logger.error(f"ファイル優先順位付けエラー: {e}")
            return available_files  # フォールバック: 元の順序
    
    def _parse_file_prioritization(self, response: LLMResponse, available_files: List[str]) -> List[str]:
        """LLM応答からファイル優先順位をパース"""
        try:
            content = response.content.strip()
            
            # ファイル名を抽出
            prioritized_files = []
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('-') or line.startswith('*'):
                    line = line[1:].strip()
                
                # 利用可能なファイルリストに含まれているかチェック
                for available_file in available_files:
                    if available_file in line or line in available_file:
                        if available_file not in prioritized_files:
                            prioritized_files.append(available_file)
            
            # 見つからなかったファイルを末尾に追加
            for file in available_files:
                if file not in prioritized_files:
                    prioritized_files.append(file)
            
            return prioritized_files
            
        except Exception as e:
            self.logger.error(f"ファイル優先順位パースエラー: {e}")
            return available_files
    
    async def synthesize_insights_from_files(
        self, 
        task_description: str,
        file_contents: Dict[str, str],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        ファイル内容からの洞察合成
        
        Args:
            task_description: タスクの説明
            file_contents: ファイル名と内容の辞書
            context: 追加コンテキスト
            
        Returns:
            洞察の要約
        """
        try:
            # ファイル内容の要約
            file_summaries = []
            for filename, content in file_contents.items():
                summary = content[:200] + "..." if len(content) > 200 else content
                file_summaries.append(f"**{filename}**: {summary}")
            
            prompt = f"""
タスク: {task_description}

ファイル内容:
{chr(10).join(file_summaries)}

上記のファイル内容を分析し、タスク実行に必要な洞察をまとめてください。
簡潔で実用的な要約を提供してください。
"""
            
            self.logger.info(f"LLMService: LLM呼び出し開始 - プロンプト長: {len(prompt)}文字")
            
            response = await self.llm_client.chat(
                prompt=prompt,
                max_tokens=600,
                temperature=0.1,
                tools=None,
                tool_choice="none"
            )
            
            # レスポンスの検証
            if response is None:
                self.logger.error("LLMService: LLMからNoneレスポンスが返されました")
                return "LLMからの応答が取得できませんでした。"
            
            if response.content is None:
                self.logger.error("LLMService: LLMレスポンスのcontentがNoneです")
                return "LLMからの応答内容が取得できませんでした。"
            
            if not response.content.strip():
                self.logger.error("LLMService: LLMレスポンスのcontentが空です")
                return "LLMからの応答内容が空でした。"
            
            self.logger.info(f"LLMService: LLM応答成功 - 文字数: {len(response.content)}")
            return response.content
            
        except Exception as e:
            self.logger.error(f"洞察合成エラー: {e}", exc_info=True)
            return f"ファイル分析中にエラーが発生しました: {str(e)}"
    
    def get_service_status(self) -> Dict[str, Any]:
        """サービスの状態を取得"""
        return {
            "llm_available": self.llm_client.is_available(),
            "llm_provider": self.llm_client.provider.value,
            "service_config": self.config,
            "service_name": "LLMService"
        }


# デフォルトLLMサービスインスタンス
llm_service = LLMService(LLMClient(LLMProvider.OPENAI))

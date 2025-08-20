"""
LLM Intent Analyzer

LLMによる深い意図理解エンジン
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

# LLMクライアントは動的にインポート（既存アダプターまたは新クライアント）


class IntentType(Enum):
    """意図の種類"""
    INFORMATION_REQUEST = "information_request"      # 情報要求
    ANALYSIS_REQUEST = "analysis_request"            # 分析要求
    CREATION_REQUEST = "creation_request"            # 作成要求
    MODIFICATION_REQUEST = "modification_request"    # 修正要求
    SEARCH_REQUEST = "search_request"                # 検索要求
    GUIDANCE_REQUEST = "guidance_request"            # ガイダンス要求


class ComplexityLevel(Enum):
    """複雑度レベル"""
    SIMPLE = "simple"        # 単純
    MODERATE = "moderate"    # 中程度
    COMPLEX = "complex"      # 複雑


@dataclass
class IntentAnalysis:
    """意図分析結果"""
    primary_intent: IntentType
    secondary_intents: List[IntentType]
    context_requirements: List[str]
    execution_complexity: ComplexityLevel
    confidence_score: float
    reasoning: str
    detected_targets: List[str]
    suggested_approach: str
    task_complexity_analysis: Dict[str, Any] = field(default_factory=dict)
    prompt_pattern: str = "base_main"
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.secondary_intents is None:
            self.secondary_intents = []
        if self.context_requirements is None:
            self.context_requirements = []
        if self.detected_targets is None:
            self.detected_targets = []
        if self.metadata is None:
            self.metadata = {}


class LLMIntentAnalyzer:
    """LLMによる深い意図理解エンジン"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
        self.intent_prompts = self._load_intent_prompts()
    
    def _load_intent_prompts(self) -> Dict[str, str]:
        return {
            "system": """あなたは高度な意図理解の専門家です。
ユーザーの要求と文脈を分析し、以下の要素を正確に特定してください：

1.  **主要意図（Primary Intent）**: 6種類の意図から最も適切なものを選択
2.  **タスク複雑度分析（Task Complexity Analysis）**: 以下の3要素を評価し、タスクの総合的な複雑度を判断する。
    - `request_complexity`: ユーザーの直接的な要求自体の複雑さ（low/medium/high）。
    - `context_dependency`: 直前の会話や短期記憶への依存度の高さ（none/low/high）。
    - `required_knowledge`: ファイル操作、コード生成など、専門知識の必要性（general/specialized）。
3.  **プロンプトパターン（Prompt Pattern）**: 上記の複雑度分析に基づき、次の処理に最適なプロンプトパターンを選択（`base_main` / `base_main_specialized`）。**特に`context_dependency`が`high`の場合や`required_knowledge`が`specialized`の場合は`base_main_specialized`を選択することが強く推奨される。**
4.  **実行複雑度（Execution Complexity）**: タスクの複雑さ（simple/moderate/complex）
5.  **信頼度スコア（Confidence Score）**: 0.0-1.0の数値
6.  **検出対象（Detected Targets）**: ファイル名、ディレクトリ名等
7.  **推奨アプローチ（Suggested Approach）**: 実行方法の提案

**6種類の意図（正確な値を使用してください）:**
- information_request: 一般的な情報の確認・説明・質問
- analysis_request: コード・データ・ファイル内容の分析・評価・確認・読み込み
- creation_request: 新規ファイル・機能の作成
- modification_request: 既存コード・設定の修正
- search_request: 特定の要素・パターンの検索
- guidance_request: 手順・方法の案内・相談""",
            
            "user_template": """ユーザー入力: {user_input}

プロジェクト文脈: {project_context}
対話履歴: {conversation_history}

上記の要求を分析し、以下のJSON形式で回答してください：

```json
{{
    "primary_intent": "creation_request",
    "task_complexity_analysis": {{
        "request_complexity": "low",
        "context_dependency": "high",
        "required_knowledge": "specialized",
        "reasoning": "ユーザーの要求は単純だが、直前のファイル読み込みの文脈に強く依存するため、タスクの全体的な複雑度は高い。"
    }},
    "prompt_pattern": "base_main_specialized",
    "execution_complexity": "complex",
    "confidence_score": 0.9,
    "reasoning": "ユーザーは直近のコンテキストに基づいた作成を要求している。",
    "detected_targets": ["implementation_plan.md"],
    "suggested_approach": "コンテキストを基に計画を生成し、ユーザーに提示する。"
}}"""
        }
    
    async def analyze_intent(
        self, 
        user_input: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> IntentAnalysis:
        prompt = self._build_intent_analysis_prompt(user_input, context)
        response = await self.llm_client.chat(
            prompt=prompt,
            system_prompt=self.intent_prompts["system"],
            max_tokens=1024,
            temperature=0.0
        )
        return self._parse_intent_analysis(response, user_input)

    def _build_intent_analysis_prompt(self, user_input: str, context: Optional[Dict[str, Any]]) -> str:
        project_context = context.get("project_info", "不明") if context else "不明"
        conversation_history = "なし"
        if context and "recent_messages" in context:
            recent_msgs = context["recent_messages"][-3:]
            conversation_history = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')[:100]}..."
                for msg in recent_msgs
            ])
        return self.intent_prompts["user_template"].format(
            user_input=user_input,
            project_context=project_context,
            conversation_history=conversation_history
        )

    def _parse_intent_analysis(self, response, user_input: str) -> IntentAnalysis:
        try:
            content = response.content
            json_str = content[content.find('{'):content.rfind('}') + 1]
            parsed_data = json.loads(json_str)

            primary_intent = IntentType(parsed_data.get("primary_intent", "information_request").lower())
            complexity = ComplexityLevel(parsed_data.get("execution_complexity", "moderate").lower())
            confidence = float(parsed_data.get("confidence_score", 0.7))
            prompt_pattern = parsed_data.get("prompt_pattern", "base_main")
            if prompt_pattern not in ["base_main", "base_main_specialized"]:
                prompt_pattern = "base_main"

            return IntentAnalysis(
                primary_intent=primary_intent,
                secondary_intents=[IntentType(i.lower()) for i in parsed_data.get("secondary_intents", []) if i.lower() in IntentType._value2member_map_],
                context_requirements=parsed_data.get("context_requirements", []),
                execution_complexity=complexity,
                confidence_score=max(0.0, min(1.0, confidence)),
                reasoning=parsed_data.get("reasoning", ""),
                detected_targets=parsed_data.get("detected_targets", []),
                suggested_approach=parsed_data.get("suggested_approach", ""),
                task_complexity_analysis=parsed_data.get("task_complexity_analysis", {}),
                prompt_pattern=prompt_pattern,
                metadata=parsed_data.get("metadata", {})
            )
        except Exception as e:
            self.logger.error(f"意図分析パースエラー: {e}", exc_info=True)
            return self._create_fallback_analysis(user_input, f"パースエラー: {str(e)}")

    def _create_fallback_analysis(self, user_input: str, error: str) -> IntentAnalysis:
        primary_intent = IntentType.INFORMATION_REQUEST
        if any(kw in user_input.lower() for kw in ["作成", "実装"]): primary_intent = IntentType.CREATION_REQUEST
        elif any(kw in user_input.lower() for kw in ["修正", "変更"]): primary_intent = IntentType.MODIFICATION_REQUEST
        elif any(kw in user_input.lower() for kw in ["分析", "確認", "読んで"]): primary_intent = IntentType.ANALYSIS_REQUEST
        
        return IntentAnalysis(
            primary_intent=primary_intent,
            secondary_intents=[],
            context_requirements=["基本的な情報"],
            execution_complexity=ComplexityLevel.MODERATE,
            confidence_score=0.4,
            reasoning=f"フォールバック分類: {error}",
            detected_targets=[],
            suggested_approach="基本的な処理",
            task_complexity_analysis={"reasoning": "Fallback due to error"},
            prompt_pattern="base_main",
            metadata={"fallback_reason": error}
        )

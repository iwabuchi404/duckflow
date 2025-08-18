"""
LLM Intent Analyzer

LLMによる深い意図理解エンジン
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
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
        """意図分析エンジンを初期化"""
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)
        
        # 意図理解プロンプトの設定
        self.intent_prompts = self._load_intent_prompts()
    
    def _load_intent_prompts(self) -> Dict[str, str]:
        """意図理解プロンプトを読み込み"""
        return {
            "system": """あなたは高度な意図理解の専門家です。
ユーザーの要求を分析し、以下の要素を正確に特定してください：

1. **主要意図（Primary Intent）**: 6種類の意図から最も適切なものを選択
2. **副次意図（Secondary Intents）**: 補助的な意図があれば特定
3. **文脈要件（Context Requirements）**: 理解に必要な追加情報
4. **実行複雑度（Execution Complexity）**: タスクの複雑さ（simple/moderate/complex）
5. **信頼度スコア（Confidence Score）**: 0.0-1.0の数値
6. **検出対象（Detected Targets）**: ファイル名、ディレクトリ名等
7. **推奨アプローチ（Suggested Approach）**: 実行方法の提案

**6種類の意図（正確な値を使用してください）:**
- information_request: 一般的な情報の確認・説明・質問（概念や手順について）
- analysis_request: コード・データ・ファイル内容の分析・評価・確認・読み込み
  例: 「ファイルを読んで」「内容を確認」「game_doc.mdを見て」
- creation_request: 新規ファイル・機能の作成
- modification_request: 既存コード・設定の修正
- search_request: 特定の要素・パターンの検索
- guidance_request: 手順・方法の案内・相談

**重要**: detected_targetsには、言及されたファイル名、ディレクトリ名、拡張子を必ず含めてください。
例: "design-doc_v3.md", "README.md", ".py", "config.json" など""",
            
            "user_template": """ユーザー入力: {user_input}

プロジェクト文脈: {project_context}
対話履歴: {conversation_history}

上記の要求を分析し、以下のJSON形式で回答してください：

```json
{{
    "primary_intent": "information_request",
    "secondary_intents": ["analysis_request"],
    "context_requirements": ["必要情報1", "必要情報2"],
    "execution_complexity": "simple",
    "confidence_score": 0.85,
    "reasoning": "分類理由の説明",
    "detected_targets": ["検出された対象1", "対象2"],
    "suggested_approach": "実行方法の提案"
}}
```

**重要**: primary_intentには必ず以下のいずれかを使用してください:
information_request, analysis_request, creation_request, modification_request, search_request, guidance_request"""
        }
    
    async def analyze_intent(
        self, 
        user_input: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> IntentAnalysis:
        """
        LLMによる意図分析の実行
        
        Args:
            user_input: ユーザーの入力
            context: 追加コンテキスト情報
            
        Returns:
            意図分析結果
        """
        try:
            # プロンプトの構築
            prompt = self._build_intent_analysis_prompt(user_input, context)
            
            # LLM実行
            response = await self.llm_client.chat(
                prompt=prompt,
                system_prompt=self.intent_prompts["system"],
                max_tokens=800,
                temperature=0.1
            )
            
            # レスポンスの解析
            return self._parse_intent_analysis(response, user_input)
            
        except Exception as e:
            self.logger.error(f"意図分析エラー: {e}")
            return self._create_fallback_analysis(user_input, str(e))
    
    def _build_intent_analysis_prompt(
        self, 
        user_input: str, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """意図分析プロンプトの構築"""
        
        # コンテキスト情報の準備
        project_context = "不明"
        conversation_history = "なし"
        
        if context:
            if "project_info" in context:
                project_context = context["project_info"]
            if "recent_messages" in context:
                recent_msgs = context["recent_messages"][-3:]  # 直近3件
                conversation_history = "\n".join([
                    f"{msg.get('role', 'unknown')}: {msg.get('content', '')[:100]}..."
                    for msg in recent_msgs
                ])
        
        # プロンプトテンプレートの適用
        return self.intent_prompts["user_template"].format(
            user_input=user_input,
            project_context=project_context,
            conversation_history=conversation_history
        )
    
    def _parse_intent_analysis(self, response, user_input: str) -> IntentAnalysis:
        """LLM応答から意図分析結果をパース"""
        try:
            # JSON部分を抽出
            content = response.content
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("JSON形式の応答が見つかりません")
            
            json_str = content[json_start:json_end]
            parsed_data = json.loads(json_str)
            
            # 必須フィールドの検証と変換
            primary_intent_str = parsed_data.get("primary_intent", "information_request").lower()
            try:
                primary_intent = IntentType(primary_intent_str)
            except ValueError:
                self.logger.warning(f"無効な主要意図: {primary_intent_str}, デフォルトを使用")
                primary_intent = IntentType.INFORMATION_REQUEST
            
            secondary_intents = []
            for intent in parsed_data.get("secondary_intents", []):
                try:
                    intent_lower = intent.lower() if isinstance(intent, str) else str(intent).lower()
                    secondary_intents.append(IntentType(intent_lower))
                except ValueError:
                    self.logger.warning(f"無効な副次意図: {intent}")
            
            complexity_str = parsed_data.get("execution_complexity", "moderate").lower()
            try:
                complexity = ComplexityLevel(complexity_str)
            except ValueError:
                self.logger.warning(f"無効な複雑度: {complexity_str}, デフォルトを使用")
                complexity = ComplexityLevel.MODERATE
            
            confidence = float(parsed_data.get("confidence_score", 0.7))
            confidence = max(0.0, min(1.0, confidence))  # 0.0-1.0に制限
            
            return IntentAnalysis(
                primary_intent=primary_intent,
                secondary_intents=secondary_intents,
                context_requirements=parsed_data.get("context_requirements", []),
                execution_complexity=complexity,
                confidence_score=confidence,
                reasoning=parsed_data.get("reasoning", "LLM分析完了"),
                detected_targets=parsed_data.get("detected_targets", []),
                suggested_approach=parsed_data.get("suggested_approach", "標準的な処理"),
                metadata={
                    "llm_provider": getattr(response, 'provider', {}).value if hasattr(response, 'provider') and hasattr(getattr(response, 'provider', None), 'value') else 'unknown',
                    "llm_model": getattr(response, 'model', 'unknown'),
                    "tokens_used": getattr(response, 'tokens_used', None)
                }
            )
            
        except Exception as e:
            self.logger.error(f"意図分析パースエラー: {e}")
            return self._create_fallback_analysis(user_input, f"パースエラー: {str(e)}")
    
    def _create_fallback_analysis(self, user_input: str, error: str) -> IntentAnalysis:
        """フォールバック用の意図分析"""
        
        # 基本的なキーワードベース分類
        input_lower = user_input.lower()
        
        # ファイル名の検出
        import re
        detected_targets = []
        
        # ファイル名パターンの検出
        file_patterns = [
            r'[\w\-\.]+\.(md|py|txt|json|yaml|yml|js|ts|html|css|xml|csv)',
            r'[\w\-\.]+\.[\w]+',  # 一般的なファイル拡張子
        ]
        
        for pattern in file_patterns:
            matches = re.findall(pattern, user_input, re.IGNORECASE)
            detected_targets.extend(matches)
        
        if any(kw in input_lower for kw in ["作成", "作って", "実装", "書いて", "構築"]):
            primary_intent = IntentType.CREATION_REQUEST
        elif any(kw in input_lower for kw in ["修正", "変更", "改善", "直して", "更新"]):
            primary_intent = IntentType.MODIFICATION_REQUEST
        elif any(kw in input_lower for kw in ["分析", "評価", "診断", "チェック", "読み", "読んで", "確認", "内容", "見て", "把握"]):
            primary_intent = IntentType.ANALYSIS_REQUEST
        elif any(kw in input_lower for kw in ["検索", "探して", "見つけて", "調べて"]):
            primary_intent = IntentType.SEARCH_REQUEST
        elif any(kw in input_lower for kw in ["説明", "教えて", "案内", "手順"]):
            primary_intent = IntentType.GUIDANCE_REQUEST
        else:
            primary_intent = IntentType.INFORMATION_REQUEST
        
        return IntentAnalysis(
            primary_intent=primary_intent,
            secondary_intents=[],
            context_requirements=["基本的な情報"],
            execution_complexity=ComplexityLevel.MODERATE,
            confidence_score=0.5,
            reasoning=f"フォールバック分類: {error}",
            detected_targets=detected_targets,
            suggested_approach="基本的な処理",
            metadata={"fallback_reason": error}
        )
    
    def get_intent_description(self, intent_type: IntentType) -> str:
        """意図タイプの説明を取得"""
        descriptions = {
            IntentType.INFORMATION_REQUEST: "情報の確認・表示・説明を求めています",
            IntentType.ANALYSIS_REQUEST: "コード・データの分析・評価を求めています",
            IntentType.CREATION_REQUEST: "新規ファイル・機能の作成を求めています",
            IntentType.MODIFICATION_REQUEST: "既存コード・設定の修正を求めています",
            IntentType.SEARCH_REQUEST: "特定の要素・パターンの検索を求めています",
            IntentType.GUIDANCE_REQUEST: "手順・方法の案内・相談を求めています"
        }
        return descriptions.get(intent_type, "意図が特定できません")
    
    def get_complexity_description(self, complexity: ComplexityLevel) -> str:
        """複雑度の説明を取得"""
        descriptions = {
            ComplexityLevel.SIMPLE: "単純な処理で済みます",
            ComplexityLevel.MODERATE: "中程度の複雑さがあります",
            ComplexityLevel.COMPLEX: "複雑な処理が必要です"
        }
        return descriptions.get(complexity, "複雑度が不明です")

"""
LLMChoiceParser - LLMベース選択解析エンジン
自然言語でのユーザー選択をLLMで解析し、理解する
"""

import json
import logging
from typing import Dict, Any, List

from .choice_models import ChoiceContext, ChoiceResult
from ..base.llm_client import llm_manager


class LLMChoiceParser:
    """自然言語選択解析エンジン
    
    LLMを使用してユーザーの自然言語選択を理解し、
    適切な選択肢へのマッピングを行う
    """
    
    def __init__(self):
        """初期化"""
        self.llm_client = llm_manager
        self.confidence_threshold_high = 0.8
        self.confidence_threshold_medium = 0.6
        self.logger = logging.getLogger(__name__)
    
    async def parse_user_choice(self, user_input: str, context: ChoiceContext) -> ChoiceResult:
        """ユーザーの自然言語選択を解析
        
        Args:
            user_input: ユーザーの入力テキスト
            context: 選択コンテキスト
            
        Returns:
            ChoiceResult: 解析結果
        """
        try:
            # LLMプロンプト構築
            system_prompt = self._build_choice_analysis_prompt(context)
            user_prompt = f"ユーザーの回答: 「{user_input}」"
            
            # LLM解析実行
            analysis = await self._analyze_with_llm(system_prompt, user_prompt)
            
            # 結果パース
            return self._parse_llm_response(analysis, context)
            
        except Exception as e:
            self.logger.error(f"LLM選択解析エラー: {e}")
            # エラー時のフォールバック
            return ChoiceResult(
                selected_options=[],
                confidence=0.0,
                reasoning=f"解析エラー: {str(e)}",
                clarification_needed=True,
                extracted_intent="エラー"
            )
    
    def _build_choice_analysis_prompt(self, context: ChoiceContext) -> str:
        """選択解析用プロンプトを構築
        
        Args:
            context: 選択コンテキスト
            
        Returns:
            str: システムプロンプト
        """
        # 選択肢を番号付きでフォーマット
        options_text = self._format_options(context.available_options, context.option_descriptions)
        
        # コンテキスト情報の構築
        context_info = self._build_context_info(context)
        
        return f"""あなたはユーザーの選択を理解する専門システムです。

## 利用可能な選択肢:
{options_text}

## 現在のコンテキスト:
{context_info}

## タスク:
ユーザーの自然言語回答を分析し、以下のJSON形式で回答してください:

{{
    "selected_options": [1, 2],  // 選択された選択肢番号の配列（1ベース）
    "confidence": 0.85,          // 解釈の確信度 (0.0-1.0)
    "reasoning": "説明",         // 解釈の理由
    "modifications": [],         // 条件付き要求があればリスト
    "clarification_needed": false, // 確認が必要かどうか
    "extracted_intent": "全実行" // 抽出された意図
}}

## 解析ルール:
1. 明確な番号指定は高確信度 (0.9+)
2. 曖昧な表現は中確信度 (0.6-0.8)
3. 理解困難は低確信度 (0.0-0.5)
4. 条件付き承認は modifications に記録
5. 不明な点は clarification_needed = true
6. 複数選択の場合は配列で返す
7. 選択の意図が不明な場合は空の配列を返す

必ず有効なJSONで回答し、他のテキストは含めないでください。"""
    
    def _format_options(self, options: List[str], descriptions: List[str]) -> str:
        """選択肢を番号付きでフォーマット
        
        Args:
            options: 選択肢リスト
            descriptions: 説明リスト
            
        Returns:
            str: フォーマットされた選択肢テキスト
        """
        formatted_lines = []
        for i, (option, desc) in enumerate(zip(options, descriptions), 1):
            formatted_lines.append(f"{i}. {option} - {desc}")
        return "\n".join(formatted_lines)
    
    def _build_context_info(self, context: ChoiceContext) -> str:
        """コンテキスト情報を構築
        
        Args:
            context: 選択コンテキスト
            
        Returns:
            str: コンテキスト情報テキスト
        """
        context_parts = []
        
        if context.current_plan:
            context_parts.append(f"- プラン: {context.current_plan}")
        else:
            context_parts.append("- プラン: なし")
        
        context_parts.append(f"- リスクレベル: {context.risk_level}")
        
        if context.previous_choices:
            choices_text = ", ".join(context.previous_choices[-3:])  # 直近3件のみ
            context_parts.append(f"- 過去の選択: {choices_text}")
        
        if context.conversation_context:
            context_parts.append(f"- 会話コンテキスト: {context.conversation_context}")
        
        return "\n".join(context_parts)
    
    async def _analyze_with_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
LLMで解析を実行
        
        Args:
            system_prompt: システムプロンプト
            user_prompt: ユーザープロンプト
            
        Returns:
            str: LLMの応答
        """
        try:
            response = await self.llm_client.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=500,
                temperature=0.1  # 一貫性を重視
            )
            return response
        except Exception as e:
            self.logger.error(f"LLM APIエラー: {e}")
            raise
    
    def _parse_llm_response(self, response: str, context: ChoiceContext) -> ChoiceResult:
        """
LLMの応答をパースしてChoiceResultに変換
        
        Args:
            response: LLMの応答
            context: 選択コンテキスト
            
        Returns:
            ChoiceResult: パースされた結果
        """
        try:
            # JSON部分を抽出
            response_clean = response.strip()
            
            # ```jsonブロックがある場合は除去
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            
            # JSONパース
            parsed = json.loads(response_clean.strip())
            
            # 必須フィールドのバリデーション
            selected_options = parsed.get("selected_options", [])
            confidence = float(parsed.get("confidence", 0.0))
            reasoning = parsed.get("reasoning", "")
            modifications = parsed.get("modifications", [])
            clarification_needed = parsed.get("clarification_needed", False)
            extracted_intent = parsed.get("extracted_intent", "")
            
            # 選択肢番号のバリデーション
            valid_options = []
            for opt in selected_options:
                if isinstance(opt, int) and 1 <= opt <= len(context.available_options):
                    valid_options.append(opt)
                else:
                    self.logger.warning(f"無効な選択肢番号: {opt}")
            
            # 無効な選択肢があった場合は確信度を下げる
            if len(valid_options) < len(selected_options):
                confidence = max(0.0, confidence - 0.2)
                clarification_needed = True
                reasoning += " (無効な選択肢が含まれていたため確信度を下げました)"
            
            return ChoiceResult(
                selected_options=valid_options,
                confidence=confidence,
                reasoning=reasoning,
                modifications=modifications,
                clarification_needed=clarification_needed,
                extracted_intent=extracted_intent
            )
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSONパースエラー: {e}, 応答: {response}")
            return ChoiceResult(
                selected_options=[],
                confidence=0.0,
                reasoning=f"JSONパースエラー: {str(e)}",
                clarification_needed=True,
                extracted_intent="パースエラー"
            )
        except Exception as e:
            self.logger.error(f"予期しないパースエラー: {e}")
            return ChoiceResult(
                selected_options=[],
                confidence=0.0,
                reasoning=f"パースエラー: {str(e)}",
                clarification_needed=True,
                extracted_intent="エラー"
            )
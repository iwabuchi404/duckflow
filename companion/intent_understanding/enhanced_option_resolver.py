"""
EnhancedOptionResolver - ハイブリッド選択解析システム
既存のパターンマッチング + LLMベース自然言語理解の統合
"""

import logging
from typing import Optional, List

from .intent_integration import OptionResolver
from companion.llm_choice.choice_models import ChoiceContext, ChoiceResult
from companion.llm_choice.choice_parser import LLMChoiceParser


class EnhancedOptionResolver:
    """
    拡張選択解析システム
    
    従来のパターンマッチングを高速・安全な基盤として保持し、
    LLM解析を自然言語理解の拡張層として追加した階層的システム
    
    処理フロー:
    1. パターンマッチング (高速・安全) → 即座に結果返却
    2. LLM解析 (自然言語理解) → 信頼度に応じた処理
    3. 信頼度チェック → 確認・明確化・実行判定
    """
    
    def __init__(self):
        """
        初期化
        """
        self.pattern_resolver = OptionResolver()
        self.llm_parser = LLMChoiceParser()
        self.choice_history: List[str] = []
        self.logger = logging.getLogger(__name__)
        
        # 信頼度しきい値
        self.high_confidence_threshold = 0.8
        self.medium_confidence_threshold = 0.6
    
    async def parse_selection_enhanced(self, text: str, context: ChoiceContext) -> ChoiceResult:
        """
        拡張選択解析
        
        Args:
            text: ユーザーの入力テキスト
            context: 選択コンテキスト
            
        Returns:
            ChoiceResult: 解析結果
        """
        try:
            # Step 1: 既存パターンマッチング (高速・安全)
            pattern_match = self.pattern_resolver.parse_selection(text)
            if pattern_match is not None:
                self.logger.debug(f"パターンマッチング成功: {text} → {pattern_match}")
                
                # パターンマッチした場合は高確信度で即座に返す
                result = ChoiceResult(
                    selected_options=[pattern_match],
                    confidence=0.95,
                    reasoning="パターンマッチング（確実な選択）",
                    extracted_intent="明確な選択"
                )
                
                # 履歴に記録
                self._add_to_history(text, result)
                return result
            
            self.logger.debug(f"パターンマッチング失敗、LLM解析に移行: {text}")
            
            # Step 2: LLM解析 (自然言語理解)
            llm_result = await self.llm_parser.parse_user_choice(text, context)
            
            # Step 3: 信頼度に基づく処理
            enhanced_result = self._process_by_confidence(llm_result, text, context)
            
            # 履歴に記録
            self._add_to_history(text, enhanced_result)
            return enhanced_result
            
        except Exception as e:
            self.logger.error(f"拡張選択解析エラー: {e}")
            return ChoiceResult(
                selected_options=[],
                confidence=0.0,
                reasoning=f"解析エラー: {str(e)}",
                clarification_needed=True,
                extracted_intent="エラー"
            )
    
    def _process_by_confidence(self, llm_result: ChoiceResult, original_text: str, context: ChoiceContext) -> ChoiceResult:
        """
        信頼度に基づいて結果を処理
        
        Args:
            llm_result: LLMの解析結果
            original_text: 元のユーザー入力
            context: 選択コンテキスト
            
        Returns:
            ChoiceResult: 処理された結果
        """
        if llm_result.confidence >= self.high_confidence_threshold:
            # 高確信度: そのまま実行
            self.logger.debug(f"高確信度 ({llm_result.confidence:.2f}): 即座に実行")
            return llm_result
        
        elif llm_result.confidence >= self.medium_confidence_threshold:
            # 中確信度: 確認要求
            self.logger.debug(f"中確信度 ({llm_result.confidence:.2f}): 確認要求")
            llm_result.clarification_needed = True
            llm_result.reasoning += " (確信度が中程度のため確認が必要)"
            return llm_result
        
        else:
            # 低確信度: 明確化要求
            self.logger.debug(f"低確信度 ({llm_result.confidence:.2f}): 明確化要求")
            return ChoiceResult(
                selected_options=[],
                confidence=0.0,
                reasoning=f"申し訳ありませんが、'{original_text}' を理解できませんでした。より明確に選択肢を指定してください。",
                clarification_needed=True,
                extracted_intent="理解困難"
            )
    
    def _add_to_history(self, user_input: str, result: ChoiceResult):
        """
        選択履歴に追加
        
        Args:
            user_input: ユーザー入力
            result: 解析結果
        """
        history_entry = f"{user_input} → {result.format_selected_options_text(['選択肢'])}"
        self.choice_history.append(history_entry)
        
        # 履歴サイズ制限 (最新10件のみ保持)
        if len(self.choice_history) > 10:
            self.choice_history = self.choice_history[-10:]
    
    def get_choice_history(self) -> List[str]:
        """
        選択履歴を取得
        
        Returns:
            List[str]: 選択履歴
        """
        return self.choice_history.copy()
    
    def clear_history(self):
        """
        選択履歴をクリア
        """
        self.choice_history.clear()
        self.logger.debug("選択履歴をクリアしました")
    
    def is_selection_input(self, text: str) -> bool:
        """
        入力が選択入力かどうかを判定
        
        Args:
            text: ユーザーの入力テキスト
            
        Returns:
            bool: 選択入力と判定される場合True
        """
        # パターンマッチングで即座に判定可能な場合
        if self.pattern_resolver.is_selection_input(text):
            return True
        
        # LLM解析が必要かもしれないが、明らかに選択ではない場合は除外
        # 例: 長い文章、質問形式、新規作成要求など
        import re
        
        # 明らかに選択ではないパターン
        non_selection_patterns = [
            r'^.{50,}',  # 50文字以上の長い文章
            r'[？?]$',   # 質問で終わる
            r'^(作成|作って|新しく|追加)',  # 新規作成要求
            r'^(教えて|説明|どうやって|なぜ|なんで)',  # 情報要求
            r'^(ヘルプ|help|使い方)',  # ヘルプ要求
        ]
        
        normalized_text = text.strip().lower()
        for pattern in non_selection_patterns:
            if re.search(pattern, normalized_text):
                return False
        
        # 簡単な選択候補のキーワードチェック
        selection_keywords = [
            '番目', '選択', '実行', 'やって', 'お願い',
            '1', '2', '3', '4', '5',
            'はい', 'いいえ', 'yes', 'no',
            '上', '下', '最初', '次',
        ]
        
        for keyword in selection_keywords:
            if keyword in normalized_text:
                return True
        
        # デフォルトは非選択入力として判定
        return False
    
    async def parse_selection_with_fallback(self, text: str, available_options: List[str]) -> ChoiceResult:
        """
        簡単なコンテキストでの選択解析（フォールバック用）
        
        Args:
            text: ユーザーの入力テキスト
            available_options: 利用可能な選択肢
            
        Returns:
            ChoiceResult: 解析結果
        """
        # 基本的なコンテキストを作成
        context = ChoiceContext(
            available_options=available_options,
            option_descriptions=[f"選択肢{i+1}" for i in range(len(available_options))]
        )
        
        return await self.parse_selection_enhanced(text, context)
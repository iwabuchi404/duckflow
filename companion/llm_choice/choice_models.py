"""
LLMベース選択処理のデータモデル
選択コンテキストと結果を表現するデータクラス
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ChoiceContext:
    """選択肢コンテキスト
    
    LLMがユーザーの選択を理解するための情報を管理
    
    Attributes:
        available_options: 利用可能な選択肢リスト
        option_descriptions: 各選択肢の説明
        current_plan: 現在のプラン内容（プラン承認時）
        risk_level: リスクレベル
        previous_choices: 過去の選択履歴
        conversation_context: 会話のコンテキスト
    """
    available_options: List[str]
    option_descriptions: List[str]
    current_plan: Optional[str] = None
    risk_level: str = "medium"
    previous_choices: List[str] = field(default_factory=list)
    conversation_context: str = ""
    
    def __post_init__(self):
        """初期化後のバリデーション"""
        if len(self.available_options) != len(self.option_descriptions):
            if not self.option_descriptions:
                # 説明が空の場合はデフォルト説明を生成
                self.option_descriptions = [f"選択肢{i+1}: {opt}" for i, opt in enumerate(self.available_options)]
            else:
                raise ValueError("選択肢と説明の数が一致しません")


@dataclass
class ChoiceResult:
    """選択結果
    
    LLMによる選択解析の結果を表現
    
    Attributes:
        selected_options: 選択された選択肢の番号リスト
        confidence: 解釈の確信度 (0.0-1.0)
        reasoning: 解釈の理由・根拠
        modifications: 条件付き要求のリスト
        clarification_needed: 確認が必要かどうか
        extracted_intent: 抽出された意図
    """
    selected_options: List[int]
    confidence: float
    reasoning: str
    modifications: List[str] = field(default_factory=list)
    clarification_needed: bool = False
    extracted_intent: str = ""
    
    def __post_init__(self):
        """初期化後のバリデーション"""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("確信度は0.0から1.0の範囲である必要があります")
        
        # 選択肢番号の正规化（1ベースで期待）
        for option_num in self.selected_options:
            if option_num < 1:
                raise ValueError("選択肢番号は1以上である必要があります")
    
    @property
    def is_high_confidence(self) -> bool:
        """高確信度かどうかを判定"""
        return self.confidence >= 0.8
    
    @property
    def is_medium_confidence(self) -> bool:
        """中確信度かどうかを判定"""
        return 0.6 <= self.confidence < 0.8
    
    @property
    def is_low_confidence(self) -> bool:
        """低確信度かどうかを判定"""
        return self.confidence < 0.6
    
    @property
    def needs_confirmation(self) -> bool:
        """確認が必要かどうかを判定"""
        return self.clarification_needed or self.is_medium_confidence or (self.modifications and self.is_high_confidence)
    
    def format_selected_options_text(self, available_options: List[str]) -> str:
        """選択された選択肢をテキストでフォーマット"""
        if not self.selected_options:
            return "選択なし"
        
        option_texts = []
        for option_num in self.selected_options:
            if 1 <= option_num <= len(available_options):
                option_texts.append(f"{option_num}. {available_options[option_num - 1]}")
            else:
                option_texts.append(f"{option_num}. (範囲外)")
        
        return ", ".join(option_texts)
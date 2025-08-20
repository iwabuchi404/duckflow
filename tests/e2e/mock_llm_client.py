"""
MockLLMClient - テスト用のモックLLMクライアント
"""

import json
import time
from typing import Dict, List, Any


class MockLLMClient:
    """テスト用のモックLLMクライアント"""
    
    def __init__(self):
        """初期化"""
        self.call_count = 0
        self.current_scenario = ""
        self.scenario_responses = {
            # 説明シナリオ用
            "explanation": [
                "Pythonのprint関数について教えてください",
                "ありがとうございます。具体例も見せてもらえますか？",
                "テスト完了"
            ],
            
            # ファイル作成シナリオ用
            "file_creation": [
                "hello.pyファイルを作ってHello Worldを出力してください",
                "はい、お願いします",
                "ファイルの内容を確認できますか？",
                "テスト完了"
            ],
            
            # レビューシナリオ用
            "review": [
                "hello.pyファイルをレビューしてください",
                "改善案を実装してもらえますか？",
                "テスト完了"
            ],
            
            # ConversationEvaluator用の応答
            "evaluator": '''```json
{
    "scenario_achievement": {
        "score": 4,
        "reason": "シナリオの目的であるhello.pyファイルの作成とHello World出力が達成されている"
    },
    "conversation_naturalness": {
        "score": 4,
        "reason": "自然な日本語での対話が行われ、適切な応答がある"
    },
    "technical_accuracy": {
        "score": 5,
        "reason": "生成されたPythonコードは正確で、実行可能な状態である"
    },
    "error_handling": {
        "score": 4,
        "reason": "承認プロセスが適切に機能し、エラーなく完了している"
    },
    "overall_score": {
        "score": 4,
        "reason": "全体的に高品質な対話とファイル作成が実現されている"
    },
    "improvement_suggestions": [
        "より詳細なコードの説明があるとさらに良い",
        "ファイル作成後の動作確認方法の提示"
    ],
    "positive_aspects": [
        "適切な承認プロセス",
        "正確なコード生成",
        "自然な対話フロー"
    ]
}
```'''
        }
        
        self.test_llm_index = 0
    
    def call_llm(self, messages: List[Dict], max_tokens: int = 1000, 
                temperature: float = 0.7, **kwargs) -> str:
        """LLM呼び出しをモック
        
        Args:
            messages: メッセージリスト
            max_tokens: 最大トークン数
            temperature: 温度パラメータ
            
        Returns:
            モック応答
        """
        self.call_count += 1
        
        # 少し待機（実際のLLM呼び出しをシミュレート）
        time.sleep(0.1)
        
        # メッセージの内容から応答タイプを判定
        last_message = messages[-1].get("content", "") if messages else ""
        
        # 評価用の呼び出しかチェック
        if "評価してください" in last_message or "JSON形式で回答" in last_message:
            return self.scenario_responses["evaluator"]
        
        # シナリオ別の応答を取得
        scenario_type = self._detect_scenario_type(last_message)
        responses = self.scenario_responses.get(scenario_type, self.scenario_responses["file_creation"])
        
        # テストLLM用の応答
        if self.test_llm_index < len(responses):
            response = responses[self.test_llm_index]
            self.test_llm_index += 1
            return response
        
        # デフォルト応答
        return "テスト完了"
    
    def _detect_scenario_type(self, message: str) -> str:
        """メッセージからシナリオタイプを判定
        
        Args:
            message: LLMに送信されるメッセージ
            
        Returns:
            シナリオタイプ（"explanation", "file_creation", "review"）
        """
        message_lower = message.lower()
        
        # 説明シナリオの判定
        explanation_keywords = ["説明", "教えて", "について", "とは", "どう", "何", "説明してください"]
        if any(keyword in message_lower for keyword in explanation_keywords):
            return "explanation"
        
        # レビューシナリオの判定
        review_keywords = ["レビュー", "確認", "チェック", "評価", "改善", "問題", "修正"]
        if any(keyword in message_lower for keyword in review_keywords):
            return "review"
        
        # ファイル作成シナリオの判定（デフォルト）
        file_keywords = ["ファイル", "作成", "作って", "作る", "書いて", "生成"]
        if any(keyword in message_lower for keyword in file_keywords):
            return "file_creation"
        
        # システムプロンプトの内容も確認
        if "シナリオ" in message_lower:
            # シナリオ説明を含む場合は内容を分析
            if "print" in message_lower and any(word in message_lower for word in ["説明", "教えて"]):
                return "explanation"
            elif "hello.py" in message_lower and any(word in message_lower for word in ["作", "作成"]):
                return "file_creation"
            elif any(word in message_lower for word in ["レビュー", "改善", "確認"]):
                return "review"
        
        # デフォルトはファイル作成
        return "file_creation"
    
    def reset(self):
        """状態をリセット"""
        self.call_count = 0
        self.test_llm_index = 0
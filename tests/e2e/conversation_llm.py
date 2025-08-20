"""
ConversationTestLLM - シナリオに沿って対話を実行するLLM
"""

import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
import openai
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from companion.base.llm_client import LLMClient
except Exception:
    # テスト環境ではモッククライアントを使用
    from tests.e2e.mock_llm_client import MockLLMClient as LLMClient


class ConversationTestLLM:
    """シナリオに沿って対話を実行するLLM"""
    
    def __init__(self, scenario: str, evaluation_criteria: str):
        """初期化
        
        Args:
            scenario: テストシナリオの内容
            evaluation_criteria: 評価基準
        """
        self.scenario = scenario
        self.evaluation_criteria = evaluation_criteria
        self.conversation_log = []
        self.min_score_threshold = 3.0
        self.max_exchanges = 10
        self.exchange_count = 0
        
        # LLMクライアントの初期化
        self.llm_client = LLMClient()
        
        # ログの設定
        self.logger = logging.getLogger(__name__)
    
    def get_system_prompt(self) -> str:
        """対話実行用のシステムプロンプトを生成
        
        Returns:
            システムプロンプト
        """
        # シナリオ別の具体的な指示を追加
        scenario_specific_guidance = self._get_scenario_specific_guidance()
        
        return f"""あなたはDuckflowのテストユーザーです。以下のシナリオに沿って自然な対話を行ってください。

## シナリオ
{self.scenario}

## シナリオ別の具体的な指示
{scenario_specific_guidance}

## 対話の進め方
1. シナリオの目的を達成するよう、自然に話しかけてください
2. Duckflowの応答を受けて、適切に続きの対話をしてください
3. 承認が求められたら、通常は「はい」「OK」「進めて」などで承認してください
4. エラーや問題があれば、適切に対応してください

## 終了条件
- シナリオの目的が達成されたら「テスト完了」と発言
- 明らかに問題がある場合は「テスト中断: [理由]」と発言
- 最大{self.max_exchanges}回の対話で終了

## 注意事項
- 自然な日本語で対話してください
- 一度に複数の要求をせず、段階的に進めてください
- Duckflowの応答を確認してから次の発言をしてください
- 短文で応答してください（1-2文程度）

それでは対話を始めてください。最初の発言をしてください。"""
    
    def _get_scenario_specific_guidance(self) -> str:
        """シナリオ別の具体的な指示を取得"""
        scenario_lower = self.scenario.lower()
        
        if "print" in scenario_lower and any(word in scenario_lower for word in ["説明", "教えて", "について"]):
            return """- このシナリオは「説明」がメインです
- 最初に「Pythonのprint関数について教えてください」のような説明要求をしてください
- ファイル作成は要求しないでください
- 説明を受けたら、理解を示したり追加の質問をしてください"""
        
        elif "hello.py" in scenario_lower and any(word in scenario_lower for word in ["作", "作成", "作って"]):
            return """- このシナリオは「ファイル作成」がメインです
- 最初に「hello.pyファイルを作ってHello Worldを出力してください」と要求してください
- 承認が求められたら承認してください
- 作成後はファイルの内容確認を求めてください"""
        
        elif any(word in scenario_lower for word in ["レビュー", "改善", "確認"]):
            return """- このシナリオは「レビュー」がメインです
- 既存のファイルがある想定で「hello.pyファイルをレビューしてください」と要求してください
- ファイルがない場合は作成を求めても構いません
- レビュー結果を受けたら、改善提案について質問してください"""
        
        else:
            return """- シナリオの内容に応じて適切な要求をしてください
- 説明系なら説明を、作成系なら作成を、レビュー系ならレビューを要求してください"""
    
    def _get_fallback_first_input(self) -> str:
        """シナリオ別のフォールバック入力を取得"""
        scenario_lower = self.scenario.lower()
        
        if "print" in scenario_lower and any(word in scenario_lower for word in ["説明", "教えて", "について"]):
            return "Pythonのprint関数について教えてください"
        
        elif "hello.py" in scenario_lower and any(word in scenario_lower for word in ["作", "作成", "作って"]):
            return "hello.pyファイルを作ってHello Worldを出力してください"
        
        elif any(word in scenario_lower for word in ["レビュー", "改善", "確認"]):
            return "hello.pyファイルをレビューしてください"
        
        else:
            return "お手伝いをお願いします"
    
    def _get_next_input_prompt(self, conversation_history: List[Dict]) -> str:
        """シナリオに基づく次の入力生成プロンプトを取得"""
        scenario_lower = self.scenario.lower()
        last_exchange = conversation_history[-1] if conversation_history else {}
        last_duckflow = last_exchange.get("duckflow", "").lower()
        
        # 説明シナリオの場合
        if "print" in scenario_lower and any(word in scenario_lower for word in ["説明", "教えて", "について"]):
            if "説明" in last_duckflow or "とは" in last_duckflow:
                return "説明を受けた後の理解確認や追加質問をしてください。例：「ありがとうございます。具体例も見せてもらえますか？」"
            else:
                return "シナリオの説明要求を進めてください。承認や確認ではなく、説明に関する応答をしてください。"
        
        # ファイル作成シナリオの場合
        elif "hello.py" in scenario_lower and any(word in scenario_lower for word in ["作", "作成", "作って"]):
            if "承認" in last_duckflow or "よろしい" in last_duckflow:
                return "承認を求められているので「はい、お願いします」と承認してください。"
            elif "作成しました" in last_duckflow:
                return "ファイルが作成されたので、内容の確認を求めてください。例：「ファイルの内容を確認できますか？」"
            else:
                return "ファイル作成タスクを進めるための適切な応答をしてください。"
        
        # レビューシナリオの場合
        elif any(word in scenario_lower for word in ["レビュー", "改善", "確認"]):
            if "レビュー" in last_duckflow or "評価" in last_duckflow:
                return "レビュー結果を受けたので、改善提案について質問してください。例：「改善案を実装してもらえますか？」"
            else:
                return "レビュータスクを進めるための適切な応答をしてください。"
        
        else:
            return "上記の対話を踏まえて、シナリオを進めるための次の発言をしてください。短文で応答してください。"
    
    def generate_first_input(self) -> str:
        """最初のユーザー入力を生成
        
        Returns:
            最初のユーザー入力
        """
        try:
            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": "対話を開始してください。シナリオに沿った最初の発言をしてください。"}
            ]
            
            response = self.llm_client.call_llm(
                messages=messages,
                max_tokens=200,
                temperature=0.7
            )
            
            self.exchange_count += 1
            user_input = response.strip()
            
            self.logger.info(f"Generated first input: {user_input}")
            return user_input
            
        except Exception as e:
            self.logger.error(f"Error generating first input: {e}")
            return self._get_fallback_first_input()  # シナリオ別フォールバック
    
    def generate_next_input(self, conversation_history: List[Dict]) -> str:
        """次のユーザー入力を生成
        
        Args:
            conversation_history: これまでの対話履歴
            
        Returns:
            次のユーザー入力
        """
        try:
            # 対話回数制限チェック
            if self.exchange_count >= self.max_exchanges:
                return "テスト完了"
            
            # システムプロンプト + 対話履歴を構築
            messages = [{"role": "system", "content": self.get_system_prompt()}]
            
            # 最新の対話履歴を追加（最大5件）
            recent_history = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            
            for exchange in recent_history:
                messages.append({"role": "user", "content": exchange.get("user", "")})
                messages.append({"role": "assistant", "content": exchange.get("duckflow", "")})
            
            # シナリオに基づく次の入力生成プロンプト
            next_prompt = self._get_next_input_prompt(conversation_history)
            messages.append({
                "role": "user", 
                "content": next_prompt
            })
            
            response = self.llm_client.call_llm(
                messages=messages,
                max_tokens=200,
                temperature=0.7
            )
            
            self.exchange_count += 1
            user_input = response.strip()
            
            self.logger.info(f"Generated next input: {user_input}")
            return user_input
            
        except Exception as e:
            self.logger.error(f"Error generating next input: {e}")
            return "テスト中断: エラーが発生しました"
    
    def should_terminate(self, last_response: str) -> bool:
        """対話終了条件を判定
        
        Args:
            last_response: 最後のDuckflow応答
            
        Returns:
            終了すべきかどうか
        """
        # 明示的な終了キーワード
        terminate_keywords = ["テスト完了", "テスト中断", "終了", "エラー"]
        
        if any(keyword in last_response for keyword in terminate_keywords):
            return True
        
        # 最大対話回数に達した場合
        if self.exchange_count >= self.max_exchanges:
            self.logger.info("Maximum exchanges reached")
            return True
        
        # Duckflowの応答が極端に短い（エラーの可能性）
        if len(last_response.strip()) < 10:
            self.logger.warning("Very short response detected")
            return True
        
        return False
    
    def reset(self):
        """テスト状態をリセット"""
        self.conversation_log = []
        self.exchange_count = 0
        self.logger.info("Test LLM state reset")
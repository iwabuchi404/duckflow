"""
ConversationEvaluator - 対話ログを評価するLLM
"""

import json
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import sys

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from companion.base.llm_client import LLMClient
except Exception:
    # テスト環境ではモッククライアントを使用
    from tests.e2e.mock_llm_client import MockLLMClient as LLMClient


class ConversationEvaluator:
    """対話ログを評価するLLM"""
    
    def __init__(self):
        """初期化"""
        # LLMクライアントの初期化
        self.llm_client = LLMClient()
        
        # ログの設定
        self.logger = logging.getLogger(__name__)
        
        # 評価項目の定義
        self.evaluation_criteria = {
            "scenario_achievement": "シナリオ達成度",
            "conversation_naturalness": "対話の自然さ",
            "technical_accuracy": "技術的正確性",
            "error_handling": "エラーハンドリング",
            "overall_score": "総合評価"
        }
    
    def evaluate_conversation(self, log: Dict, scenario: str, 
                            evaluation_criteria: str) -> Dict:
        """対話全体を評価
        
        Args:
            log: 対話ログ
            scenario: テストシナリオ
            evaluation_criteria: 評価基準
            
        Returns:
            評価結果
        """
        try:
            # 評価用プロンプトを構築
            evaluation_prompt = self._build_evaluation_prompt(log, scenario, evaluation_criteria)
            
            # LLMによる評価実行
            messages = [
                {"role": "system", "content": "あなたは厳格で公正なAIシステム評価者です。"},
                {"role": "user", "content": evaluation_prompt}
            ]
            
            response = self.llm_client.call_llm(
                messages=messages,
                max_tokens=1500,
                temperature=0.3  # 一貫性のため低めに設定
            )
            
            # 評価結果をパース
            evaluation_result = self._parse_evaluation_result(response, log)
            
            self.logger.info(f"Evaluation completed for scenario: {scenario}")
            return evaluation_result
            
        except Exception as e:
            self.logger.error(f"Error during evaluation: {e}")
            return self._create_error_evaluation(str(e))
    
    def _build_evaluation_prompt(self, log: Dict, scenario: str, criteria: str) -> str:
        """評価用プロンプトを構築
        
        Args:
            log: 対話ログ
            scenario: シナリオ
            criteria: 評価基準
            
        Returns:
            評価用プロンプト
        """
        # 対話履歴の整形
        conversation_text = self._format_conversation_log(log)
        
        # ファイル操作の整形
        files_text = self._format_file_operations(log)
        
        # 統計情報の整形
        stats_text = self._format_statistics(log)
        
        return f"""以下のAIアシスタント（Duckflow）の対話ログを評価してください。

## テストシナリオ
{scenario}

## 評価基準
{criteria}

## 対話ログ
{conversation_text}

## ファイル操作履歴
{files_text}

## 統計情報
{stats_text}

## 評価してください
以下の項目を1-5点で評価し、理由も含めて回答してください：

1. **シナリオ達成度** (1-5点)
   - シナリオの目的が達成されているか
   - 要求された作業が完了しているか

2. **対話の自然さ** (1-5点)
   - Duckflowの応答が自然で適切か
   - ユーザーとの対話が滑らかか

3. **技術的正確性** (1-5点)
   - 生成されたファイルやコードが適切か
   - 技術的な内容に間違いがないか

4. **エラーハンドリング** (1-5点)
   - 問題が発生した際の対応が適切か
   - エラーメッセージが分かりやすいか

5. **総合評価** (1-5点)
   - 全体的な品質とユーザビリティ

## 回答形式
必ずJSON形式で回答してください：

```json
{{
    "scenario_achievement": {{
        "score": 数値,
        "reason": "評価理由"
    }},
    "conversation_naturalness": {{
        "score": 数値,
        "reason": "評価理由"
    }},
    "technical_accuracy": {{
        "score": 数値,
        "reason": "評価理由"
    }},
    "error_handling": {{
        "score": 数値,
        "reason": "評価理由"
    }},
    "overall_score": {{
        "score": 数値,
        "reason": "評価理由"
    }},
    "improvement_suggestions": [
        "改善提案1",
        "改善提案2"
    ],
    "positive_aspects": [
        "良かった点1",
        "良かった点2"
    ]
}}
```"""
    
    def _format_conversation_log(self, log: Dict) -> str:
        """対話ログを整形
        
        Args:
            log: ログデータ
            
        Returns:
            整形された対話ログ
        """
        if not log.get("exchanges"):
            return "対話なし"
        
        lines = []
        for i, exchange in enumerate(log["exchanges"], 1):
            lines.append(f"【対話{i}】")
            lines.append(f"ユーザー: {exchange['user']}")
            lines.append(f"Duckflow: {exchange['duckflow']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_file_operations(self, log: Dict) -> str:
        """ファイル操作履歴を整形
        
        Args:
            log: ログデータ
            
        Returns:
            整形されたファイル操作履歴
        """
        if not log.get("files_created"):
            return "ファイル操作なし"
        
        lines = []
        for file_op in log["files_created"]:
            lines.append(f"- {file_op['operation']}: {file_op['file_path']}")
            if file_op.get("content_preview"):
                lines.append(f"  内容プレビュー: {file_op['content_preview'][:100]}...")
        
        return "\n".join(lines)
    
    def _format_statistics(self, log: Dict) -> str:
        """統計情報を整形
        
        Args:
            log: ログデータ
            
        Returns:
            整形された統計情報
        """
        stats = log.get("statistics", {})
        if not stats:
            return "統計情報なし"
        
        return f"""- 総対話数: {stats.get('total_exchanges', 0)}回
- 対話時間: {stats.get('duration_seconds', 0):.1f}秒
- 作成ファイル数: {stats.get('total_files_created', 0)}個
- エラー数: {stats.get('total_errors', 0)}個
- 完了ステータス: {log.get('completion_status', 'unknown')}"""
    
    def _parse_evaluation_result(self, llm_response: str, log: Dict) -> Dict:
        """評価結果をパース
        
        Args:
            llm_response: LLMからの応答
            log: 元のログデータ
            
        Returns:
            パースされた評価結果
        """
        try:
            # JSONブロックを抽出
            json_start = llm_response.find("```json")
            json_end = llm_response.find("```", json_start + 7)
            
            if json_start != -1 and json_end != -1:
                json_text = llm_response[json_start + 7:json_end].strip()
            else:
                # JSONブロックが見つからない場合、全体をJSONとして試行
                json_text = llm_response.strip()
            
            # JSONパース
            evaluation_data = json.loads(json_text)
            
            # 基本情報を追加
            result = {
                "evaluation_timestamp": log.get("end_time"),
                "scenario_name": log.get("scenario_name"),
                "session_id": log.get("session_id"),
                "evaluator_version": "1.0.0",
                "evaluation": evaluation_data
            }
            
            # 合格判定
            overall_score = evaluation_data.get("overall_score", {}).get("score", 0)
            result["passed"] = overall_score >= 3.0
            
            return result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse evaluation JSON: {e}")
            return self._create_fallback_evaluation(llm_response, log)
        except Exception as e:
            self.logger.error(f"Error parsing evaluation result: {e}")
            return self._create_error_evaluation(str(e))
    
    def _create_fallback_evaluation(self, raw_response: str, log: Dict) -> Dict:
        """JSONパースに失敗した場合のフォールバック評価
        
        Args:
            raw_response: 生の応答
            log: ログデータ
            
        Returns:
            フォールバック評価結果
        """
        return {
            "evaluation_timestamp": log.get("end_time"),
            "scenario_name": log.get("scenario_name"),
            "session_id": log.get("session_id"),
            "evaluator_version": "1.0.0",
            "evaluation": {
                "scenario_achievement": {"score": 2, "reason": "評価解析エラー"},
                "conversation_naturalness": {"score": 2, "reason": "評価解析エラー"},
                "technical_accuracy": {"score": 2, "reason": "評価解析エラー"},
                "error_handling": {"score": 2, "reason": "評価解析エラー"},
                "overall_score": {"score": 2, "reason": "評価解析エラー"},
                "improvement_suggestions": ["評価システムの改善が必要"],
                "positive_aspects": []
            },
            "passed": False,
            "evaluation_error": "JSON解析エラー",
            "raw_response": raw_response[:500]  # 最初の500文字のみ保存
        }
    
    def _create_error_evaluation(self, error_message: str) -> Dict:
        """エラー時の評価結果を作成
        
        Args:
            error_message: エラーメッセージ
            
        Returns:
            エラー評価結果
        """
        return {
            "evaluation_timestamp": None,
            "scenario_name": "unknown",
            "session_id": "unknown",
            "evaluator_version": "1.0.0",
            "evaluation": {
                "scenario_achievement": {"score": 1, "reason": "評価実行エラー"},
                "conversation_naturalness": {"score": 1, "reason": "評価実行エラー"},
                "technical_accuracy": {"score": 1, "reason": "評価実行エラー"},
                "error_handling": {"score": 1, "reason": "評価実行エラー"},
                "overall_score": {"score": 1, "reason": "評価実行エラー"},
                "improvement_suggestions": ["評価システムのエラー修正が必要"],
                "positive_aspects": []
            },
            "passed": False,
            "evaluation_error": error_message
        }
"""
LLMCallManager - Phase 2: 基本的なLLM呼び出し
DuckFlowのLLM呼び出し管理システムを実装する
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime


class LLMCallManager:
    """基本的なLLM呼び出しを管理"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.max_retries = 3
        self.timeout_seconds = 30
        self.call_history = []
        self.max_history = 10
    
    def call_llm(self, prompt: str, 
                  expected_format: str = "json",
                  temperature: float = 0.7,
                  max_tokens: int = 1000) -> Dict[str, Any]:
        """LLMを呼び出し"""
        try:
            self.logger.info(f"LLM呼び出し開始: {len(prompt)}文字, 形式: {expected_format}")
            
            # 呼び出し履歴に記録
            call_record = {
                'timestamp': datetime.now().isoformat(),
                'prompt_length': len(prompt),
                'expected_format': expected_format,
                'temperature': temperature,
                'max_tokens': max_tokens
            }
            
            # 実際のLLM呼び出し（現在はモック）
            response = self._mock_llm_call(prompt, expected_format, temperature, max_tokens)
            
            # 呼び出し結果を記録
            call_record['success'] = response.get('success', False)
            call_record['response_length'] = len(str(response.get('content', '')))
            call_record['processing_time'] = response.get('processing_time', 0)
            
            self._add_to_history(call_record)
            
            if response.get('success'):
                self.logger.info(f"LLM呼び出し成功: {response.get('processing_time', 0)}ms")
            else:
                self.logger.error(f"LLM呼び出し失敗: {response.get('error', 'Unknown error')}")
            
            return response
            
        except Exception as e:
            self.logger.error(f"LLM呼び出しエラー: {e}")
            return {
                'success': False,
                'error': str(e),
                'content': None,
                'processing_time': 0
            }
    
    def _mock_llm_call(self, prompt: str, 
                       expected_format: str,
                       temperature: float,
                       max_tokens: int) -> Dict[str, Any]:
        """モックLLM呼び出し（実際のLLM統合前の仮実装）"""
        import time
        start_time = time.time()
        
        # プロンプトの内容に基づいて適切な応答を生成
        if "実装計画" in prompt or "実装" in prompt:
            mock_response = self._generate_implementation_response(prompt)
        elif "計画" in prompt or "プラン" in prompt:
            mock_response = self._generate_planning_response(prompt)
        elif "設計" in prompt or "アーキテクチャ" in prompt:
            mock_response = self._generate_design_response(prompt)
        else:
            mock_response = self._generate_generic_response(prompt)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return {
            'success': True,
            'content': mock_response,
            'processing_time': processing_time,
            'format': expected_format,
            'temperature': temperature,
            'max_tokens': max_tokens
        }
    
    def _generate_implementation_response(self, prompt: str) -> str:
        """実装関連の応答を生成"""
        if "json" in prompt.lower():
            return json.dumps({
                "rationale": "実装計画の作成と実行",
                "goal_consistency": "yes - ユーザーの実装要求と一致",
                "constraint_check": "yes - 安全なファイル操作のみ実行",
                "next_step": "continue",
                "step": "EXECUTION",
                "state_delta": "ステップをPLANNINGからEXECUTIONに変更"
            }, ensure_ascii=False, indent=2)
        else:
            return """実装計画を作成し、実行を開始します。

1. プロジェクト構成の確認
2. 必要なファイルの作成
3. 基本構造の実装
4. テストと検証

安全な実装を進めます。"""
    
    def _generate_planning_response(self, prompt: str) -> str:
        """計画関連の応答を生成"""
        if "json" in prompt.lower():
            return json.dumps({
                "rationale": "計画の作成と検討",
                "goal_consistency": "yes - 計画作成要求と一致",
                "constraint_check": "yes - 制約内での計画作成",
                "next_step": "pending_user",
                "step": "PLANNING",
                "state_delta": "計画作成完了、ユーザー確認待ち"
            }, ensure_ascii=False, indent=2)
        else:
            return """計画を作成しました。

詳細な実装手順を含む包括的な計画を提案します。
ご確認いただければ、次のステップに進みます。"""
    
    def _generate_design_response(self, prompt: str) -> str:
        """設計関連の応答を生成"""
        if "json" in prompt.lower():
            return json.dumps({
                "rationale": "設計の提案と検討",
                "goal_consistency": "yes - 設計要求と一致",
                "constraint_check": "yes - 制約内での設計提案",
                "next_step": "continue",
                "step": "PLANNING",
                "state_delta": "設計提案完了、詳細検討中"
            }, ensure_ascii=False, indent=2)
        else:
            return """設計を提案します。

アーキテクチャ、コンポーネント、インターフェースを含む
包括的な設計を提供します。"""
    
    def _generate_generic_response(self, prompt: str) -> str:
        """汎用的な応答を生成"""
        if "json" in prompt.lower():
            return json.dumps({
                "rationale": "一般的な要求の処理",
                "goal_consistency": "yes - 要求と一致",
                "constraint_check": "yes - 制約内での処理",
                "next_step": "continue",
                "step": "PLANNING",
                "state_delta": "要求処理中"
            }, ensure_ascii=False, indent=2)
        else:
            return """要求を処理中です。

適切な対応を検討し、実行します。"""
    
    def _add_to_history(self, call_record: Dict[str, Any]):
        """呼び出し履歴に追加"""
        self.call_history.append(call_record)
        
        # 最大履歴数を制限
        if len(self.call_history) > self.max_history:
            self.call_history = self.call_history[-self.max_history:]
    
    def get_call_statistics(self) -> Dict[str, Any]:
        """呼び出し統計を取得"""
        if not self.call_history:
            return {
                'total_calls': 0,
                'success_rate': 0.0,
                'average_processing_time': 0.0,
                'total_tokens': 0
            }
        
        total_calls = len(self.call_history)
        successful_calls = sum(1 for call in self.call_history if call.get('success', False))
        success_rate = successful_calls / total_calls if total_calls > 0 else 0.0
        
        processing_times = [call.get('processing_time', 0) for call in self.call_history]
        average_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0.0
        
        total_tokens = sum(call.get('response_length', 0) for call in self.call_history)
        
        return {
            'total_calls': total_calls,
            'success_rate': success_rate,
            'average_processing_time': average_processing_time,
            'total_tokens': total_tokens
        }
    
    def clear_history(self):
        """呼び出し履歴をクリア"""
        self.call_history.clear()
        self.logger.info("LLM呼び出し履歴をクリアしました")
    
    def validate_response_format(self, response: str, expected_format: str) -> bool:
        """応答形式を検証"""
        try:
            if expected_format.lower() == "json":
                json.loads(response)
                return True
            elif expected_format.lower() == "text":
                return len(response.strip()) > 0
            else:
                return True  # 不明な形式は検証スキップ
        except Exception as e:
            self.logger.warning(f"応答形式検証失敗: {e}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で取得"""
        return {
            'max_retries': self.max_retries,
            'timeout_seconds': self.timeout_seconds,
            'max_history': self.max_history,
            'statistics': self.get_call_statistics()
        }

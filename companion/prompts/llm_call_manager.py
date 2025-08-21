"""
LLMCallManager - Phase 2: 基本的なLLM呼び出し
DuckFlowのLLM呼び出し管理システムを実装する
"""

import json
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

from .prompt_context_service import PromptPattern


class LLMCallManager:
    """基本的なLLM呼び出しを管理"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.max_retries = 3
        self.timeout_seconds = 30
        self.call_history = []
        self.max_history = 10
        
        # 本番環境チェック
        self.is_production = self._check_production_environment()
        
        try:
            # 設定反映（存在すれば）
            from ..config.config_manager import config_manager
            cfg = config_manager.get_config()
            # LLM関連の設定
            self.timeout_seconds = int(getattr(cfg, 'llm_timeout_seconds', self.timeout_seconds))
            self.max_retries = int(getattr(cfg, 'llm_max_retries', self.max_retries))
        except Exception:
            pass
    
    def _check_production_environment(self) -> bool:
        """本番環境かどうかをチェック"""
        try:
            # 環境変数で本番環境フラグをチェック
            if os.getenv('DUCKFLOW_ENV') == 'production':
                return True
            
            # APIキーの存在で本番環境と判断
            api_keys = [
                'OPENAI_API_KEY',
                'ANTHROPIC_API_KEY', 
                'GROQ_API_KEY',
                'OPENROUTER_API_KEY'
            ]
            
            for key in api_keys:
                if os.getenv(key):
                    return True
            
            # 開発環境の場合はFalse
            return False
            
        except Exception as e:
            self.logger.warning(f"環境チェックエラー: {e}")
            # エラーの場合は安全側に倒して本番環境とみなす
            return True
    
    def call_llm(self, prompt: str, 
                  expected_format: str = "json",
                  temperature: float = 0.7,
                  max_tokens: int = 1000,
                  retries: Optional[int] = None,
                  timeout_seconds: Optional[int] = None) -> Dict[str, Any]:
        """LLMを呼び出し（従来の互換性維持）"""
        return self.call(
            mode="general",
            input_text=prompt,
            system_prompt="",
            pattern=PromptPattern.BASE_MAIN,
            expected_format=expected_format,
            temperature=temperature,
            max_tokens=max_tokens,
            retries=retries,
            timeout_seconds=timeout_seconds
        )
    
    async def call(self, mode: str, input_text: str, system_prompt: str, 
                   pattern: PromptPattern = PromptPattern.BASE_MAIN, **kwargs) -> str:
        """統一されたLLM呼び出し（新規実装）"""
        try:
            self.logger.info(f"統一LLM呼び出し開始: mode={mode}, pattern={pattern.value}")
            
            # プロンプト合成
            full_prompt = self._compose_prompt(mode, input_text, system_prompt, pattern)
            
            # パラメータ設定
            expected_format = kwargs.get('expected_format', 'text')
            temperature = kwargs.get('temperature', 0.7)
            max_tokens = kwargs.get('max_tokens', 1000)
            retries = kwargs.get('retries', self.max_retries)
            timeout_seconds = kwargs.get('timeout_seconds', self.timeout_seconds)
            
            # LLM呼び出し
            response = await self._call_llm_async(full_prompt, mode, expected_format, 
                                                temperature, max_tokens, retries, timeout_seconds)
            
            # 結果検証・後処理
            processed_response = self._post_process(response, mode)
            
            # ログ記録
            self._log_call(mode, pattern, len(full_prompt), len(processed_response))
            
            return processed_response
            
        except Exception as e:
            self.logger.error(f"統一LLM呼び出しエラー: {e}")
            return f"LLM呼び出しエラー: {str(e)}"
    
    def _compose_prompt(self, mode: str, input_text: str, system_prompt: str, pattern: PromptPattern) -> str:
        """モード別プロンプト合成"""
        try:
            if not system_prompt:
                # system_promptが空の場合はinput_textをそのまま使用
                return input_text
            
            if mode == "summarize":
                return f"{system_prompt}\n\n以下の内容を要約してください:\n{input_text}"
            elif mode == "extract":
                return f"{system_prompt}\n\n以下の内容から指定された情報を抽出してください:\n{input_text}"
            elif mode == "generate_content":
                return f"{system_prompt}\n\n以下の要求に基づいて内容を生成してください:\n{input_text}"
            elif mode == "plan":
                return f"{system_prompt}\n\n以下の要求に基づいて計画を立案してください:\n{input_text}"
            elif mode == "conversation_summarize":
                return f"{system_prompt}\n\n以下の会話履歴を要約してください:\n{input_text}"
            else:
                # デフォルト: 一般的な応答生成
                return f"{system_prompt}\n\n{input_text}"
                
        except Exception as e:
            self.logger.error(f"プロンプト合成エラー: {e}")
            return input_text
    
    async def _call_llm_async(self, full_prompt: str, mode: str, expected_format: str,
                             temperature: float, max_tokens: int, retries: int, 
                             timeout_seconds: int) -> Dict[str, Any]:
        """非同期LLM呼び出し"""
        try:
            # 本番環境では絶対にモックLLMを使用しない
            if self.is_production:
                return await self._call_real_llm(
                    prompt=full_prompt,
                    expected_format=expected_format,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    retries=retries,
                    timeout_seconds=timeout_seconds
                )
            else:
                # 開発環境でのみモックLLMを使用
                self.logger.info("開発環境: モックLLMを使用")
                return self._mock_llm_call(
                    prompt=full_prompt,
                    expected_format=expected_format,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
        except Exception as e:
            self.logger.error(f"非同期LLM呼び出しエラー: {e}")
            return {
                'success': False,
                'error': str(e),
                'content': None,
                'processing_time': 0
            }
    
    async def _call_real_llm(self, prompt: str, expected_format: str,
                            temperature: float, max_tokens: int, retries: int,
                            timeout_seconds: int) -> Dict[str, Any]:
        """実LLMを呼び出し（本番環境用）"""
        try:
            # 実LLMクライアントを使用
            from ..base.llm_client import llm_manager
            
            # モッククライアントがデフォルトの場合はエラー
            if llm_manager.is_mock_client():
                raise Exception("本番環境ではモックLLMは使用できません。実LLMのAPIキーを設定してください。")
            
            # 実LLMで生成
            response = await llm_manager.generate(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return {
                'success': True,
                'content': response,
                'processing_time': 0,  # 実際の処理時間は計測できない
                'format': expected_format
            }
            
        except Exception as e:
            self.logger.error(f"実LLM呼び出しエラー: {e}")
            return {
                'success': False,
                'error': str(e),
                'content': None,
                'processing_time': 0
            }
    
    def _post_process(self, response: Dict[str, Any], mode: str) -> str:
        """レスポンスの後処理"""
        try:
            if not response.get('success', False):
                error_msg = response.get('error', 'Unknown error')
                return f"LLM呼び出し失敗: {error_msg}"
            
            content = response.get('content', '')
            if not content:
                return "LLMからの応答が空です"
            
            # モード別の後処理
            if mode == "summarize":
                return self._post_process_summary(content)
            elif mode == "extract":
                return self._post_process_extraction(content)
            elif mode == "generate_content":
                return self._post_process_generated_content(content)
            else:
                return str(content)
                
        except Exception as e:
            self.logger.error(f"後処理エラー: {e}")
            return str(response.get('content', '後処理エラー'))
    
    def _post_process_summary(self, content: str) -> str:
        """要約結果の後処理"""
        try:
            # 要約の品質チェック
            if len(content.strip()) < 10:
                return "要約が短すぎます。再度生成してください。"
            
            # 不要なプレフィックスを除去
            prefixes_to_remove = ["要約:", "Summary:", "以下が要約です:", "要約結果:"]
            for prefix in prefixes_to_remove:
                if content.startswith(prefix):
                    content = content[len(prefix):].strip()
            
            return content
            
        except Exception as e:
            self.logger.error(f"要約後処理エラー: {e}")
            return content
    
    def _post_process_extraction(self, content: str) -> str:
        """抽出結果の後処理"""
        try:
            # JSON形式の場合はパースして整形
            if content.strip().startswith('{'):
                try:
                    parsed = json.loads(content)
                    return json.dumps(parsed, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    pass
            
            return content
            
        except Exception as e:
            self.logger.error(f"抽出後処理エラー: {e}")
            return content
    
    def _post_process_generated_content(self, content: str) -> str:
        """生成内容の後処理"""
        try:
            # 生成内容の品質チェック
            if len(content.strip()) < 5:
                return "生成された内容が短すぎます。再度生成してください。"
            
            return content
            
        except Exception as e:
            self.logger.error(f"生成内容後処理エラー: {e}")
            return content
    
    def _log_call(self, mode: str, pattern: PromptPattern, prompt_length: int, response_length: int):
        """呼び出しログを記録"""
        try:
            log_record = {
                'timestamp': datetime.now().isoformat(),
                'mode': mode,
                'pattern': pattern.value,
                'prompt_length': prompt_length,
                'response_length': response_length
            }
            
            self._add_to_history(log_record)
            self.logger.info(f"LLM呼び出し記録: {mode}/{pattern.value}, "
                           f"プロンプト: {prompt_length}文字, レスポンス: {response_length}文字")
            
        except Exception as e:
            self.logger.error(f"ログ記録エラー: {e}")
    
    def _mock_llm_call(self, prompt: str, expected_format: str, 
                       temperature: float, max_tokens: int) -> Dict[str, Any]:
        """モックLLM呼び出し（開発・テスト用）"""
        import time
        import random
        
        start_time = time.time()
        
        # モック応答生成
        if expected_format == "json":
            mock_response = {
                "status": "success",
                "message": "モック応答",
                "timestamp": datetime.now().isoformat()
            }
            content = json.dumps(mock_response, ensure_ascii=False)
        else:
            content = f"これはモックLLMの応答です。\nプロンプト長: {len(prompt)}文字\n温度: {temperature}\n最大トークン: {max_tokens}"
        
        # 処理時間をシミュレート
        processing_time = random.randint(100, 500)  # 100-500ms
        
        time.sleep(processing_time / 1000)  # 実際に待機
        
        return {
            'success': True,
            'content': content,
            'processing_time': processing_time,
            'format': expected_format
        }
    
    def validate_response_format(self, content: str, expected_format: str) -> bool:
        """応答形式を検証"""
        try:
            if expected_format == "json":
                # JSON形式の検証
                json.loads(content)
                return True
            elif expected_format == "text":
                # テキスト形式の検証（空でなければOK）
                return bool(content and content.strip())
            else:
                # その他の形式は常にOK
                return True
        except Exception:
            return False
    
    def _add_to_history(self, record: Dict[str, Any]):
        """呼び出し履歴に追加"""
        try:
            self.call_history.append(record)
            if len(self.call_history) > self.max_history:
                self.call_history = self.call_history[-self.max_history:]
        except Exception as e:
            self.logger.error(f"履歴追加エラー: {e}")
    
    def get_call_statistics(self) -> Dict[str, Any]:
        """呼び出し統計を取得"""
        try:
            if not self.call_history:
                return {'total_calls': 0, 'success_rate': 0.0}
            
            total_calls = len(self.call_history)
            successful_calls = sum(1 for call in self.call_history if call.get('success', False))
            success_rate = successful_calls / total_calls if total_calls > 0 else 0.0
            
            # 平均処理時間
            processing_times = [call.get('processing_time', 0) for call in self.call_history if call.get('processing_time')]
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
            
            # 平均プロンプト長
            prompt_lengths = [call.get('prompt_length', 0) for call in self.call_history if call.get('prompt_length')]
            avg_prompt_length = sum(prompt_lengths) / len(prompt_lengths) if prompt_lengths else 0
            
            return {
                'total_calls': total_calls,
                'successful_calls': successful_calls,
                'success_rate': success_rate,
                'avg_processing_time_ms': avg_processing_time,
                'avg_prompt_length': avg_prompt_length,
                'last_call_time': self.call_history[-1]['timestamp'] if self.call_history else None
            }
        except Exception as e:
            self.logger.error(f"統計取得エラー: {e}")
            return {'total_calls': 0, 'success_rate': 0.0, 'error': str(e)}
    
    def clear_history(self):
        """呼び出し履歴をクリア"""
        try:
            self.call_history.clear()
            self.logger.info("呼び出し履歴をクリアしました")
        except Exception as e:
            self.logger.error(f"履歴クリアエラー: {e}")
    
    def get_recent_calls(self, count: int = 5) -> List[Dict[str, Any]]:
        """最近の呼び出し履歴を取得"""
        try:
            return self.call_history[-count:] if self.call_history else []
        except Exception as e:
            self.logger.error(f"最近の呼び出し取得エラー: {e}")
            return []

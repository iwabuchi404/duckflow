# companion/llm_call_manager.py
"""
LLM API呼び出しを管理するモジュール。
実際のLLM APIを使用してJSON応答を取得し、フォールバックとして
キーワードベースのダミー応答もサポート。
"""
import logging
import json
import asyncio
from typing import Dict, Any, Optional
from .llm.llm_client import LLMClient, LLMProvider
from .base.llm_client import MockLLMClient, LLMRequest, ExternalManagerClient, LLMClientError

class LLMCallManager:
    def __init__(self, use_real_llm: bool = True):
        self.logger = logging.getLogger(__name__)
        self.use_real_llm = use_real_llm
        self.llm_client: Optional[LLMClient] = None
        self.mock_client: Optional[MockLLMClient] = None
        self.external_client: Optional[ExternalManagerClient] = None
        
        if use_real_llm:
            try:
                # 既存のLLMClient（設定ファイル自動読み込み）を使用
                self.llm_client = LLMClient()  # 設定ファイルから自動的にプロバイダーとAPIキーを読み込み
                self.logger.info(f"LLMCallManager が {self.llm_client.provider.value} で初期化されました。")
            except Exception as e:
                self.logger.warning(f"LLMClient初期化失敗: {e}")
                try:
                    # 外部LLMマネージャーを試行
                    self.external_client = ExternalManagerClient("external")
                    self.logger.info("LLMCallManager が外部LLMで初期化されました。")
                except Exception as e2:
                    self.logger.warning(f"外部LLM初期化失敗: {e2}")
                    # 最後のフォールバックとしてMockLLMClientを使用
                    self.mock_client = MockLLMClient()
                    self.logger.info("LLMCallManager がMockLLMで初期化されました。")
        else:
            self.mock_client = MockLLMClient()
            self.logger.info("LLMCallManager がダミーモードで初期化されました。")

    async def call(self, system_prompt: str, user_prompt: str, tools: list = None, tool_choice: str = "auto") -> str:
        """
        LLMを呼び出す。
        実際のLLM APIを使用し、失敗時はダミー応答を返す。
        """
        self.logger.info("LLM呼び出し開始...")
        
        # 実際LLMを使用する場合
        if self.use_real_llm and (self.llm_client or self.external_client):
            try:
                return await self._call_real_llm(system_prompt, user_prompt, tools, tool_choice)
            except Exception as e:
                self.logger.error(f"実際LLM呼び出し失敗: {e}")
                self.logger.info("フォールバック: ダミーモードで実行")
                return await self._call_dummy_llm(system_prompt, user_prompt)
        else:
            return await self._call_dummy_llm(system_prompt, user_prompt)
    
    async def _call_real_llm(self, system_prompt: str, user_prompt: str, tools: list = None, tool_choice: str = "auto") -> str:
        """実際のLLM APIを呼び出す"""
        self.logger.info("実際LLM APIへの呼び出し...")
        
        # プロンプトを結合
        combined_prompt = f"""{system_prompt}

---

{user_prompt}"""
        
        try:
            # 既存のLLMClientを優先
            if self.llm_client:
                # 既存のLLMClientのchatメソッドを使用
                # ツール呼び出し対応の引数を準備
                chat_args = {
                    "prompt": user_prompt,
                    "system_prompt": system_prompt,
                    "temperature": 0.3,  # JSON出力のため低めに設定
                    "max_tokens": 2000
                }
                
                # ツールが指定されている場合は追加
                if tools:
                    chat_args["tools"] = tools
                    chat_args["tool_choice"] = tool_choice
                
                response = await self.llm_client.chat(**chat_args)
                
                # レスポンスのNullチェック
                if response is None:
                    raise LLMClientError("LLMClientからNullレスポンスが返されました")
                
                if response.content is None:
                    raise LLMClientError("LLMレスポンスのcontentがNullです")
                
                # デバッグ用ログ
                self.logger.info(f"LLMClient レスポンス内容（文字数: {len(response.content)}）: {response.content[:100]}...")
                
                return response.content
            
            # 外部クライアントを次に試行
            elif self.external_client:
                request = LLMRequest(
                    prompt=combined_prompt,
                    model="external",
                    temperature=0.3,
                    max_tokens=2000,
                    metadata={'system_prompt': system_prompt}
                )
                response = await self.external_client.generate(request)
                return response.content
            
            else:
                raise LLMClientError("利用可能なLLMクライアントがありません")
                
        except Exception as e:
            self.logger.error(f"LLM API呼び出しエラー: {e}")
            raise
    
    async def _call_dummy_llm(self, system_prompt: str, user_prompt: str) -> str:
        """ダミーLLM応答を生成（フォールバック）"""
        self.logger.info("ダミーLLMモードで実行...")
        
        # MockLLMClientがある場合はそれを使用
        if self.mock_client:
            combined_prompt = f"""{system_prompt}

---

{user_prompt}"""
            request = LLMRequest(
                prompt=combined_prompt,
                temperature=0.3,
                max_tokens=2000,
                metadata={'system_prompt': system_prompt}
            )
            response = await self.mock_client.generate(request)
            return response.content

        # --- キーワードベースのダミー応答ロジック ---
        user_input_lower = user_prompt.lower()
        
        # user_promptから現在の状態を簡易的に解析
        try:
            state_json_str = user_prompt.split("### 現在の状態:")[1].split("### ユーザーの要求:")[0].strip()
            current_state = json.loads(state_json_str)
            active_plan = current_state.get("active_plan")
        except (IndexError, json.JSONDecodeError):
            active_plan = None

        # 状態に応じた分岐ロジック
        if active_plan and ("進めて" in user_input_lower or "実装" in user_input_lower):
            # プランがあり、実行を促された場合 -> task_tool.generate_list を呼び出す
            # 最初の未完了ステップを探す
            plan_id = active_plan.get("plan_id", "")
            # この仮実装ではステップIDをハードコード
            next_step_id = "step_001" # 本来はAgentStateから動的に取得
            response_json = {
                "action_list": [
                    {
                        "operation": "task_tool.generate_list",
                        "args": {"step_id": next_step_id},
                        "reasoning": f"アクティブなプラン'{active_plan.get('name')}'の次のステップ'{next_step_id}'のタスクを生成します。"
                    }
                ]
            }
        # ファイル読み取りの意図を模倣
        elif "game_doc.md" in user_input_lower and ("見て" in user_input_lower or "概要" in user_input_lower or "把握" in user_input_lower):
            file_path = "game_doc.md" # 簡易抽出
            response_json = {
                "action_list": [
                    {
                        "operation": "file_ops.read_file",
                        "args": {"file_path": file_path},
                        "reasoning": f"ユーザーが {file_path} の概要を求めているため、まずファイルを読み込みます。"
                    }
                ]
            }
        # 計画提案の意図を模倣
        elif "計画" in user_input_lower or "プラン" in user_input_lower:
             response_json = {
                "action_list": [
                    {
                        "operation": "plan_tool.propose",
                        "args": {"user_goal": user_prompt.split("### ユーザーの要求:")[-1].strip()},
                        "reasoning": "ユーザーが計画の立案を要求しているため。"
                    }
                ]
            }
        # その他の場合は「不明」
        else:
            response_json = {
                "action_list": [
                    {
                        "operation": "response.echo",
                        "args": {"message": "すみません、よく分かりませんでした。"},
                        "reasoning": "ユーザーの意図を特定できませんでした。"
                    }
                ]
            }
        
        return json.dumps(response_json)

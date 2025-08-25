"""
IntentAnalyzerLLM - 意図理解器
ユーザー入力を解析し、上位意図とprompt_patternを決定
ファイル名抽出機能も統合
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from ..state.agent_state import AgentState
from ..prompts.prompt_context_service import PromptPattern
from ..llm.llm_client import LLMClient, LLMProvider


class ActionType(Enum):
    """アクションタイプの定義"""
    FILE_OPERATION = "file_operation"
    PLAN_GENERATION = "plan_generation"
    DIRECT_RESPONSE = "direct_response"
    CODE_EXECUTION = "code_execution"
    SUMMARY_GENERATION = "summary_generation"
    CONTENT_EXTRACTION = "content_extraction"


class SpecializedDomain(Enum):
    """専門領域の定義"""
    FILE_ANALYSIS = "file_analysis"
    CODE_REVIEW = "code_review"
    PLANNING = "planning"
    EXECUTION = "execution"
    REVIEW = "review"


@dataclass
class ToolOperation:
    """ツール操作の定義"""
    operation: str
    args: Dict[str, Any]


@dataclass
class IntentAnalysisResult:
    """意図分析結果"""
    action_type: ActionType
    prompt_pattern: PromptPattern
    tool_operations: List[ToolOperation]
    file_target: Optional[str]
    require_approval: bool
    confidence: float
    reasoning: str
    specialized_domain: Optional[SpecializedDomain]
    user_input: str  # 元のユーザー入力を保持


class IntentAnalyzerLLM:
    """LLMベースの意図理解器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # 設定ファイルから自動的にプロバイダーを選択
        self.llm_client = LLMClient()
        
        # 信頼度閾値設定
        self.confidence_thresholds = {
            "high": 0.8,
            "medium": 0.6,
            "low": 0.4
        }
    
    async def analyze(self, user_input: str, agent_state: AgentState, 
                     context: Optional[str] = None) -> IntentAnalysisResult:
        """ユーザー入力を解析して意図を理解"""
        try:
            self.logger.info(f"意図分析開始: {user_input[:100]}...")
            
            # LLMによる意図分析
            analysis_prompt = self._build_analysis_prompt(user_input, agent_state, context)
            llm_response = await self.llm_client.chat(analysis_prompt)
            
            # レスポンスの検証
            if not llm_response or not llm_response.content:
                self.logger.warning("LLMレスポンスが空または無効です")
                return self._get_fallback_result(user_input, agent_state)
            
            # レスポンスをパース
            parsed_result = self._parse_llm_response(llm_response.content)
            
            # 結果を検証・補完
            validated_result = self._validate_and_complete_result(parsed_result, user_input, agent_state)
            
            self.logger.info(f"意図分析完了: {validated_result.action_type.value}, "
                           f"信頼度: {validated_result.confidence}")
            
            return validated_result
            
        except Exception as e:
            self.logger.error(f"意図分析エラー: {e}")
            return self._get_fallback_result(user_input, agent_state)
    
    def _build_analysis_prompt(self, user_input: str, agent_state: AgentState, 
                              context: Optional[str]) -> str:
        """意図分析用のプロンプトを構築（改善版）"""
        
        # 基本プロンプト
        base_prompt = """あなたはDuckFlowの意図理解器です。
ユーザーの入力を分析し、以下のJSON形式で回答してください。

ユーザー入力: {user_input}

現在の状態:
- Step: {current_step}
- Status: {current_status}
- 作業ディレクトリ: {work_dir}
- セッションID: {session_id}

以下のJSON形式で回答してください（必ず有効なJSONとして出力）:
{{
    "action_type": "file_operation|plan_generation|direct_response|code_execution|summary_generation|content_extraction",
    "prompt_pattern": "base_specialized|base_main|base_main_specialized",
    "tool_operations": [
        {{
            "operation": "read|write|create|delete|list|exists|summarize|extract|run",
            "args": {{
                "file_target": "ファイル名（例: game_doc.md）",
                "content": "内容（必要に応じて）",
                "options": {{}}
            }}
        }}
    ],
    "file_target": "ファイル名（操作対象がある場合）",
    "require_approval": false,
    "confidence": 0.87,
    "reasoning": "なぜこの判断をしたかの理由",
    "specialized_domain": "file_analysis|code_review|planning|execution|review"
}}

重要:
1. ファイル名抽出: ユーザー入力から操作対象のファイル名を正確に抽出
2. 信頼度: 0.0-1.0の範囲で設定（高いほど確信）
3. 承認要否: 書き込み・削除・実行系はtrue
4. プロンプトパターン: 軽量処理はbase_specialized、複雑処理はbase_main_specialized
5. 専門領域: 現在のStep/Statusに応じて適切に設定
6. 必ず有効なJSONとして出力し、文字列の終端を正しく処理してください"""

        # コンテキスト情報を追加
        context_info = ""
        if context:
            context_info = f"\n追加コンテキスト:\n{context}"
        
        # 会話履歴を追加（最新3件）
        conversation_context = ""
        if hasattr(agent_state, 'conversation_history') and agent_state.conversation_history:
            recent_messages = agent_state.conversation_history[-3:]
            conversation_context = "\n最近の会話:\n"
            for msg in recent_messages:
                role = "ユーザー" if msg.role == "user" else "アシスタント"
                content = getattr(msg, 'content', '')
                if content:
                    conversation_context += f"- {role}: {content[:100]}...\n"
        
        # 固定5項目の情報を追加
        fixed_five_context = ""
        if hasattr(agent_state, 'goal') and agent_state.goal:
            fixed_five_context += f"\n目標: {agent_state.goal}"
        if hasattr(agent_state, 'why_now') and agent_state.why_now:
            fixed_five_context += f"\nなぜ今やるのか: {agent_state.why_now}"
        if hasattr(agent_state, 'constraints') and agent_state.constraints:
            fixed_five_context += f"\n制約: {', '.join(agent_state.constraints)}"
        if hasattr(agent_state, 'plan_brief') and agent_state.plan_brief:
            fixed_five_context += f"\n直近の計画: {', '.join(agent_state.plan_brief)}"
        if hasattr(agent_state, 'open_questions') and agent_state.open_questions:
            fixed_five_context += f"\n未解決の問い: {', '.join(agent_state.open_questions)}"
        
        # プロンプトを完成
        prompt = base_prompt.format(
            user_input=user_input,
            current_step=getattr(agent_state, 'step', 'IDLE'),
            current_status=getattr(agent_state, 'status', 'PENDING'),
            work_dir=self._get_work_dir_safely(agent_state),
            session_id=getattr(agent_state, 'session_id', 'unknown')
        )
        
        prompt += context_info + conversation_context + fixed_five_context
        
        # 最終的な指示を追加
        prompt += "\n\n重要: 上記のJSONを正確に出力してください。文字列の終端を正しく処理し、有効なJSONとして出力してください。"
        
        return prompt
    
    def _parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """LLMレスポンスをパース（強化版）"""
        try:
            # レスポンスの前処理
            cleaned_response = self._clean_llm_response(llm_response)
            
            # JSON部分を抽出（複数の方法を試行）
            json_data = self._extract_json_from_response(cleaned_response)
            
            if json_data:
                # 必須フィールドの検証
                required_fields = ['action_type', 'prompt_pattern', 'confidence']
                for field in required_fields:
                    if field not in json_data:
                        self.logger.warning(f"必須フィールドが不足: {field}")
                        json_data[field] = self._get_default_value_for_field(field)
                
                return json_data
            else:
                raise ValueError("JSON形式が見つかりません")
                
        except Exception as e:
            self.logger.error(f"LLMレスポンスパースエラー: {e}")
            # フォールバック処理
            return self._create_fallback_json_response(llm_response)
    
    def _clean_llm_response(self, response: str) -> str:
        """LLMレスポンスをクリーニング"""
        try:
            # 前後の空白を除去
            cleaned = response.strip()
            
            # マークダウンブロック記号を除去
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            
            # 改行文字を正規化
            cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
            
            return cleaned.strip()
            
        except Exception as e:
            self.logger.warning(f"レスポンスクリーニングエラー: {e}")
            return response
    
    def _extract_json_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """レスポンスからJSONを抽出（複数方法）"""
        try:
            # 方法1: 直接JSONパース
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                pass
            
            # 方法2: 中括弧で囲まれた部分を探す
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
            
            # 方法3: 行ごとにJSONを探す
            lines = response.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('{') and line.endswith('}'):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
            
            # 方法4: 部分的なJSON修復を試行
            return self._repair_partial_json(response)
            
        except Exception as e:
            self.logger.warning(f"JSON抽出エラー: {e}")
            return None
    
    def _repair_partial_json(self, response: str) -> Optional[Dict[str, Any]]:
        """部分的なJSONを修復"""
        try:
            # 一般的な問題を修復
            repaired = response
            
            # 未終了の文字列を修復
            import re
            # 引用符で囲まれていない文字列を修復
            repaired = re.sub(r'([^"\s]):\s*([^"\s,}]+)', r'\1: "\2"', repaired)
            
            # 末尾のカンマを除去
            repaired = re.sub(r',\s*}', '}', repaired)
            repaired = re.sub(r',\s*]', ']', repaired)
            
            # 不完全なオブジェクトを修復
            if not repaired.endswith('}'):
                repaired += '}'
            
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
            
            return None
            
        except Exception as e:
            self.logger.warning(f"JSON修復エラー: {e}")
            return None
    
    def _get_default_value_for_field(self, field: str) -> Any:
        """フィールドのデフォルト値を取得"""
        defaults = {
            'action_type': 'direct_response',
            'prompt_pattern': 'base_main',
            'confidence': 0.5,
            'require_approval': False,
            'reasoning': 'デフォルト値が使用されました',
            'specialized_domain': None,
            'tool_operations': [],
            'file_target': None
        }
        return defaults.get(field, '')
    
    def _create_fallback_json_response(self, original_response: str) -> Dict[str, Any]:
        """フォールバック用のJSONレスポンスを作成"""
        try:
            # 元のレスポンスから情報を抽出
            response_lower = original_response.lower()
            
            # キーワードベースでアクションタイプを推定
            if any(kw in response_lower for kw in ['file', 'read', 'write', 'create', 'delete']):
                action_type = 'file_operation'
            elif any(kw in response_lower for kw in ['plan', 'planning', 'design']):
                action_type = 'plan_generation'
            elif any(kw in response_lower for kw in ['run', 'execute', 'test']):
                action_type = 'code_execution'
            else:
                action_type = 'direct_response'
            
            return {
                'action_type': action_type,
                'prompt_pattern': 'base_main',
                'confidence': 0.3,
                'require_approval': False,
                'reasoning': 'パースエラーによりフォールバック処理を使用',
                'specialized_domain': None,
                'tool_operations': [],
                'file_target': None
            }
            
        except Exception as e:
            self.logger.error(f"フォールバックJSON作成エラー: {e}")
            # 最小限のフォールバック
            return {
                'action_type': 'direct_response',
                'prompt_pattern': 'base_main',
                'confidence': 0.1,
                'require_approval': False,
                'reasoning': 'エラーにより最小限のフォールバックを使用',
                'specialized_domain': None,
                'tool_operations': [],
                'file_target': None
            }
    
    def _validate_and_complete_result(self, parsed_result: Dict[str, Any], 
                                    user_input: str, agent_state: AgentState) -> IntentAnalysisResult:
        """結果を検証・補完"""
        try:
            # ActionTypeの検証・変換
            action_type = self._validate_action_type(parsed_result.get('action_type', ''))
            
            # PromptPatternの検証・変換
            prompt_pattern = self._validate_prompt_pattern(parsed_result.get('prompt_pattern', ''))
            
            # ツール操作の検証・変換
            tool_operations = self._validate_tool_operations(parsed_result.get('tool_operations', []))
            
            # ファイルターゲットの抽出・検証
            file_target = self._extract_and_validate_file_target(
                parsed_result.get('file_target', ''),
                user_input,
                action_type
            )
            
            # 承認要否の判定
            require_approval = self._determine_approval_requirement(
                action_type, tool_operations, file_target
            )
            
            # 信頼度の検証
            confidence = self._validate_confidence(parsed_result.get('confidence', 0.5))
            
            # 推論の検証
            reasoning = parsed_result.get('reasoning', '推論情報がありません')
            
            # 専門領域の検証・変換
            specialized_domain = self._validate_specialized_domain(
                parsed_result.get('specialized_domain', '')
            )
            
            return IntentAnalysisResult(
                action_type=action_type,
                prompt_pattern=prompt_pattern,
                tool_operations=tool_operations,
                file_target=file_target,
                require_approval=require_approval,
                confidence=confidence,
                reasoning=reasoning,
                specialized_domain=specialized_domain,
                user_input=user_input # 元のユーザー入力を追加
            )
            
        except Exception as e:
            self.logger.error(f"結果検証・補完エラー: {e}")
            raise
    
    def _validate_action_type(self, action_type_str: str) -> ActionType:
        """ActionTypeを検証・変換"""
        try:
            if isinstance(action_type_str, str):
                for action_type in ActionType:
                    if action_type.value == action_type_str:
                        return action_type
            
            # デフォルト値を返す
            self.logger.warning(f"無効なActionType: {action_type_str}, デフォルト使用")
            return ActionType.DIRECT_RESPONSE
            
        except Exception:
            return ActionType.DIRECT_RESPONSE
    
    def _validate_prompt_pattern(self, pattern_str: str) -> PromptPattern:
        """PromptPatternを検証・変換"""
        try:
            if isinstance(pattern_str, str):
                for pattern in PromptPattern:
                    if pattern.value == pattern_str:
                        return pattern
            
            # デフォルト値を返す
            self.logger.warning(f"無効なPromptPattern: {pattern_str}, デフォルト使用")
            return PromptPattern.BASE_MAIN
            
        except Exception:
            return PromptPattern.BASE_MAIN
    
    def _validate_tool_operations(self, operations: List[Dict[str, Any]]) -> List[ToolOperation]:
        """ツール操作を検証・変換"""
        validated_operations = []
        
        try:
            for op in operations:
                if isinstance(op, dict) and 'operation' in op:
                    validated_op = ToolOperation(
                        operation=op.get('operation', ''),
                        args=op.get('args', {})
                    )
                    validated_operations.append(validated_op)
        except Exception as e:
            self.logger.warning(f"ツール操作検証エラー: {e}")
        
        return validated_operations
    
    def _extract_and_validate_file_target(self, extracted_target: str, user_input: str, 
                                        action_type: ActionType) -> Optional[str]:
        """ファイルターゲットを抽出・検証"""
        try:
            # 1. LLMが抽出したファイルターゲットを優先
            if extracted_target and extracted_target.strip():
                return extracted_target.strip()
            
            # 2. ファイル操作系の場合、ユーザー入力から抽出を試行
            if action_type in [ActionType.FILE_OPERATION, ActionType.CONTENT_EXTRACTION]:
                # 簡易的なファイル名抽出（拡張子ベース）
                import re
                file_extensions = r'\.(md|txt|py|js|html|css|json|yaml|yml|xml|csv|log)$'
                file_match = re.search(r'(\S+' + file_extensions + r')', user_input)
                if file_match:
                    return file_match.group(1)
                
                # 一般的なファイル名パターン
                words = user_input.split()
                for word in words:
                    if re.search(r'\.\w+$', word):
                        return word
            
            return None
            
        except Exception as e:
            self.logger.warning(f"ファイルターゲット抽出エラー: {e}")
            return None
    
    def _determine_approval_requirement(self, action_type: ActionType, 
                                      tool_operations: List[ToolOperation],
                                      file_target: Optional[str]) -> bool:
        """承認要否を判定"""
        try:
            # 書き込み・削除・実行系は常に承認必要
            if action_type in [ActionType.CODE_EXECUTION]:
                return True
            
            # ツール操作で危険な操作がある場合
            dangerous_operations = ['write', 'create', 'delete', 'run', 'execute']
            for op in tool_operations:
                if op.operation in dangerous_operations:
                    return True
            
            return False
            
        except Exception:
            return True  # エラー時は安全側に倒す
    
    def _validate_confidence(self, confidence: Any) -> float:
        """信頼度を検証"""
        try:
            if isinstance(confidence, (int, float)):
                confidence_float = float(confidence)
                if 0.0 <= confidence_float <= 1.0:
                    return confidence_float
            
            # デフォルト値を返す
            self.logger.warning(f"無効な信頼度: {confidence}, デフォルト使用")
            return 0.5
            
        except Exception:
            return 0.5
    
    def _validate_specialized_domain(self, domain_str: str) -> Optional[SpecializedDomain]:
        """専門領域を検証・変換"""
        try:
            if isinstance(domain_str, str):
                for domain in SpecializedDomain:
                    if domain.value == domain_str:
                        return domain
            
            return None
            
        except Exception:
            return None
    
    def _extract_file_target_fallback(self, user_input: str) -> Optional[str]:
        """フォールバック用のファイルターゲット抽出"""
        try:
            self.logger.info(f"ファイルターゲット抽出開始: {user_input}")
            
            # 簡易的なファイル名抽出（拡張子ベース）
            import re
            file_extensions = r'\.(md|txt|py|js|html|css|json|yaml|yml|xml|csv|log)$'
            file_match = re.search(r'(\S+' + file_extensions + r')', user_input)
            if file_match:
                file_target = file_match.group(1)
                self.logger.info(f"拡張子ベースで抽出: {file_target}")
                return file_target
            
            # 一般的なファイル名パターン
            words = user_input.split()
            for word in words:
                if re.search(r'\.\w+$', word):
                    self.logger.info(f"パターンベースで抽出: {word}")
                    return word
            
            # 特定のファイル名のキーワード（フォールバック）
            if "game_doc.md" in user_input:
                self.logger.info("キーワードベースで抽出: game_doc.md")
                return "game_doc.md"
            elif "readme" in user_input.lower():
                self.logger.info("キーワードベースで抽出: README.md")
                return "README.md"
            
            self.logger.warning("ファイルターゲットが見つかりませんでした")
            return None
            
        except Exception as e:
            self.logger.warning(f"ファイルターゲット抽出エラー: {e}")
            return None

    def _get_work_dir_safely(self, agent_state: AgentState) -> str:
        """agent_state.workspaceのwork_dirを安全に取得"""
        try:
            if (agent_state and 
                hasattr(agent_state, 'workspace') and 
                agent_state.workspace and 
                hasattr(agent_state.workspace, 'work_dir') and 
                agent_state.workspace.work_dir):
                return agent_state.workspace.work_dir
        except Exception as e:
            self.logger.warning(f"ワークスペース情報取得エラー: {e}")
        
        return './work' # デフォルト値

    def _get_fallback_result(self, user_input: str, agent_state: AgentState) -> IntentAnalysisResult:
        """フォールバック用の結果を生成"""
        self.logger.warning("フォールバック結果を使用")
        
        # 簡易的な意図判定（キーワードベース）
        user_input_lower = user_input.lower()
        
        # ファイル操作の判定
        if any(kw in user_input_lower for kw in ["読", "見て", "確認", "内容", "ファイル", "file", "読み", "読んで"]):
            action_type = ActionType.FILE_OPERATION
            file_target = self._extract_file_target_fallback(user_input)
            self.logger.info(f"フォールバック: ファイル操作として判定、ターゲット: {file_target}")
        elif any(kw in user_input_lower for kw in ["作成", "書", "出力", "生成", "create", "write"]):
            action_type = ActionType.FILE_OPERATION
            file_target = self._extract_file_target_fallback(user_input)
            self.logger.info(f"フォールバック: ファイル操作として判定、ターゲット: {file_target}")
        elif any(kw in user_input_lower for kw in ["実行", "run", "テスト", "test"]):
            action_type = ActionType.CODE_EXECUTION
            file_target = None
            self.logger.info("フォールバック: コード実行として判定")
        elif any(kw in user_input_lower for kw in ["プラン", "計画", "設計", "plan"]):
            action_type = ActionType.PLAN_GENERATION
            file_target = None
            self.logger.info("フォールバック: プラン生成として判定")
        else:
            action_type = ActionType.DIRECT_RESPONSE
            file_target = None
            self.logger.info("フォールバック: 直接応答として判定")
        
        return IntentAnalysisResult(
            action_type=action_type,
            prompt_pattern=PromptPattern.BASE_MAIN,
            tool_operations=[],
            file_target=file_target,
            require_approval=False,
            confidence=0.3,
            reasoning="エラーによりフォールバック処理を使用",
            specialized_domain=None,
            user_input=user_input # 元のユーザー入力を追加
        )
    
    def get_confidence_level(self, confidence: float) -> str:
        """信頼度レベルを取得"""
        if confidence >= self.confidence_thresholds["high"]:
            return "high"
        elif confidence >= self.confidence_thresholds["medium"]:
            return "medium"
        elif confidence >= self.confidence_thresholds["low"]:
            return "low"
        else:
            return "very_low"
    
    def should_clarify(self, result: IntentAnalysisResult) -> bool:
        """明確化が必要かどうかを判定"""
        # 低信頼度または承認が必要な場合は明確化
        return (result.confidence < self.confidence_thresholds["medium"] or 
                result.require_approval)

#!/usr/bin/env python3
"""
Enhanced Companion Core V7 - 重複表示防止機能付き

AI応答の重複表示を防ぎ、適切な区切り表示を提供する
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# 既存のimport
try:
    from .state.agent_state import AgentState, Plan
    from .llm.llm_client import LLMClient
    from .llm.llm_service import LLMService
    from .intent_understanding.intent_analyzer_llm import IntentAnalyzerLLM, ActionType
    from .prompts.prompt_context_service import PromptContextService
    from .prompts.prompt_patterns import PromptPattern
except ImportError:
    # フォールバック用のダミークラス
    class AgentState: pass
    class Plan: pass
    class LLMClient: pass
    class LLMService: pass
    class IntentAnalyzerLLM: pass
    class PromptContextService: pass
    class PromptPattern: pass
    # ActionTypeのフォールバック
    class ActionType:
        FILE_OPERATION = type('ActionType', (), {'value': 'file_operation'})()
        CODE_EXECUTION = type('ActionType', (), {'value': 'code_execution'})()
        PLAN_GENERATION = type('ActionType', (), {'value': 'plan_generation'})()
        DIRECT_RESPONSE = type('ActionType', (), {'value': 'direct_response'})()
        SUMMARY_GENERATION = type('ActionType', (), {'value': 'summary_generation'})()
        CONTENT_EXTRACTION = type('ActionType', (), {'value': 'content_extraction'})()

# 設定
LLMSERVICE_AVAILABLE = True
INTENT_ANALYZER_AVAILABLE = True

@dataclass
class Action:
    """アクション定義"""
    operation: str
    args: Dict[str, Any]
    reasoning: str = ""
    action_id: str = ""

class EnhancedCompanionCoreV7:
    
    def __init__(self, dual_loop_system):
        # 🔥 修正: ロガーを最初に初期化
        self.logger = logging.getLogger(__name__)
        
        # システム起動時に文字コード環境を設定（一元化された設定を使用）
        self._setup_encoding_environment()
        
        # 基本システムの初期化
        self.dual_loop_system = dual_loop_system
        self.agent_state = dual_loop_system.agent_state
        self.llm_call_manager = dual_loop_system.llm_call_manager
        self.llm_service = dual_loop_system.llm_service
        self.intent_analyzer = dual_loop_system.intent_analyzer
        self.prompt_context_service = dual_loop_system.prompt_context_service
        
        # 🔥 新規: 重複表示防止のための状態管理
        self._last_response_hash = None
        self._response_count = 0
        self._last_response_time = None
        
        # UI初期化
        self.ui = self._initialize_ui()
        
        # 設定読み込み
        self.config = self._load_config()
        
        # ツールを登録（file_ops.pyの高機能版を使用）
        from .file_ops import SimpleFileOps
        self.file_ops = SimpleFileOps()
        
        self.tools = {
            "file_ops": {
                "analyze_file_structure": self.file_ops.analyze_file_structure,
                "search_content": self.file_ops.search_content,
                "read_file": self.file_ops.read_file
            },
            "plan_tool": {
                "propose": self._propose_plan,
                "update_step": self._update_plan_step,
                "get_plan": self._get_plan
            },
            "task_tool": {
                "generate_list": self._generate_task_list,
                "create_task": self._create_task
            },
            "response": {
                "echo": self._echo_response
            },
            "llm_service": {
                "synthesize_insights_from_files": self._synthesize_insights
            },
            "task_loop": {
                "execute_task_list": self._execute_task_list
            }
        }
        
        self.logger.info("EnhancedCompanionCore (v7) が初期化されました。")

    # 🔥 削除：file_ops.pyの高機能版を使用するため不要
    
    # 🔥 削除：file_ops.pyの高機能版を使用するため不要
    
    # 🔥 削除：file_ops.pyの高機能版を使用するため不要
    
    def _propose_plan(self, agent_state, user_goal: str) -> Dict[str, Any]:
        """プランを提案する"""
        return {
            'operation': 'プラン提案',
            'plan_id': f"plan_{hash(user_goal) % 10000:04d}",
            'user_goal': user_goal,
            'status': 'proposed'
        }
    
    def _update_plan_step(self, agent_state, step_id: str, status: str) -> Dict[str, Any]:
        """プランのステップを更新する"""
        return {
            'operation': 'ステップ更新',
            'step_id': step_id,
            'status': status
        }
    
    def _get_plan(self, agent_state) -> Dict[str, Any]:
        """プランを取得する"""
        return {
            'operation': 'プラン取得',
            'plans': []
        }
    
    def _generate_task_list(self, agent_state, step_id: str) -> Dict[str, Any]:
        """タスクリストを生成する"""
        return {
            'operation': 'タスクリスト生成',
            'step_id': step_id,
            'tasks': []
        }
    
    def _create_task(self, task_description: str) -> Dict[str, Any]:
        """タスクを作成する"""
        return {
            'operation': 'タスク作成',
            'task_id': f"task_{hash(task_description) % 10000:04d}",
            'description': task_description
        }
    
    def _echo_response(self, message: str) -> str:
        """応答をエコーする"""
        return f"応答完了: {message}"
    
    def _synthesize_insights(self, task_description: str, file_contents: Dict[str, Any]) -> Dict[str, Any]:
        """ファイル内容から洞察を合成する（簡易版）"""
        try:
            # 🔥 修正：LLMServiceの代わりに簡易的な要約を提供
            if not file_contents:
                insights = "分析対象のファイル内容が見つかりませんでした。"
            else:
                # AgentStateから最新のfile_ops結果を取得して簡易分析
                structure_info = "構造情報なし"
                search_info = "検索情報なし"
                
                # 直近のaction結果から情報収集
                action_results = self.agent_state.short_term_memory.get('action_results', [])
                for result in reversed(action_results[-10:]):  # 最新10件をチェック
                    if 'analyze_file_structure' in result.get('operation', ''):
                        result_data = result.get('result', {})
                        if isinstance(result_data, dict):
                            file_info = result_data.get('file_info', {})
                            headers = result_data.get('headers', [])
                            structure_info = f"ファイル: {file_info.get('total_lines', 'N/A')}行, ヘッダー: {len(headers)}個"
                    
                    elif 'search_content' in result.get('operation', ''):
                        result_data = result.get('result', {})
                        if isinstance(result_data, dict):
                            matches_found = result_data.get('matches_found', 0)
                            pattern = result_data.get('pattern', 'N/A')
                            search_info = f"パターン '{pattern}' で {matches_found} 件マッチ"
                
                insights = f"""📋 **{task_description}**

🏗️ **構造分析**: {structure_info}
🔍 **検索結果**: {search_info}

💡 **要約**: 
ファイルの構造と検索結果から、主要な技術情報と実装指針を確認できました。詳細な分析については、個別のセクションを参照してください。

⚠️ **注意**: LLMServiceによる高度な分析は現在利用できません。基本的な構造情報のみ提供しています。"""
                
            return {
                'operation': '洞察合成',
                'task_description': task_description,
                'insights': insights
            }
        except Exception as e:
            self.logger.error(f"洞察合成エラー: {e}", exc_info=True)
            return {
                'operation': '洞察合成',
                'task_description': task_description,
                'insights': f'分析中にエラーが発生しました: {str(e)}'
            }
    
    def _execute_task_list(self, task_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """タスクリストを実行する"""
        return {
            'operation': 'タスク実行',
            'task_count': len(task_list),
            'status': 'dispatched'
        }
    
    def _setup_encoding_environment(self):
        """文字コード環境を設定"""
        try:
            import locale
            import sys
            
            # システムのデフォルトエンコーディングを確認
            default_encoding = locale.getpreferredencoding()
            self.logger.info(f"システムデフォルトエンコーディング: {default_encoding}")
            
            # 標準出力・標準エラーのエンコーディングを設定
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stderr.reconfigure(encoding='utf-8')
                self.logger.info("標準出力・標準エラーのエンコーディングをUTF-8に設定")
            
        except Exception as e:
            self.logger.warning(f"文字コード環境設定に失敗: {e}")
    
    def _initialize_ui(self):
        """UIを初期化"""
        try:
            from .ui import RichUI
            return RichUI()
        except ImportError:
            try:
                from .ui import SimpleUI
                return SimpleUI()
            except ImportError:
                self.logger.warning("UI初期化に失敗、標準出力を使用")
                return None
    
    def _load_config(self):
        """設定を読み込み"""
        try:
            import yaml
            config_path = "config/config.yaml"
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.warning(f"設定ファイル読み込みに失敗: {e}")
            return {}
    
    def _is_duplicate_response(self, message: str) -> bool:
        """重複応答かどうかを判定
        
        Args:
            message: 応答メッセージ
            
        Returns:
            bool: 重複応答の場合True
        """
        import hashlib
        import time
        
        # メッセージのハッシュを計算
        message_hash = hashlib.md5(str(message).encode('utf-8')).hexdigest()
        current_time = time.time()
        
        # 重複チェック
        if (self._last_response_hash == message_hash and 
            self._last_response_time and 
            current_time - self._last_response_time < 5.0):  # 5秒以内の重複
            return True
        
        # 状態を更新
        self._last_response_hash = message_hash
        self._last_response_time = current_time
        self._response_count += 1
        
        return False

    async def process_user_input(self, user_input: str) -> str:
        """ユーザー入力を処理するメインのエントリーポイント"""
        had_error = False
        try:
            # ユーザー入力をAgentStateに記録
            self.agent_state.add_message("user", user_input)
            
            action_list = await self._generate_action_list(user_input)
            execution_results = await self._dispatch_action_list(action_list)
            final_response = self._create_final_response(execution_results)
            
            # アシスタントの応答をAgentStateに記録
            self.agent_state.add_message("assistant", final_response)
            
            # 成功時のvitals更新
            self._update_vitals(had_error=False, is_progress=True)
            
            return final_response
        except Exception as e:
            had_error = True
            self.logger.error(f"処理中にエラーが発生しました: {e}", exc_info=True)
            error_response = f"エラーが発生しました: {e}"
            # エラーもAgentStateに記録
            self.agent_state.add_message("assistant", error_response, {"error": True})
            
            # エラー時のvitals更新
            self._update_vitals(had_error=True, is_progress=False)
            
            return error_response

    def _get_tool_definitions_for_llm(self) -> List[Dict[str, Any]]:
        """LLMに提供するためのツール定義をネイティブ形式で生成する"""
        tool_defs = [
            {
                "type": "function",
                "function": {
                    "name": "execute_action_list",
                    "description": "ユーザーの要求に基づいて、一連のアクションを実行します。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action_list": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "operation": {
                                            "type": "string",
                                            "description": "実行する操作（例: plan_tool.propose, file_ops.read_file）"
                                        },
                                        "args": {
                                            "type": "object",
                                            "description": "操作に必要な引数"
                                        },
                                        "reasoning": {
                                            "type": "string",
                                            "description": "このアクションを実行する理由"
                                        }
                                    },
                                    "required": ["operation", "args", "reasoning"]
                                }
                            }
                        },
                        "required": ["action_list"]
                    }
                }
            }
        ]
        return tool_defs
    
    def _get_available_operations_description(self) -> str:
        """利用可能な操作の説明文を生成"""
        operations = [
            "plan_tool.propose - 長期計画を立案 (引数: user_goal)",
            "task_tool.generate_list - タスクリストを生成 (引数: step_id)",
            "file_ops.read_file - ファイルを読み込み (引数: file_path) - 小〜中容量ファイル用",
            "file_ops.search_content - 高速コンテンツ検索 (引数: file_path, pattern, context_lines) - 大容量ファイル対応",
            "file_ops.read_file_section - セクション読み込み (引数: file_path, start_line, line_count) - 大容量ファイル対応",
            "file_ops.analyze_file_structure - 構造分析 (引数: file_path) - マークダウンファイル等の構造把握",
            "file_ops.write - ファイルに書き込み (引数: file_path, content)",
            "task_loop.run - タスクを非同期実行 (引数: task_list)",
            "llm_service.synthesize_insights_from_files - ファイル内容をLLMで分析・要約 (引数: task_description, file_contents)",
            "response.echo - メッセージを返信 (引数: message)"
        ]
        return "\n".join(f"- {op}" for op in operations)

    async def _generate_action_list(self, user_input: str) -> List[Action]:
        """LLMを呼び出し、ユーザー入力と現在の状態に基づいてActionListを生成する"""
        self.logger.info("メインLLMを呼び出し、ActionListを生成します...")
        
        # 意図分析を実行
        intent_result = None
        if self.intent_analyzer:
            try:
                self.logger.info("意図分析を開始します...")
                intent_result = await self.intent_analyzer.analyze(user_input, self.agent_state)
                self.logger.info(f"意図分析完了: {intent_result.action_type.value}, 信頼度: {intent_result.confidence}")
            except Exception as e:
                self.logger.error(f"意図分析エラー: {e}")
                intent_result = None
        else:
            self.logger.info("IntentAnalyzer が利用できないため、意図分析をスキップします")
        
        tool_definitions = self._get_tool_definitions_for_llm()
        available_operations = self._get_available_operations_description()
        context_summary = self.agent_state.get_context_summary()

        system_prompt = f"""あなたは優秀なAIアシスタントの司令塔です。ユーザーの要求と現在の状況を分析し、次に実行すべき一連のアクションを決定してください。

### 利用可能な操作:
{available_operations}

### 🚀 大容量ファイル処理の完全ガイド:

#### 高性能ツール群:
1. **file_ops.read_file** - 基本ファイル読み込み（小〜中容量ファイル1000文字以下推奨）
2. **file_ops.search_content** - ripgrepベース超高速検索 ⚡ 大容量ファイル対応
3. **file_ops.read_file_section** - メモリ効率的部分読み込み 📄 大容量ファイル対応  
4. **file_ops.analyze_file_structure** - 構造分析 🏗️ マークダウンファイル等の構造把握
5. **llm_service.synthesize_insights_from_files** - AI要約・分析 🧠

#### ⚠️ 重要な大容量ファイル処理ルール:
1. **ファイルサイズ判定**: 1000文字を超えるファイルは大容量として扱う
2. **効率的アプローチ**: `read_file`結果を直接JSON引数で使用せず、以下の最適化ツールを活用:
   - 特定情報検索: `file_ops.search_content(file_path="file.md", pattern="キーワード", context_lines=3)`
   - 部分読み込み: `file_ops.read_file_section(file_path="file.md", start_line=1, line_count=50)`
   - 構造分析: `file_ops.analyze_file_structure(file_path="file.md")`
3. **スマートプロキシ**: 大容量ファイル参照時は自動的に最適化された形式で提供されます

#### 🎯 推奨処理パターン:

**パターンA: 構造的アプローチ（推奨）**
```json
[
  {{"operation": "file_ops.analyze_file_structure", "args": {{"file_path": "game_doc.md"}}}},
  {{"operation": "file_ops.search_content", "args": {{"file_path": "game_doc.md", "pattern": "実装優先度|技術仕様", "context_lines": 2}}}},
  {{"operation": "llm_service.synthesize_insights_from_files", "args": {{"task_description": "構造情報と重要箇所から実装計画を策定", "file_contents": {{}}}}}},
  {{"operation": "response.echo", "args": {{"message": "📋 構造: {{@act_000_file_ops_analyze_file_structure}}\\n\\n🔍 重要情報: {{@act_001_file_ops_search_content}}\\n\\n🧠 分析結果: {{@act_002_llm_service_synthesize_insights_from_files}}"}}}}
]
```

**パターンB: AI要約中心アプローチ**
```json
[
  {{"operation": "llm_service.synthesize_insights_from_files", "args": {{"task_description": "ファイル内容を分析し実装に必要な情報を抽出", "file_contents": {{}}}}}},
  {{"operation": "response.echo", "args": {{"message": "{{@act_000_llm_service_synthesize_insights_from_files}}"}}}}
]
```

### テンプレート変数の使用方法（ActionID参照形式）:
- `{{@act_000_file_ops_read_file}}` - 1番目のファイル読み込み結果を参照（番号は0ベース）
- `{{@act_001_llm_service_synthesize_insights_from_files}}` - 2番目のLLMServiceの分析結果を参照
- `{{@act_002_plan_tool_propose}}` - 3番目のプラン生成結果を参照
- `{{latest:file_ops.read_file}}` - 最新のファイル読み込み結果を参照（時間制限付き）
**重要**: ActionID番号は0から始まります（act_000, act_001, act_002...）

### file_contents引数の使用方法:
- **自動取得**: `"file_contents": {{}}` でAgentStateから自動取得（推奨）
- **明示的指定**: `"file_contents": {{"ファイル名": "内容"}}` で明示的に指定
- **大容量ファイル**: システムが自動的にスマートプロキシを適用

### JSON出力形式:
適切なアクションを選択して、以下のJSON形式で回答してください：

```json
[
  {{"operation": "操作名", "args": {{引数}}, "reasoning": "理由"}}
]
```

テンプレート変数を適切に使用して、前のアクション結果を効率的に連携してください。大容量ファイルの場合は最適化されたツールを優先的に使用してください。"""
        
        user_prompt = f"""### 現在の状態:
{json.dumps(context_summary, indent=2, ensure_ascii=False)}

### ユーザーの要求:
{user_input}

上記を分析し、実行すべきActionListをJSONで出力してください。"""
        
        # デバッグ用ログ（プロンプト内容）
        self.logger.info(f"システムプロンプト（文字数: {len(system_prompt)}）: {system_prompt[:200]}...")
        self.logger.info(f"ユーザープロンプト（文字数: {len(user_prompt)}）: {user_prompt[:200]}...")
        
        try:
            # 意図分析結果に基づいてツール呼び出しの必要性を判定
            needs_tool_calls = self._should_use_tool_calls(intent_result, user_input)
            
            if needs_tool_calls:
                # ツール呼び出しが必要な場合
                self.logger.info("ツール呼び出しモードでLLMを呼び出し")
                response_str = await self.llm_call_manager.call(
                    system_prompt, 
                    user_prompt, 
                    tools=tool_definitions,
                    tool_choice="auto"
                )
            else:
                # ツール呼び出しが不要な場合
                self.logger.info("テキスト応答モードでLLMを呼び出し")
                response_str = await self.llm_call_manager.call(
                    system_prompt, 
                    user_prompt, 
                    tools=None,
                    tool_choice="none"
                )
            
            # デバッグ用ログ（None チェック）
            if response_str is None:
                raise ValueError("LLMからNullレスポンスが返されました")
                
            self.logger.info(f"LLMレスポンス（文字数: {len(response_str)}）: {response_str[:200]}...")
            
            if not response_str.strip():
                raise ValueError("LLMから空のレスポンスが返されました")
            
            # ツール呼び出しの有無に応じてレスポンスを解析
            if needs_tool_calls:
                # ツール呼び出しレスポンスを解析
                self.logger.info("ツール呼び出しレスポンスの解析を開始")
                action_list = self._parse_tool_call_response(response_str)
            else:
                # テキスト応答からActionListを解析
                self.logger.info("テキスト応答の解析を開始")
                action_list = self._parse_text_response_to_action_list(response_str)
            
            # 解析結果のログ
            if action_list:
                self.logger.info(f"レスポンス解析成功: {len(action_list)}件のアクション")
                for i, action in enumerate(action_list):
                    self.logger.info(f"  アクション{i+1}: {action.operation} - {action.reasoning}")
            else:
                self.logger.warning("レスポンス解析結果が空です")
                
            if not action_list:
                # より詳細なエラー情報を提供
                self.logger.error("ActionListが空です。レスポンス内容を確認してください。")
                self.logger.error(f"レスポンス内容: {response_str[:500]}...")
                
                # フォールバックとして、基本的なファイル読み込みアクションを生成
                fallback_action = Action(
                    operation='file_ops.read_file',
                    args={'file_path': 'game_doc.md'},
                    reasoning='エラーによりフォールバック処理を使用'
                )
                
                self.logger.info("フォールバックアクションを生成: file_ops.read_file")
                return [fallback_action]

            self.logger.info(f"生成されたActionList: {action_list}")
            return action_list

        except Exception as e:
            self.logger.error(f"ActionListの生成に失敗しました: {e}", exc_info=True)
            return [Action(operation='response.echo', args={'message': f"申し訳ありません、コマンドの解釈中にエラーが発生しました。もう一度試していただけますか？ (エラー: {e})"})]

    async def _dispatch_action_list(self, action_list: List[Action]) -> List[Any]:
        """ActionListを解釈し、各Actionを実行する（ActionID+タイムスタンプベース）"""
        import uuid
        action_list_id = f"al_{uuid.uuid4().hex[:8]}"  # ActionList全体のID
        results = []
        
        self.logger.info(f"ActionList実行開始: {action_list_id}, {len(action_list)}件のアクション")
        
        # 現在のaction_list_idを保存（ツール実行時に参照できるように）
        self._current_action_list_id = action_list_id
        
        for i, action in enumerate(action_list):
            # ActionIDを生成（ActionList内で一意）
            action_id = f"act_{i:03d}_{action.operation.replace('.', '_')}"
            
            self.logger.info(f"アクション実行: {action_id} ({action.operation})")
            
            # 参照解決（同一ActionList内の前のアクション結果を参照）
            processed_args = self._resolve_action_references(
                action.args, action_list_id, i
            )
            
            op_parts = action.operation.split('.')
            if len(op_parts) != 2:
                results.append({"error": f"無効な操作形式: {action.operation}"})
                continue
            
            tool_name, method_name = op_parts
            args = processed_args
            result = None

            # ツール実行の開始時刻を記録
            start_time = datetime.now()
            
            try:
                if tool_name in self.tools and method_name in self.tools[tool_name]:
                    method = self.tools[tool_name][method_name]
                    # 引数にagent_stateを要求するかどうかを判定（仮）
                    if method_name in ["propose", "update_step", "get_plan", "generate_list"]:
                        result = method(self.agent_state, **args)
                    else:
                        result = method(**args)
                    
                    # ツール実行履歴をAgentStateに記録
                    execution_time = (datetime.now() - start_time).total_seconds()
                    self._record_tool_execution(tool_name, method_name, args, result, execution_time)
                    
                    # ファイル読み込み結果をAgentStateに保存
                    if tool_name == "file_ops" and method_name == "read_file":
                        if isinstance(result, dict) and result.get("success") and "file_path" in result:
                            file_path = result["file_path"]
                            content = result.get("content", "")
                            metadata = result.get("metadata", {})
                            
                            # 新しいメタデータ対応のメソッドを使用
                            self.agent_state.add_file_content(
                                file_path=file_path,
                                content=content,
                                metadata=metadata
                            )
                            self.logger.info(f"ファイル読み込み結果をAgentStateに保存: {file_path} (切り詰め: {metadata.get('is_truncated', False)})")
                    
                    # プラン生成結果をAgentStateに保存
                    elif tool_name == "plan_tool" and method_name == "propose":
                        if hasattr(result, 'plan_id'):
                            # プランコンテキストを更新
                            self.agent_state.update_plan_context(
                                plan_id=result.plan_id,
                                context_data={
                                    "generation_context": args,
                                    "recent_files": self.agent_state.short_term_memory.get("recent_files", [])[-3:]
                                }
                            )
                            self.logger.info(f"プラン生成結果をAgentStateに保存: {result.plan_id}")
                            
                elif tool_name == "task_loop":
                    self.logger.info("重いタスクをTaskLoopに委譲します...")
                    task_command = {"type": "execute_task_list", "task_list": args.get("task_list", [])}
                    self.dual_loop_system.task_queue.put(task_command)
                    result = {"status": "dispatched", "message": "TaskLoopで非同期実行を開始しました。"}
                elif tool_name == "response":
                    if method_name == "echo":
                        # メッセージを取得（既に参照解決済み）
                        message = args.get("message", "メッセージが指定されていません")
                        
                        # メッセージが操作の説明文の場合は、実際の内容を取得
                        if isinstance(message, str) and message.startswith("応答完了:"):
                            # 操作の説明文の場合は、実際のファイル内容を取得
                            file_contents_with_metadata = self.agent_state.get_all_file_contents_with_metadata()
                            if file_contents_with_metadata:
                                # メタデータ付きファイル内容を表示
                                result = "📄 **ファイル内容の要約**\n\n"
                                for file_path, file_data in file_contents_with_metadata.items():
                                    content = file_data.get("content", "")
                                    metadata = file_data.get("metadata", {})
                                    
                                    if metadata.get("is_truncated"):
                                        result += f"**{file_path}** (切り詰め済み):\n{content}\n\n"
                                        result += f"⚠️ 完全な内容が必要な場合は `file_ops.read_file_section(file_path=\"{file_path}\", start_line=N, line_count=100)` を使用してください\n\n"
                                    else:
                                        result += f"**{file_path}**:\n{content}\n\n"
                            else:
                                result = "ファイル内容が見つかりませんでした。"
                        else:
                            # 通常のメッセージの場合は、そのまま表示
                            result = message
                        
                        # 🔥 最適化: 重複表示防止と適切な要約処理
                        if len(str(result)) > 1000:
                            self.logger.info(f"大容量メッセージを検出: {len(str(result))}文字 -> 要約処理を実行")
                            
                            # シンプルな要約処理
                            if isinstance(result, str):
                                result = result[:800] + "...\n\n(内容が長すぎるため要約しました。詳細が必要な場合は適切なツールを使用してください。)"
                            
                            self.logger.info(f"要約完了: {len(str(result))}文字")
                        
                        # ログ出力を最適化
                        log_preview = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                        self.logger.info(f"response.echo: {log_preview}")
                        
                        # UIに表示
                        if hasattr(self, 'ui') and self.ui:
                            self.ui.echo(result)
                        else:
                            print(f"🦆 {result}")
                elif tool_name == "llm_service":
                    # LLMServiceの処理
                    if not self.llm_service:
                        result = {"error": "LLMService が利用できません"}
                    elif method_name == "synthesize_insights_from_files":
                        try:
                            task_description = args.get("task_description", "")
                            file_contents = args.get("file_contents", {})
                            
                            self.logger.info(f"LLMService呼び出し開始: {method_name}")
                            self.logger.info(f"task_description: {task_description}")
                            self.logger.info(f"file_contents type: {type(file_contents)}")
                            self.logger.info(f"file_contents keys: {list(file_contents.keys()) if isinstance(file_contents, dict) else 'N/A'}")
                            
                            # file_contentsが文字列の場合は、AgentStateから取得
                            if isinstance(file_contents, str):
                                self.logger.info(f"file_contentsが文字列として渡されました: {file_contents}")
                                file_contents = self.agent_state.get_file_contents()
                            
                            # ファイル内容が空の場合は、AgentStateから取得
                            if not file_contents:
                                self.logger.info("file_contentsが空のため、AgentStateから取得します")
                                file_contents = self.agent_state.get_file_contents()
                            
                            # 🔥 改善：file_contentsが空の場合、直近のアクション結果から情報を収集
                            if not file_contents:
                                self.logger.info("AgentStateにファイル内容がないため、直近のアクション結果から情報を収集します")
                                # action_list_idを取得（実行コンテキストから）
                                current_action_list_id = getattr(self, '_current_action_list_id', None)
                                if current_action_list_id:
                                    file_contents = self._collect_file_info_from_recent_actions(current_action_list_id)
                                else:
                                    self.logger.warning("action_list_idが取得できませんでした")
                            
                            if file_contents:
                                self.logger.info(f"LLMServiceでファイル分析を開始: {len(file_contents)}件のファイル")
                                self.logger.info(f"ファイル一覧: {list(file_contents.keys())}")
                                
                                result = await self.llm_service.synthesize_insights_from_files(
                                    task_description=task_description,
                                    file_contents=file_contents
                                )
                                
                                self.logger.info(f"LLMService処理完了: 結果文字数 {len(result) if result else 0}")
                            else:
                                result = "分析対象のファイルが見つかりませんでした。"
                                self.logger.warning("分析対象のファイルが見つかりませんでした")
                        except Exception as e:
                            self.logger.error(f"LLMService処理エラー: {e}", exc_info=True)
                            result = f"ファイル分析中にエラーが発生しました: {str(e)}"
                    else:
                        result = {"error": f"不明なLLMServiceメソッド: {method_name}"}
                else:
                    result = {"error": f"不明なツール: {tool_name}"}
            except Exception as e:
                self.logger.error(f"アクション実行エラー: {action.operation} - {e}", exc_info=True)
                result = {"error": str(e)}
                
                # エラー時もツール実行履歴に記録
                execution_time = (datetime.now() - start_time).total_seconds()
                self._record_tool_execution(tool_name, method_name, args, result, execution_time, str(e))
            
            # 実行結果をAgentStateに記録
            self._record_action_result(action, result)
            
            # 結果をAgentStateに保存（ActionID+タイムスタンプベース）
            # 次のActionが参照できるように、実行直後に保存
            metadata = {
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "input_args": args,
                "result_type": type(result).__name__
            }
            
            # ファイル操作の場合、file_pathをmetadataに記録
            if tool_name == "file_ops" and "file_path" in args:
                metadata["file_path"] = args["file_path"]
            
            self.agent_state.add_action_result(
                action_id=action_id,
                operation=action.operation,
                result=result,
                action_list_id=action_list_id,
                sequence_number=i,
                metadata=metadata
            )
            
            results.append(result)
        
        # クリーンアップ
        self._current_action_list_id = None
        
        return results

    def _resolve_action_references(self, args: Dict[str, Any], 
                                  action_list_id: str, current_sequence: int) -> Dict[str, Any]:
        """アクション参照を解決"""
        processed_args = {}
        
        for key, value in args.items():
            if isinstance(value, str):
                processed_value = self._resolve_single_reference(
                    value, action_list_id, current_sequence
                )
                processed_args[key] = processed_value
            elif isinstance(value, dict):
                processed_args[key] = self._resolve_action_references(value, action_list_id, current_sequence)
            elif isinstance(value, list):
                processed_args[key] = [
                    self._resolve_action_references(item, action_list_id, current_sequence) 
                    if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                processed_args[key] = value
        
        return processed_args
    
    def _resolve_single_reference(self, value: str, action_list_id: str, 
                                 current_sequence: int) -> Any:
        """単一の参照を解決"""
        
        self.logger.info(f"参照解決開始: '{value}' (action_list_id: {action_list_id}, sequence: {current_sequence})")
        
        # 文字列内のテンプレート変数を置換する処理を追加
        if '{{@' in value or '{{latest:' in value or '{@' in value or '{latest:' in value:
            import re
            result_value = value
            
            # 1. ActionID参照を処理（波括弧2つ） {{@action_id}}
            action_id_pattern = r'\{\{@([^}]+)\}\}'
            for match in re.finditer(action_id_pattern, value):
                action_id = match.group(1)
                self.logger.info(f"ActionID参照試行（波括弧2つ）: {action_id}")
                replacement = self.agent_state.get_action_result_by_id(action_id, action_list_id)
                if replacement is not None:
                    self.logger.info(f"ActionID参照成功: {action_id} -> 結果長: {len(str(replacement))}")
                    # シンプルな処理（古いスマートプロキシを削除）
                    result_value = result_value.replace(match.group(0), str(replacement))
                else:
                    self.logger.warning(f"ActionID参照失敗: {action_id}")
                    result_value = result_value.replace(match.group(0), f"参照エラー: {action_id}")
            
            # 1b. ActionID参照を処理（波括弧1つ） {@action_id}
            single_action_id_pattern = r'\{@([^}]+)\}'
            for match in re.finditer(single_action_id_pattern, value):
                action_id = match.group(1)
                self.logger.info(f"ActionID参照試行（波括弧1つ）: {action_id}")
                replacement = self.agent_state.get_action_result_by_id(action_id, action_list_id)
                if replacement is not None:
                    self.logger.info(f"ActionID参照成功: {action_id} -> 結果長: {len(str(replacement))}")
                    # シンプルな処理（古いスマートプロキシを削除）
                    result_value = result_value.replace(match.group(0), str(replacement))
                else:
                    self.logger.warning(f"ActionID参照失敗: {action_id}")
                    result_value = result_value.replace(match.group(0), f"参照エラー: {action_id}")
            
            # 2. 最新結果参照を処理（波括弧2つ） {{latest:operation}}
            latest_pattern = r'\{\{latest:([^}]+)\}\}'
            for match in re.finditer(latest_pattern, value):
                operation = match.group(1)
                self.logger.info(f"最新結果参照試行（波括弧2つ）: {operation}")
                replacement = self.agent_state.get_latest_result_by_operation(operation, max_age_minutes=30)
                if replacement is not None:
                    self.logger.info(f"最新結果参照成功: {operation}")
                    result_value = result_value.replace(match.group(0), str(replacement))
                else:
                    self.logger.warning(f"最新結果参照失敗または古すぎる: {operation}")
                    result_value = result_value.replace(match.group(0), f"最新の{operation}結果が見つかりません（30分以内）")
            
            # 2b. 最新結果参照を処理（波括弧1つ） {latest:operation}
            single_latest_pattern = r'\{latest:([^}]+)\}'
            for match in re.finditer(single_latest_pattern, value):
                operation = match.group(1)
                self.logger.info(f"最新結果参照試行（波括弧1つ）: {operation}")
                replacement = self.agent_state.get_latest_result_by_operation(operation, max_age_minutes=30)
                if replacement is not None:
                    self.logger.info(f"最新結果参照成功: {operation}")
                    result_value = result_value.replace(match.group(0), str(replacement))
                else:
                    self.logger.warning(f"最新結果参照失敗または古すぎる: {operation}")
                    result_value = result_value.replace(match.group(0), f"最新の{operation}結果が見つかりません（30分以内）")
            
            return result_value
        
        # 古い形式の単一完全一致（後方互換性）
        # 1. 同一ActionList内の特定アクション参照
        if value.startswith("{{@") and value.endswith("}}"):  # 例: "{{@act_001_file_ops_read_file}}"
            action_id = value[3:-2]  # "{{@" と "}}" を除去
            self.logger.info(f"ActionID参照試行: {action_id}")
            result = self.agent_state.get_action_result_by_id(action_id, action_list_id)
            if result is not None:
                self.logger.info(f"ActionID参照成功: {action_id} -> 結果長: {len(str(result))}")
                return result
            else:
                self.logger.warning(f"ActionID参照失敗: {action_id}")
                return f"参照エラー: {action_id}"
        
        # 2. 最新の操作結果参照（時間制限付き）
        elif value.startswith("{{latest:"):  # 例: "{{latest:file_ops.read_file}}"
            operation = value[9:-2]  # "{{latest:" と "}}" を除去
            result = self.agent_state.get_latest_result_by_operation(operation, max_age_minutes=30)
            if result is not None:
                self.logger.info(f"最新結果参照成功: {operation}")
                return result
            else:
                self.logger.warning(f"最新結果参照失敗または古すぎる: {operation}")
                return f"最新の{operation}結果が見つかりません（30分以内）"
        
        # 3. 簡単な省略形（既存の互換性維持）
        elif value == "{{file_content}}":
            result = self.agent_state.get_latest_result_by_operation("file_ops.read_file", max_age_minutes=10)
            return result if result is not None else "ファイル内容が見つかりません"
        elif value == "{{analysis}}" or value == "{{summary}}":
            result = self.agent_state.get_latest_result_by_operation("llm_service.synthesize_insights_from_files", max_age_minutes=10)
            return result if result is not None else "分析結果が見つかりません"
        elif value == "{{file_contents}}":
            # AgentState.get_file_contents()との互換性
            return self.agent_state.get_file_contents()
        
        return value
    
    # 🔥 古いスマートプロキシ処理を削除（新しいファイル処理システムに置き換え）
    
    def _extract_file_path_from_action_id(self, action_id: str) -> str:
        """ActionIDからファイルパスを推測"""
        # ActionIDの形式: act_000_file_ops_read_file
        # AgentStateの実行履歴から対応するファイルパスを検索
        try:
            action_results = self.agent_state.short_term_memory.get('action_results', [])
            for result in action_results:
                if result.get('action_id') == action_id:
                    # 実行時の引数からfile_pathを取得
                    metadata = result.get('metadata', {})
                    return metadata.get('file_path', 'unknown_file')
            
            # フォールバック: 一般的なファイル名
            return "target_file"
        except Exception:
            return "target_file"
    
    # 🔥 古い要約処理メソッドを削除（新しいファイル処理システムに置き換え）
    
    # 🔥 不要になったメソッドを削除し、シンプルな判定に統一
    

    

    

    


    def _collect_file_info_from_recent_actions(self, action_list_id: str) -> Dict[str, str]:
        """直近のアクション結果からファイル情報を収集してLLMService用のfile_contentsを構築"""
        
        file_contents = {}
        
        try:
            # ActionResultsから直近の結果を取得
            action_results = self.agent_state.short_term_memory.get('action_results', [])
            
            # 現在のaction_list_idに関連する結果のみをフィルター
            relevant_results = [
                result for result in action_results 
                if result.get('action_list_id') == action_list_id
            ]
            
            self.logger.info(f"action_list_id {action_list_id} の関連結果: {len(relevant_results)}件")
            
            collected_info = []
            
            for result in relevant_results:
                operation = result.get('operation', '')
                result_data = result.get('result', '')
                action_id = result.get('action_id', '')
                
                if isinstance(result_data, dict):
                    
                    # 構造分析結果の処理
                    if 'analyze_file_structure' in operation:
                        file_path = result_data.get('file_path', 'unknown')
                        headers = result_data.get('headers', [])
                        sections = result_data.get('sections', [])
                        file_info = result_data.get('file_info', {})
                        
                        structure_summary = f"""
## ファイル構造分析結果 ({file_path})
- 総行数: {file_info.get('total_lines', 'N/A')}
- 総文字数: {file_info.get('total_chars', 'N/A')}

### ヘッダー構造:
{chr(10).join([f"L{h.get('line_number', 'N/A')}: {'#' * h.get('level', 1)} {h.get('text', 'N/A')}" for h in headers[:10]])}

### セクション情報:
{chr(10).join([f"- {s.get('title', 'N/A')} (L{s.get('start_line', 'N/A')}-{s.get('end_line', 'N/A')})" for s in sections[:5]])}
"""
                        collected_info.append(structure_summary)
                        self.logger.info(f"構造分析結果を追加: {file_path}")
                    
                    # 検索結果の処理
                    elif 'search_content' in operation:
                        file_path = result_data.get('file_path', 'unknown')
                        pattern = result_data.get('pattern', 'N/A')
                        results = result_data.get('results', [])
                        matches_found = result_data.get('matches_found', 0)
                        
                        search_summary = f"""
## コンテンツ検索結果 ({file_path})
検索パターン: {pattern}
マッチ数: {matches_found}件

### 検索結果:
"""
                        for match in results[:3]:  # 最大3件
                            line_num = match.get('line_number', 'N/A')
                            match_text = match.get('match', 'N/A')
                            context_lines = match.get('context_lines', [])
                            
                            search_summary += f"""
L{line_num}: {match_text}
コンテキスト:
{chr(10).join(context_lines[:5])}
"""
                        
                        collected_info.append(search_summary)
                        self.logger.info(f"検索結果を追加: {file_path} (パターン: {pattern})")
                    
                    # セクション読み込み結果の処理  
                    elif 'read_file_section' in operation:
                        file_path = result_data.get('file_path', 'unknown')
                        section_info = result_data.get('section_info', {})
                        content = result_data.get('content', '')
                        
                        section_summary = f"""
## ファイルセクション ({file_path})
範囲: L{section_info.get('start_line', 'N/A')}-{section_info.get('end_line', 'N/A')}
読み込み行数: {section_info.get('actual_lines', 'N/A')} / {section_info.get('total_file_lines', 'N/A')}

### 内容:
{content}
"""
                        collected_info.append(section_summary)
                        self.logger.info(f"セクション内容を追加: {file_path}")
            
            # 収集した情報を統合
            if collected_info:
                combined_content = "\n\n".join(collected_info)
                file_contents["collected_file_info"] = combined_content
                self.logger.info(f"ファイル情報を収集完了: {len(combined_content)}文字")
            else:
                self.logger.warning("アクション結果からファイル情報を収集できませんでした")
        
        except Exception as e:
            self.logger.error(f"ファイル情報収集中にエラー: {e}")
        
        return file_contents

    def _should_use_tool_calls(self, intent_result, user_input: str) -> bool:
        """意図分析結果に基づいてツール呼び出しの必要性を判定する"""
        try:
            # 意図分析結果が利用可能な場合
            if intent_result and hasattr(intent_result, 'action_type') and INTENT_ANALYZER_AVAILABLE:
                action_type = intent_result.action_type
                
                # ファイル操作系はツール呼び出しが必要
                if action_type == ActionType.FILE_OPERATION:
                    self.logger.info(f"ツール呼び出しが必要: ファイル操作 ({action_type.value})")
                    return True
                
                # コード実行系はツール呼び出しが必要
                elif action_type == ActionType.CODE_EXECUTION:
                    self.logger.info(f"ツール呼び出しが必要: コード実行 ({action_type.value})")
                    return True
                
                # プラン生成系はツール呼び出しが必要
                elif action_type == ActionType.PLAN_GENERATION:
                    self.logger.info(f"ツール呼び出しが必要: プラン生成 ({action_type.value})")
                    return True
                
                # 直接応答系はツール呼び出しが不要
                elif action_type == ActionType.DIRECT_RESPONSE:
                    self.logger.info(f"ツール呼び出しが不要: 直接応答 ({action_type.value})")
                    return False
                
                # 要約生成系はツール呼び出しが不要
                elif action_type == ActionType.SUMMARY_GENERATION:
                    self.logger.info(f"ツール呼び出しが不要: 要約生成 ({action_type.value})")
                    return False
                
                # コンテンツ抽出系はツール呼び出しが不要
                elif action_type == ActionType.CONTENT_EXTRACTION:
                    self.logger.info(f"ツール呼び出しが不要: コンテンツ抽出 ({action_type.value})")
                    return False
            
            # 意図分析結果が利用できない場合、キーワードベースで判定
            self.logger.info("意図分析結果が利用できないため、キーワードベースで判定")
            return self._fallback_tool_call_detection(user_input)
            
        except Exception as e:
            self.logger.error(f"ツール呼び出し判定エラー: {e}")
            # エラー時は安全側に倒してツール呼び出しを有効化
            return True
    
    def _fallback_tool_call_detection(self, user_input: str) -> bool:
        """フォールバック用のツール呼び出し判定（キーワードベース）"""
        user_input_lower = user_input.lower()
        
        # ツール呼び出しが必要なキーワード
        tool_call_keywords = [
            "実行", "実行して", "実行してください",
            "作成", "作成して", "作成してください",
            "生成", "生成して", "生成してください",
            "提案", "提案して", "提案してください",
            "計画", "計画を", "計画を立てて",
            "タスク", "タスクを", "タスクを作成",
            "ファイル", "ファイルを", "ファイルを作成",
            "コード", "コードを", "コードを生成",
            "実装", "実装して", "実装してください",
            "進めて", "進めてください", "開始して"
        ]
        
        # ツール呼び出しが不要なキーワード
        no_tool_call_keywords = [
            "説明", "説明して", "説明してください",
            "要約", "要約して", "要約してください",
            "分析", "分析して", "分析してください",
            "確認", "確認して", "確認してください",
            "見て", "見てください", "把握してください",
            "把握", "把握して", "理解してください",
            "理解", "理解して"
        ]
        
        # ツール呼び出しが必要なキーワードが含まれているかチェック
        for keyword in tool_call_keywords:
            if keyword in user_input_lower:
                self.logger.info(f"フォールバック判定: ツール呼び出しが必要 - キーワード '{keyword}' を検出")
                return True
        
        # ツール呼び出しが不要なキーワードのみが含まれているかチェック
        has_no_tool_keywords = any(keyword in user_input_lower for keyword in no_tool_call_keywords)
        has_tool_keywords = any(keyword in user_input_lower for keyword in tool_call_keywords)
        
        if has_no_tool_keywords and not has_tool_keywords:
            self.logger.info("フォールバック判定: ツール呼び出しが不要 - 情報取得・確認系の操作")
            return False
        
        # デフォルトはツール呼び出しが必要
        self.logger.info("フォールバック判定: ツール呼び出しが必要 - デフォルト設定")
        return True

    def _parse_tool_call_response(self, response_str: str) -> List[Action]:
        """ツール呼び出しレスポンスを解析してActionListを生成する"""
        try:
            # ツール呼び出しレスポンスの形式を確認
            if "execute_action_list" in response_str:
                # execute_action_listツールの呼び出しを解析
                return self._parse_execute_action_list_response(response_str)
            else:
                # その他のツール呼び出しを解析
                return self._parse_generic_tool_call_response(response_str)
                
        except Exception as e:
            self.logger.error(f"ツール呼び出しレスポンス解析エラー: {e}")
            # エラー時はテキスト応答として解析を試行
            return self._parse_text_response_to_action_list(response_str)
    
    def _parse_execute_action_list_response(self, response_str: str) -> List[Action]:
        """execute_action_listツールの呼び出しレスポンスを解析"""
        try:
            # JSON部分を抽出
            import re
            
            # action_listの引数を探す（複数のパターンを試行）
            patterns = [
                r'"action_list":\s*(\[.*?\])',  # 標準的なパターン
                r'"arguments":\s*"([^"]*)"',    # arguments全体を取得
                r'arguments":\s*"([^"]*)"',     # arguments部分のみ
            ]
            
            action_list_json = None
            for pattern in patterns:
                match = re.search(pattern, response_str, re.DOTALL)
                if match:
                    if pattern == r'"arguments":\s*"([^"]*)"':
                        # arguments全体を取得した場合、JSONとしてパース
                        try:
                            args_str = match.group(1)
                            args_data = json.loads(args_str)
                            if 'action_list' in args_data:
                                action_list_json = json.dumps(args_data['action_list'])
                                break
                        except json.JSONDecodeError:
                            continue
                    else:
                        action_list_json = match.group(1)
                        break
            
            if action_list_json:
                self.logger.info(f"execute_action_listからActionListを抽出: {action_list_json[:100]}...")
                
                # JSONをパース
                action_data = json.loads(action_list_json)
                
                # Actionオブジェクトに変換
                actions = []
                for action_dict in action_data:
                    if isinstance(action_dict, dict) and 'operation' in action_dict:
                        action = Action(
                            operation=action_dict['operation'],
                            args=action_dict.get('args', {}),
                            reasoning=action_dict.get('reasoning', '')
                        )
                        actions.append(action)
                
                self.logger.info(f"ActionList解析完了: {len(actions)}件のアクション")
                return actions
            else:
                self.logger.warning("execute_action_listの引数が見つかりません")
                # フォールバック: レスポンス全体をJSONとしてパースを試行
                return self._fallback_parse_response(response_str)
                
        except Exception as e:
            self.logger.error(f"execute_action_listレスポンス解析エラー: {e}")
            return self._fallback_parse_response(response_str)
    
    def _fallback_parse_response(self, response_str: str) -> List[Action]:
        """フォールバック用のレスポンス解析"""
        try:
            # レスポンス全体をJSONとしてパース
            response_data = json.loads(response_str)
            
            # tool_callsからaction_listを抽出
            if 'tool_calls' in response_data:
                for tool_call in response_data['tool_calls']:
                    if tool_call.get('function', {}).get('name') == 'execute_action_list':
                        args = json.loads(tool_call['function']['arguments'])
                        if 'action_list' in args:
                            actions = []
                            for action_dict in args['action_list']:
                                if isinstance(action_dict, dict) and 'operation' in action_dict:
                                    action = Action(
                                        operation=action_dict['operation'],
                                        args=action_dict.get('args', {}),
                                        reasoning=action_dict.get('reasoning', '')
                                    )
                                    actions.append(action)
                            
                            self.logger.info(f"フォールバック解析成功: {len(actions)}件のアクション")
                            return actions
            
            # 直接action_listが含まれている場合
            if 'action_list' in response_data:
                actions = []
                for action_dict in response_data['action_list']:
                    if isinstance(action_dict, dict) and 'operation' in action_dict:
                        action = Action(
                            operation=action_dict['operation'],
                            args=action_dict.get('args', {}),
                            reasoning=action_dict.get('reasoning', '')
                        )
                        actions.append(action)
                
                self.logger.info(f"直接解析成功: {len(actions)}件のアクション")
                return actions
            
            self.logger.warning("フォールバック解析でもActionListが見つかりません")
            return []
            
        except Exception as e:
            self.logger.error(f"フォールバック解析エラー: {e}")
            return []
    
    def _parse_generic_tool_call_response(self, response_str: str) -> List[Action]:
        """一般的なツール呼び出しレスポンスを解析"""
        try:
            # まず、直接的なJSONレスポンスとしてパースを試行
            try:
                response_data = json.loads(response_str)
                
                # action_listが直接含まれている場合
                if 'action_list' in response_data:
                    self.logger.info("直接的なaction_listレスポンスを検出")
                    actions = []
                    for action_dict in response_data['action_list']:
                        if isinstance(action_dict, dict) and 'operation' in action_dict:
                            action = Action(
                                operation=action_dict['operation'],
                                args=action_dict.get('args', {}),
                                reasoning=action_dict.get('reasoning', '')
                            )
                            actions.append(action)
                    
                    self.logger.info(f"直接的なJSON解析成功: {len(actions)}件のアクション")
                    return actions
                
                # tool_callsが含まれている場合
                if 'tool_calls' in response_data:
                    self.logger.info("tool_callsレスポンスを検出")
                    return self._parse_tool_calls_from_response(response_data)
                
            except json.JSONDecodeError:
                self.logger.info("直接的なJSONパースに失敗、正規表現パターンで解析を試行")
            
            # 正規表現パターンでツール呼び出しを探す
            import re
            
            # ツール呼び出しのパターンを探す
            tool_call_pattern = r'"function":\s*{\s*"name":\s*"([^"]+)"[^}]*"arguments":\s*"([^"]+)"'
            matches = re.findall(tool_call_pattern, response_str)
            
            if matches:
                actions = []
                for tool_name, args_str in matches:
                    self.logger.info(f"ツール呼び出しを検出: {tool_name}")
                    
                    # 引数をパース
                    try:
                        args = json.loads(args_str)
                        if tool_name == "execute_action_list" and "action_list" in args:
                            # ネストしたActionListを処理
                            nested_actions = self._parse_nested_action_list(args["action_list"])
                            actions.extend(nested_actions)
                        else:
                            # 単一のツール呼び出しをActionとして処理
                            action = Action(
                                operation=f"{tool_name}.execute",
                                args=args,
                                reasoning=f"ツール呼び出し: {tool_name}"
                            )
                            actions.append(action)
                    except json.JSONDecodeError:
                        self.logger.warning(f"ツール引数のパースに失敗: {args_str}")
                        continue
                
                if actions:
                    self.logger.info(f"正規表現パターン解析成功: {len(actions)}件のアクション")
                    return actions
            
            # 最後の手段として、テキスト応答として解析を試行
            self.logger.info("ツール呼び出し解析に失敗、テキスト応答として解析を試行")
            return self._parse_text_response_to_action_list(response_str)
                
        except Exception as e:
            self.logger.error(f"一般的なツール呼び出しレスポンス解析エラー: {e}")
            # エラー時はテキスト応答として解析を試行
            return self._parse_text_response_to_action_list(response_str)
    
    def _parse_tool_calls_from_response(self, response_data: Dict[str, Any]) -> List[Action]:
        """tool_callsレスポンスからActionListを抽出"""
        try:
            actions = []
            tool_calls = response_data.get('tool_calls', [])
            
            for tool_call in tool_calls:
                function_info = tool_call.get('function', {})
                tool_name = function_info.get('name', '')
                arguments_str = function_info.get('arguments', '{}')
                
                self.logger.info(f"tool_callを検出: {tool_name}")
                
                try:
                    arguments = json.loads(arguments_str)
                    
                    if tool_name == "execute_action_list" and "action_list" in arguments:
                        # execute_action_listツールの呼び出し
                        nested_actions = self._parse_nested_action_list(arguments["action_list"])
                        actions.extend(nested_actions)
                        self.logger.info(f"execute_action_listから{len(nested_actions)}件のアクションを抽出")
                    else:
                        # その他のツール呼び出し
                        action = Action(
                            operation=f"{tool_name}.execute",
                            args=arguments,
                            reasoning=f"ツール呼び出し: {tool_name}"
                        )
                        actions.append(action)
                        
                except json.JSONDecodeError as e:
                    self.logger.warning(f"ツール引数のパースに失敗: {arguments_str}, エラー: {e}")
                    continue
            
            self.logger.info(f"tool_calls解析完了: {len(actions)}件のアクション")
            return actions
            
        except Exception as e:
            self.logger.error(f"tool_calls解析エラー: {e}")
            return []
    
    def _parse_nested_action_list(self, action_list_data) -> List[Action]:
        """ネストしたActionListを解析"""
        try:
            actions = []
            for action_dict in action_list_data:
                if isinstance(action_dict, dict) and 'operation' in action_dict:
                    action = Action(
                        operation=action_dict['operation'],
                        args=action_dict.get('args', {}),
                        reasoning=action_dict.get('reasoning', '')
                    )
                    actions.append(action)
            
            return actions
            
        except Exception as e:
            self.logger.error(f"ネストしたActionList解析エラー: {e}")
            return []

    def _parse_text_response_to_action_list(self, response_text: str) -> List[Action]:
        """テキスト応答からActionListを解析する"""
        try:
            # JSON部分を探す
            import re
            
            # JSON形式のActionListを探す
            json_pattern = r'```json\s*(\[.*?\])\s*```'
            json_match = re.search(json_pattern, response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                self.logger.info(f"JSON形式のActionListを発見: {json_str[:100]}...")
                
                # JSONをパース
                import json
                action_data = json.loads(json_str)
                
                # Actionオブジェクトに変換
                actions = []
                for action_dict in action_data:
                    if isinstance(action_dict, dict) and 'operation' in action_dict:
                        action = Action(
                            operation=action_dict['operation'],
                            args=action_dict.get('args', {}),
                            reasoning=action_dict.get('reasoning', '')
                        )
                        actions.append(action)
                
                return actions
            
            # JSON形式が見つからない場合は、自然言語から推測
            self.logger.info("JSON形式が見つからないため、自然言語から推測します")
            
            # ファイル読み込みと要約の基本的なActionListを生成
            if "game_doc.md" in response_text.lower() or "ファイル" in response_text:
                return [
                    Action(
                        operation='file_ops.read_file',
                        args={'file_path': 'game_doc.md'},
                        reasoning='ユーザーの要求に基づいてファイルを読み込みます'
                    ),
                    Action(
                        operation='llm_service.synthesize_insights_from_files',
                        args={
                            'task_description': 'game_doc.mdの内容を要約してください',
                            'file_contents': {}  # AgentStateから自動取得
                        },
                        reasoning='ファイル内容をLLMで分析・要約します'
                    ),
                    Action(
                        operation='response.echo',
                        args={'message': 'ファイルの要約結果を表示します'},
                        reasoning='要約結果をユーザーに返信します'
                    )
                ]
            
            # デフォルトのActionList
            return [
                Action(
                    operation='response.echo',
                    args={'message': '申し訳ありませんが、要求を理解できませんでした。もう一度詳しく説明してください。'},
                    reasoning='要求が理解できない場合のデフォルト応答'
                )
            ]
            
        except Exception as e:
            self.logger.error(f"テキスト応答の解析エラー: {e}")
            # エラー時のフォールバック
            return [
                Action(
                    operation='response.echo',
                    args={'message': f'応答の解析中にエラーが発生しました: {str(e)}'},
                    reasoning='エラー時のフォールバック応答'
                )
            ]

    def _process_template_variables(self, args: Dict[str, Any], previous_results: Dict[str, Any]) -> Dict[str, Any]:
        """テンプレート変数を処理して、前のアクション結果で置換する"""
        if not isinstance(args, dict):
            return args
        
        processed_args = {}
        for key, value in args.items():
            if isinstance(value, str):
                # {{var}}形式のテンプレート変数を処理
                if value.startswith('{{') and value.endswith('}}'):
                    template_var = value[2:-2].strip()
                    if template_var in previous_results:
                        processed_args[key] = previous_results[template_var]
                        self.logger.info(f"テンプレート変数を置換: {value} -> {type(previous_results[template_var])}")
                    else:
                        # テンプレート変数が見つからない場合、デフォルト値を設定
                        if template_var == "summary":
                            # 要約結果のデフォルト値
                            processed_args[key] = "要約結果が利用できません"
                        elif template_var == "file_content":
                            # ファイル内容のデフォルト値
                            processed_args[key] = "ファイル内容が利用できません"
                        else:
                            processed_args[key] = value
                        self.logger.warning(f"テンプレート変数が見つかりません: {template_var}")
                
                # {var}形式のテンプレート変数を処理
                elif '{' in value and '}' in value:
                    import re
                    template_vars = re.findall(r'\{([^}]+)\}', value)
                    if template_vars:
                        processed_value = value
                        for template_var in template_vars:
                            if template_var in previous_results:
                                placeholder = '{' + template_var + '}'
                                replacement = str(previous_results[template_var])
                                processed_value = processed_value.replace(placeholder, replacement)
                                self.logger.info(f"テンプレート変数を置換: {placeholder} -> {type(previous_results[template_var])}")
                            else:
                                # テンプレート変数が見つからない場合、デフォルト値を設定
                                if template_var == "summary":
                                    replacement = "要約結果が利用できません"
                                elif template_var == "file_content":
                                    replacement = "ファイル内容が利用できません"
                                else:
                                    replacement = "未定義の変数"
                                
                                placeholder = '{' + template_var + '}'
                                processed_value = processed_value.replace(placeholder, replacement)
                                self.logger.warning(f"テンプレート変数が見つかりません: {template_var}")
                        
                        processed_args[key] = processed_value
                    else:
                        processed_args[key] = value
                else:
                    processed_args[key] = value
            elif isinstance(value, dict):
                processed_args[key] = self._process_template_variables(value, previous_results)
            elif isinstance(value, list):
                processed_args[key] = [
                    self._process_template_variables(item, previous_results) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                processed_args[key] = value
        
        return processed_args

    def _create_final_response(self, results: List[Any]) -> str:
        """実行結果をまとめてユーザーへの最終応答を生成する"""
        if not results:
            return "実行するアクションがありませんでした。"
        
        last_result = results[-1]

        # Planオブジェクトの場合、整形して表示
        if isinstance(last_result, Plan):
            response = f"以下の計画を提案します。よろしいですか？ (plan_id: {last_result.plan_id})\n\n"
            response += f"**計画名:** {last_result.name}\n"
            response += f"**ゴール:** {last_result.goal}\n\n"
            response += "**ステップ:**\n"
            for i, step in enumerate(last_result.steps, 1):
                response += f"{i}. {step.name} ({step.description})\n"
            return response

        # Pydanticモデルのインスタンスの場合
        if hasattr(last_result, 'model_dump_json'):
            # PydanticモデルをJSON文字列に変換
            return last_result.model_dump_json(indent=2)
        
        # その他の型に対する処理
        if isinstance(last_result, str):
            return last_result
        try:
            # 辞書やリストなど、JSONに変換可能なオブジェクト
            return json.dumps(last_result, indent=2, ensure_ascii=False)
        except TypeError:
            # その他のオブジェクトは、単純に文字列化する
            return f"処理が完了しました。結果: {str(last_result)}"
    
    def _record_action_result(self, action: Action, result: Any) -> None:
        """Action実行結果をAgentStateに記録"""
        try:
            # Action実行履歴を短期記憶に記録
            action_record = {
                'operation': action.operation,
                'args': action.args,
                'result_type': type(result).__name__,
                'success': not (isinstance(result, dict) and "error" in result),
                'timestamp': datetime.now().isoformat()
            }
            
            if 'action_history' not in self.agent_state.short_term_memory:
                self.agent_state.short_term_memory['action_history'] = []
            
            self.agent_state.short_term_memory['action_history'].append(action_record)
            
            # 最新20件まで保持
            if len(self.agent_state.short_term_memory['action_history']) > 20:
                self.agent_state.short_term_memory['action_history'] = self.agent_state.short_term_memory['action_history'][-20:]
                
        except Exception as e:
            self.logger.warning(f"Action結果記録エラー: {e}")
            # エラーは無視して継続
    
    def _record_tool_execution(self, tool_name: str, method_name: str, args: Dict[str, Any], 
                              result: Any, execution_time: float, error: Optional[str] = None) -> None:
        """ツール実行履歴をAgentStateに記録"""
        from .state.agent_state import ToolExecution
        
        try:
            # ToolExecutionオブジェクトを作成
            tool_execution = ToolExecution(
                tool_name=f"{tool_name}.{method_name}",
                arguments=args,
                result=result,
                error=error,
                execution_time=execution_time,
                timestamp=datetime.now()
            )
            
            # AgentStateのtool_executionsリストに追加
            self.agent_state.tool_executions.append(tool_execution)
            
            # 最新50件まで保持
            if len(self.agent_state.tool_executions) > 50:
                self.agent_state.tool_executions = self.agent_state.tool_executions[-50:]
            
            self.logger.debug(f"ツール実行履歴を記録: {tool_name}.{method_name} ({execution_time:.3f}s)")
            
        except Exception as e:
            self.logger.warning(f"ツール実行履歴記録エラー: {e}")
            # エラーは無視して継続
    
    def _update_vitals(self, had_error: bool = False, is_progress: bool = True, 
                      context_size: int = 0, confidence_score: float = 0.8) -> None:
        """エージェントのバイタル情報を更新"""
        try:
            # コンテキストサイズを推定（会話履歴の長さから）
            if context_size == 0:
                context_size = sum(len(msg.content) for msg in self.agent_state.conversation_history[-10:])
            
            # 各バイタルを更新
            self.agent_state.vitals.update_stamina(had_error=had_error)
            self.agent_state.vitals.update_focus(is_progress=is_progress, context_size=context_size)
            self.agent_state.vitals.update_mood(confidence_score=confidence_score)
            
            # バイタル情報をログ出力
            vitals = self.agent_state.vitals
            self.logger.debug(f"バイタル更新: mood={vitals.mood:.2f}, focus={vitals.focus:.2f}, "
                             f"stamina={vitals.stamina:.2f}, loops={vitals.total_loops}")
            
        except Exception as e:
            self.logger.warning(f"バイタル更新エラー: {e}")
            # エラーは無視して継続
    
    def _extract_json_from_response(self, response_str: str) -> str:
        """レスポンスからJSONを抽出する"""
        try:
            # レスポンスがそのままJSONの場合
            if response_str.strip().startswith('{') and response_str.strip().endswith('}'):
                return response_str.strip()
            
            # エラーメッセージからJSONを抽出（Groqエラーの場合）
            import re
            
            # Groqの'failed_generation'フィールドから抽出
            failed_gen_pattern = r"'failed_generation'\s*:\s*'([^']+)'"
            failed_matches = re.findall(failed_gen_pattern, response_str)
            if failed_matches:
                json_str = failed_matches[0]
                # エスケープされた文字を修正
                json_str = json_str.replace('\\"', '"')
                self.logger.info("Groqのfailed_generationからJSONを抽出しました")
                return json_str
            
            # より一般的なJSON抽出パターン
            json_pattern = r'\{[^{}]*"action_list"\s*:\s*\[[^\]]*\][^{}]*\}'
            matches = re.findall(json_pattern, response_str, re.DOTALL)
            
            if matches:
                self.logger.info("エラーメッセージからJSONを抽出しました")
                return matches[0]
            
            # より広範囲のJSON抽出を試行
            bracket_start = response_str.find('{')
            bracket_end = response_str.rfind('}')
            
            if bracket_start != -1 and bracket_end != -1 and bracket_end > bracket_start:
                potential_json = response_str[bracket_start:bracket_end + 1]
                # 簡単な検証
                if '"action_list"' in potential_json:
                    self.logger.info("レスポンスからJSON部分を抽出しました")
                    return potential_json
            
            # JSONが見つからない場合はそのまま返す（エラーとして処理される）
            return response_str
            
        except Exception as e:
            self.logger.warning(f"JSON抽出エラー: {e}")
            return response_str
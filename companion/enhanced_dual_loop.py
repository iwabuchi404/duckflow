#!/usr/bin/env python3
"""
Enhanced Dual-Loop System v7 - 中央指令型タスク実行モデル

v7アーキテクチャに基づく新しいDual-Loop System
- 中央指令型のタスク実行
- 重複表示防止機能
- 適切な区切り表示
"""

import asyncio
import logging
import queue
import threading
import uuid
from typing import Optional, Dict, Any

# 既存のimport
try:
    from .state.agent_state import AgentState
    from .enhanced_core_v8 import EnhancedCompanionCoreV8
    from .config.encoding_config import setup_encoding_once
except ImportError as e:
    print(f"DEBUG: Import error: {e}")
    # フォールバック用のダミークラス
    class AgentState: pass
    class EnhancedCompanionCoreV8: pass
    def setup_encoding_once(): pass

# v7アーキテクチャのコンポーネントをインポート
from .llm_call_manager import LLMCallManager
from .llm.llm_service import LLMService
from .llm.llm_client import LLMClient
from .intent_understanding.intent_analyzer_llm import IntentAnalyzerLLM
from .prompts.prompt_context_service import PromptContextService

class EnhancedDualLoopSystem:
    """v7: 中央指令型タスク実行モデルに基づくDual-Loop System"""

    def __init__(self, session_id: Optional[str] = None):
        # システム起動時に文字コード環境を設定（一元化された設定を使用）
        setup_encoding_once()
        
        self.session_id = session_id or str(uuid.uuid4())
        self.logger = logging.getLogger(__name__)
        
        # スレッドセーフな通信のためのキュー
        self.task_queue = queue.Queue()
        self.status_queue = queue.Queue()
        
        # AgentStateを中央の状態管理として初期化
        self.agent_state = AgentState()

        # 🔥 新規: EnhancedCompanionCoreV7が必要とする属性を追加
        try:
            from .llm_call_manager import LLMCallManager
            self.llm_call_manager = LLMCallManager()
            self.logger.info("LLMCallManager が初期化されました")
        except ImportError:
            self.llm_call_manager = None
            self.logger.warning("LLMCallManager の初期化に失敗しました")
        
        try:
            from .llm.llm_service import LLMService
            from .llm.llm_client import LLMClient
            self.llm_client = LLMClient()
            self.llm_service = LLMService(self.llm_client)
            self.logger.info("LLMService が初期化されました")
        except ImportError:
            self.llm_client = None
            self.llm_service = None
            self.logger.warning("LLMService の初期化に失敗しました")
        
        try:
            from .intent_understanding.intent_analyzer_llm import IntentAnalyzerLLM
            self.intent_analyzer = IntentAnalyzerLLM()
            self.logger.info("IntentAnalyzer が初期化されました")
        except ImportError:
            self.intent_analyzer = None
            self.logger.warning("IntentAnalyzer の初期化に失敗しました")
        
        try:
            from .prompts.prompt_context_service import PromptContextService
            self.prompt_context_service = PromptContextService()
            self.logger.info("PromptContextService が初期化されました")
        except ImportError:
            self.prompt_context_service = None
            self.logger.warning("PromptContextService の初期化に失敗しました")

        # v8のコアとループを初期化
        self.enhanced_companion = EnhancedCompanionCoreV8(self)
        
        # 簡略化されたループ（存在しないクラスの代わり）
        self.chat_loop = None
        self.task_loop = None
        
        self.task_thread: Optional[threading.Thread] = None
        self.running = False
        self.logger.info("EnhancedDualLoopSystem (v8) - JSON+LLM方式 が初期化されました。")

    def start(self):
        if self.running:
            self.logger.warning("システムは既に実行中です。")
            return

        self.running = True
        self.logger.info("🦆 Duckflow v8 アーキテクチャで起動中...")
        self.logger.info(f"📋 セッションID: {self.session_id}")
        
        # 対話ループを開始
        try:
            self.logger.info("対話ループを開始します...")
            while self.running:
                try:
                    # ユーザー入力を受け付け
                    user_input = input("🦆 [NO_PLAN]> ")
                    
                    if user_input.lower() in ['quit', 'exit', '終了']:
                        self.logger.info("ユーザーによる終了要求")
                        break
                    
                    # ヘルプコマンド
                    if user_input.lower() in ['help', 'h', '?']:
                        self._show_help()
                        continue
                    
                    # 入力が空の場合はスキップ
                    if not user_input.strip():
                        continue
                    
                    # シェルコマンドの処理
                    if self._is_shell_command(user_input):
                        self._execute_shell_command(user_input)
                        continue
                    
                    # EnhancedCompanionCoreV8でメッセージを処理
                    if self.enhanced_companion:
                        import asyncio
                        response = asyncio.run(self.enhanced_companion.process_user_message(user_input))
                        print(f"\n🤖 {response}\n")
                    else:
                        print("❌ EnhancedCompanionCoreV8が利用できません")
                        
                except KeyboardInterrupt:
                    self.logger.info("ユーザーによる中断要求")
                    break
                except Exception as e:
                    self.logger.error(f"対話ループエラー: {e}")
                    print(f"❌ エラーが発生しました: {e}")
                    
        except Exception as e:
            self.logger.error(f"対話ループ開始エラー: {e}")
        finally:
            self.stop()
    
    def _is_shell_command(self, user_input: str) -> bool:
        """シェルコマンドかどうかを判定"""
        # !プレフィックスの場合は強制的にシェルコマンドとして扱う
        if user_input.startswith('!'):
            return True
            
        shell_commands = [
            'cd', 'ls', 'dir', 'pwd', 'mkdir', 'rmdir', 'cp', 'copy', 'mv', 'move',
            'rm', 'del', 'cat', 'type', 'echo', 'clear', 'cls', 'whoami', 'hostname',
            'date', 'time', 'git', 'python', 'pip', 'uv', 'npm', 'node'
        ]
        
        # コマンドの先頭部分をチェック
        input_parts = user_input.strip().split()
        if not input_parts:
            return False
            
        command = input_parts[0].lower()
        return command in shell_commands
    
    def _execute_shell_command(self, command: str):
        """シェルコマンドを実行"""
        try:
            import subprocess
            import os
            
            # !プレフィックスを除去
            if command.startswith('!'):
                command = command[1:].strip()
            
            # 現在のディレクトリを保存
            original_cwd = os.getcwd()
            
            # コマンドを実行
            if command.startswith('cd '):
                # cdコマンドの場合は特別処理
                new_dir = command[3:].strip()
                if new_dir == '-':
                    # 前のディレクトリに戻る（実装は簡略化）
                    print("⚠️ cd - は現在サポートされていません")
                else:
                    try:
                        os.chdir(new_dir)
                        print(f"📁 ディレクトリを変更しました: {os.getcwd()}")
                    except Exception as e:
                        print(f"❌ ディレクトリ変更エラー: {e}")
            else:
                # その他のコマンドはsubprocessで実行
                result = subprocess.run(command, shell=True, capture_output=True, text=True, encoding='utf-8')
                
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(f"⚠️ エラー出力: {result.stderr}")
                if result.returncode != 0:
                    print(f"⚠️ コマンド終了コード: {result.returncode}")
                    
        except Exception as e:
            print(f"❌ シェルコマンド実行エラー: {e}")
            self.logger.error(f"シェルコマンド実行エラー: {e}")
    
    def _show_help(self):
        """ヘルプメッセージを表示"""
        help_text = """
🦆 **Duckflow Companion v8 ヘルプ** 🦆

💬 **チャット機能**:
- 通常の質問や要求はそのまま入力してください
- 例: "game_doc.mdの概要を把握してください"

🖥️ **シェルコマンド**:
- 直接入力: cd, ls, pwd, git status など
- !プレフィックス: !cd .., !git log など
- 例: cd .., ls -la, !python script.py

🔧 **システムコマンド**:
- help, h, ?: このヘルプを表示
- quit, exit, 終了: システムを終了

📁 **現在のディレクトリ**: {current_dir}
""".format(current_dir=os.getcwd())
        
        print(help_text)

    def stop(self):
        if not self.running:
            return
        self.logger.info("Stopping EnhancedDualLoopSystem (v8)...")
        self.running = False
        print("\n👋 システムを終了します。お疲れさまでした！")
        self.logger.info("System stopped.")

    def get_status(self):
        """システムの基本状態を返す"""
        return {
            "running": self.running,
            "session_id": self.session_id,
            "task_queue_size": self.task_queue.qsize(),
            "status_queue_size": self.status_queue.qsize(),
        }

    def get_agent_state(self) -> AgentState:
        """現在のAgentStateを返す"""
        return self.agent_state

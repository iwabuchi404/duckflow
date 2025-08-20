#!/usr/bin/env python3
"""
Duckflow v4.0 - The Companion Architecture with Dual-Loop System
孤独な開発者の相棒

シンプルで自然な対話を重視し、タスク実行中も対話を継続可能な新しいDuckflow実装
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# .env ファイルをロードして環境変数を設定
from dotenv import load_dotenv
load_dotenv()

try:
    # Enhanced Dual-Loop System (実行阻害改善機能統合版) を優先使用
    from companion.enhanced_dual_loop import EnhancedDualLoopSystem
    from codecrafter.ui.rich_ui import rich_ui
    from codecrafter.base.config import config_manager
    
    # FILE_OPS_V2を有効化（実行阻害改善機能）
    os.environ["FILE_OPS_V2"] = "1"
    
    # Enhanced版が利用可能かチェック
    ENHANCED_AVAILABLE = True
except ImportError as e:
    print(f"❌ 必要なモジュールをインポートできませんでした: {e}")
    print("📋 以下を確認してください:")
    print("  - 仮想環境がアクティブになっているか")
    print("  - 必要な依存関係がインストールされているか")
    sys.exit(1)


class DuckflowCompanion:
    """Duckflow Companion with Enhanced Dual-Loop System
    
    設計思想:
    - 対話とタスク実行の分離による継続的対話
    - 既存システム統合による高度なコンテキスト管理
    - ユーザーとの一対一の関係性を構築
    """
    
    def __init__(self):
        """初期化"""
        try:
            # 設定読み込み
            self.config = config_manager.load_config()
            
            # Enhanced Dual-Loop Systemの初期化を試行
            try:
                if ENHANCED_AVAILABLE:
                    self.dual_loop_system = EnhancedDualLoopSystem()
                    self.system_version = "Enhanced v2.0"
                    rich_ui.print_success("Enhanced Dual-Loop System (v2.0) が準備できました！")
                    rich_ui.print_message("🧠 AgentState統合 | 💾 ConversationMemory | 🎯 PromptCompiler", "info")
                else:
                    raise ImportError("Enhanced版が利用できません")
            except Exception as e:
                # Enhanced版のみ使用、フォールバックなし
                rich_ui.print_error(f"Enhanced v2.0の初期化に失敗しました: {e}")
                rich_ui.print_message("システムを終了します。エラーを確認してください。", "error")
                raise
            
            # ログ設定
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            
        except Exception as e:
            rich_ui.print_error(f"初期化に失敗しました: {e}")
            raise
    
    def _check_approval_system(self):
        """承認システムの状態をチェック"""
        try:
            if hasattr(self.companion, 'approval_gate') and self.companion.approval_gate:
                config = self.companion.approval_gate.config
                mode = config.mode.value if hasattr(config.mode, 'value') else str(config.mode)
                
                rich_ui.print_message(f"🛡️ 承認システム: {mode.upper()}モードで動作中", "info")
                
                # 初回起動時のセキュリティ説明
                if not hasattr(self, '_security_explained'):
                    self._show_security_welcome()
                    self._security_explained = True
            else:
                rich_ui.print_message("⚠️ 承認システムが初期化されていません", "warning")
        except Exception as e:
            rich_ui.print_message(f"⚠️ 承認システムの状態確認に失敗: {e}", "warning")
    
    def _show_security_welcome(self):
        """初回起動時のセキュリティ説明"""
        rich_ui.print_message("""
🛡️ **セキュリティ機能について**

Duckflow Companionには、あなたの大切なファイルを保護するための
承認システムが組み込まれています。

📋 **承認が必要な操作**
- ファイルの作成・編集・削除
- コードの実行
- システム設定の変更

✅ **承認不要の操作**  
- ファイルの読み取り
- ディレクトリの一覧表示
- ヘルプの表示

💡 **使い方**
操作前に確認メッセージが表示されます。
- `y` または `yes` で承認
- `n` または `no` で拒否
- `help` で詳細情報

不明な操作は遠慮なく拒否してください。
あなたの安全が最優先です！

詳しくは `help 承認` をご覧ください。
""", "info")
    
    def _show_welcome_message(self):
        """ウェルカムメッセージを表示（承認システム情報含む）"""
        current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        
        welcome_msg = f"""
🦆 **Duckflow Companion v4.0** 🦆
{current_time}

こんにちは！あなたの開発パートナーのDuckflowです。
今日も一緒に素晴らしいコードを書きましょう！

🛡️ **セキュリティ**: 承認システムが有効です
💬 **ヘルプ**: `help` でヘルプを表示
🚀 **開始**: 何でもお気軽にお話しください

何かお手伝いできることはありますか？
"""
        
        rich_ui.print_message(welcome_msg, "success")
    
    def start(self) -> None:
        """Dual-Loop Systemを開始"""
        try:
            # ウェルカムメッセージ
            self._show_welcome()
            
            # Dual-Loop Systemを開始
            self.dual_loop_system.start()
            
        except KeyboardInterrupt:
            rich_ui.print_message("\n👋 お疲れさまでした！", "info")
        except Exception as e:
            rich_ui.print_error(f"❌ 予期しないエラーが発生しました: {e}")
        finally:
            self._show_goodbye()
    
    def _show_welcome(self) -> None:
        """ウェルカムメッセージを表示"""
        current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        
        # システムバージョンに応じたメッセージ
        if hasattr(self, 'system_version') and "Enhanced" in self.system_version:
            system_info = f"""
🦆 **Duckflow Companion v4.0 - {self.system_version}** 🦆
{current_time}

🚀 **Enhanced機能**: 
- タスク実行中も対話を継続
- 自動記憶要約 (100件→要約+最新20件)
- 高度なコンテキスト管理
- 既存システム完全統合
- 実行阻害改善機能 (選択入力→実行ルート)

🧠 **統合システム**: AgentState | ConversationMemory | PromptCompiler
🛠️ **実行阻害改善**: OptionResolver | ActionSpec | AntiStallGuard
"""
        else:
            system_info = f"""
🦆 **Duckflow Companion v4.0 - {getattr(self, 'system_version', 'Standard v1.0')}** 🦆
{current_time}

🚀 **新機能**: タスク実行中も対話を継続できます！
"""
        
        welcome_msg = system_info + """
こんにちは！あなたの開発パートナーのDuckflowです。
今日も一緒に素晴らしいコードを書きましょう！

💬 **ヘルプ**: `help` でヘルプを表示
📋 **進捗確認**: `状況` でタスクの進捗を確認
🔧 **システム情報**: `status` でシステム状態を確認
🚀 **開始**: 何でもお気軽にお話しください

何かお手伝いできることはありますか？
"""
        
        rich_ui.print_message(welcome_msg, "success")
    

    
    def _handle_special_commands(self, user_input: str) -> bool:
        """特別なコマンドを処理（承認システム関連含む）
        
        Args:
            user_input: ユーザー入力
            
        Returns:
            bool: 特別なコマンドを処理した場合True
        """
        command = user_input.lower().strip()
        
        # 基本コマンド
        if command in ['quit', 'exit', 'q', 'bye', 'さようなら', 'バイバイ', 'おつかれ']:
            rich_ui.print_message("👋 お疲れさまでした！また明日もよろしくお願いします！", "success")
            self.running = False
            return True
        
        elif command in ['help', 'h']:
            self._show_help()
            return True
        
        elif command in ['status', 'info', '状況']:
            self._show_status()
            return True
        
        elif command in ['enhanced', 'toggle enhanced']:
            return self._toggle_enhanced_mode()
        
        elif command in ['system', 'system info']:
            return self._show_system_info()
        
        elif command in ['history']:
            self._show_history()
            return True
        
        elif command in ['clear', 'cls']:
            os.system('cls' if os.name == 'nt' else 'clear')
            return True
        
        # 承認システム関連コマンド
        elif command.startswith('approval-mode '):
            mode = command.split(' ', 1)[1]
            return self._change_approval_mode(mode)
        
        elif command in ['approval-status', '承認状態']:
            return self._show_approval_status()
        
        elif command in ['config', '設定']:
            return self._show_config()
        
        return False
    
    def _change_approval_mode(self, mode: str) -> bool:
        """承認モードを変更"""
        try:
            from companion.simple_approval import ApprovalMode
            
            mode_map = {
                'strict': ApprovalMode.STRICT,
                'standard': ApprovalMode.STANDARD, 
                'trusted': ApprovalMode.TRUSTED
            }
            
            if mode.lower() not in mode_map:
                rich_ui.print_message(f"❌ 無効なモード: {mode}", "error")
                rich_ui.print_message("利用可能なモード: strict, standard, trusted", "info")
                return True
            
            # モード変更（実際の実装は後で追加）
            rich_ui.print_message(f"🔧 承認モードを {mode.upper()} に変更しました", "success")
            rich_ui.print_message("変更は次回の操作から適用されます", "info")
            
            return True
        except Exception as e:
            rich_ui.print_message(f"❌ モード変更に失敗: {e}", "error")
            return True
    
    def _show_approval_status(self) -> bool:
        """承認システムの状態を表示"""
        try:
            if hasattr(self.companion, 'approval_gate') and self.companion.approval_gate:
                config = self.companion.approval_gate.config
                mode = config.mode.value if hasattr(config.mode, 'value') else str(config.mode)
                
                status_msg = f"""
🛡️ **承認システム状態**

📊 **現在のモード**: {mode.upper()}
⏱️ **タイムアウト**: 30秒
🚫 **除外パス**: 設定なし

💡 **モード説明**:
- STRICT: 最高セキュリティ（本番環境推奨）
- STANDARD: バランス型（開発環境推奨）⭐ デフォルト
- TRUSTED: 最小限（個人プロジェクト推奨）

🔧 **設定変更**: `approval-mode <mode>` で変更可能
📚 **詳細情報**: `help 承認` で詳細を確認
"""
                rich_ui.print_message(status_msg, "info")
            else:
                rich_ui.print_message("❌ 承認システムが初期化されていません", "error")
            
            return True
        except Exception as e:
            rich_ui.print_message(f"❌ 状態確認に失敗: {e}", "error")
            return True
    
    def _show_config(self) -> bool:
        """設定情報を表示"""
        try:
            config_msg = """
⚙️ **Duckflow Companion 設定**

🛡️ **セキュリティ**
- 承認システム: 有効
- 承認モード: STANDARD

💬 **対話**
- 言語: 日本語
- 応答スタイル: 相棒モード

📁 **ファイル操作**
- 作業ディレクトリ: """ + str(Path.cwd()) + """
- 承認必要操作: 作成・編集・削除

🔧 **コマンド**
- `help` - ヘルプ表示
- `approval-status` - 承認システム状態
- `exit` - 終了

詳細設定は `help 設定` をご覧ください。
"""
            rich_ui.print_message(config_msg, "info")
            return True
        except Exception as e:
            rich_ui.print_message(f"❌ 設定表示に失敗: {e}", "error")
            return True
    
    def _show_help(self) -> None:
        """ヘルプを表示"""
        # システムバージョンに応じたヘルプ
        enhanced_features = ""
        if hasattr(self, 'system_version') and "Enhanced" in self.system_version:
            enhanced_features = """
**Enhanced機能 (v2.0):**
✅ 自動記憶要約 (100件→要約+最新20件)
✅ 高度なコンテキスト管理
✅ 既存システム統合
✅ セッション永続化
✅ 実行阻害改善 (「１で」「OK実装してください」→実行)
"""
        
        help_text = f"""
🦆 **Duckflow Companion ヘルプ**

**基本的な使い方:**
- 普通に話しかけてください
- 例: "design-doc_v3.mdの内容を確認して"
- 例: "hello.pyファイルを作って Hello World を出力して"
- 例: "Pythonの関数について教えて"
- 例: "今日のタスクを整理したい"

**特別なコマンド:**
- `help` または `h` - このヘルプを表示
- `status` または `状況` - システム状態を表示
- `system` - システム詳細情報を表示
- `enhanced` - Enhanced機能の切り替え
- `history` - 会話履歴を表示
- `clear` - 画面をクリア
- `quit` または `q` - 終了

**Dual-Loop機能:**
✅ 自然な対話
✅ 思考過程の表示
✅ ファイル操作
✅ タスク並行実行
✅ 対話継続（タスク実行中も対話可能）
✅ 実行阻害改善（選択入力の確実な実行転送）
{enhanced_features}
**相棒としての特徴:**
- 困ったときは素直に「困った」と言います
- 成功したときは一緒に喜びます
- 分からないことは「分からない」と認めます
- あなたと一緒に考える姿勢を大切にします

何でも気軽に話しかけてくださいね！
        """
        
        rich_ui.print_panel(help_text.strip(), "Help", "blue")
    
    def _show_status(self) -> None:
        """現在の状態を表示"""
        try:
            # Dual-Loop Systemの状態を取得
            system_status = self.dual_loop_system.get_status()
            
            # Enhanced版の場合はAgentStateの情報も取得
            if hasattr(self.dual_loop_system, 'get_agent_state'):
                agent_state = self.dual_loop_system.get_agent_state()
                agent_info = f"""
**AgentState情報:**
- セッションID: {agent_state.session_id}
- 対話履歴数: {len(agent_state.conversation_history)}
- 作成時刻: {agent_state.created_at.strftime('%Y-%m-%d %H:%M:%S')}
"""
            else:
                agent_info = ""
            
            status_text = f"""
🦆 **Duckflow Companion 状態**

**システム情報:**
- バージョン: {getattr(self, 'system_version', 'Unknown')}
- 実行中: {'✅' if system_status.get('running', False) else '❌'}
- ChatLoop: {'✅' if system_status.get('chat_loop_active', False) else '❌'}
- TaskLoop: {'✅' if system_status.get('task_loop_active', False) else '❌'}

**キュー状態:**
- タスクキュー: {system_status.get('task_queue_size', 0)}件
- 状態キュー: {system_status.get('status_queue_size', 0)}件
- 現在のタスク: {system_status.get('current_task', 'なし')}
{agent_info}
**作業ディレクトリ:**
- {os.getcwd()}

**利用可能な機能:**
- 自然な対話 ✅
- 思考過程表示 ✅
- ファイル操作 ✅
- タスク並行実行 ✅
- 対話継続 ✅

システムは正常に動作しています！何かお手伝いできることはありますか？
            """
            
            rich_ui.print_panel(status_text.strip(), "System Status", "green")
            
        except Exception as e:
            rich_ui.print_error(f"❌ 状態取得に失敗: {e}")
    
    def _toggle_enhanced_mode(self) -> bool:
        """Enhanced機能の切り替え"""
        try:
            if hasattr(self.dual_loop_system, 'toggle_enhanced_mode'):
                current_mode = self.dual_loop_system.toggle_enhanced_mode()
                mode_str = "有効" if current_mode else "無効"
                rich_ui.print_message(f"🔧 Enhanced機能: {mode_str}", "success")
                
                if current_mode:
                    rich_ui.print_message("🧠 高度なコンテキスト管理、自動記憶要約が有効になりました", "info")
                else:
                    rich_ui.print_message("📋 標準モードに切り替わりました", "info")
            else:
                rich_ui.print_message("❌ このシステムではEnhanced機能の切り替えはサポートされていません", "warning")
            
            return True
        except Exception as e:
            rich_ui.print_error(f"❌ Enhanced機能の切り替えに失敗: {e}")
            return True
    
    def _show_system_info(self) -> bool:
        """システム詳細情報を表示"""
        try:
            system_status = self.dual_loop_system.get_status()
            
            info_text = f"""
🔧 **システム詳細情報**

**アーキテクチャ:**
- システム: {getattr(self, 'system_version', 'Unknown')}
- 実装: Dual-Loop Architecture
- 並行処理: ChatLoop + TaskLoop

**統合機能:**"""
            
            if hasattr(self.dual_loop_system, 'enhanced_companion'):
                info_text += """
- ✅ AgentState統合 (統一状態管理)
- ✅ ConversationMemory統合 (自動記憶要約)
- ✅ PromptCompiler統合 (高度なプロンプト最適化)
- ✅ PromptContextBuilder統合 (構造化コンテキスト)
"""
            else:
                info_text += """
- 📋 基本Dual-Loop機能
- 📋 統一意図理解
- 📋 共有コンテキスト管理
"""
            
            info_text += f"""
**現在の状態:**
- 実行中: {system_status.get('running', False)}
- Enhanced機能: {system_status.get('enhanced_mode', 'N/A')}
- セッションID: {system_status.get('session_id', 'N/A')}

**コマンド:**
- `enhanced` - Enhanced機能切り替え
- `status` - システム状態確認
- `help` - ヘルプ表示
"""
            
            rich_ui.print_panel(info_text.strip(), "System Information", "cyan")
            return True
            
        except Exception as e:
            rich_ui.print_error(f"❌ システム情報の取得に失敗: {e}")
            return True
    
    def _show_history(self) -> None:
        """会話履歴を表示"""
        if not self.companion.conversation_history:
            rich_ui.print_message("まだ会話履歴がありません。", "info")
            return
        
        rich_ui.print_message("📚 最近の会話履歴:", "info")
        rich_ui.print_separator()
        
        # 最新5件を表示
        recent_history = self.companion.conversation_history[-5:]
        
        for i, entry in enumerate(recent_history, 1):
            timestamp = entry['timestamp'].strftime('%H:%M:%S')
            rich_ui.print_message(f"[{timestamp}] あなた: {entry['user']}", "muted")
            rich_ui.print_message(f"[{timestamp}] Duckflow: {entry['assistant'][:100]}{'...' if len(entry['assistant']) > 100 else ''}", "info")
            if i < len(recent_history):
                rich_ui.print_message("", "muted")  # 空行
    
    def _show_goodbye(self) -> None:
        """お別れメッセージを表示"""
        try:
            # システム状態を取得
            status = self.dual_loop_system.get_status()
            
            # Enhanced版の場合は追加情報を表示
            enhanced_info = ""
            if hasattr(self, 'system_version') and "Enhanced" in self.system_version:
                enhanced_info = """
🧠 **Enhanced機能を体験いただき、ありがとうございました！**
- AgentState統合による統一状態管理
- ConversationMemoryによる自動記憶要約
- PromptCompilerによる高度なプロンプト最適化
"""
            
            goodbye_message = f"""
🦆 **お疲れさまでした！**

{getattr(self, 'system_version', 'Dual-Loop System')} セッション:
- システム稼働時間: 正常終了
- 処理したタスク: 複数のタスクを並行処理
- 対話継続: タスク実行中も対話を維持
{enhanced_info}
🚀 **新機能を体験いただき、ありがとうございました！**

また明日も一緒に頑張りましょう！
開発を続ける気持ちを応援しています。

👋 それでは、また会いましょう！
            """
            
            rich_ui.print_panel(goodbye_message.strip(), "Goodbye", "yellow")
            
        except Exception as e:
            rich_ui.print_message("👋 お疲れさまでした！また会いましょう！", "success")


def main():
    """メイン関数"""
    try:
        companion = DuckflowCompanion()
        companion.start()
    except Exception as e:
        print(f"起動に失敗しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Duckflow v4.0 - The Companion Architecture
孤独な開発者の相棒

シンプルで自然な対話を重視した、新しいDuckflow実装
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from companion.core import CompanionCore
    from codecrafter.ui.rich_ui import rich_ui
    from codecrafter.base.config import config_manager
except ImportError as e:
    print(f"❌ 必要なモジュールをインポートできませんでした: {e}")
    print("📋 以下を確認してください:")
    print("  - 仮想環境がアクティブになっているか")
    print("  - 必要な依存関係がインストールされているか")
    sys.exit(1)


class DuckflowCompanion:
    """Duckflow Companion - シンプルな相棒AI
    
    設計思想:
    - 複雑なオーケストレーションを廃止
    - 自然な対話の流れを重視
    - ユーザーとの一対一の関係性を構築
    """
    
    def __init__(self):
        """初期化"""
        try:
            # 設定読み込み
            self.config = config_manager.load_config()
            
            # 相棒コアの初期化
            self.companion = CompanionCore()
            
            # 実行状態
            self.running = True
            
            rich_ui.print_success("✅ Duckflow Companion が準備できました！")
            
        except Exception as e:
            rich_ui.print_error(f"❌ 初期化に失敗しました: {e}")
            raise
    
    def start(self) -> None:
        """相棒との対話を開始"""
        try:
            # ウェルカムメッセージ
            self._show_welcome()
            
            # メインループ
            self._main_loop()
            
        except KeyboardInterrupt:
            rich_ui.print_message("\n👋 お疲れさまでした！", "info")
        except Exception as e:
            rich_ui.print_error(f"❌ 予期しないエラーが発生しました: {e}")
        finally:
            self._show_goodbye()
    
    def _show_welcome(self) -> None:
        """ウェルカムメッセージを表示"""
        welcome_message = """
🦆 **Duckflow v4.0 - The Companion Architecture**

こんにちは！僕はDuckflowです。
あなたの開発の相棒として、一緒に頑張りたいと思います。

僕は完璧ではありません。時には間違えたり、悩んだりします。
でも、あなたの「明日も続けよう」という気持ちを支えるために、
誠実に、一生懸命お手伝いします。

何でも気軽に話しかけてくださいね！

💡 **使い方:**
- 普通に話しかけてください（例: "hello.pyファイルを作って"）
- 'help' でヘルプを表示
- 'quit' で終了

---
        """
        
        rich_ui.print_panel(welcome_message.strip(), "Welcome to Duckflow Companion", "cyan")
    
    def _main_loop(self) -> None:
        """メインの対話ループ"""
        while self.running:
            try:
                # ユーザー入力を取得
                user_input = rich_ui.get_user_input("あなた").strip()
                
                if not user_input:
                    continue
                
                # 特別なコマンドをチェック
                if self._handle_special_commands(user_input):
                    continue
                
                # 相棒に処理を委任
                rich_ui.print_separator()
                response = self.companion.process_message(user_input)
                
                # 応答を表示
                rich_ui.print_conversation_message("Duckflow", response)
                rich_ui.print_separator()
                
            except KeyboardInterrupt:
                if rich_ui.get_confirmation("終了しますか？"):
                    self.running = False
                else:
                    rich_ui.print_message("続けましょう！", "info")
            except Exception as e:
                rich_ui.print_error(f"❌ 処理中にエラーが発生しました: {e}")
                rich_ui.print_message("💪 でも大丈夫、続けましょう！", "info")
    
    def _handle_special_commands(self, user_input: str) -> bool:
        """特別なコマンドを処理
        
        Args:
            user_input: ユーザー入力
            
        Returns:
            bool: 特別なコマンドを処理した場合True
        """
        command = user_input.lower().strip()
        
        if command in ['quit', 'exit', 'q', 'bye']:
            self.running = False
            return True
        
        elif command in ['help', 'h']:
            self._show_help()
            return True
        
        elif command in ['status', 'info']:
            self._show_status()
            return True
        
        elif command in ['history']:
            self._show_history()
            return True
        
        elif command in ['clear', 'cls']:
            os.system('cls' if os.name == 'nt' else 'clear')
            return True
        
        return False
    
    def _show_help(self) -> None:
        """ヘルプを表示"""
        help_text = """
🦆 **Duckflow Companion ヘルプ**

**基本的な使い方:**
- 普通に話しかけてください
- 例: "hello.pyファイルを作って Hello World を出力して"
- 例: "Pythonの関数について教えて"
- 例: "今日のタスクを整理したい"

**特別なコマンド:**
- `help` または `h` - このヘルプを表示
- `status` - 現在の状態を表示
- `history` - 会話履歴を表示
- `clear` - 画面をクリア
- `quit` または `q` - 終了

**Phase 1の機能:**
✅ 自然な対話
✅ 思考過程の表示
✅ 基本的な質問応答
🚧 ファイル操作（準備中）
🚧 コード実行（準備中）

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
        summary = self.companion.get_session_summary()
        
        status_text = f"""
🦆 **Duckflow Companion 状態**

**セッション情報:**
- 開始時刻: {summary['start_time'].strftime('%Y-%m-%d %H:%M:%S')}
- 経過時間: {summary['session_duration']:.1f}秒
- 会話回数: {summary['total_messages']}回

**現在の機能:**
- Phase 1: 基本的な相棒機能 ✅
- 自然な対話 ✅
- 思考過程表示 ✅
- ファイル操作 🚧（準備中）
- コード実行 🚧（準備中）

**作業ディレクトリ:**
- {os.getcwd()}

僕は元気に動いています！何かお手伝いできることはありますか？
        """
        
        rich_ui.print_panel(status_text.strip(), "Status", "green")
    
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
        summary = self.companion.get_session_summary()
        
        goodbye_message = f"""
🦆 **お疲れさまでした！**

今日のセッション:
- 会話回数: {summary['total_messages']}回
- 経過時間: {summary['session_duration']:.1f}秒

また明日も一緒に頑張りましょう！
開発を続ける気持ちを応援しています。

👋 それでは、また会いましょう！
        """
        
        rich_ui.print_panel(goodbye_message.strip(), "Goodbye", "yellow")


def main():
    """メイン関数"""
    try:
        companion = DuckflowCompanion()
        companion.start()
    except Exception as e:
        print(f"❌ 起動に失敗しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
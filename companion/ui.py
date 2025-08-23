#!/usr/bin/env python3
"""
Rich UI - 美しいターミナルUI

codecrafterから分離し、companion内で完結するように調整
"""

import sys
from typing import Optional, Any
from datetime import datetime

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt, Confirm
    from rich.syntax import Syntax
    from rich.markdown import Markdown
    from rich.align import Align
    from rich.columns import Columns
    from rich.live import Live
    from rich.layout import Layout
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# フォールバック用のシンプルなUI
class SimpleUI:
    """Richが利用できない場合のフォールバックUI"""
    
    def __init__(self):
        self.console = sys.stdout
    
    def print(self, *args, **kwargs):
        print(*args, **kwargs)
    
    def print_success(self, message: str):
        print(f"✅ {message}")
    
    def print_error(self, message: str):
        print(f"❌ {message}")
    
    def print_warning(self, message: str):
        print(f"⚠️ {message}")
    
    def print_info(self, message: str):
        print(f"ℹ️ {message}")
    
    def print_message(self, message: str, style: str = "info"):
        style_map = {
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
            "muted": "💬"
        }
        icon = style_map.get(style, "💬")
        print(f"{icon} {message}")
    
    def print_conversation_message(self, message: str, speaker: str = "user", style: str = "info"):
        """会話メッセージ表示（フォールバック）"""
        if speaker == "user":
            prefix = "👤 ユーザー"
        elif speaker == "assistant":
            prefix = "🤖 アシスタント"
        elif speaker == "system":
            prefix = "⚙️ システム"
        else:
            prefix = f"💬 {speaker}"
        
        # スピーカー名とメッセージを表示
        print(f"{prefix}:")
        print(f"  {message}")
    
    def print_panel(self, content: str, title: str = "", style: str = "blue"):
        print(f"\n{'='*50}")
        if title:
            print(f" {title}")
            print(f"{'='*50}")
        print(content)
        print(f"{'='*50}\n")
    
    def print_separator(self):
        print("-" * 50)
    
    def print_table(self, headers: list, rows: list, title: str = ""):
        """テーブル表示（フォールバック）"""
        print(f"\n{title if title else 'テーブル'}")
        print("-" * 50)
        for header in headers:
            print(f"{header:15}", end="")
        print()
        print("-" * 50)
        for row in rows:
            for cell in row:
                print(f"{str(cell):15}", end="")
            print()
        print("-" * 50)
    
    def echo(self, message: str, clear_previous: bool = True):
        """AI応答を表示（重複防止・区切り表示付き）
        
        Args:
            message: 表示するメッセージ
            clear_previous: 前の応答をクリアするかどうか
        """
        # 前の応答をクリア（オプション）
        if clear_previous:
            print()  # 空行で区切り
        
        # 応答の開始を示す区切り線
        print("-" * 60)
        
        # AI応答のヘッダー
        print("🤖 AIアシスタント:")
        
        # メッセージ内容を表示
        if len(message) > 2000:
            # 長いメッセージは要約版を表示
            summary = message[:2000] + "\n\n... (内容が長いため要約版を表示しています)"
            print(summary)
            
            # 詳細表示の提案
            print("\n💡 詳細が必要な場合は、適切なツールを使用してください。")
        else:
            # 通常のメッセージ表示
            print(message)
        
        # 応答の終了を示す区切り線
        print("-" * 60)
        print()  # 空行で区切り
    
    def get_user_input(self, prompt: str = "", default: str = "") -> str:
        """ユーザー入力取得（EnhancedDualLoopSystem用）"""
        if prompt:
            print(f"{prompt}", end="")
        if default:
            print(f" [{default}]: ", end="")
        else:
            print(": ", end="")
        user_input = input().strip()
        return user_input if user_input else default


class RichUI:
    """Richを使用した美しいターミナルUI"""
    
    def __init__(self):
        self.console = Console()
        self._setup_styles()
    
    def _setup_styles(self):
        """スタイルの設定"""
        self.styles = {
            'success': 'bold green',
            'error': 'bold red',
            'warning': 'bold yellow',
            'info': 'bold blue',
            'muted': 'dim',
            'highlight': 'bold cyan'
        }
    
    def print(self, *args, **kwargs):
        """基本的な出力"""
        self.console.print(*args, **kwargs)
    
    def print_success(self, message: str):
        """成功メッセージ"""
        self.console.print(f"✅ {message}", style=self.styles['success'])
    
    def print_error(self, message: str):
        """エラーメッセージ"""
        self.console.print(f"❌ {message}", style=self.styles['error'])
    
    def print_warning(self, message: str):
        """警告メッセージ"""
        self.console.print(f"⚠️ {message}", style=self.styles['warning'])
    
    def print_info(self, message: str):
        """情報メッセージ"""
        self.console.print(f"ℹ️ {message}", style=self.styles['info'])
    
    def print_message(self, message: str, style: str = "info"):
        """スタイル付きメッセージ"""
        if style in self.styles:
            self.console.print(message, style=self.styles[style])
        else:
            self.console.print(message)
    
    def print_conversation_message(self, message: str, speaker: str = "user", style: str = "info"):
        """会話メッセージ表示"""
        if speaker == "user":
            prefix = "👤 ユーザー"
            speaker_style = "bold cyan"
        elif speaker == "assistant":
            prefix = "🤖 アシスタント"
            speaker_style = "bold green"
        elif speaker == "system":
            prefix = "⚙️ システム"
            speaker_style = "bold yellow"
        else:
            prefix = f"💬 {speaker}"
            speaker_style = "bold blue"
        
        # スピーカー名とメッセージを表示
        self.console.print(f"{prefix}:", style=speaker_style)
        if style in self.styles:
            self.console.print(f"  {message}", style=self.styles[style])
        else:
            self.console.print(f"  {message}")
    
    def print_panel(self, content: str, title: str = "", style: str = "blue"):
        """パネル表示"""
        panel = Panel(content, title=title, border_style=style)
        self.console.print(panel)
    
    def print_separator(self):
        """区切り線"""
        self.console.print("─" * 50, style="dim")
    
    def print_table(self, headers: list, rows: list, title: str = ""):
        """テーブル表示"""
        table = Table(title=title, show_header=True, header_style="bold magenta")
        for header in headers:
            table.add_column(header)
        for row in rows:
            table.add_row(*[str(cell) for cell in row])
        self.console.print(table)
    
    def print_code(self, code: str, language: str = "python"):
        """コード表示"""
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        self.console.print(syntax)
    
    def print_markdown(self, markdown_text: str):
        """Markdown表示"""
        md = Markdown(markdown_text)
        self.console.print(md)
    
    def echo(self, message: str, clear_previous: bool = True):
        """AI応答を表示（重複防止・区切り表示付き）
        
        Args:
            message: 表示するメッセージ
            clear_previous: 前の応答をクリアするかどうか
        """
        # 前の応答をクリア（オプション）
        if clear_previous:
            self.console.print()  # 空行で区切り
        
        # 応答の開始を示す区切り線
        self.console.print("─" * 60, style="dim")
        
        # AI応答のヘッダー
        self.console.print("🤖 AIアシスタント:", style="bold green")
        
        # メッセージ内容を表示
        if len(message) > 2000:
            # 長いメッセージは要約版を表示
            summary = message[:2000] + "\n\n... (内容が長いため要約版を表示しています)"
            self.console.print(summary, style="white")
            
            # 詳細表示の提案
            self.console.print("\n💡 詳細が必要な場合は、適切なツールを使用してください。", style="dim")
        else:
            # 通常のメッセージ表示
            self.console.print(message, style="white")
        
        # 応答の終了を示す区切り線
        self.console.print("─" * 60, style="dim")
        self.console.print()  # 空行で区切り
    
    def input(self, prompt: str = "") -> str:
        """ユーザー入力"""
        return Prompt.ask(prompt)
    
    def confirm(self, message: str, default: bool = True) -> bool:
        """確認入力"""
        return Confirm.ask(message, default=default)
    
    def get_user_input(self, prompt: str = "", default: str = "") -> str:
        """ユーザー入力取得（EnhancedDualLoopSystem用）"""
        return Prompt.ask(prompt, default=default)
    
    def progress(self, description: str = "処理中..."):
        """プログレスバー"""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        )

# グローバルUIインスタンス
try:
    rich_ui = RichUI()
except Exception:
    rich_ui = SimpleUI()

# 便利関数
def print_success(message: str):
    """成功メッセージ表示"""
    rich_ui.print_success(message)

def print_error(message: str):
    """エラーメッセージ表示"""
    rich_ui.print_error(message)

def print_warning(message: str):
    """警告メッセージ表示"""
    rich_ui.print_warning(message)

def print_info(message: str):
    """情報メッセージ表示"""
    rich_ui.print_info(message)

def print_message(message: str, style: str = "info"):
    """スタイル付きメッセージ表示"""
    rich_ui.print_message(message, style)

def print_panel(content: str, title: str = "", style: str = "blue"):
    """パネル表示"""
    rich_ui.print_panel(content, title, style)

def print_separator():
    """区切り線表示"""
    rich_ui.print_separator()

def print_table(headers: list, rows: list, title: str = ""):
    """テーブル表示"""
    rich_ui.print_table(headers, rows, title)

def print_code(code: str, language: str = "python"):
    """コード表示"""
    rich_ui.print_code(code, language)

def print_markdown(markdown_text: str):
    """Markdown表示"""
    rich_ui.print_markdown(markdown_text)

def input_text(prompt: str = "") -> str:
    """ユーザー入力"""
    return rich_ui.input(prompt)

def confirm_action(message: str, default: bool = True) -> bool:
    """確認入力"""
    return rich_ui.confirm(message, default)

def get_user_input(prompt: str = "", default: str = "") -> str:
    """ユーザー入力取得"""
    return rich_ui.get_user_input(prompt, default)


def print_conversation_message(message: str, speaker: str = "user", style: str = "info"):
    """会話メッセージ表示"""
    rich_ui.print_conversation_message(message, speaker, style)

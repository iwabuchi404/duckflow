"""
Rich UIモジュール - ステップ1で使用するシンプルなUI
"""
from typing import Any, Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markup import escape

from ..base.config import config_manager


class RichUI:
    """Richを使用したターミナルUI"""
    
    def __init__(self):
        """初期化"""
        self.config = config_manager.load_config()
        self.ui_config = self.config.ui.rich
        
        # コンソールの初期化
        self.console = Console(
            highlight=self.ui_config.get('highlight', True),
        )
        
        # カラー設定
        self.colors = {
            'primary': 'cyan',
            'success': 'green',
            'warning': 'yellow',
            'error': 'red',
            'info': 'blue',
            'muted': 'dim',
        }
    
    def print_header(self, title: str, subtitle: Optional[str] = None) -> None:
        """ヘッダーを表示"""
        header_text = f"[bold {self.colors['primary']}]{title}[/]"
        if subtitle:
            header_text += f"\n[{self.colors['muted']}]{subtitle}[/]"
        
        panel = Panel(
            header_text,
            border_style=self.colors['primary'],
            padding=(1, 2)
        )
        self.console.print(panel)
        self.console.print()
    
    def show_duck_status(self, vitals_display: str) -> None:
        """Duck Pacemakerのステータスを特別な形式で表示"""
        try:
            panel = Panel(
                vitals_display,
                title="🦆 Duck Pacemaker Status",
                border_style="cyan",
                padding=(0, 1)
            )
            self.console.print(panel)
        except Exception as e:
            self.console.print(f"[red]Duck status表示エラー: {e}[/]")
    
    def print_message(self, message: str, style: str = "info") -> None:
        """メッセージを表示"""
        color = self.colors.get(style, self.colors['info'])
        self.console.print(f"[{color}]{escape(message)}[/]")
    
    def print_success(self, message: str) -> None:
        """成功メッセージを表示"""
        self.console.print(f"[{self.colors['success']}][OK] {escape(message)}[/]")
    
    def print_warning(self, message: str) -> None:
        """警告メッセージを表示"""
        self.console.print(f"[{self.colors['warning']}][WARN] {escape(message)}[/]")
    
    def print_error(self, message: str) -> None:
        """エラーメッセージを表示"""
        self.console.print(f"[{self.colors['error']}][ERROR] {escape(message)}[/]")
    
    def print_code(self, code: str, language: str = "python") -> None:
        """コードを構文ハイライト付きで表示"""
        syntax = Syntax(code, language, line_numbers=True)
        self.console.print(syntax)
    
    def print_file_content(self, file_path: str, content: str, language: str = "python") -> None:
        """ファイル内容を表示"""
        panel = Panel(
            Syntax(content, language, line_numbers=True),
            title=f"[{self.colors['primary']}]{file_path}[/]",
            border_style=self.colors['primary']
        )
        self.console.print(panel)
    
    def print_file_list(self, files: List[Dict[str, Any]], title: str = "Files") -> None:
        """ファイル一覧をテーブル形式で表示"""
        if not files:
            self.print_message("ファイルが見つかりませんでした。", "muted")
            return
        
        table = Table(title=title, border_style=self.colors['primary'])
        table.add_column("Name", style=self.colors['primary'])
        table.add_column("Size", justify="right")
        table.add_column("Modified", style=self.colors['muted'])
        
        for file_info in files:
            size_str = self._format_file_size(file_info.get('size', 0))
            modified_str = file_info.get('modified', '')[:16]  # 日時のみ表示
            
            table.add_row(
                file_info['name'],
                size_str,
                modified_str
            )
        
        self.console.print(table)
    
    def print_task_steps(self, steps: List[Dict[str, Any]], title: str = "Task Steps") -> None:
        """タスクステップを表示"""
        if not steps:
            self.print_message("タスクステップがありません。", "muted")
            return
        
        table = Table(title=title, border_style=self.colors['primary'])
        table.add_column("Step", style=self.colors['primary'])
        table.add_column("Status", justify="center")
        table.add_column("Description")
        
        for i, step in enumerate(steps, 1):
            status = step.get('status', 'pending')
            description = step.get('description', '')
            
            # ステータスに応じたアイコンと色
            status_icons = {
                'pending': ('○', self.colors['muted']),
                'in_progress': ('●', self.colors['warning']),
                'completed': ('✓', self.colors['success']),
                'failed': ('✗', self.colors['error']),
            }
            
            icon, color = status_icons.get(status, ('?', self.colors['muted']))
            status_text = f"[{color}]{icon} {status}[/]"
            
            table.add_row(
                str(i),
                status_text,
                description
            )
        
        self.console.print(table)
    
    def get_user_input(self, prompt: str, default: Optional[str] = None) -> str:
        """ユーザー入力を取得"""
        try:
            return Prompt.ask(
                f"[{self.colors['primary']}]{prompt}[/]",
                default=default
            )
        except EOFError:
            # EOF（Ctrl+D、パイプ終了等）の場合は終了を示す特殊値を返す
            return "quit"
        except KeyboardInterrupt:
            # Ctrl+Cの場合は中断を示す
            raise
    
    def get_confirmation(self, message: str, default: bool = False) -> bool:
        """確認の入力を取得 (y/n)。RichのConfirmが使えない場合は標準入力へフォールバック"""
        label = "Y/n" if default else "y/N"
        prompt_text = f"[{self.colors['warning']}]{escape(message)}[/] [{label}]"
        try:
            return Confirm.ask(prompt_text, default=default)
        except Exception:
            # フォールバック: 標準入力
            try:
                resp = input(f"{message} [{label}]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return default
            if not resp:
                return default
            return resp in ("y", "yes", "1", "true")
    
    def show_progress(self, description: str) -> Progress:
        """プログレス表示を開始"""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        )
        progress.start()
        task_id = progress.add_task(description, total=None)
        return progress
    
    def print_separator(self, char: str = "-", length: int = 80) -> None:
        """セパレーターを表示"""
        self.console.print(f"[{self.colors['muted']}]{char * length}[/]")
    
    def print_panel(self, content: str, title: str, style: str = "info") -> None:
        """パネル形式でコンテンツを表示"""
        color = self.colors.get(style, self.colors['info'])
        panel = Panel(
            content,
            title=f"[{color}]{title}[/]",
            border_style=color,
            padding=(1, 2)
        )
        self.console.print(panel)
    
    def clear_screen(self) -> None:
        """画面をクリア"""
        self.console.clear()
    
    def _format_file_size(self, size_bytes: int) -> str:
        """ファイルサイズを人間が読みやすい形式でフォーマット"""
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"
    
    def print_conversation_message(self, role: str, content: str, timestamp: Optional[str] = None) -> None:
        """対話メッセージを表示"""
        role_colors = {
            'user': self.colors['primary'],
            'assistant': self.colors['success'],
            'system': self.colors['muted'],
        }
        
        role_icons = {
            'user': '👤',
            'assistant': '🤖',
            'system': '⚙️',
        }
        
        color = role_colors.get(role, self.colors['info'])
        icon = role_icons.get(role, '•')
        
        header = f"[{color}]{icon} {role.title()}[/]"
        if timestamp:
            header += f" [{self.colors['muted']}]({timestamp})[/]"
        
        panel = Panel(
            content,
            title=header,
            border_style=color,
            padding=(0, 1)
        )
        self.console.print(panel)
    
    def print_step(self, step: str, description: str = "") -> None:
        """ステップ表示（4ノードオーケストレーター用）"""
        if description:
            message = f"{step}: {description}"
        else:
            message = step
        self.print_message(message, "info")


# グローバルなUIインスタンス
rich_ui = RichUI()
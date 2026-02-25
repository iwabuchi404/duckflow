from typing import Any, Dict, Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.theme import Theme
from rich.spinner import Spinner
from rich.live import Live
from rich.text import Text
from rich.table import Table
import time

# Custom theme for Duckflow
duck_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "duck": "bold yellow",
    "user": "bold blue",
    "thought": "italic grey70",
    "action": "bold magenta",
    "tool": "cyan",
    "path": "underline blue"
})

class DuckUI:
    """
    Rich Text User Interface for Duckflow.
    Handles all console output with style.
    """
    def __init__(self):
        self.console = Console(theme=duck_theme)
        self.live_spinner = None

    def print_welcome(self):
        """Print the welcome banner."""
        title = r"""
    ____             __   ______            
   / __ \__  _______/ /__/ __/ /___ _      __
  / / / / / / / ___/ //_/ /_/ / __ \ | /| / /
 / /_/ / /_/ / /__/ ,< / __/ / /_/ / |/ |/ / 
/_____/\__,_/\___/_/|_/_/ /_/\____/|__/|__/  
                                             v4.0
        """
        self.console.print(Panel(
            Text(title, style="duck", justify="center"),
            title="[bold]Duckflow Agent[/bold]",
            subtitle="Your AI Coding Companion",
            border_style="duck",
            expand=False
        ))

    def print_system(self, message: str):
        """Print a system message."""
        self.console.print(f"[info]ℹ️ {message}[/info]")

    def print_user(self, message: str):
        """Print user input."""
        self.console.print(Panel(
            Markdown(message),
            title="[user]👤 You[/user]",
            border_style="user",
            expand=False
        ))

    def print_conversation_message(self, message: str, speaker: str = "user", style: str = "info"):
        """Print a message from a conversation history turn."""
        if speaker == "user":
            prefix = "👤 User"
            speaker_style = "user"
        elif speaker == "assistant":
            prefix = "🤖 Assistant"
            speaker_style = "success"
        else:
            prefix = f"💬 {speaker}"
            speaker_style = "info"
        
        self.console.print(f"[{speaker_style}]{prefix}:[/{speaker_style}]")
        self.console.print(f"{message}\n", markup=False)

    def print_separator(self):
        """Print a separator line."""
        self.console.print("─" * 50, style="dim")

    def print_thinking(self, thought: str):
        """Print the agent's thought process."""
        self.console.print(f"\n[duck]🦆 Thinking...[/duck]")
        self.console.print(f"[thought]{thought}[/thought]\n")

    def print_action(self, action_name: str, params: Dict[str, Any], thought: str):
        """Print an action being executed."""
        param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
        if len(param_str) > 100:
            param_str = param_str[:97] + "..."
            
        self.console.print(f"[action]⚡ Action:[/action] [tool]{action_name}[/tool] ({param_str})")
        self.console.print(f"   [thought]Reason: {thought}[/thought]")

    def print_result(self, result: str, is_error: bool = False):
        """Print the result of an action."""
        from rich.markup import escape  # 安全のためにここでインポート
        
        style = "error" if is_error else "success"
        icon = "❌" if is_error else "✅"
        
        # 外部からのテキストの [] を無害化する
        safe_result = escape(str(result))
        
        # If result is long or contains newlines, use a panel
        if "\n" in safe_result or len(safe_result) > 100:
            self.console.print(Panel(
                safe_result,  # エスケープ済みの変数を渡す
                title=f"{icon} Result",
                border_style=style,
                expand=False
            ))
        else:
            self.console.print(f"   [{style}]{icon} Result: {safe_result}[/{style}]")

    def print_error(self, message: str):
        """Print a general error message."""
        from rich.markup import escape  
        
        # エラーメッセージ内の [] も無害化する
        safe_message = escape(str(message))
        self.console.print(f"[error]❌ Error: {safe_message}[/error]")

    def print_info(self, message: str):
        """Print an info message."""
        self.console.print(f"[info]ℹ️ {message}[/info]")

    def print_success(self, message: str):
        """Print a success message."""
        self.console.print(f"[success]✅ {message}[/success]")

    def print_warning(self, message: str):
        """Print a warning message."""
        self.console.print(f"[warning]⚠️  {message}[/warning]")

    def print_code(self, code: str, language: str = "python"):
        """Print syntax highlighted code."""
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        self.console.print(syntax)

    def print_markdown(self, markdown_text: str):
        """Print rendered markdown."""
        md = Markdown(markdown_text)
        self.console.print(md)

    def print_token_usage(self, stats: Dict[str, Any]):
        """Print token usage statistics."""
        total = stats.get("total_tokens", 0)
        input_tok = stats.get("input_tokens", 0)
        output_tok = stats.get("output_tokens", 0)
        
        self.console.print(
            f"[thought]📊 Tokens: {total:,} (In: {input_tok:,}, Out: {output_tok:,})[/thought]",
            justify="right"
        )

    def print_plan(self, plan_data: Any):
        """Print the current plan status."""
        # This would be implemented to nicely display the plan table
        pass

    def print_vitals(self, vitals: Any, loop_count: int, max_loops: int):
        """Print current vitals and loop status. (Sym-Ops v3.1: c/s/m/f)"""
        conf_icon  = "💪" if vitals.confidence > 0.7 else "🤔" if vitals.confidence > 0.4 else "😰"
        safety_icon = "🛡️" if vitals.safety > 0.7 else "⚠️" if vitals.safety > 0.4 else "🚨"
        memory_icon = "🧠" if vitals.memory > 0.7 else "📦" if vitals.memory > 0.4 else "💾"
        focus_icon  = "🎯" if vitals.focus > 0.7 else "🔍" if vitals.focus > 0.4 else "😵"

        status = (
            f"{conf_icon} Confidence: {vitals.confidence:.2f}  "
            f"{safety_icon} Safety: {vitals.safety:.2f}  "
            f"{memory_icon} Memory: {vitals.memory:.2f}  "
            f"{focus_icon} Focus: {vitals.focus:.2f}  "
            f"🔄 Loop: {loop_count}/{max_loops}"
        )

        self.console.print(Panel(
            status,
            title="[duck]Agent Vitals[/duck]",
            border_style="duck",
            expand=False
        ))

    def print_safety_warning(self, safety_score: float):
        """Safety Score Interceptor 用の警告パネルを表示する。

        Args:
            safety_score: LLMが報告したSafetyスコア (0.0-1.0)
        """
        self.console.print(Panel(
            f"[bold red]Safety Score が低い値です: s={safety_score:.2f}[/bold red]\n\n"
            "このスコアはLLMが危険または破壊的な操作だと判断していることを示します。\n"
            "操作の内容を確認してから続行してください。",
            title="[bold red]🚨 Safety Score Interceptor[/bold red]",
            border_style="red",
            expand=False
        ))

    def create_spinner(self, text: str):
        """Return a status spinner context manager."""
        return self.console.status(f"[duck]{text}[/duck]", spinner="dots")

    def request_confirmation(self, message: str) -> bool:
        """Request yes/no confirmation from the user."""
        from rich.prompt import Prompt
        
        while True:
            try:
                # Allow full-width characters
                response = Prompt.ask(
                    f"[warning]⚠️  {message} [y/n][/warning]", 
                    console=self.console
                )
                
                # Normalize input
                if not response:
                    return False # Default to No if empty? Or loop? Prompt.ask handles default if provided.
                
                normalized = response.lower().strip().replace("ｙ", "y").replace("ｎ", "n")
                
                if normalized in ["y", "yes"]:
                    return True
                elif normalized in ["n", "no"]:
                    return False
                # If invalid, Prompt.ask loop logic isn't used here, so we loop manually
                self.console.print("[red]Please enter y or n[/red]")
                
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[error]Input interrupted. Defaulting to No.[/error]")
                return False

    def confirm_action(self, message: str, default: bool = True) -> bool:
        """Alias for request_confirmation to match module level API."""
        return self.request_confirmation(message)
    
    def select_from_list(self, title: str, options: List[tuple], description: str = "") -> Optional[int]:
        """
        Display a numbered list and let the user select an option.
        
        Args:
            title: Title for the selection prompt
            options: List of tuples (display_text, value)
            description: Optional description text
            
        Returns:
            Index of selected option, or None if cancelled
        """
        from rich.prompt import Prompt
        
        # Display the options
        if description:
            self.console.print(f"\n[info]{description}[/info]")
        
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("#", style="cyan", width=4)
        table.add_column(title, style="white")
        
        for idx, (display_text, _) in enumerate(options, 1):
            table.add_row(str(idx), display_text)
        
        self.console.print(Panel(
            table,
            title=f"[bold]{title}[/bold]",
            border_style="cyan",
            expand=False
        ))
        
        # Get user selection
        while True:
            try:
                response = Prompt.ask(
                    f"[cyan]選択してください (1-{len(options)}, またはキャンセルするには 'c')[/cyan]",
                    console=self.console
                )
                
                if response.lower() in ['c', 'cancel', 'q', 'quit']:
                    return None
                
                try:
                    selection = int(response)
                    if 1 <= selection <= len(options):
                        return selection - 1  # Return 0-based index
                    else:
                        self.console.print(f"[red]1から{len(options)}の間の数字を入力してください[/red]")
                except ValueError:
                    self.console.print("[red]数字を入力してください[/red]")
                    
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[error]キャンセルされました[/error]")
                return None

    def print_debug_context(self, messages: List[Dict[str, str]], mode: str = "console"):
        """Print the full context messages for debugging."""
        from rich.rule import Rule
        from datetime import datetime
        
        if mode == "file":
            with open("debug_context.log", "a", encoding="utf-8") as f:
                f.write(f"\n--- Context at {datetime.now()} ---\n")
                for msg in messages:
                    f.write(f"[{msg.get('role', 'unknown')}]\n{msg.get('content', '')}\n\n")
            self.console.print("[dim]Context written to debug_context.log[/dim]")
            return

        # Console mode
        self.console.print(Rule("[bold yellow]DEBUG CONTEXT START[/bold yellow]"))
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            
            style = "white"
            title = role.upper()
            
            if role == "system":
                style = "cyan"
            elif role == "user":
                style = "green"
            elif role == "assistant":
                style = "blue"
            elif role == "tool":
                style = "magenta"
                
            self.console.print(Panel(content, title=f"[{style}]{title}[/{style}]", border_style=style))
            
        self.console.print(Rule("[bold yellow]DEBUG CONTEXT END[/bold yellow]"))


    async def select_model_interactive(self, models: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Display an interactive model selector using prompt_toolkit with arrow keys.
        Returns the selected model dict or None if cancelled.
        """
        from companion.ui.model_selector import select_model_interactive as _select_model

        if not models:
            self.print_warning("利用可能なモデルがありません")
            return None

        try:
            selected = await _select_model(models, title="モデルを選択")
            return selected
        except Exception as e:
            self.print_error(f"モデル選択UIの起動に失敗しました: {e}")
            return None

    async def get_user_input(self, prompt: str = "You: ") -> str:
        """Get input from user with prompt_toolkit for history and completion."""
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import NestedCompleter
        from prompt_toolkit.styles import Style

        # Define completer
        completer = NestedCompleter.from_nested_dict({
            '/config': {'show': None, 'set': None, 'reload': None},
            '/status': None,
            '/help': None,
            '/exit': None,
            '/clear': None,
            '/model': {'list': None, 'current': None},
        })
        
        style = Style.from_dict({
            'prompt': 'bold blue',
        })

        session = PromptSession(completer=completer, style=style)
        
        try:
            self.console.print() # Newline before prompt
            return await session.prompt_async(prompt)
        except (EOFError, KeyboardInterrupt):
            return "/exit"

# Global instance
ui = DuckUI()

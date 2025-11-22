from typing import Any, Dict, Optional
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
        style = "error" if is_error else "success"
        icon = "❌" if is_error else "✅"
        
        # If result is long or contains newlines, use a panel
        if "\n" in result or len(result) > 100:
            self.console.print(Panel(
                result,
                title=f"{icon} Result",
                border_style=style,
                expand=False
            ))
        else:
            self.console.print(f"   [{style}]{icon} Result: {result}[/{style}]")

    def print_error(self, message: str):
        """Print a general error message."""
        self.console.print(f"[error]❌ Error: {message}[/error]")

    def print_warning(self, message: str):
        """Print a warning message."""
        self.console.print(f"[warning]⚠️  {message}[/warning]")

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

    def create_spinner(self, text: str):
        """Return a status spinner context manager."""
        return self.console.status(f"[duck]{text}[/duck]", spinner="dots")

    def request_confirmation(self, message: str) -> bool:
        """Request yes/no confirmation from the user."""
        from rich.prompt import Confirm
        return Confirm.ask(f"[warning]⚠️  {message}[/warning]", console=self.console)

# Global instance
ui = DuckUI()

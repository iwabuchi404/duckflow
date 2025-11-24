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

    def print_vitals(self, vitals: Any, loop_count: int, max_loops: int):
        """Print current vitals and loop status."""
        mood_icon = "😊" if vitals.mood > 0.7 else "😐" if vitals.mood > 0.4 else "😞"
        focus_icon = "🧠" if vitals.focus > 0.7 else "🤔" if vitals.focus > 0.4 else "😵"
        stamina_icon = "⚡" if vitals.stamina > 0.7 else "🔋" if vitals.stamina > 0.4 else "🪫"
        
        status = (
            f"{mood_icon} Mood: {vitals.mood:.2f}  "
            f"{focus_icon} Focus: {vitals.focus:.2f}  "
            f"{stamina_icon} Stamina: {vitals.stamina:.2f}  "
            f"🔄 Loop: {loop_count}/{max_loops}"
        )
        
        self.console.print(Panel(
            status,
            title="[duck]Agent Vitals[/duck]",
            border_style="duck",
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

# Global instance
ui = DuckUI()

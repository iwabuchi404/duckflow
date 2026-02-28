from typing import Any, Dict, Optional, List, Union
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.theme import Theme
from rich.live import Live
from rich.text import Text
from rich.rule import Rule
import time
import sys

# Custom theme for Duckflow
duck_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "duck": "bold orange1",
    "user": "bold blue",
    "thought": "italic grey70",
    "action": "bold magenta",
    "tool": "cyan",
    "path": "underline blue",
    "log": "grey50"
})

class DuckUI:
    """
    Modular Rich Text User Interface for Duckflow.
    Focuses on a stable, scroll-based output with a fixed status bar.
    Supports real-time verbosity toggling via keys.
    """
    def __init__(self):
        self.console = Console(theme=duck_theme)
        self.live = None
        self.vitals_data = None
        self.loop_info = (0, 0)
        self.status_text = ""
        
        # Verbosity settings
        self.show_full_logs = False # Toggle with 'v' key during execution

    def _make_status_line(self) -> Text:
        """Create a single line status bar."""
        if not self.vitals_data:
            mode_tag = " [V]" if self.show_full_logs else ""
            return Text(f" 🦆 Duckflow{mode_tag} | {self.status_text}", style="dim")
            
        v = self.vitals_data
        l_curr, l_max = self.loop_info
        
        conf_icon  = "💪" if v.confidence > 0.7 else "🤔" if v.confidence > 0.4 else "😰"
        safety_icon = "🛡️" if v.safety > 0.7 else "⚠️" if v.safety > 0.4 else "🚨"
        
        mode_str = " [FULL LOGS]" if self.show_full_logs else ""
        
        return Text.assemble(
            (" 🦆 ", "duck"),
            (f"{conf_icon} Conf: {v.confidence:.2f} ", "info"),
            ("| ", "dim"),
            (f"{safety_icon} Safe: {v.safety:.2f} ", "warning" if v.safety < 0.5 else "info"),
            ("| ", "dim"),
            (f"🧠 Mem: {v.memory:.2f} ", "info"),
            ("| ", "dim"),
            (f"🎯 Foc: {v.focus:.2f} ", "info"),
            ("| ", "dim"),
            (f"🔄 Loop: {l_curr}/{l_max} ", "duck"),
            (f"{mode_str} ", "bold yellow" if self.show_full_logs else "dim"),
            (f"| {self.status_text}", "thought")
        )

    def _check_keys(self):
        """Non-blocking key check to toggle modes (OS-specific but encapsulated)."""
        try:
            if sys.platform == 'win32':
                import msvcrt
                if msvcrt.kbhit():
                    ch = msvcrt.getch().lower()
                    if ch == b'v':
                        self.show_full_logs = not self.show_full_logs
                        self.update_status(f"Verbosity toggled: {'ON' if self.show_full_logs else 'OFF'}")
            else:
                import select
                if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                    ch = sys.stdin.read(1).lower()
                    if ch == 'v':
                        self.show_full_logs = not self.show_full_logs
                        self.update_status(f"Verbosity toggled: {'ON' if self.show_full_logs else 'OFF'}")
        except Exception:
            pass

    def start_live(self):
        """Start the live status bar at the bottom."""
        if not self.live:
            self.live = Live(
                self._make_status_line(), 
                console=self.console, 
                refresh_per_second=4, 
                auto_refresh=True,
                transient=True
            )
            self.live.start()

    def stop_live(self):
        """Stop the live status bar."""
        if self.live:
            self.live.stop()
            self.live = None

    def update_status(self, text: str):
        """Update the message in the status bar."""
        self.status_text = text
        if self.live:
            self._check_keys()
            self.live.update(self._make_status_line())

    def add_log(self, message: str):
        """Add system log. In full mode, print them directly."""
        if self.show_full_logs:
            self.console.print(f"  [log]LOG: {message}[/log]")
        # Even if not shown, we could buffer it for later or just ignore

    def print_welcome(self):
        title = r"""
    ____             __   ______            
   / __ \__  _______/ /__/ __/ /___ _      __
  / / / / / / / ___/ //_/ /_/ / __ \ | /| / /
 / /_/ / /_/ / /__/ ,< / __/ / /_/ / |/ |/ / 
/_____/\__,_/\___/_/|_/_/ /_/\____/|__/|__/  
        """
        self.console.print(Text(title, style="duck", justify="center"))
        self.console.print(Rule(style="duck"))

    def print_system(self, message: str):
        self.console.print(f"ℹ️ [info]{message}[/info]")

    def print_user(self, message: str):
        self.console.print(f"\n[user]👤 You:[/user] {message}")

    def print_thinking(self, thought: str):
        self.console.print(f"\n[duck]🦆 Thinking...[/duck]")
        if thought:
            self.console.print(f"  [thought]{thought}[/thought]")

    def print_action(self, action_name: str, params: Dict[str, Any], thought: str):
        param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
        # If not in full mode, truncate long params
        if not self.show_full_logs and len(param_str) > 100:
            param_str = param_str[:97] + "..."
            
        self.console.print(f"\n[action]⚡ Action:[/action] [tool]{action_name}[/tool] [dim]({param_str})[/dim]")
        if thought:
            self.console.print(f"   [thought]Reason: {thought}[/thought]")

    def print_result(self, result: str, is_error: bool = False):
        style = "error" if is_error else "success"
        icon = "❌" if is_error else "✅"
        content = str(result)
        
        self.console.print(f"   {icon} [bold]{style.upper()}[/bold]: ", end="")
        lines = content.splitlines()
        
        if self.show_full_logs:
            # Show everything
            self.console.print()
            for line in lines:
                self.console.print(f"     [dim]{line}[/dim]")
        else:
            # Abbreviated mode
            if len(lines) > 1 or len(content) > 80:
                self.console.print()
                for line in lines[:10]:
                    self.console.print(f"     [dim]{line}[/dim]")
                if len(lines) > 10:
                    self.console.print(f"     [dim]... ({len(lines)-10} more lines. Press 'v' to see all next time)[/dim]")
            else:
                self.console.print(f"[dim]{content}[/dim]")

    def print_vitals(self, vitals: Any, loop_count: int, max_loops: int):
        self.vitals_data = vitals
        self.loop_info = (loop_count, max_loops)
        if self.live:
            self._check_keys()
            self.live.update(self._make_status_line())

    def print_error(self, message: str):
        self.console.print(f"[error]❌ Error: {message}[/error]")

    def print_info(self, message: str):
        self.console.print(f"[info]ℹ️ {message}[/info]")

    def print_warning(self, message: str):
        self.console.print(f"[warning]⚠️  {message}[/warning]")

    def print_success(self, message: str):
        self.console.print(f"[success]✅ {message}[/success]")

    def print_token_usage(self, stats: Dict[str, Any]):
        total = stats.get("total_tokens", 0)
        self.console.print(f"[thought]📊 Tokens: {total:,}[/thought]", justify="right")

    def create_spinner(self, text: str):
        self.update_status(text)
        return self.console.status(f"[duck]{text}[/duck]", spinner="dots")

    def request_confirmation(self, message: str) -> bool:
        was_live = self.live is not None
        if was_live: self.stop_live()
        from rich.prompt import Prompt
        res = Prompt.ask(f"[warning]⚠️  {message} [y/n][/warning]", console=self.console)
        if was_live: self.start_live()
        return res.lower().strip() in ["y", "yes"]

    async def get_user_input(self, prompt: str = "You: ") -> str:
        if self.live: self.stop_live()
        from prompt_toolkit import PromptSession
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.completion import NestedCompleter
        
        # Define completer for slash commands
        completer = NestedCompleter.from_nested_dict({
            '/config': {'show': None, 'set': None, 'setup': None},
            '/log': None,
            '/scan': None,
            '/help': None,
            '/exit': None,
            '/status': None,
            '/model': {'list': None, 'current': None},
        })

        kb = KeyBindings()

        @kb.add('escape', 'v') # Alt+V
        def _(event):
            self.show_full_logs = not self.show_full_logs
            # We can't use live.update here as it's stopped, so use console.print
            status = "ON" if self.show_full_logs else "OFF"
            self.console.print(f"[thought] (Verbosity toggled: {status})[/thought]")

        session = PromptSession(completer=completer, key_bindings=kb)
        try:
            return await session.prompt_async(prompt)
        except (EOFError, KeyboardInterrupt):
            return "/exit"

    def print_conversation_message(self, message: str, speaker: str = "user"):
        if speaker == "user":
            self.console.print(f"\n[user]👤 User:[/user] {message}")
        else:
            self.console.print(f"\n[success]🦆 Assistant:[/success]\n{message}")

    def print_separator(self):
        self.console.print(Rule(style="dim"))

    def confirm_action(self, message: str, default: bool = True) -> bool:
        return self.request_confirmation(message)

    def print_markdown(self, markdown_text: str):
        self.console.print(Markdown(markdown_text))

    def print_code(self, code: str, language: str = "python"):
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        self.console.print(syntax)

    def print_safety_warning(self, safety_score: float):
        self.console.print(Rule(title="🚨 Safety Warning", style="error"))
        self.console.print(f"[error]Safety Score が低いです: {safety_score:.2f}[/error]")

    async def select_from_list(self, title: str, options: List[tuple], description: str = "") -> Optional[int]:
        """Display a selection dialog with orange theme and return the chosen index."""
        if self.live: self.stop_live()
        from prompt_toolkit.shortcuts import radiolist_dialog
        from prompt_toolkit.styles import Style
        
        # Custom orange-themed style
        custom_style = Style.from_dict({
            'dialog': 'bg:#222222',
            'dialog frame.label': 'fg:#ff8700 bold',  # Orange title
            'dialog.body': 'fg:#cccccc',
            'radiolist.current': 'fg:#ff8700',        # Orange cursor
            'radiolist.selected': 'fg:#ff8700 bold',  # Orange selection
            'button': 'fg:#ffffff bg:#444444',
            'button.focused': 'fg:#ffffff bg:#ff8700', # Orange focused button
        })
        
        result = await radiolist_dialog(
            title=title,
            text=description or "矢印キーで選択し、Enterで決定してください:",
            values=[(i, opt[0]) for i, opt in enumerate(options)],
            style=custom_style
        ).run_async()
        
        return result

    async def select_model_interactive(self, models: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Interactive model selector using the restored selection logic."""
        if not models: return None
        
        options = [(f"{m.get('id')} ({m.get('context_length', 0)//1024}k)", m) for m in models]
        idx = await self.select_from_list("モデルの選択", options, description="使用するモデルを選択してください:")
        
        if idx is not None:
            return models[idx]
        return None

# Global instance
ui = DuckUI()

import importlib
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, cast

from companion.ui.console import ui


class _Config(Protocol):
    """設定ハンドラーが必要とする設定の最小インターフェース。"""

    _config: dict[str, Any] | None

    def _load_config(self) -> None:
        """設定ファイルを再読み込みする。"""


_config_module = importlib.import_module("companion.config.config_loader")
config = cast(_Config, _config_module.config)
Command = Callable[[list[str]], Awaitable[None]]


class CommandHandler:
    """
    Handles internal slash commands.
    """

    def __init__(self, agent: Any) -> None:
        """コマンドハンドラーを初期化する。

        Args:
            agent: コマンドが操作するエージェント。
        """
        self.agent = agent
        self.commands: dict[str, Command] = {
            "/config": self.handle_config,
            "/status": self.handle_status,
            "/help": self.handle_help,
            "/exit": self.handle_exit,
            "/clear": self.handle_clear,
        }

    def is_command(self, input_text: str) -> bool:
        return input_text.startswith("/")

    async def execute(self, input_text: str) -> bool:
        """
        Execute command. Returns True if execution was successful and loop should continue (skip LLM).
        Returns False if it wasn't a command or execution failed (though we catch errors).
        """
        if not self.is_command(input_text):
            return False

        parts = input_text.split()
        cmd = parts[0]
        args = parts[1:]

        if cmd in self.commands:
            try:
                await self.commands[cmd](args)
            except Exception as e:
                ui.print_error(f"Command execution failed: {e}")
            return True
        else:
            ui.print_error(f"Unknown command: {cmd}. Type /help for list.")
            return True

    async def handle_config(self, args: list[str]) -> None:
        """設定表示・更新・リロードを処理する。

        Args:
            args: サブコマンドと引数のリスト。
        """
        import json

        from rich.panel import Panel
        from rich.syntax import Syntax
        from rich.table import Table

        if not args:
            # Help display
            table = Table(show_header=True, header_style="bold magenta", box=None)
            table.add_column("Command", style="cyan")
            table.add_column("Description", style="white")

            table.add_row("/config show", "Show current configuration")
            table.add_row("/config set <key> <value>", "Set config value (temporary)")
            table.add_row("/config reload", "Reload config from file")

            ui.console.print(
                Panel(
                    table,
                    title="[bold]Config Commands[/bold]",
                    border_style="blue",
                    expand=False,
                )
            )
            return

        subcmd = args[0]

        if subcmd == "show":
            # Show current config
            json_str = json.dumps(config._config, indent=2, ensure_ascii=False)
            ui.console.print(
                Panel(
                    Syntax(json_str, "json", theme="monokai", line_numbers=False),
                    title="[bold]Current Configuration[/bold]",
                    border_style="green",
                    expand=False,
                )
            )

        elif subcmd == "set":
            if len(args) < 3:
                ui.print_error("Usage: /config set <key> <value>")
                return
            key = args[1]
            value: Any = args[2]

            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            elif value.isdigit():
                value = int(value)
            elif value.replace(".", "", 1).isdigit():
                value = float(value)

            # Update config in memory
            self._set_config_value(key, value)
            ui.print_success(f"Config updated: {key} = {value}")

            # If max_loops changed, update pacemaker
            if key == "agent.max_loops" and self.agent.pacemaker:
                self.agent.pacemaker.max_loops = int(value)

        elif subcmd == "reload":
            config._load_config()
            ui.print_success("Config reloaded from file.")

        else:
            ui.print_error(f"Unknown config subcommand: {subcmd}")

    async def handle_status(self, args: list[str]) -> None:
        """エージェントの状態とPacemaker進捗を表示する。

        Args:
            args: 使用しない引数。
        """
        if self.agent.pacemaker:
            vitals = self.agent.state.vitals
            ui.print_vitals(
                vitals, self.agent.pacemaker.loop_count, self.agent.pacemaker.max_loops
            )
        else:
            ui.print_info("Pacemaker not initialized.")

    async def handle_help(self, args: list[str]) -> None:
        """利用可能なコマンドを一覧表示する。

        Args:
            args: 使用しない引数。
        """
        help_text = """
        [bold]Available Commands:[/bold]
        [cyan]/config show[/cyan]        - Show current configuration
        [cyan]/config set <k> <v>[/cyan] - Set config value (temporary)
        [cyan]/config reload[/cyan]      - Reload config from file
        [cyan]/status[/cyan]             - Show agent vitals and loop status
        [cyan]/clear[/cyan]              - Clear conversation history
        [cyan]/exit[/cyan]               - Exit the agent
        [cyan]/help[/cyan]               - Show this help
        """
        ui.console.print(help_text)

    async def handle_exit(self, args: list[str]) -> None:
        """エージェントを終了状態にする。

        Args:
            args: 使用しない引数。
        """
        ui.print_info("Exiting agent...")
        self.agent.running = False

    async def handle_clear(self, args: list[str]) -> None:
        """会話履歴をクリアする。

        Args:
            args: 使用しない引数。
        """
        self.agent.state.conversation_history = []
        ui.print_success("Conversation history cleared.")

    def _set_config_value(self, key_path: str, value: Any) -> None:
        """ドット区切りの設定キーを更新する。

        Args:
            key_path: 更新する設定のキー。
            value: 設定に格納する値。
        """
        keys = key_path.split(".")
        current = config._config
        if current is None:
            current = {}
            config._config = current
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            child = current[key]
            if not isinstance(child, dict):
                raise ValueError(f"設定パス {key_path} にオブジェクトがありません")
            current = child
        current[keys[-1]] = value

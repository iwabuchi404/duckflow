from typing import List, Dict, Any, Optional
import yaml
import json
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from companion.config.config_loader import config
from companion.ui import ui
from companion.modules.model_manager import model_manager
from companion.tools import get_project_tree

class CommandHandler:
    """
    Handles internal slash commands.
    """
    def __init__(self, agent):
        self.agent = agent
        self.commands = {
            "/config": self.handle_config,
            "/status": self.handle_status,
            "/help": self.handle_help,
            "/exit": self.handle_exit,
            "/clear": self.handle_clear,
            "/model": self.handle_model,
            "/scan": self.handle_scan,
            "/log": self.handle_log,
            "/config": self.handle_config,
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

    async def handle_config(self, args: List[str]):
        if not args:
            # Help display
            table = Table(show_header=True, header_style="bold magenta", box=None)
            table.add_column("Command", style="cyan")
            table.add_column("Description", style="white")
            
            table.add_row("/config show", "Show current configuration")
            table.add_row("/config set <key> <value>", "Set config value (temporary)")
            table.add_row("/config reload", "Reload config from file")
            
            # Using ui.print_panel equivalent or direct console access if necessary
            # Since new ui.py uses RichUI, we can use print_panel or access console directly?
            # Let's try to use ui methods where possible
            if hasattr(ui, 'console'):
                ui.console.print(Panel(table, title="[bold]Config Commands[/bold]", border_style="blue", expand=False))
            else:
                 # Fallback for SimpleUI
                 pass 
            return

        subcmd = args[0]
        
        if subcmd == "show":
            # Show current config
            json_str = json.dumps(config._config, indent=2, ensure_ascii=False)
            if hasattr(ui, 'console'):
                ui.console.print(Panel(
                    Syntax(json_str, "json", theme="monokai", line_numbers=False),
                    title="[bold]Current Configuration[/bold]",
                    border_style="green",
                    expand=False
                ))
            else:
                print(json_str)
        
        elif subcmd == "set":
            if len(args) < 3:
                ui.print_error("Usage: /config set <key> <value>")
                return
            key = args[1]
            value = args[2]
            
            # Try to convert value to appropriate type
            if value.lower() == "true": value = True
            elif value.lower() == "false": value = False
            elif value.isdigit(): value = int(value)
            elif value.replace(".", "", 1).isdigit(): value = float(value)
            
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

    async def handle_log(self, args: List[str]):
        """Toggle full log verbosity."""
        ui.show_full_logs = not ui.show_full_logs
        status = "ON (Full Logs)" if ui.show_full_logs else "OFF (Abbreviated)"
        ui.print_success(f"Log verbosity toggled: {status}")

    async def handle_config(self, args: List[str]):
        """Handle configuration commands: /config show | set <key> <value> | setup."""
        if not args:
            ui.print_info("Usage: /config [show | set <key> <value> | setup]")
            return

        subcommand = args[0].lower()
        
        if subcommand == "show":
            # Display current config in a table
            table = Table(title="Current Configuration", show_header=True, header_style="bold cyan")
            table.add_column("Key", style="dim")
            table.add_column("Value", style="yellow")
            
            def flatten_dict(d, prefix=""):
                for k, v in d.items():
                    key = f"{prefix}{k}"
                    if isinstance(v, dict):
                        flatten_dict(v, f"{key}.")
                    else:
                        table.add_row(key, str(v))
            
            flatten_dict(config._config)
            ui.console.print(table)

        elif subcommand == "set":
            if len(args) < 3:
                ui.print_error("Usage: /config set <key_path> <value>")
                ui.print_info("Example: /config set language en")
                return
            
            key_path = args[1]
            value = args[2]
            
            # Update in-memory config and persist to YAML
            from companion.config.config_writer import ConfigWriter
            writer = ConfigWriter()
            
            # Simple conversion for bool/int
            if value.lower() == "true": value = True
            elif value.lower() == "false": value = False
            elif value.isdigit(): value = int(value)
            
            # Update YAML via nested dictionary structure
            keys = key_path.split('.')
            update_dict = {}
            curr = update_dict
            for k in keys[:-1]:
                curr[k] = {}
                curr = curr[k]
            curr[keys[-1]] = value
            
            writer.write_yaml(update_dict)
            config.reload()
            ui.print_success(f"Config updated and saved: {key_path} = {value}")

        elif subcommand == "setup":
            from companion.ui.setup_wizard import SetupWizard
            wizard = SetupWizard()
            await wizard.run()
            config.reload()
            ui.print_success("Setup wizard completed. Config reloaded.")

    async def handle_status(self, args: List[str]):
        if self.agent.pacemaker:
            vitals = self.agent.state.vitals
            ui.print_vitals(vitals, self.agent.pacemaker.loop_count, self.agent.pacemaker.max_loops)
            ui.print_info(f"Model: {self.agent.llm.model}")
            ui.print_info(f"turn_count: {self.agent.state.turn_count}")
            ui.print_info(f"current_mode: {self.agent.state.current_mode}")
        else:
            ui.print_info("Pacemaker not initialized.")

    async def handle_help(self, args: List[str]):
        help_text = """
        [bold]Available Commands:[/bold]
        [cyan]/config show[/cyan]        - Show current configuration
        [cyan]/config set <k> <v>[/cyan] - Set config value (temporary)
        [cyan]/config reload[/cyan]      - Reload config from file
        [cyan]/status[/cyan]             - Show agent vitals and loop status
        [cyan]/model[/cyan]              - Interactive model selection
        [cyan]/model list[/cyan]         - List available models (config + dynamic)
        [cyan]/model refresh[/cyan]      - Refresh OpenRouter model list
        [cyan]/model current[/cyan]      - Show current model
        [cyan]/model <provider>/<model>[/cyan] - Switch to a specific model
        [cyan]/clear[/cyan]              - Clear conversation history
        [cyan]/exit[/cyan]               - Exit the agent
        [cyan]/scan <depth>[/cyan]     - Show project tree (default depth: 3)
        [cyan]/log[/cyan]              - Toggle full log verbosity (Alt+V also works)
        [cyan]/config[/cyan]           - Show/set configuration or run setup wizard
        [cyan]/help[/cyan]               - Show this help
        """
        if hasattr(ui, 'console'):
            ui.console.print(help_text)
        else:
            print(help_text)

    async def handle_exit(self, args: List[str]):
        ui.print_info("Exiting agent...")
        self.agent.running = False

    async def handle_clear(self, args: List[str]):
        self.agent.state.conversation_history = []
        ui.print_success("Conversation history cleared.")
    
    async def handle_scan(self, args: List[str]):
        """Handle /scan command to show project tree."""
        depth = 3
        if args:
            try:
                depth = int(args[0])
            except ValueError:
                ui.print_error(f"Invalid depth: {args[0]}. Using default (3).")
        
        ui.print_info(f"🔍 Scanning project tree (depth={depth})...")
        tree = await get_project_tree(depth=depth)
        
        if hasattr(ui, 'console'):
            ui.console.print(Panel(
                tree,
                title=f"[bold]Project Tree (depth={depth})[/bold]",
                border_style="cyan",
                expand=False
            ))
        else:
            print(tree)
    
    async def handle_model(self, args: List[str]):
        """Handle /model command for switching LLM models."""
        if not args:
            # No arguments - show interactive selection
            await self._interactive_model_selection()
            return
        
        subcmd = args[0]
        
        if subcmd == "refresh":
            ui.print_info("🔄 Refreshing OpenRouter model list...")
            models = await model_manager.fetch_openrouter_models(force=True)
            if models:
                ui.print_success(f"✅ Refreshed {len(models)} models from OpenRouter.")
            else:
                ui.print_error("❌ Failed to refresh models.")
            return

        if subcmd == "list":
            # Show available models from config
            models_config = config.get("llm.available_models", [])
            
            if models_config:
                # New format with detailed model list
                table = Table(show_header=True, header_style="bold magenta", box=None)
                table.add_column("Name", style="cyan", no_wrap=False)
                table.add_column("Provider", style="yellow")
                table.add_column("Model ID", style="white")
                table.add_column("Status", style="green")
                
                current_provider = config.get("llm.provider", "unknown")
                current_model = self.agent.llm.model
                
                for model_info in models_config:
                    name = model_info.get("name", "Unknown")
                    provider = model_info.get("provider", "N/A")
                    model = model_info.get("model", "N/A")
                    description = model_info.get("description", "")
                    
                    # Add description to name if available
                    display_name = name
                    if description:
                        display_name += f"\n[dim]{description}[/dim]"
                    
                    status = "✓ Active" if provider == current_provider and model == current_model else ""
                    table.add_row(display_name, provider, model, status)
                
                if hasattr(ui, 'console'):
                    ui.console.print(Panel(table, title="[bold]Available Models (Config)[/bold]", border_style="green", expand=False))
                else:
                    print("Available models (Config):")
                    for model_info in models_config:
                        print(f"  {model_info.get('name')}: {model_info.get('provider')}/{model_info.get('model')}")
                
                # Also list top 10 from OpenRouter if available
                dynamic_models = model_manager.models
                if dynamic_models:
                    table_dyn = Table(show_header=True, header_style="bold magenta", box=None)
                    table_dyn.add_column("Name", style="cyan")
                    table_dyn.add_column("Model ID", style="white")
                    table_dyn.add_column("Context", style="yellow")
                    
                    for dm in dynamic_models[:10]: # Limit to top 10 for list command to avoid flood
                        table_dyn.add_row(dm["name"], dm["id"], f"{dm['context_length']//1024}k")
                    
                    if hasattr(ui, 'console'):
                        ui.console.print(Panel(table_dyn, title="[bold]Available Models (OpenRouter - Top 10)[/bold]", subtitle="Use /model refresh to update, or /model for full list", border_style="blue", expand=False))
            else:
                # Fallback to old format
                table = Table(show_header=True, header_style="bold magenta", box=None)
                table.add_column("Provider", style="cyan")
                table.add_column("Model", style="white")
                table.add_column("Status", style="green")
                
                current_provider = config.get("llm.provider", "unknown")
                current_model = self.agent.llm.model
                
                # List models from config
                providers = ["openai", "anthropic", "groq", "openrouter", "google"]
                for provider in providers:
                    model = config.get(f"llm.{provider}.model", "N/A")
                    if model != "N/A":
                        status = "✓ Active" if provider == current_provider and model == current_model else ""
                        table.add_row(provider, model, status)
                
                if hasattr(ui, 'console'):
                    ui.console.print(Panel(table, title="[bold]Available Models[/bold]", border_style="green", expand=False))
                else:
                    print("Available models:")
                    for provider in providers:
                        model = config.get(f"llm.{provider}.model", "N/A")
                        if model != "N/A":
                            print(f"  {provider}: {model}")
        
        elif subcmd == "current":
            # Show current model
            current_provider = config.get("llm.provider", "unknown")
            current_model = self.agent.llm.model
            
            info_text = f"""
            [bold]Current Model Configuration:[/bold]
            Provider: [cyan]{current_provider}[/cyan]
            Model: [cyan]{current_model}[/cyan]
            Base URL: [cyan]{self.agent.llm.base_url or 'default'}[/cyan]
            """
            
            if hasattr(ui, 'console'):
                ui.console.print(Panel(info_text, title="[bold]Current Model[/bold]", border_style="blue", expand=False))
            else:
                print(f"Current provider: {current_provider}")
                print(f"Current model: {current_model}")
        
        else:
            # Assume it's a provider/model specification
            if "/" not in subcmd:
                ui.print_error("Invalid format. Use: /model <provider>/<model> (e.g., /model openai/gpt-4o)")
                return
            
            try:
                provider, model = subcmd.split("/", 1)
                provider = provider.strip()
                model = model.strip()
                
                if not provider or not model:
                    ui.print_error("Provider and model cannot be empty")
                    return
                
                # Call agent's switch_model method
                ui.print_info(f"🔄 Switching to {provider}/{model}...")
                success = await self.agent.switch_model(provider, model)
                
                if success:
                    ui.print_success(f"✅ Successfully switched to {provider}/{model}")
                else:
                    ui.print_error(f"❌ Failed to switch model. Check logs for details.")
                    
            except ValueError:
                ui.print_error("Invalid format. Use: /model <provider>/<model>")
            except Exception as e:
                ui.print_error(f"Error switching model: {e}")
    
    async def _interactive_model_selection(self):
        """Interactive model selection using number input (compatible with all environments)."""
        # Get available models from config
        models_config = config.get("llm.available_models", [])

        if not models_config:
            # Fallback to old method if no model list defined
            ui.print_warning("設定ファイルに llm.available_models が見つかりません。")
            # models_config remains empty, we will try to get dynamic ones below

        # Get dynamic models from OpenRouter (use cached if available)
        ui.print_info("🔍 Getting latest models...")
        dynamic_models = await model_manager.fetch_openrouter_models()

        current_provider = config.get("llm.provider", "unknown")
        current_model = self.agent.llm.model

        # Prepare models in the format expected by select_model_interactive
        # Required fields: id, name, context_length, prompt_price, completion_price, description
        seen_models = set()
        models_for_ui = []

        # Add static models from config
        for model_info in models_config:
            provider = model_info.get("provider")
            model = model_info.get("model")
            name = model_info.get("name", f"{provider}/{model}")

            if not provider or not model:
                continue

            # Skip duplicates
            if (provider, model) in seen_models:
                continue
            seen_models.add((provider, model))

            models_for_ui.append({
                "id": model,
                "model_id": model,
                "name": name,
                "provider": provider,
                "context_length": 0,  # Config models don't have context length
                "prompt_price": "0",
                "completion_price": "0",
                "description": model_info.get("description", ""),
            })

        # Add dynamic models from OpenRouter (avoid duplicates)
        for dm in dynamic_models:
            provider = dm["provider"]
            model = dm["id"]

            if (provider, model) in seen_models:
                continue

            seen_models.add((provider, model))

            models_for_ui.append({
                "id": model,
                "model_id": model,
                "name": dm["name"],
                "provider": provider,
                "context_length": dm.get("context_length", 0),
                "prompt_price": dm.get("prompt_price", "0"),
                "completion_price": dm.get("completion_price", "0"),
                "description": dm.get("description", ""),
            })

        if not models_for_ui:
            ui.print_error("利用可能なモデルが見つかりません")
            return

        # Show TUI selection (number input - compatible with all environments)
        selection = await ui.select_from_list(
            "利用可能なモデル",
            [(m.get("name", m.get("id", "Unknown")), (m.get("provider"), m.get("id"), m.get("name")))
            for m in models_for_ui
        ],
            "モデルを選択してください："
        )

        if selection is None:
            ui.print_info("キャンセルされました")
            return

        # Get selected provider and model
        _, (provider, model, name) = [(m.get("name", m.get("id", "Unknown")), (m.get("provider"), m.get("id"), m.get("name")))
            for m in models_for_ui
        ][selection]

        # Check if already using this model
        if provider == current_provider and model == current_model:
            ui.print_info(f"既に {name} を使用しています")
            return

        # Switch to selected model
        ui.print_info(f"🔄 {name} に切り替えています...")
        success = await self.agent.switch_model(provider, model)

        if success:
            ui.print_success(f"✅ {name} に切り替えました")
        else:
            ui.print_error(f"❌ モデルの切り替えに失敗しました。ログを確認してください。")
    
    async def _interactive_model_selection_legacy(self):
        """Legacy interactive model selection (fallback)."""
        # Collect available models from config (old method)
        providers = ["openai", "anthropic", "groq", "openrouter", "google"]
        available_models = []
        
        current_provider = config.get("llm.provider", "unknown")
        current_model = self.agent.llm.model
        
        for provider in providers:
            model = config.get(f"llm.{provider}.model")
            if model:
                # Check if this is the current model
                is_current = (provider == current_provider and model == current_model)
                display_text = f"{provider}/{model}"
                if is_current:
                    display_text += " [green]✓ 現在使用中[/green]"
                
                available_models.append((display_text, (provider, model)))
        
        if not available_models:
            ui.print_error("設定ファイルにモデルが見つかりません")
            return
        
        # Show selection menu
        selection = ui.select_from_list(
            "利用可能なモデル",
            available_models,
            "モデルを選択してください："
        )
        
        if selection is None:
            ui.print_info("キャンセルされました")
            return
        
        # Get selected provider and model
        _, (provider, model) = available_models[selection]
        
        # Check if already using this model
        if provider == current_provider and model == current_model:
            ui.print_info(f"既に {provider}/{model} を使用しています")
            return
        
        # Switch to selected model
        ui.print_info(f"🔄 {provider}/{model} に切り替えています...")
        success = await self.agent.switch_model(provider, model)
        
        if success:
            ui.print_success(f"✅ {provider}/{model} に切り替えました")
        else:
            ui.print_error(f"❌ モデルの切り替えに失敗しました。ログを確認してください。")

    def _set_config_value(self, key_path: str, value: Any):
        # Helper to set nested dict value
        keys = key_path.split('.')
        current = config._config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

import asyncio
import importlib
import os
import sys
from typing import Any, Protocol, cast

from prompt_toolkit.shortcuts import input_dialog, radiolist_dialog
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme


class _ConfigWriter(Protocol):
    """セットアップウィザードが必要とする設定書き込みインターフェース。"""

    def write_env(self, key: str, value: str) -> None:
        """環境変数を書き込む。"""

    def ensure_gitignore(self) -> None:
        """.envをgitignoreへ登録する。"""

    def write_yaml(self, updates: dict[str, Any]) -> None:
        """YAML設定を書き込む。"""


# Duckflow Theme
setup_theme = Theme(
    {
        "duck": "bold orange1",
        "step": "bold cyan",
        "info": "grey70",
        "success": "bold green",
    }
)


class SetupWizard:
    """
    Interactive setup wizard using arrow-key navigation (prompt_toolkit).
    """

    def __init__(self) -> None:
        """セットアップウィザードを初期化する。"""
        self.console = Console(theme=setup_theme)
        config_writer_module = importlib.import_module("companion.config.config_writer")
        self.writer = cast(_ConfigWriter, config_writer_module.ConfigWriter())
        self.data: dict[str, str] = {
            "provider": "openrouter",
            "api_key": "",
            "model": "",
            "language": "ja",
            "safety": "strict",
            "stack": "Python",
        }

    def should_run(self) -> bool:
        if "--setup" in sys.argv:
            return True
        providers = ["openrouter", "anthropic", "openai", "groq", "google"]
        for provider in providers:
            if os.getenv(f"{provider.upper()}_API_KEY"):
                return False
        return not os.path.exists("duckflow.yaml")

    async def run(self) -> None:
        """初期設定の各ステップを順番に実行する。"""
        self.console.clear()
        self.console.print(
            Panel(
                Text(
                    "\n🦆 DUCKFLOW AGENT v4.0\nInitial Setup Wizard",
                    style="duck",
                    justify="center",
                ),
                border_style="duck",
            )
        )

        # 1. Provider Selection (Arrow Keys)
        await self._step_provider()
        # 2. API Key & Model (Input)
        await self._step_auth()
        # 3. Preferences (Arrow Keys)
        await self._step_prefs()
        # 4. Finalize
        await self._step_finish()

    async def _step_provider(self) -> None:
        """LLMプロバイダーを選択する。"""
        result = radiolist_dialog(
            title="Step 1: LLM Provider",
            text="矢印キーで選択し、Enterで決定してください:",
            values=[
                ("openrouter", "OpenRouter (Recommended - DeepSeek/Claude/Llama)"),
                ("anthropic", "Anthropic (Claude 3.5 Sonnet)"),
                ("openai", "OpenAI (GPT-4o)"),
                ("groq", "Groq (High Speed Llama 3)"),
            ],
            default="openrouter",
        ).run()

        if result is None:
            sys.exit(0)
        self.data["provider"] = result

    async def _step_auth(self) -> None:
        """APIキーとモデルIDを入力する。"""
        provider_name = self.data["provider"].upper()
        env_var = f"{provider_name}_API_KEY"

        # API Key Input
        key = input_dialog(
            title=f"Step 2: {provider_name} Authentication",
            text=f"{env_var} を入力してください:",
            password=True,
        ).run()
        if key is None:
            sys.exit(0)
        self.data["api_key"] = key

        # Model Input
        defaults = {
            "openrouter": "deepseek/deepseek-r1",
            "anthropic": "claude-3-5-sonnet-20241022",
            "openai": "gpt-4o",
            "groq": "llama-3.3-70b-versatile",
        }
        model = input_dialog(
            title="Step 2: Model Selection",
            text="使用するモデルIDを入力してください:",
            default=defaults.get(self.data["provider"], ""),
        ).run()
        if model is None:
            sys.exit(0)
        self.data["model"] = model

    async def _step_prefs(self) -> None:
        """言語・安全レベル・技術スタックを設定する。"""
        # Language
        lang = radiolist_dialog(
            title="Step 3: Language Preference",
            text="エージェントとの対話言語を選択してください:",
            values=[("ja", "日本語 (Japanese)"), ("en", "English")],
            default="ja",
        ).run()
        if lang is None:
            sys.exit(0)
        self.data["language"] = lang

        # Safety
        safety = radiolist_dialog(
            title="Step 3: Safety Level",
            text="安全承認レベルを選択してください:",
            values=[
                ("strict", "Strict (全てのファイル変更に確認が必要)"),
                ("normal", "Normal (新規作成や小規模修正は自動)"),
            ],
            default="strict",
        ).run()
        if safety is None:
            sys.exit(0)
        self.data["safety"] = safety

        # Tech Stack
        stack = input_dialog(
            title="Step 3: Tech Stack",
            text="主要な開発言語・フレームワークを入力してください:",
            default="Python, FastAPI",
        ).run()
        if stack is None:
            sys.exit(0)
        self.data["stack"] = stack

    async def _step_finish(self) -> None:
        """入力された初期設定をファイルへ保存する。"""
        self.console.print("\n[step]STEP 4:[/step] [bold]設定の保存中...[/bold]")

        # Write .env
        env_var = f"{self.data['provider'].upper()}_API_KEY"
        self.writer.write_env(env_var, self.data["api_key"])
        self.writer.ensure_gitignore()

        # Write duckflow.yaml
        updates = {
            "llm": {
                "provider": self.data["provider"],
                self.data["provider"]: {"model": self.data["model"]},
            },
            "language": self.data["language"],
            "safety_level": self.data["safety"],
            "tech_stack": self.data["stack"],
        }
        self.writer.write_yaml(updates)

        self.console.print(
            Panel(
                Text(
                    "\n✅ 初期設定が完了しました！\nDuckflow を起動します...",
                    style="success",
                    justify="center",
                ),
                border_style="success",
            )
        )
        await asyncio.sleep(1.5)

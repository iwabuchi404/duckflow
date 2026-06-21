#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from companion.core import DuckAgent
from companion.modules.session_manager import SessionManager

from logging.handlers import RotatingFileHandler
from rich.traceback import install

# Install rich traceback handler
install(show_locals=False)

from companion.ui import ui


class UILogHandler(logging.Handler):
    """Custom logging handler to send logs to the DuckUI sidebar."""

    def emit(self, record):
        try:
            msg = self.format(record)
            ui.add_log(msg)
        except Exception:
            self.handleError(record)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(
            "duckflow_v4.log",
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding="utf-8",
        ),
        UILogHandler(),  # Use UI sidebar instead of StreamHandler
    ],
)
# Set external libs to WARNING to reduce noise
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

import argparse
from companion.tools.file_ops import file_ops


def _prompt_session_resume(session_manager: SessionManager):
    """
    起動時に前回セッションの継続有無をユーザーに尋ねる。

    Args:
        session_manager: セッション一覧を取得するマネージャー

    Returns:
        復元された AgentState、または None（新規セッション）
    """
    latest_id = session_manager.get_latest_id()
    if not latest_id:
        return None  # 前回セッションなし

    sessions = session_manager.list_sessions()
    if not sessions:
        return None

    latest = sessions[0]  # list_sessions() は最新順

    # 日時をフォーマット
    try:
        from datetime import datetime

        last_active = datetime.fromisoformat(latest["last_active"])
        time_str = last_active.strftime("%Y-%m-%d %H:%M")
    except Exception:
        time_str = latest.get("last_active", "不明")

    turn_count = latest.get("turn_count", 0)

    print(f"\n🦆 前回のセッションが見つかりました")
    print(f"   日時: {time_str} | ターン数: {turn_count}")
    print(f"   Session ID: {latest_id}")

    while True:
        try:
            answer = input("前回のセッションを継続しますか？ [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"

        if answer in ("y", "yes"):
            state = session_manager.load_latest()
            if state:
                print(
                    f"✅ セッションを復元しました（{len(state.conversation_history)} 件の会話履歴）\n"
                )
                return state
            else:
                print(
                    "⚠️  セッションの読み込みに失敗しました。新規セッションで起動します。\n"
                )
                return None
        elif answer in ("n", "no", ""):
            return None
        else:
            print("⚠️  'y' または 'n' を入力してください。")


async def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Duckflow v4 Agent")
    parser.add_argument(
        "--dir", type=str, default=".", help="Working directory for the agent"
    )
    parser.add_argument(
        "--no-session",
        action="store_true",
        help="セッション保存・復元を無効化して新規起動する",
    )
    parser.add_argument("--setup", action="store_true", help="Run the setup wizard")
    args = parser.parse_args()

    # 1. Check if setup is needed
    from companion.ui.setup_wizard import SetupWizard

    wizard = SetupWizard()
    if args.setup or wizard.should_run():
        await wizard.run()
        # Reload environment and config after setup
        from dotenv import load_dotenv

        load_dotenv(override=True)
        from companion.config.config_loader import config

        config.reload()

    # Set workspace
    file_ops.set_workspace_root(args.dir)

    # セッション管理
    session_manager = None
    resume_state = None

    if not args.no_session:
        session_manager = SessionManager()
        resume_state = _prompt_session_resume(session_manager)

    agent = DuckAgent(
        session_manager=session_manager,
        resume_state=resume_state,
    )
    await agent.run()


def cli() -> None:
    """Run the Duckflow command line entrypoint."""
    asyncio.run(main())


if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        pass

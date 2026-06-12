"""
プロンプトデバッグツール。

各モードで LLM に実際に送られるプロンプトを結合して出力する。
今回のようなツール説明の漏れ・マッピングミスを素早くキャッチするために使う。

使用方法:
    uv run python -X utf8 dump_prompt.py [mode] [--output <file>] [--raw]

引数:
    mode        : planning / investigation / task / all (デフォルト: all)
    --output    : 出力先ファイルパス（省略時は標準出力）
    --raw       : JSON 形式でメッセージリストをそのまま出力

例:
    uv run python -X utf8 dump_prompt.py task
    uv run python -X utf8 dump_prompt.py all --output prompt_dump.txt
    uv run python -X utf8 dump_prompt.py task --raw
"""

import sys
import json
import argparse
from pathlib import Path

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent))

from companion.core import DuckAgent
from companion.state.agent_state import AgentState, AgentMode
from companion.prompts.builder import PromptBuilder


MODES = ["planning", "investigation", "task"]

SEPARATOR = "=" * 80


def build_prompt_for_mode(agent: DuckAgent, mode: str) -> list[dict]:
    """指定モードのプロンプトメッセージリストを構築して返す。"""
    # モードを設定した状態を作る
    state = AgentState()
    state.current_mode = AgentMode(mode)

    tool_descriptions = agent.get_tool_descriptions(mode)
    builder = PromptBuilder(state)
    return builder.build_messages(tool_descriptions)


def format_messages(mode: str, messages: list[dict]) -> str:
    """メッセージリストを人間が読みやすい形式に整形する。"""
    lines = []
    lines.append(SEPARATOR)
    lines.append(f"MODE: {mode.upper()}")
    lines.append(f"Messages: {len(messages)} blocks")
    lines.append(SEPARATOR)

    for i, msg in enumerate(messages, 1):
        role = msg.get("role", "?").upper()
        content = msg.get("content", "")
        cache = " [CACHED]" if "cache_control" in msg else ""
        lines.append(f"\n[{i}] {role}{cache}  ({len(content)} chars)")
        lines.append("-" * 40)
        lines.append(content)

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="LLM に送られる実際のプロンプトを出力するデバッグツール"
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="all",
        choices=MODES + ["all"],
        help="出力するモード (デフォルト: all)",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="出力先ファイルパス（省略時は標準出力）",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="JSON 形式でメッセージリストをそのまま出力",
    )
    args = parser.parse_args()

    target_modes = MODES if args.mode == "all" else [args.mode]

    # DuckAgent を起動せずにインスタンス化（ツール登録だけ走る）
    agent = DuckAgent()

    output_parts = []
    output_parts.append(f"Duckflow Prompt Inspector")
    output_parts.append(f"Modes: {', '.join(target_modes)}")
    output_parts.append("")

    all_data = {}

    for mode in target_modes:
        messages = build_prompt_for_mode(agent, mode)
        all_data[mode] = messages

        if not args.raw:
            output_parts.append(format_messages(mode, messages))

    if args.raw:
        output_text = json.dumps(all_data, ensure_ascii=False, indent=2)
    else:
        output_text = "\n".join(output_parts)

    if args.output:
        Path(args.output).write_text(output_text, encoding="utf-8")
        print(f"出力完了: {args.output}")
    else:
        print(output_text)


if __name__ == "__main__":
    main()

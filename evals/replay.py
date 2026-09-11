"""Single-turn replay probe for model comparison.

Takes a recorded transcript, truncates the conversation history at a given
point, and asks a (possibly different) model what it would do next — without
executing anything. Used to compare decision-making on identical inputs
(GPT step 2: same input, different models).

Usage:
    uv run python -X utf8 evals/replay.py --transcript <path> --before N --model <id>
    --before N keeps history up to (excluding) the Nth assistant message
    (0-based), mimicking the exact context the original model saw.
    --turns K runs K autonomous think-decide steps (default 1), still
    without executing tools or asking the user.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()


def truncate_history(
    history: list[dict[str, Any]], before_assistant: int
) -> list[dict[str, Any]]:
    """Cut history before the Nth assistant message.

    Args:
        history: Full conversation_history.
        before_assistant: Keep messages before the Nth (0-based) assistant
            message. Negative values count from the end (-1 = drop last
            assistant message and everything after it).

    Returns:
        Truncated history ending at a user message when possible.
    """
    indices = [i for i, m in enumerate(history) if m.get("role") == "assistant"]
    if not indices:
        return list(history)
    if before_assistant < 0:
        before_assistant = len(indices) + before_assistant
    cut = indices[max(0, min(before_assistant, len(indices) - 1))]
    prefix = history[:cut]
    while prefix and prefix[-1].get("role") != "user":
        prefix.pop()
    return prefix


async def probe(
    transcript_path: Path,
    before: int,
    provider: str,
    model: str,
    mode: str,
    llm_call: int | None = None,
) -> dict[str, Any]:
    """Run one think-decide step on truncated history.

    Args:
        transcript_path: Source transcript.json.
        before: Truncation point (see truncate_history). Ignored when
            llm_call is given.
        provider: LLM provider.
        model: Model identifier.
        mode: Agent mode for tool descriptions.
        llm_call: When given, resend the exact saved messages of the Nth
            recorded LLM call verbatim (no prompt rebuilding). Old
            transcripts without llm_calls fall back to rebuilt prompts.

    Returns:
        Dict with proposed reasoning, actions and vitals.
    """
    from companion.base.llm_client import LLMClient
    from companion.core import DuckAgent
    from companion.prompts.builder import PromptBuilder
    from companion.state.agent_state import ActionList, AgentMode

    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))

    llm = LLMClient(provider=provider, model=model)
    if llm_call is not None:
        calls = transcript.get("llm_calls") or []
        if llm_call < 0:
            llm_call = len(calls) + llm_call
        if not (0 <= llm_call < len(calls)):
            raise SystemExit(
                f"llm_call {llm_call} out of range (have {len(calls)} calls)"
            )
        saved = calls[llm_call]
        settings = saved.get("settings", {}) or {}
        action_list: ActionList = await llm.chat(
            saved["messages"],
            response_model=ActionList,
            temperature=settings.get("temperature"),
            max_tokens=settings.get("max_tokens"),
        )
        return {
            "model": model,
            "verbatim": True,
            "input_sha": saved.get("input_sha"),
            "reasoning": action_list.reasoning,
            "actions": [
                {"name": a.name, "parameters": a.parameters}
                for a in action_list.actions
            ],
            "vitals": action_list.vitals,
            "parse_error": action_list.parse_error_type,
        }

    history = transcript.get("conversation_history", [])
    prefix = truncate_history(history, before)

    agent = DuckAgent(llm_client=llm, session_manager=None)
    agent.state.conversation_history = prefix
    try:
        agent.state.current_mode = AgentMode(mode)
    except ValueError:
        agent.state.current_mode = AgentMode.TASK

    builder = PromptBuilder(agent.state, llm.tier_profile)
    messages = builder.build_messages(
        agent.get_tool_descriptions(agent.state.current_mode.value)
    )
    messages = messages + prefix

    action_list: ActionList = await llm.chat(messages, response_model=ActionList)
    return {
        "model": model,
        "kept_messages": len(prefix),
        "reasoning": action_list.reasoning,
        "actions": [
            {"name": a.name, "parameters": a.parameters} for a in action_list.actions
        ],
        "vitals": action_list.vitals,
        "parse_error": action_list.parse_error_type,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Replay a transcript prefix")
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--before", type=int, default=-1)
    parser.add_argument("--llm-call", type=int, default=None,
                        help="Resend the Nth recorded LLM call verbatim")
    parser.add_argument("--provider", default="openrouter")
    parser.add_argument("--model", required=True)
    parser.add_argument("--mode", default="task")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    result = asyncio.run(
        probe(
            Path(args.transcript),
            args.before,
            args.provider,
            args.model,
            args.mode,
            args.llm_call,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

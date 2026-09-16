"""Native tool-calling round-trip probe (docs/research §4 steps 2-3).

Sends a side-effect-free test tool to a model via the chat API, records
the received tool_calls (names, arguments, IDs), returns tool results
with tool_call_ids, and records the follow-up normal response.

No Duckflow main-loop changes: this verifies provider/model capability
before any native implementation is considered.

Usage:
    uv run python -X utf8 evals/tool_probe/probe.py
    uv run python -X utf8 evals/tool_probe/probe.py --model deepseek/deepseek-v4.1-flash
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

PROBE_TOOL = {
    "type": "function",
    "function": {
        "name": "probe_echo",
        "description": (
            "Test tool with no side effects. Call it with the exact message "
            "given by the user so the harness can verify tool-call delivery."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Message to echo back verbatim",
                }
            },
            "required": ["message"],
        },
    },
}

PROBE_USER_MESSAGE = "Call probe_echo with message 'duckflow-probe-123'."


def extract_tool_calls(response: Any) -> list[dict[str, Any]]:
    """Extract tool-call records from a chat completion response.

    Handles content=null tool_calls, multiple calls, and plain-text
    responses without tool calls (recorded as an empty list, not an
    error — refusal/avoidance is a finding, not a crash).

    Args:
        response: Chat completion response object.

    Returns:
        List of {id, name, arguments} dicts (arguments parsed when
        possible, kept raw otherwise).
    """
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError):
        return []
    calls = getattr(message, "tool_calls", None) or []
    records = []
    for call in calls:
        fn = getattr(call, "function", None)
        raw_args = getattr(fn, "arguments", "") if fn else ""
        try:
            args = json.loads(raw_args) if raw_args else {}
        except (json.JSONDecodeError, TypeError):
            args = {"_raw": raw_args}
        records.append(
            {
                "id": getattr(call, "id", None),
                "name": getattr(fn, "name", None) if fn else None,
                "arguments": args,
            }
        )
    return records


def build_tool_result_messages(
    assistant_message: Any, calls: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Build the reply messages returning tool results.

    Args:
        assistant_message: The original assistant message object carrying
            tool_calls (re-sent verbatim to preserve IDs).
        calls: Extracted tool-call records from extract_tool_calls().

    Returns:
        Assistant message dict followed by one tool message per call.
    """
    messages: list[dict[str, Any]] = [
        {
            "role": "assistant",
            "content": getattr(assistant_message, "content", None),
            "tool_calls": [
                {
                    "id": c["id"],
                    "type": "function",
                    "function": {
                        "name": c["name"],
                        "arguments": json.dumps(c["arguments"], ensure_ascii=False),
                    },
                }
                for c in calls
                if c["id"]
            ],
        },
        *(
            {
                "role": "tool",
                "tool_call_id": c["id"],
                "content": json.dumps(
                    {"echo": (c["arguments"] or {}).get("message")},
                    ensure_ascii=False,
                ),
            }
            for c in calls
            if c["id"]
        ),
    ]
    return messages


def default_client_factory(provider: str) -> Any:
    """Create a chat-completions client for the provider.

    Args:
        provider: Provider name (currently only openrouter).

    Returns:
        AsyncOpenAI-compatible client.
    """
    import os

    from openai import AsyncOpenAI

    if provider != "openrouter":
        raise ValueError(f"probe supports openrouter only, got {provider!r}")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    return AsyncOpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL, timeout=120)


async def run_probe(
    model: str,
    provider: str = "openrouter",
    client_factory: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Run one tool-calling round trip against a model.

    Sends PROBE_TOOL with tool_choice auto, records received calls,
    returns results with tool_call_ids, and records the follow-up
    response text. A run with no tool calls is outcome "no_call"
    (capability finding), API/transport failures are outcome "error"
    (never classified as model non-support).

    Args:
        model: Provider-specific model ID.
        provider: Provider name.
        client_factory: Optional client constructor for tests.

    Returns:
        Result dict with outcome, calls, result messages, and
        follow-up text.
    """
    client = (client_factory or default_client_factory)(provider)
    outcome: dict[str, Any] = {
        "model": model,
        "provider": provider,
        "probed_at_utc": datetime.now(timezone.utc).isoformat(),
        "outcome": "unknown",
        "calls": [],
        "follow_up": None,
        "error": None,
    }
    try:
        first = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": PROBE_USER_MESSAGE}],
            tools=[PROBE_TOOL],
            tool_choice="auto",
        )
    except Exception as e:
        outcome["outcome"] = "error"
        outcome["error"] = f"{type(e).__name__}: {e}"
        return outcome

    calls = extract_tool_calls(first)
    outcome["calls"] = calls
    if not calls or not any(c["id"] for c in calls):
        outcome["outcome"] = "no_call"
        try:
            outcome["follow_up"] = first.choices[0].message.content
        except (AttributeError, IndexError):
            outcome["follow_up"] = None
        return outcome

    assistant_message = first.choices[0].message
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": PROBE_USER_MESSAGE},
        *build_tool_result_messages(assistant_message, calls),
    ]
    try:
        second = await client.chat.completions.create(model=model, messages=messages)
    except Exception as e:
        outcome["outcome"] = "error"
        outcome["error"] = f"round-trip failed after tool results: {type(e).__name__}: {e}"
        return outcome

    try:
        outcome["follow_up"] = second.choices[0].message.content
    except (AttributeError, IndexError):
        outcome["follow_up"] = None
    outcome["outcome"] = "round_trip_ok"
    return outcome


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Native tool-call probe")
    parser.add_argument("--model", default="minimax/minimax-m2.1")
    parser.add_argument("--provider", default="openrouter")
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parent / "results"),
        help="Result JSON output directory",
    )
    args = parser.parse_args()

    result = asyncio.run(run_probe(args.model, args.provider))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_model = args.model.replace("/", "_")
    path = out_dir / f"{safe_model}-{stamp}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nsaved: {path}")


if __name__ == "__main__":
    main()

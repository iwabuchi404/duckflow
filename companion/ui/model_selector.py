"""
Interactive model selector using simple input.
Allows users to select models using arrow keys (on Windows) or number input.
"""
from typing import List, Dict, Any, Optional


async def select_model_interactive(models: List[Dict[str, Any]], title: str = "モデルを選択") -> Optional[Dict[str, Any]]:
    """
    Launch an interactive model selector.

    Args:
        models: List of model dictionaries from ModelManager
        title: Title to display in the selector

    Returns:
        Selected model dict or None if cancelled
    """
    if not models:
        return None

    # Prepare display strings for each model
    choices = []

    for m in models:
        model_id = m.get("id", m.get("model_id", ""))
        name = m.get("name", m.get("id", "Unknown"))
        context_len = m.get("context_length", 0)
        prompt_price = m.get("prompt_price", "0")

        # Format context length
        if context_len >= 1_000_000:
            ctx_str = f"{context_len // 1000}K"
        elif context_len >= 1000:
            ctx_str = f"{context_len // 1000}K"
        else:
            ctx_str = str(context_len)

        # Format price
        try:
            price = float(prompt_price) * 1000
            if price < 0.01:
                price_str = f"${price:.4f}/1K"
            else:
                price_str = f"${price:.2f}/1K"
        except (ValueError, TypeError):
            price_str = "N/A"

        display_text = f"{name} ({ctx_str}, {price_str})"
        choices.append((display_text, m))

    # Use Rich's prompt with choices (number input, but better UX)
    from rich.prompt import Prompt

    # Print header
    print(f"\n{title}")
    print("─" * 60)

    for i, (display_text, _) in enumerate(choices, 1):
        print(f"  {i}. {display_text}")

    print(f"\n矢印キー（↑↓）または番号で選択 | Enter で決定 | Esc/q でキャンセル")

    # Try arrow key input on Windows
    try:
        import msvcrt
        import sys

        state = {"selected": 0}
        num_choices = len(choices)

        # Arrow key handling on Windows
        while True:
            if msvcrt.kbhit():
                ch = msvcrt.getch()

                if ch == b'\x00' or ch == b'\xe0':
                    # Function key prefix
                    ch2 = msvcrt.getch()
                    if ch2 == b'H':  # Up arrow
                        state["selected"] = max(0, state["selected"] - 1)
                    elif ch2 == b'P':  # Down arrow
                        state["selected"] = min(num_choices - 1, state["selected"] + 1)
                elif ch == b'\r':  # Enter
                    return choices[state["selected"]][1]
                elif ch == b'\x1b':  # Esc
                    return None
                elif ch >= b'1' and ch <= b'9':  # Number keys 1-9
                    num = int(ch) - 1
                    if 0 <= num < num_choices:
                        return choices[num][1]

            import time
            time.sleep(0.01)

    except ImportError:
        # Non-Windows: fall back to Rich prompt
        while True:
            try:
                response = Prompt.ask(
                    "番号を入力してください",
                    choices=[str(i) for i in range(1, len(choices) + 1)],
                    default="1"
                )
                if response.lower() in ["c", "q", "cancel", "quit"]:
                    return None
                index = int(response) - 1
                if 0 <= index < len(choices):
                    return choices[index][1]
            except (ValueError, KeyboardInterrupt, EOFError):
                return None


if __name__ == "__main__":
    # Test the selector with sample models
    import asyncio

    test_models = [
        {"id": "openai/gpt-4o", "name": "GPT-4o", "context_length": 128000,
         "prompt_price": "0.000005", "completion_price": "0.000015"},
        {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "context_length": 200000,
         "prompt_price": "0.000003", "completion_price": "0.000015"},
        {"id": "google/gemini-2.0-flash", "name": "Gemini 2.0 Flash", "context_length": 1000000,
         "prompt_price": "0.0000001", "completion_price": "0.0000004"},
    ]

    async def test():
        selected = await select_model_interactive(test_models)
        if selected:
            print(f"Selected: {selected['id']}")
        else:
            print("Cancelled")

    asyncio.run(test())

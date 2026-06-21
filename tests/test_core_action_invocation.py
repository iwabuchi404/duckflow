from companion.core_action_invocation import filter_call_parameters


def test_filter_call_parameters_drops_unaccepted_keys() -> None:
    """
    Parameters not accepted by the tool callable should be dropped.

    Args:
        None.

    Returns:
        None.
    """

    def tool(path: str, content: str) -> str:
        """Test callable with explicit parameters."""
        return f"{path}:{content}"

    filtered, dropped = filter_call_parameters(
        tool,
        {"path": "a.py", "content": "x", "unexpected": "y"},
    )

    assert filtered == {"path": "a.py", "content": "x"}
    assert dropped == {"unexpected"}


def test_filter_call_parameters_preserves_all_keys_for_kwargs() -> None:
    """
    Callables accepting **kwargs should receive all model parameters.

    Args:
        None.

    Returns:
        None.
    """

    def tool(**kwargs: str) -> dict[str, str]:
        """Test callable accepting arbitrary keyword arguments."""
        return kwargs

    filtered, dropped = filter_call_parameters(
        tool,
        {"path": "a.py", "extra": "ok"},
    )

    assert filtered == {"path": "a.py", "extra": "ok"}
    assert dropped == set()

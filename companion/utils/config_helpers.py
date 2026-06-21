"""Shared helpers for configuration value handling.

Extracts the string→typed-value coercion and nested-dict get/set logic
that was duplicated across multiple command handler modules and the
config loader.
"""

from typing import Any


def coerce_config_value(value: str) -> bool | int | float | str:
    """Convert a raw string value to the most appropriate Python type.

    Conversion order: bool → int → float → str (unchanged).

    Args:
        value: The raw string to convert.

    Returns:
        The converted value.
    """
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if value.isdigit():
        return int(value)
    if value.replace(".", "", 1).isdigit():
        return float(value)
    return value


def get_nested(config: dict[str, Any], key_path: str, default: Any = None) -> Any:
    """Retrieve a value from a nested dict using a dot-separated key path.

    Args:
        config: The root dictionary.
        key_path: Dot-separated path (e.g. ``"llm.groq.model"``).
        default: Value returned when any segment is missing.

    Returns:
        The resolved value, or *default*.
    """
    current: Any = config
    for key in key_path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def set_nested(config: dict[str, Any], key_path: str, value: Any) -> None:
    """Set a value inside a nested dict, creating intermediate dicts as needed.

    Args:
        config: The root dictionary (mutated in place).
        key_path: Dot-separated path (e.g. ``"llm.provider"``).
        value: The value to store.
    """
    keys = key_path.split(".")
    current = config
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value

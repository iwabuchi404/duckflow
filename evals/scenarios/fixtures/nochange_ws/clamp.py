def clamp(value: int, low: int, high: int) -> int:
    """Clamp value into the [low, high] range."""
    if value < low:
        return low
    if value > high:
        return high
    return value

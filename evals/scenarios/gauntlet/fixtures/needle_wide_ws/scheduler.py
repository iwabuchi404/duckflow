"""Job scheduler."""


def midnight_cron() -> str:
    """Midnight schedule expression."""
    return "0 0 * * *"

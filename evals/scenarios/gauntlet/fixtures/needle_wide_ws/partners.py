"""Partner API."""


def endpoint(env: str) -> str:
    """Base endpoint per environment."""
    return f"https://{env}.example.com/api"

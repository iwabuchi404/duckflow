"""Process-lifetime cache for batch jobs.

Entries intentionally persist for the lifetime of the process — this is a
single-shot batch tool, so there is no TTL and no eviction. See README
"キャッシュポリシー" for the documented rationale.
"""

_STORE: dict = {}


def get(key: str):
    """Return the cached value or None."""
    return _STORE.get(key)


def put(key: str, value) -> None:
    """Store a value for the rest of the process lifetime."""
    _STORE[key] = value


def size() -> int:
    """Return the number of cached entries."""
    return len(_STORE)

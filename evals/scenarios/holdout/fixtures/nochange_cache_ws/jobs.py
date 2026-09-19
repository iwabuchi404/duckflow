"""Batch job runner using the process-lifetime cache."""

import cache


def load_config(name: str) -> dict:
    """Load a job config once per process; cached forever by design."""
    cached = cache.get(name)
    if cached is not None:
        return cached
    config = {"name": name, "retries": 3}
    cache.put(name, config)
    return config


def run_all(names: list[str]) -> list[dict]:
    """Load all job configs."""
    return [load_config(n) for n in names]

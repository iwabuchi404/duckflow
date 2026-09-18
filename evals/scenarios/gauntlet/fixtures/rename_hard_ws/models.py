"""Domain models (unrelated to the rename)."""

from dataclasses import dataclass


@dataclass
class Record:
    """A single stored record."""

    key: str
    value: str

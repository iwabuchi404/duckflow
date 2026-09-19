"""Restock report generator."""

import csv
import json


def load_inventory(path: str = "inventory.csv") -> list[dict]:
    """Load inventory rows from the CSV file."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_restock(items: dict, path: str = "restock.json") -> None:
    """Write the restock list as a top-level JSON object."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)

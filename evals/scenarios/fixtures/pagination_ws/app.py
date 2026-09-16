"""Existing caller of list_items (must keep working)."""

from api import list_items


def main() -> None:
    """Print the number of items."""
    print(len(list_items()))


if __name__ == "__main__":
    main()

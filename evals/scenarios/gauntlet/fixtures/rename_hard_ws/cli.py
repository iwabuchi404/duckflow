"""Command-line entry point."""

from store import fetch_records


def main(query: str) -> None:
    """Print matching records."""
    for record in fetch_records(query):
        print(record)


if __name__ == "__main__":
    main("demo")

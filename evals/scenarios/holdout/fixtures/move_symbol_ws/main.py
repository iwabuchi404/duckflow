"""CLI entry point."""

from calc import compute_tax


def main() -> None:
    """Print a demo tax calculation."""
    print(compute_tax(100.0, 0.1))


if __name__ == "__main__":
    main()

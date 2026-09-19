"""Entry point for the batch runner."""

from jobs import run_all


def main() -> None:
    """Run the demo batch."""
    print(run_all(["nightly", "weekly"]))


if __name__ == "__main__":
    main()

"""Demo entry point exercising the allocation flow."""

from orders import fulfill


def main() -> None:
    """Run a sample fulfillment."""
    print(fulfill({"apple": 3, "cherry": 1, "banana": 10}))


if __name__ == "__main__":
    main()

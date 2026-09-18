"""Nightly job entry point."""

from orders import discount
from reports import table
from shipping import fee


def run() -> str:
    """Build the nightly sales summary."""
    orders = {"apple": discount(100.0, 0.1), "postage": float(fee(2))}
    return table(orders)


if __name__ == "__main__":
    print(run())

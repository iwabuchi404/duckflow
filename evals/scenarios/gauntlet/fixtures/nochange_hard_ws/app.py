"""Entry point wiring orders and pricing together."""

from orders import line_total
from pricing import order_total

SAMPLE_ORDER = [
    {"price": 95, "qty": 2, "discount": 0.1},
    {"price": 120, "qty": 1},
]


def main() -> None:
    """Print a sample order total."""
    print(order_total(SAMPLE_ORDER))
    print(line_total(95, 2, 0.1))


if __name__ == "__main__":
    main()

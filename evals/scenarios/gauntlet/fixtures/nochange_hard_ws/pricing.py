"""Order-level aggregation."""

from orders import line_total


def order_total(items: list[dict]) -> int:
    """Sum line totals across an order.

    Args:
        items: Dicts with keys 'price', 'qty' and optional 'discount'.

    Returns:
        Order total in whole yen.
    """
    return sum(
        line_total(i["price"], i["qty"], i.get("discount", 0.0)) for i in items
    )

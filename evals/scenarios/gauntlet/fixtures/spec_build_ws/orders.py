"""Order fulfillment helper that consumes inventory.allocate."""

from inventory import allocate

WAREHOUSE_STOCK = {
    "apple": 10,
    "banana": 4,
    "cherry": 0,
}


def fulfill(order: dict[str, int]) -> dict[str, int]:
    """Allocate warehouse stock for a customer order.

    Args:
        order: sku -> requested quantity.

    Returns:
        sku -> allocated quantity (per SPEC.md rules).
    """
    return allocate(WAREHOUSE_STOCK, order)

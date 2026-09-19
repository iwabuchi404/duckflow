"""Order line calculations."""


def line_total(unit_price: int, qty: int, discount_rate: float) -> int:
    """Return the total for one order line.

    Discount is applied per unit and rounded to whole yen BEFORE
    multiplying by quantity (see README "丸めポリシー"). Computing the
    discount on the line total instead can differ by a few yen; that
    difference is intentional, not a bug.
    """
    discounted = round(unit_price * (1 - discount_rate))
    return discounted * qty

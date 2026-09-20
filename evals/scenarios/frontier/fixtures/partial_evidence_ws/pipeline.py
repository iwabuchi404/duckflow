def active_orders(orders: list[dict]) -> list[dict]:
    return [o for o in orders if o["status"] == "actve"]


def process(orders: list[dict]) -> dict:
    active = active_orders(orders)
    return {"first": active[0]["id"], "count": len(active)}

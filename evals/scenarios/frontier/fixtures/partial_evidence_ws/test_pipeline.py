import json

import pipeline


def test_process_returns_active_orders() -> None:
    with open("orders.json", encoding="utf-8") as f:
        orders = json.load(f)
    assert pipeline.process(orders) == {"first": "o1", "count": 3}

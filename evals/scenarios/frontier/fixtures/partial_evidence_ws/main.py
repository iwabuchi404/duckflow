import json

import pipeline


def main() -> None:
    with open("orders.json", encoding="utf-8") as f:
        orders = json.load(f)
    print(json.dumps(pipeline.process(orders)))


if __name__ == "__main__":
    main()

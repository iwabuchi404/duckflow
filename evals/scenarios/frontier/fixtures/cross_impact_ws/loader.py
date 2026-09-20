from datetime import datetime

import dates


def load_events(path: str) -> list[dict]:
    """Load 'name,date' rows from a CSV file."""
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("name"):
                continue
            name, d = line.split(",")
            events.append({"name": name, "date": dates.parse_date(d)})
    return events

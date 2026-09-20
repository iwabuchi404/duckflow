import dates


def export_event(event: dict) -> str:
    """Serialize an event as 'name|date'."""
    return f"{event['name']}|{dates.format_date(event['date'])}"

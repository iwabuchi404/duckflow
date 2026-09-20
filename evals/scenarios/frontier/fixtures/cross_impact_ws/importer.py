from datetime import datetime


def import_legacy(line: str) -> dict:
    """Import a legacy 'name;date' line."""
    name, d = line.split(";")
    return {"name": name, "date": datetime.strptime(d, "%Y-%m-%d")}

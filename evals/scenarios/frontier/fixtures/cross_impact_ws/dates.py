from datetime import datetime

DATE_FMT = "%Y-%m-%d"


def format_date(dt: datetime) -> str:
    return dt.strftime(DATE_FMT)


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, DATE_FMT)

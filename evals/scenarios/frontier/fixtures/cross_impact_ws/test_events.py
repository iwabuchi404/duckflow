from datetime import datetime

import dates
import exporter
import importer
import loader


def test_parse_and_format_european() -> None:
    dt = dates.parse_date("25/12/2026")
    assert dt == datetime(2026, 12, 25)
    assert dates.format_date(dt) == "25/12/2026"


def test_load_events_european(tmp_path) -> None:
    events = loader.load_events("events.csv")
    assert events[0]["date"] == datetime(2026, 12, 25)


def test_import_legacy_european() -> None:
    e = importer.import_legacy("Concert;03/04/2026")
    assert e["date"] == datetime(2026, 4, 3)


def test_export_european() -> None:
    out = exporter.export_event({"name": "Launch", "date": datetime(2026, 12, 25)})
    assert out == "Launch|25/12/2026"

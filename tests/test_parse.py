from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sync.parse import parse_datetime, parse_timetable

BKK = ZoneInfo("Asia/Bangkok")
FIXTURE = (Path(__file__).parent / "fixtures" / "timetable.html").read_text(encoding="utf-8")


def test_parses_good_rows_and_skips_the_rest():
    events = parse_timetable(FIXTURE)
    assert [e.title for e in events] == ["A-Level Physics", "Further Maths FP2"]  # duplicate and broken rows dropped


def test_fields_and_times_are_in_bangkok():
    physics = parse_timetable(FIXTURE)[0]
    assert physics.start_dt == datetime(2025, 10, 13, 16, 0, tzinfo=BKK)
    assert physics.end_dt == datetime(2025, 10, 13, 17, 30, tzinfo=BKK)
    assert (physics.instructor, physics.student, physics.location, physics.status) == (
        "Kru Ann",
        "Tarm",
        "Room 3",
        "Confirmed",
    )
    assert physics.remark is None
    assert physics.raw_id == "1"


def test_alternative_headers_and_a_single_time_column():
    html = """<table><tr><th>Date</th><th>Time</th><th>Subject</th><th>Teacher</th><th>Room</th></tr>
    <tr><td>2025-11-02</td><td>13.00 - 14.30</td><td>Chemistry</td><td>Kru C</td><td>Lab</td></tr></table>"""
    (event,) = parse_timetable(html)
    assert event.title == "Chemistry"
    assert event.instructor == "Kru C" and event.location == "Lab"
    assert event.start_dt.hour == 13 and event.end_dt.hour == 14 and event.end_dt.minute == 30


def test_no_table_means_no_events():
    assert parse_timetable("<html><body>Please log in</body></html>") == []


def test_parse_datetime_converts_aware_input():
    dt = parse_datetime("2025-10-13", "09:00+00:00")
    assert dt.tzinfo == BKK and dt.hour == 16

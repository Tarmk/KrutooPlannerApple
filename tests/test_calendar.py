from datetime import datetime
from zoneinfo import ZoneInfo

from icalendar import Calendar

from sync.icloud_caldav import sync_calendar, to_ical
from sync.models import ClassEvent

BKK = ZoneInfo("Asia/Bangkok")


def lesson(title="Physics", hour=16, location="Room 3", status="Confirmed"):
    return ClassEvent(
        title=title,
        start_dt=datetime(2025, 10, 13, hour, 0, tzinfo=BKK),
        end_dt=datetime(2025, 10, 13, hour + 1, 0, tzinfo=BKK),
        location=location,
        status=status,
        instructor="Kru Ann",
        student="Tarm",
    )


class FakeItem:
    def __init__(self, data):
        self.data = data
        self.saves = 0

    @property
    def icalendar_component(self):
        return next(iter(Calendar.from_ical(self.data).walk("VEVENT")))

    def save(self):
        self.saves += 1


class FakeCalendar:
    def __init__(self, items=()):
        self.items = list(items)
        self.created = []

    def events(self):
        return self.items

    def save_event(self, ical):
        self.created.append(ical)
        self.items.append(FakeItem(ical))


def test_uid_is_stable_and_ignores_status():
    assert lesson().uid == lesson(status="Cancelled").uid
    assert lesson().uid != lesson(hour=17).uid
    assert lesson().uid.endswith("@krutoosync")


def test_ical_has_the_event_fields():
    vevent = next(iter(Calendar.from_ical(to_ical(lesson())).walk("VEVENT")))
    assert str(vevent["SUMMARY"]) == "Physics"
    assert str(vevent["LOCATION"]) == "Room 3"
    assert "Teacher: Kru Ann" in str(vevent["DESCRIPTION"])
    assert vevent.decoded("DTSTART") == datetime(2025, 10, 13, 16, 0, tzinfo=BKK)


def test_sync_creates_then_skips_unchanged_then_updates_in_place():
    cal = FakeCalendar()
    first = sync_calendar(cal, [lesson(), lesson(title="Maths", hour=9)])
    assert (first.created, first.updated, first.unchanged) == (2, 0, 0)

    again = sync_calendar(cal, [lesson(), lesson(title="Maths", hour=9)])
    assert (again.created, again.updated, again.unchanged) == (0, 0, 2)

    moved = sync_calendar(cal, [lesson(location="Online"), lesson(title="Maths", hour=9)])
    assert (moved.created, moved.updated, moved.unchanged) == (0, 1, 1)
    assert len(cal.items) == 2  # updated in place, nothing deleted and re-created
    assert sum(item.saves for item in cal.items) == 1


def test_sync_ignores_events_it_did_not_create():
    foreign = FakeItem(
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:someone-else\r\nSUMMARY:Dentist\r\n"
        "DTSTART:20251013T090000Z\r\nDTEND:20251013T100000Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    cal = FakeCalendar([foreign])
    report = sync_calendar(cal, [lesson()])
    assert report.created == 1 and foreign.saves == 0

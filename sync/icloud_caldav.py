"""Write events into an iCloud calendar over CalDAV."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from icalendar import Calendar as ICalendar
from icalendar import Event as ICEvent

from .models import ClassEvent

ICLOUD_URL = "https://caldav.icloud.com/"


@dataclass
class SyncReport:
    created: int = 0
    updated: int = 0
    unchanged: int = 0

    def __str__(self) -> str:
        return f"{self.created} created, {self.updated} updated, {self.unchanged} unchanged"


def to_ical(event: ClassEvent) -> str:
    cal = ICalendar()
    cal.add("prodid", "-//Krutoo Sync//EN")
    cal.add("version", "2.0")
    vevent = ICEvent()
    vevent.add("uid", event.uid)
    vevent.add("summary", event.title)
    vevent.add("dtstart", event.start_dt)
    vevent.add("dtend", event.end_dt)
    if event.location:
        vevent.add("location", event.location)
    vevent.add("description", event.description)
    cal.add_component(vevent)
    return cal.to_ical().decode("utf-8")


def _fingerprint(ical_text: str) -> tuple:
    """The parts of an event that matter; used to skip writes when nothing changed."""
    cal = ICalendar.from_ical(ical_text)
    for component in cal.walk("VEVENT"):
        return tuple(
            str(component.get(key, "")) if key not in ("DTSTART", "DTEND") else component.decoded(key).isoformat()
            for key in ("SUMMARY", "DTSTART", "DTEND", "LOCATION", "DESCRIPTION")
        )
    return ()


def _find_or_create_calendar(principal, name: Optional[str]):
    calendars = principal.calendars()
    if not name:
        if not calendars:
            raise RuntimeError("The iCloud account has no calendars; set ICLOUD_CALENDAR_NAME to create one.")
        return calendars[0]
    for cal in calendars:
        if cal.get_display_name() == name:
            return cal
    return principal.make_calendar(name=name)


def upsert_events(
    username: str,
    app_password: str,
    events: Iterable[ClassEvent],
    calendar_name: Optional[str] = None,
    url: str = ICLOUD_URL,
) -> SyncReport:
    """Create new lessons and update changed ones in place. Lessons are matched by UID."""
    import caldav  # imported lazily so parsing and tests do not need it

    client = caldav.DAVClient(url=url, username=username, password=app_password)
    calendar = _find_or_create_calendar(client.principal(), calendar_name)
    return sync_calendar(calendar, events)


def sync_calendar(calendar, events: Iterable[ClassEvent]) -> SyncReport:
    """The CalDAV-agnostic part of :func:`upsert_events` (takes any caldav.Calendar-like object)."""
    existing: Dict[str, object] = {}
    for item in calendar.events():
        uid = item.icalendar_component.get("UID")
        if uid and str(uid).endswith("@krutoosync"):
            existing[str(uid)] = item

    report = SyncReport()
    for event in events:
        ical = to_ical(event)
        current = existing.get(event.uid)
        if current is None:
            calendar.save_event(ical)
            report.created += 1
        elif _fingerprint(current.data) == _fingerprint(ical):
            report.unchanged += 1
        else:
            current.data = ical
            current.save()
            report.updated += 1
    return report

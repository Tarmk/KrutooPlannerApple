from __future__ import annotations

import hashlib
from typing import List, Optional

import caldav
from caldav import Calendar
from icalendar import Calendar as ICalendar, Event as ICEvent, vCalAddress, vText
from datetime import datetime

from .models import ClassEvent


def _find_or_create_calendar(principal: caldav.Principal, name: Optional[str]) -> Calendar:
    calendars = principal.calendars()
    if name:
        for cal in calendars:
            props = cal.get_properties(["{DAV:}displayname"])  # type: ignore
            if props.get("{DAV:}displayname") == name:
                return cal
        return principal.make_calendar(name)
    return calendars[0]


def _event_uid(ev: ClassEvent) -> str:
    basis = ev.uid_basis().encode("utf-8")
    return hashlib.sha1(basis).hexdigest() + "@krutoosync"


def _serialize_event(ev: ClassEvent) -> ICalendar:
    cal = ICalendar()
    cal.add("prodid", "-//Krutoo Sync//EN")
    cal.add("version", "2.0")
    ice = ICEvent()
    ice.add("uid", _event_uid(ev))
    ice.add("summary", ev.title)
    ice.add("dtstart", ev.start_dt)
    ice.add("dtend", ev.end_dt)
    if ev.location:
        ice.add("location", ev.location)
    desc = []
    if ev.status:
        desc.append(f"Status: {ev.status}")
    if ev.remark:
        desc.append(f"Remark: {ev.remark}")
    ice.add("description", "\n".join(desc) + "\nSource: krutooschool.com")
    cal.add_component(ice)
    return cal


def upsert_events(url: str, username: str, app_password: str, calendar_name: Optional[str], events: List[ClassEvent]) -> None:
    client = caldav.DAVClient(url=url, username=username, password=app_password)
    principal = client.principal()
    calendar = _find_or_create_calendar(principal, calendar_name)

    existing = {item.vobject_instance.vevent.uid.value: item for item in calendar.events()}  # type: ignore

    for ev in events:
        ical = _serialize_event(ev)
        uid = _event_uid(ev)
        if uid in existing:
            existing[uid].delete()
        calendar.add_event(ical.to_ical().decode("utf-8"))


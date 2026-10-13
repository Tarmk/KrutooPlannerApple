"""Parse the KRUTOO "Show list" timetable table into events. No browser needed."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from .models import ClassEvent

BANGKOK = ZoneInfo("Asia/Bangkok")

# Header text (lower-cased) -> field. The first header found for a field wins.
COLUMNS = {
    "title": ("course", "subject", "class", "event"),
    "date": ("date",),
    "start": ("start", "start time", "from"),
    "end": ("end", "end time", "to"),
    "location": ("location", "room"),
    "status": ("status",),
    "remark": ("remark", "remarks", "note"),
    "instructor": ("instructor", "teacher"),
    "student": ("student",),
    "raw_id": ("#", "id", "no."),
    "time_range": ("time", "hour", "hours", "period"),
}
TIME_RANGE = re.compile(r"(\d{1,2}[:.]\d{2})\s*(?:-|–|to)\s*(\d{1,2}[:.]\d{2})")


def parse_datetime(date_str: str, time_str: str, tz=BANGKOK) -> datetime:
    """Combine the table's date and time cells into an aware datetime (Bangkok time)."""
    dt = dateutil_parser.parse(f"{date_str} {time_str}", dayfirst=False)
    return dt.replace(tzinfo=tz) if dt.tzinfo is None else dt.astimezone(tz)


def _pick(row: Dict[str, str], field: str) -> Optional[str]:
    for header in COLUMNS[field]:
        value = row.get(header)
        if value:
            return value
    return None


def parse_timetable(html: str) -> List[ClassEvent]:
    """Return one event per lesson row. Rows that cannot be parsed are skipped."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []

    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
    body = table.find("tbody") or table
    events: List[ClassEvent] = []
    seen = set()
    for tr in body.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if not cells:
            continue  # header row
        row = dict(zip(headers, cells))
        date_str, start_str, end_str = _pick(row, "date"), _pick(row, "start"), _pick(row, "end")
        if not (start_str and end_str):
            # Some views show one "10:00 - 11:30" column instead of start and end.
            match = TIME_RANGE.search(_pick(row, "time_range") or "")
            if match:
                start_str, end_str = (part.replace(".", ":") for part in match.groups())
        if not (date_str and start_str and end_str):
            continue
        if end_str.isdigit() and len(end_str) <= 2:
            continue  # an "hours" column, not an end time
        try:
            start, end = parse_datetime(date_str, start_str), parse_datetime(date_str, end_str)
        except (ValueError, OverflowError):
            continue
        if end <= start:
            continue

        event = ClassEvent(
            title=_pick(row, "title") or "Class",
            start_dt=start,
            end_dt=end,
            location=_pick(row, "location"),
            status=_pick(row, "status"),
            remark=_pick(row, "remark"),
            instructor=_pick(row, "instructor"),
            student=_pick(row, "student"),
            raw_id=_pick(row, "raw_id"),
        )
        if event.uid not in seen:  # the list can repeat rows when it is scrolled
            seen.add(event.uid)
            events.append(event)
    return events

"""Scrape the KRUTOO timetable and sync it into iCloud Calendar.

python -m sync.main                  # scrape and sync (credentials from env vars)
python -m sync.main --dry-run        # scrape and print, do not touch iCloud
python -m sync.main --html page.html # parse a saved page instead of scraping
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional, Sequence

from .icloud_caldav import upsert_events
from .models import ClassEvent
from .parse import parse_timetable


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing environment variable {name}.")
    return value


def load_events(html_file: Optional[str]) -> List[ClassEvent]:
    if html_file:
        with open(html_file, encoding="utf-8") as f:
            return parse_timetable(f.read())
    from .krutooschool_scraper import scrape_show_list

    headless = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    return scrape_show_list(_env("KRUTOO_USERNAME"), _env("KRUTOO_PASSWORD"), headless=headless)


def run_sync(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Sync the KRUTOO timetable into iCloud Calendar.")
    parser.add_argument("--dry-run", action="store_true", help="print the lessons instead of writing to iCloud")
    parser.add_argument("--html", metavar="FILE", help="parse a saved timetable page instead of logging in")
    args = parser.parse_args(argv)

    events = load_events(args.html)
    print(f"Found {len(events)} lesson(s).")
    if not events:
        return 0

    if args.dry_run:
        for ev in sorted(events, key=lambda e: e.start_dt):
            where = f" @ {ev.location}" if ev.location else ""
            print(f"  {ev.start_dt:%a %d %b %H:%M}-{ev.end_dt:%H:%M}  {ev.title}{where}")
        return 0

    report = upsert_events(
        username=_env("ICLOUD_USERNAME"),
        app_password=_env("ICLOUD_APP_PASSWORD"),
        calendar_name=os.environ.get("ICLOUD_CALENDAR_NAME") or None,
        events=events,
    )
    print(f"iCloud: {report}.")
    return 0


if __name__ == "__main__":
    sys.exit(run_sync())

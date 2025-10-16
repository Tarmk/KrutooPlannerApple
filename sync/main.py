import os
from typing import Optional

from .krutooschool_scraper import scrape_show_list
from .icloud_caldav import upsert_events


def run_sync():
    kr_user = os.environ["KRUTOO_USERNAME"]
    kr_pass = os.environ["KRUTOO_PASSWORD"]
    ic_user = os.environ["ICLOUD_USERNAME"]
    ic_pass = os.environ["ICLOUD_APP_PASSWORD"]
    cal_name: Optional[str] = os.environ.get("ICLOUD_CALENDAR_NAME") or None

    events = scrape_show_list(kr_user, kr_pass)
    if not events:
        print("No events scraped.")
        return
    upsert_events(
        url="https://caldav.icloud.com/",
        username=ic_user,
        app_password=ic_pass,
        calendar_name=cal_name,
        events=events,
    )


if __name__ == "__main__":
    run_sync()


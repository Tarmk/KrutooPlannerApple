from __future__ import annotations

import hashlib
import os
from dataclasses import asdict
from datetime import datetime
from typing import Iterable, List

from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser
import pytz
from playwright.sync_api import sync_playwright

from .models import ClassEvent


BKK_TZ = pytz.timezone("Asia/Bangkok")


def _parse_datetime(date_str: str, time_str: str) -> datetime:
    dt = dateutil_parser.parse(f"{date_str} {time_str}", dayfirst=False)
    if dt.tzinfo is None:
        dt = BKK_TZ.localize(dt)
    else:
        dt = dt.astimezone(BKK_TZ)
    return dt


def scrape_show_list(username: str, password: str) -> List[ClassEvent]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(timezone_id="Asia/Bangkok")
        page = context.new_page()
        page.goto("https://krutooschool.com/", wait_until="domcontentloaded")
        # Dismiss cookie banner if present (text-based selector)
        for txt in ["Accept", "I agree", "ตกลง", "ยอมรับ"]:
            try:
                page.click(f'button:has-text("{txt}")', timeout=2000)
                break
            except Exception:
                continue

        # Login (robust selectors)
        try:
            page.fill('input[type="email"]', username, timeout=10000)
        except Exception:
            # Fallback: first text input
            page.locator('input[type="text"], input[placeholder*="mail" i]').first.fill(username)
        page.fill('input[type="password"]', password)
        # Submit strategies
        submitted = False
        for selector in [
            'button:has-text("SIGN IN")',
            'button:has-text("Sign in")',
            'input[type="submit"]',
            'button[type="submit"]',
        ]:
            try:
                page.click(selector, timeout=3000)
                submitted = True
                break
            except Exception:
                continue
        if not submitted:
            page.keyboard.press("Enter")

        # Wait for signs of authenticated app instead of strict URL
        signed_in = False
        for _ in range(2):  # try twice, second time after direct navigation
            try:
                page.wait_for_selector('a:has-text("Timetable"), button:has-text("Show Timetable"), button:has-text("Show List")', timeout=30000)
                signed_in = True
                break
            except Exception:
                page.goto("https://krutooschool.com/profile/", wait_until="domcontentloaded")

        # Click Show List
        # Try to click Show List when available
        clicked_list = False
        for selector in [
            'button:has-text("Show List")',
            'text=Show List',
            'a:has-text("Show List")',
            'a[role="button"]:has-text("Show List")',
        ]:
            try:
                page.click(selector, timeout=5000)
                clicked_list = True
                break
            except Exception:
                continue
        if not clicked_list:
            # Maybe it defaulted to list view already
            # Ensure we're on Timetable page and try the other button
            try:
                page.click('a:has-text("Timetable")', timeout=3000)
                page.click('button:has-text("Show List")', timeout=5000)
                clicked_list = True
            except Exception:
                pass

        page.wait_for_selector("table", timeout=60000)

        # Ensure all rows are loaded (if virtualized, try scrolling)
        for _ in range(10):
            page.mouse.wheel(0, 2000)

        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    # Try to infer columns
    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
    events: List[ClassEvent] = []
    for tr in table.find("tbody").find_all("tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        row = dict(zip(headers, tds))
        try:
            title = row.get("course") or row.get("subject") or row.get("event") or "Class"
            date_str = row.get("date") or ""
            start_str = row.get("start") or row.get("start time") or ""
            end_str = row.get("end") or row.get("end time") or row.get("hour") or ""
            # If hour is duration, we can't parse end; skip in that case
            if len(end_str) <= 2 and end_str.isdigit():
                continue
            start_dt = _parse_datetime(date_str, start_str)
            end_dt = _parse_datetime(date_str, end_str)
            ev = ClassEvent(
                title=title,
                start_dt=start_dt,
                end_dt=end_dt,
                location=row.get("location"),
                status=row.get("status"),
                remark=row.get("remark"),
                instructor=row.get("instructor"),
                student=row.get("student"),
                raw_id=row.get("#") or row.get("id"),
            )
            events.append(ev)
        except Exception:
            continue

    return events


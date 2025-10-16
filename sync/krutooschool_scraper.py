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


def _snapshot(page, name: str) -> None:
    try:
        os.makedirs("artifacts", exist_ok=True)
        page.screenshot(path=f"artifacts/{name}.png", full_page=True)
        with open(f"artifacts/{name}.html", "w", encoding="utf-8") as f:
            f.write(page.content())
    except Exception:
        pass


def scrape_show_list(username: str, password: str) -> List[ClassEvent]:
    with sync_playwright() as p:
        storage_state_path = os.environ.get("PLAYWRIGHT_STORAGE_STATE", "storage_state.json")
        headless = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
        browser = p.chromium.launch(headless=headless, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ])
        context_kwargs = dict(timezone_id="Asia/Bangkok")
        if os.path.exists(storage_state_path):
            context_kwargs["storage_state"] = storage_state_path
        context = browser.new_context(**context_kwargs)
        # Start tracing to collect network + DOM steps
        try:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
        except Exception:
            pass
        page = context.new_page()
        page.goto("https://krutooschool.com/", wait_until="domcontentloaded")
        _snapshot(page, "00-login-loaded")
        # If storage state exists, try going straight to profile
        if os.path.exists(storage_state_path):
            try:
                page.goto("https://krutooschool.com/profile/", wait_until="domcontentloaded")
                page.wait_for_selector('button:has-text("Show Timetable"), button:has-text("Show List")', timeout=10000)
                _snapshot(page, "00a-storage-state-profile")
                # Save refreshed state to keep session alive
                try:
                    context.storage_state(path=storage_state_path)
                except Exception:
                    pass
            except Exception:
                pass

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
        # Explicit double-submit flow as requested
        def do_one_submit():
            # Try multiple visible button selectors only (no Enter, no form.submit)
            button_selectors = [
                'button:has-text("SIGN IN")',
                'button:has-text("Sign in")',
                'button:has-text("LOGIN")',
                'button:has-text("Login")',
                'role=button[name=/sign in|login|เข้าสู่ระบบ/i]'
            ]
            for selector in button_selectors:
                try:
                    page.locator(selector).first.scroll_into_view_if_needed(timeout=2000)
                    page.locator(selector).first.click(timeout=3000)
                    return True
                except Exception:
                    continue
            # Low-level mouse click on best-guess button element
            for guess in [
                'button[type="submit"]',
                'button:has-text("SIGN IN")',
                'button:has-text("Login")',
            ]:
                try:
                    btn = page.locator(guess).first
                    btn.scroll_into_view_if_needed(timeout=2000)
                    box = btn.bounding_box()
                    if box:
                        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                        page.mouse.down(); page.mouse.up()
                        return True
                except Exception:
                    continue
            # JS dispatch click on any matching button by text content
            try:
                page.evaluate(
                    "() => {\n"
                    "  const candidates = Array.from(document.querySelectorAll('button, [role=button]'));\n"
                    "  const re = /(sign in|login|เข้าสู่ระบบ)/i;\n"
                    "  const el = candidates.find(e => re.test((e.innerText||'') + ' ' + (e.ariaLabel||'')));\n"
                    "  if (el) { el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true})); }\n"
                    "}"
                )
                return True
            except Exception:
                return False

        # First attempt
        do_one_submit()
        _snapshot(page, "01a-after-first-submit")
        page.wait_for_timeout(3000)
        # Refill and submit again
        try:
            page.fill('input[type="email"]', username, timeout=3000)
        except Exception:
            try:
                page.locator('input[type="text"], input[placeholder*="mail" i]').first.fill(username)
            except Exception:
                pass
        try:
            page.fill('input[type="password"]', password, timeout=3000)
        except Exception:
            pass
        do_one_submit()
        _snapshot(page, "01b-after-second-submit")

        # Wait for signs of authenticated app instead of strict URL
        signed_in = False
        for _ in range(2):  # try twice, second time after direct navigation
            try:
                page.wait_for_selector('a:has-text("Timetable"), button:has-text("Show Timetable"), button:has-text("Show List")', timeout=30000)
                signed_in = True
                break
            except Exception:
                page.goto("https://krutooschool.com/profile/", wait_until="domcontentloaded")
                _snapshot(page, "02-after-profile-nav")

        # Persist session if login succeeded
        if signed_in:
            try:
                context.storage_state(path=storage_state_path)
            except Exception:
                pass

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

        _snapshot(page, "03-before-wait-table")
        # Capture any visible error message around the form, if table isn't present
        try:
            err_texts = []
            for sel in [
                ".error, .alert, .text-danger, .validation-message", 
                "form >> text=/invalid|incorrect|timeout|session|error/i"
            ]:
                for el in page.locator(sel).all():
                    err_texts.append(el.inner_text())
            if err_texts:
                os.makedirs("artifacts", exist_ok=True)
                with open("artifacts/errors.txt", "w", encoding="utf-8") as f:
                    f.write("\n".join(err_texts))
        except Exception:
            pass

        page.wait_for_selector("table", timeout=60000)
        _snapshot(page, "04-table-visible")

        # Ensure all rows are loaded (if virtualized, try scrolling)
        for _ in range(10):
            page.mouse.wheel(0, 2000)

        html = page.content()
        try:
            os.makedirs("artifacts", exist_ok=True)
            context.tracing.stop(path="artifacts/trace.zip")
        except Exception:
            pass
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


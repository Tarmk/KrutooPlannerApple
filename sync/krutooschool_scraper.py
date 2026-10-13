"""Log in to krutooschool.com with Playwright and grab the timetable list as HTML."""

from __future__ import annotations

import os
from typing import List, Optional

from .models import ClassEvent
from .parse import parse_timetable

SITE = "https://krutooschool.com/"
PROFILE = "https://krutooschool.com/profile/"
COOKIE_BUTTONS = ("Accept", "I agree", "ตกลง", "ยอมรับ")
SUBMIT_BUTTONS = (
    'button:has-text("SIGN IN")',
    'button:has-text("Sign in")',
    'button:has-text("LOGIN")',
    'button:has-text("Login")',
    'button[type="submit"]',
)
LOGGED_IN = 'a:has-text("Timetable"), button:has-text("Show Timetable"), button:has-text("Show List")'
SHOW_LIST = ('button:has-text("Show List")', 'a:has-text("Show List")', "text=Show List")

# If the Show List button is disabled because no date range is set, fill in today + 30 days.
_ENABLE_SHOW_LIST_JS = """
() => {
  const btn = [...document.querySelectorAll('button, [role=button]')]
    .find(b => /show list/i.test((b.innerText || '') + ' ' + (b.ariaLabel || '')));
  if (!btn || !(btn.disabled || btn.hasAttribute('disabled'))) return;
  const [start, end] = document.querySelectorAll('input[type=date], input[name*=start i], input[name*=end i]');
  const iso = d => d.toISOString().slice(0, 10);
  const today = new Date();
  if (start) start.value = iso(today);
  if (end) end.value = iso(new Date(today.getTime() + 30 * 86400000));
  btn.disabled = false;
  btn.removeAttribute('disabled');
}
"""


class Scraper:
    def __init__(self, page, artifacts_dir: Optional[str] = "artifacts") -> None:
        self.page = page
        self.artifacts_dir = artifacts_dir

    def snapshot(self, name: str) -> None:
        """Save a screenshot and the HTML, for debugging failed runs (git-ignored)."""
        if not self.artifacts_dir:
            return
        try:
            os.makedirs(self.artifacts_dir, exist_ok=True)
            base = os.path.join(self.artifacts_dir, name)
            self.page.screenshot(path=f"{base}.png", full_page=True)
            with open(f"{base}.html", "w", encoding="utf-8") as f:
                f.write(self.page.content())
        except Exception:
            pass

    def click_first(self, selectors, timeout: int = 3000) -> bool:
        for selector in selectors:
            try:
                target = self.page.locator(selector).first
                target.scroll_into_view_if_needed(timeout=timeout)
                target.click(timeout=timeout)
                return True
            except Exception:
                continue
        return False

    def dismiss_cookies(self) -> None:
        self.click_first([f'button:has-text("{text}")' for text in COOKIE_BUTTONS], timeout=1500)

    def is_logged_in(self, timeout: int) -> bool:
        try:
            self.page.wait_for_selector(LOGGED_IN, timeout=timeout)
            return True
        except Exception:
            return False

    def fill_credentials(self, username: str, password: str) -> None:
        try:
            self.page.fill('input[type="email"]', username, timeout=10_000)
        except Exception:
            self.page.locator('input[type="text"], input[placeholder*="mail" i]').first.fill(username)
        self.page.fill('input[type="password"]', password)

    def log_in(self, username: str, password: str) -> None:
        # The login form often ignores the first submit, so try twice before giving up.
        for attempt in (1, 2):
            self.fill_credentials(username, password)
            self.click_first(SUBMIT_BUTTONS)
            if self.is_logged_in(timeout=15_000):
                return
            self.snapshot(f"login-attempt-{attempt}")
            self.page.goto(PROFILE, wait_until="domcontentloaded")
            if self.is_logged_in(timeout=5_000):
                return
        raise RuntimeError("Could not log in to krutooschool.com (see artifacts/ for screenshots).")

    def open_list(self) -> None:
        self.dismiss_cookies()
        if not self.click_first(SHOW_LIST, timeout=4000):
            self.page.evaluate(_ENABLE_SHOW_LIST_JS)
            if not self.click_first(SHOW_LIST, timeout=4000):
                self.click_first(['a:has-text("Timetable")'])
                self.click_first(SHOW_LIST, timeout=5000)
        self.page.wait_for_selector("table", timeout=60_000)
        for _ in range(10):  # make sure lazily rendered rows are loaded
            self.page.mouse.wheel(0, 2000)


def fetch_timetable_html(
    username: str,
    password: str,
    storage_state: Optional[str] = None,
    headless: bool = True,
    artifacts_dir: Optional[str] = "artifacts",
) -> str:
    from playwright.sync_api import sync_playwright  # only needed when actually scraping

    storage_state = storage_state or os.environ.get("PLAYWRIGHT_STORAGE_STATE") or "storage_state.json"
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        context_args = {"timezone_id": "Asia/Bangkok"}
        if os.path.exists(storage_state):
            context_args["storage_state"] = storage_state
        context = browser.new_context(**context_args)
        scraper = Scraper(context.new_page(), artifacts_dir)
        try:
            scraper.page.goto(PROFILE, wait_until="domcontentloaded")
            scraper.dismiss_cookies()
            if not scraper.is_logged_in(timeout=10_000):
                scraper.page.goto(SITE, wait_until="domcontentloaded")
                scraper.dismiss_cookies()
                scraper.log_in(username, password)
            scraper.open_list()
            html = scraper.page.content()
            context.storage_state(path=storage_state)  # keep the session for next time
            return html
        except Exception:
            scraper.snapshot("failure")
            raise
        finally:
            browser.close()


def scrape_show_list(username: str, password: str, **kwargs) -> List[ClassEvent]:
    return parse_timetable(fetch_timetable_html(username, password, **kwargs))

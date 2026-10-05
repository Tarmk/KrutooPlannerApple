# Krutoo → iCloud Calendar Auto‑Sync

Scrapes the "Show list" timetable from the KRUTOO school portal with Playwright and upserts it into an iCloud calendar over CalDAV, so lessons show up on iPhone/Mac/Watch automatically.

**Status:** this ran every 15 minutes from a self-hosted Windows runner during my last school year. I have since graduated, so the schedule is switched off and the workflow is manual-only (`Run workflow`). The code still works for anyone with a KRUTOO account.

## How it works
1. `sync/krutooschool_scraper.py` logs in (reusing `storage_state.json` when present), opens the timetable list and parses each lesson into an event (Asia/Bangkok time).
2. `sync/icloud_caldav.py` connects to `caldav.icloud.com` with an app-specific password and creates/updates events in the chosen calendar, keyed by a stable UID so re-runs do not duplicate.
3. `sync/main.py` wires the two together from environment variables.

## Setup
1. In your GitHub repo, add Actions Secrets:
   - `KRUTOO_USERNAME`, `KRUTOO_PASSWORD`
   - `ICLOUD_USERNAME`, `ICLOUD_APP_PASSWORD`
   - `ICLOUD_CALENDAR_NAME` (optional, e.g., `KRUTOO`)
2. Push this repo and start it from the Actions tab with **Run workflow** (the job targets a `self-hosted, Windows` runner; change `runs-on` in `.github/workflows/krutoo-sync.yml` to `windows-latest` if you want GitHub-hosted runners).

## Local run
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
export KRUTOO_USERNAME=... KRUTOO_PASSWORD=... ICLOUD_USERNAME=... ICLOUD_APP_PASSWORD=...   # optional: ICLOUD_CALENDAR_NAME
python -m sync.main
```
Set `PLAYWRIGHT_HEADLESS=false` to watch the browser, and `PLAYWRIGHT_STORAGE_STATE=path` to reuse a saved login.

All times use Asia/Bangkok.

`storage_state.json` (saved login) and `artifacts/` (debug screenshots/HTML) are git-ignored; never commit them.


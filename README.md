# Krutoo → iCloud Calendar Auto‑Sync

This syncs your KRUTOO timetable "Show list" to iCloud Calendar every 15 minutes.

## Setup
1. In your GitHub repo, add Actions Secrets:
   - `KRUTOO_USERNAME`, `KRUTOO_PASSWORD`
   - `ICLOUD_USERNAME`, `ICLOUD_APP_PASSWORD`
   - `ICLOUD_CALENDAR_NAME` (optional, e.g., `KRUTOO`)
2. Push this repo. The workflow runs every 15 minutes or via Run workflow.

## Local run
```bash
pip install -r requirements.txt icalendar
python -m playwright install chromium
python -c "from sync.main import run_sync; run_sync()"
```

All times use Asia/Bangkok.

## Git hygiene
Add these to your global/local `.gitignore` if not already present:
- Python caches: `**/__pycache__/`, `*.pyc`
- Playwright login state: `storage_state.json`
- Debug artifacts directory: `artifacts/`


from pathlib import Path

from sync.main import run_sync

FIXTURE = Path(__file__).parent / "fixtures" / "timetable.html"


def test_dry_run_from_a_saved_page(capsys):
    assert run_sync(["--dry-run", "--html", str(FIXTURE)]) == 0
    out = capsys.readouterr().out
    assert "Found 2 lesson(s)." in out
    assert "Mon 13 Oct 16:00-17:30  A-Level Physics @ Room 3" in out

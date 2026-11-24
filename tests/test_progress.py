"""Practice time, streak and daily goal: what counts and what doesn't."""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pianove  # noqa: E402,F401
from pianove import progress  # noqa: E402
from pianove.state import storage  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_path", tmp_path / "storage.json")
    monkeypatch.setattr(storage, "_data", {})
    progress._clock.update(last=None, pending=0.0)
    yield
    progress._clock.update(last=None, pending=0.0)


def test_time_between_notes_counts():
    for t in range(0, 61, 2):               # a note every 2 s for a minute
        progress.note_played(now=1000.0 + t)
    progress.flush_practice_time()
    assert progress.practice_log()[date.today().isoformat()] == pytest.approx(60.0)
    assert progress.minutes_today() == 1


def test_a_long_pause_is_not_practice():
    progress.note_played(now=0.0)
    progress.note_played(now=5.0)           # 5 s
    progress.note_played(now=500.0)         # away from the piano: not counted
    progress.note_played(now=503.0)         # 3 s
    progress.flush_practice_time()
    assert progress.practice_log()[date.today().isoformat()] == pytest.approx(8.0)


def test_leaving_the_page_stops_the_clock():
    progress.note_played(now=0.0)
    progress.note_played(now=4.0)
    progress.stop_clock()
    progress.note_played(now=10.0)          # a new stretch: the 6 s in between don't count
    progress.flush_practice_time()
    assert progress.practice_log()[date.today().isoformat()] == pytest.approx(4.0)


def test_streak_counts_songs_and_practice_not_only_lessons():
    today = date.today()
    storage.set("lesson_dates", [today.isoformat()])
    storage.set("practice_sessions", [{"date": (today - timedelta(days=1)).isoformat(),
                                       "accuracy": 1.0, "notes": 8, "bpm": 80}])
    progress.add_practice_seconds(300, day=today - timedelta(days=2))
    progress.record_activity(day=today - timedelta(days=3))
    progress.add_practice_seconds(20, day=today - timedelta(days=4))   # under a minute
    assert progress.streak() == 4


def test_total_minutes_and_goal():
    storage.set("total_minutes", 30)        # an older storage's total is kept
    progress.add_practice_seconds(600)
    assert progress.total_practice_minutes() == 40
    assert progress.daily_goal_minutes() == 10
    progress.set_daily_goal_minutes(20)
    assert progress.daily_goal_minutes() == 20


def test_recent_minutes_ends_today():
    progress.add_practice_seconds(120)
    days = progress.recent_minutes(7)
    assert len(days) == 7 and days[-1] == (date.today(), 2.0)

"""Today's session: what it plans, and how it moves on as items are finished."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
import pianove  # noqa: E402,F401
import pianove.context as ctx  # noqa: E402
from pianove import session  # noqa: E402
from pianove.state import storage  # noqa: E402


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "_path", tmp_path / "storage.json")
    monkeypatch.setattr(storage, "_data", {"completed_lessons": ["welcome"]})
    opened = []
    router = SimpleNamespace(active_page_name="home",
                             navigate=lambda page, *a, **k: opened.append(page),
                             refresh=lambda: opened.append("refresh"))
    monkeypatch.setattr(ctx, "router", router)
    monkeypatch.setattr(ctx, "practice_mode", False)
    monkeypatch.setattr(ctx, "current_song_id", None)
    monkeypatch.setattr(session, "song_in_progress", lambda: None)
    yield opened


def test_plan_without_a_song():
    items = session.plan()
    kinds = [it["kind"] for it in items]
    assert kinds[0] == "sight" and items[0]["notes"] == 8        # a short warm-up first
    assert "lesson" in kinds                                     # the next lesson
    assert items[[i for i, k in enumerate(kinds) if k == "lesson"][0]]["id"] == "c_major_scale"
    assert session.minutes(items) > 0


def test_session_moves_on_only_when_the_open_item_finishes(fresh):
    session.start()
    assert session.position() == (1, len(session._state()["items"]))
    assert ctx.practice_mode is True and fresh[-1] == "lesson"   # the warm-up opened
    session.finish_current()
    assert session.current()["kind"] == "lesson"
    session.finish_current()                                     # the lesson isn't open yet
    assert session.current()["kind"] == "lesson"
    session.launch_next()
    assert ctx.practice_mode is False and ctx.current_lesson_id == "c_major_scale"
    session.finish_current()
    assert session.current()["kind"] == "sight"


def test_the_session_is_for_today_only():
    session.start()
    st = storage.get("session")
    st["day"] = "2000-01-01"
    storage.set("session", st)
    assert not session.active() and session.current() is None


def test_last_activity():
    session.note_activity("song", "abc")
    assert session.last_activity()["id"] == "abc"

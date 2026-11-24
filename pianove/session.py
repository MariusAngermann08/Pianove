"""Today's session: what to practise, decided for you.

One tap on Home starts a short plan built from where you are: a warm-up of fresh
sight-reading, your next lesson, the next step of the song you're learning, and (for a
longer daily goal) a little more sight-reading. Each item opens like it would from its
own tab; its finish screen offers the next item instead of the usual "next" button.

    items = plan()          # what today's session would be
    start()                 # begin it (opens the first item)
    current(), position()   # where it stands
    finish_current()        # called by a finish screen (idempotent)
    launch_next()           # the finish screen's "Next in today's session"

The plan is kept for the day in storage["session"], so leaving and coming back (or
restarting the app) continues it.
"""
from __future__ import annotations

from datetime import date

import pianove.context as ctx

_KEY = "session"


# ── what is due ─────────────────────────────────────────────────────────────────

def last_activity() -> dict | None:
    from pianove.state import storage
    return storage.get("last_activity")


def note_activity(kind: str, item_id: str):
    """Remember what was opened last (a lesson or a song), for Home's "Continue"."""
    from pianove.state import storage
    rec = {"kind": kind, "id": item_id, "day": date.today().isoformat()}
    if storage.get("last_activity") != rec:
        storage.set("last_activity", rec)


def next_lesson() -> tuple[dict, dict, int] | None:
    """(lesson, course, index in course) of the next unfinished lesson, suggested course first."""
    from pianove import recommend
    from pianove.lesson_loader import list_courses, load_lesson
    from pianove.progress import is_complete
    for course in recommend.ordered_courses(list_courses()):
        for i, lid in enumerate(course["lessons"]):
            if not is_complete(lid):
                lesson = load_lesson(lid)
                if lesson:
                    return lesson, course, i
    return None


def song_in_progress() -> tuple[dict, dict] | None:
    """(song, next step) of the song you're learning: the last one opened if its path isn't
    finished, else any song with a path started and not finished."""
    from pianove import song_path
    from pianove.song_store import get_song, list_songs
    last = last_activity()
    order = []
    if last and last.get("kind") == "song":
        order.append(last["id"])
    order += [s["id"] for s in list_songs() if s["id"] not in order]
    for sid in order:
        song = get_song(sid)
        if not song:
            continue
        try:
            path = song_path.build_path(sid)
        except Exception:
            continue
        steps = path["steps"] if path else []
        if not steps:
            continue
        done = song_path.progress(sid)
        started = any(st["id"] in done for st in steps) or (last and last.get("id") == sid)
        i = song_path.next_step(path, done)
        if started and i < len(steps):
            return song, steps[i]
    return None


def learned_songs() -> list[dict]:
    """Songs whose whole learning path is done: the pieces you can play."""
    from pianove import song_path
    from pianove.song_store import list_songs
    out = []
    for s in list_songs():
        try:
            steps = song_path.build_path(s["id"])["steps"]
        except Exception:
            continue
        done = song_path.progress(s["id"])
        if steps and all(st["id"] in done for st in steps):
            out.append(s)
    return out


# ── the plan ────────────────────────────────────────────────────────────────────

def _sight(notes: int, warm_up: bool) -> dict:
    from pianove import recommend
    return {"kind": "sight", "notes": notes, "level": recommend.practice_level(),
            "label": "session_warmup" if warm_up else "session_sight", "minutes": 2 if warm_up else 3}


def plan() -> list[dict]:
    from pianove.progress import daily_goal_minutes
    goal = daily_goal_minutes()
    items = [_sight(8, True)]
    nl = next_lesson()
    if nl:
        lesson, course, i = nl
        items.append({"kind": "lesson", "id": lesson["id"], "course": course["id"], "index": i,
                      "title": lesson["title"], "label": "session_lesson",
                      "minutes": int(lesson.get("meta", {}).get("estimated_minutes") or 6)})
    sp = song_in_progress()
    if sp:
        song, step = sp
        key, fmt = step["title"]
        items.append({"kind": "song", "id": song["id"], "step": step["id"],
                      "title": song.get("title", ""), "step_title": [key, fmt],
                      "label": "session_song", "minutes": 4})
    if goal >= 15 or len(items) < 3:
        items.append(_sight(16, False))
    return items


def minutes(items: list[dict]) -> int:
    return sum(int(it.get("minutes", 3)) for it in items)


def _state() -> dict | None:
    from pianove.state import storage
    st = storage.get(_KEY)
    if not st or st.get("day") != date.today().isoformat():
        return None
    return st


def _save(st: dict | None):
    from pianove.state import storage
    if st is None:
        storage.remove(_KEY)
    else:
        storage.set(_KEY, st)


def active() -> bool:
    st = _state()
    return bool(st) and st["i"] < len(st["items"])


def finished_today() -> bool:
    st = _state()
    return bool(st) and st["i"] >= len(st["items"])


def position() -> tuple[int, int]:
    """(1-based number of the current item, how many there are)."""
    st = _state()
    if not st:
        return 0, 0
    return min(st["i"] + 1, len(st["items"])), len(st["items"])


def current() -> dict | None:
    st = _state()
    if not st or st["i"] >= len(st["items"]):
        return None
    return st["items"][st["i"]]


def upcoming() -> dict | None:
    """The item after the current one (what a finish screen offers next)."""
    st = _state()
    if not st or st["i"] + 1 >= len(st["items"]):
        return None
    return st["items"][st["i"] + 1]


def is_current_open() -> bool:
    """Whether the page now open is today's current session item."""
    it = current()
    if not it:
        return False
    if it["kind"] == "sight":
        return bool(ctx.practice_mode)
    if it["kind"] == "lesson":
        return not ctx.practice_mode and not ctx.current_song_id and ctx.current_lesson_id == it["id"]
    return ctx.current_song_id == it["id"] and ctx.path_step == it["step"]


def finish_current():
    """The open item is done: move the session on (only once per item)."""
    st = _state()
    if st and st["i"] < len(st["items"]) and is_current_open():
        st["i"] += 1
        _save(st)


def start():
    st = {"day": date.today().isoformat(), "items": plan(), "i": 0}
    _save(st)
    launch(current())


def stop():
    _save(None)


def launch(item: dict | None):
    if not item:
        ctx.router.navigate("home", "left")
        return
    ctx.lesson_test_return = None
    ctx.session_done_marker = None        # a new item: its finish screen counts again
    if item["kind"] == "sight":
        from pianove.home.tab_practice import start_sight_reading
        start_sight_reading({"clef": "treble", "difficulty": item.get("level", "beginner"),
                             "key": "C", "notes": item["notes"], "bpm": 70})
    elif item["kind"] == "lesson":
        ctx.practice_mode = False
        ctx.current_song_id = None
        ctx.path_step = ctx.song_range = None
        ctx.current_lesson_id = item["id"]
        ctx.current_course_id = item["course"]
        ctx.current_course_index = item["index"]
        ctx.lesson_step_idx = ctx.lesson_current_idx = ctx.lesson_section_idx = 0
        ctx.lesson_completed = False
        ctx.lesson_phase = "practice"
        _open_lesson_page()
    else:
        from pianove import song_path
        from pianove.pages.lesson import start_path_step
        path = song_path.build_path(item["id"]) or {"steps": []}
        step = next((s for s in path["steps"] if s["id"] == item["step"]), None)
        if step is None:                       # the song changed: skip it
            st = _state()
            if st:
                st["i"] += 1
                _save(st)
            launch(current())
            return
        ctx.practice_mode = False
        ctx.current_song_id = item["id"]
        start_path_step(step)
        _open_lesson_page()


def _open_lesson_page():
    if ctx.router.active_page_name == "lesson":   # from a finish screen: build it anew
        ctx.router.refresh()
    else:
        ctx.router.navigate("lesson", "right")


def launch_next():
    launch(current())


def describe(item: dict) -> str:
    """One line for an item, in the app's language."""
    from pianove.i18n import t
    if item["kind"] == "sight":
        return t(item["label"], n=item["notes"])
    if item["kind"] == "lesson":
        return t(item["label"], title=item["title"])
    key, fmt = item["step_title"]
    return t(item["label"], title=item["title"], step=t(key, **fmt))

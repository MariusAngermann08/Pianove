import atexit
import time
from datetime import date, timedelta
from pianove.state import storage

# ── Practice time ────────────────────────────────────────────────────────────────
# Counted from the keys you play while a lesson, song or sight-reading session is open:
# the time between two notes counts when it is under _IDLE_GAP (a pause to think or to
# read counts; a page left open while you make tea does not). Kept per day in
# storage["practice_log"] = {"2026-11-23": seconds, …}.
_IDLE_GAP     = 20.0     # seconds without a note after which the clock stops
_FLUSH_EVERY  = 15.0     # write to storage at least this often (seconds of practice)
_ACTIVE_DAY_S = 60.0     # a day with at least this much practice keeps the streak
GOAL_OPTIONS  = [5, 10, 15, 20, 30, 45, 60]   # minutes; storage["daily_goal_minutes"]
_clock = {"last": None, "pending": 0.0}


def note_played(now: float | None = None):
    """Called for every key played while practising (lesson, song, sight-reading)."""
    now = time.monotonic() if now is None else now
    last = _clock["last"]
    if last is not None and 0 < now - last < _IDLE_GAP:
        _clock["pending"] += now - last
    _clock["last"] = now
    if _clock["pending"] >= _FLUSH_EVERY:
        flush_practice_time()


def stop_clock():
    """The practice page was left: the next note starts a fresh stretch."""
    flush_practice_time()
    _clock["last"] = None


def flush_practice_time():
    secs = _clock["pending"]
    if secs <= 0:
        return
    _clock["pending"] = 0.0
    add_practice_seconds(secs)


def add_practice_seconds(secs: float, day: date | None = None):
    key = (day or date.today()).isoformat()
    log = dict(storage.get("practice_log", {}))
    log[key] = round(float(log.get(key, 0.0)) + float(secs), 1)
    storage.set("practice_log", log)


atexit.register(flush_practice_time)


def practice_log() -> dict[str, float]:
    log = dict(storage.get("practice_log", {}))
    if _clock["pending"] > 0:                       # not yet written: still counts
        key = date.today().isoformat()
        log[key] = log.get(key, 0.0) + _clock["pending"]
    return log


def minutes_today() -> int:
    return int(practice_log().get(date.today().isoformat(), 0.0) // 60)


def total_practice_minutes() -> int:
    """Everything practised; an older storage's "total_minutes" is kept as a base."""
    return int(sum(practice_log().values()) // 60) + int(storage.get("total_minutes", 0) or 0)


def recent_minutes(days: int = 7) -> list[tuple[date, float]]:
    """(day, minutes practised) for the last `days` days, today last."""
    log   = practice_log()
    today = date.today()
    return [(d, round(log.get(d.isoformat(), 0.0) / 60, 1))
            for d in (today - timedelta(days=days - 1 - i) for i in range(days))]


def daily_goal_minutes() -> int:
    try:
        return int(storage.get("daily_goal_minutes", 10))
    except (TypeError, ValueError):
        return 10


def set_daily_goal_minutes(minutes: int):
    storage.set("daily_goal_minutes", int(minutes))


def active_days() -> set[str]:
    """Days you practised: a lesson finished, a song step or a sight-reading session
    played, or at least a minute at the keys."""
    days = set(storage.get("lesson_dates", []))
    days |= set(storage.get("activity_dates", []))
    days |= {s.get("date") for s in storage.get("practice_sessions", []) if s.get("date")}
    days |= {d for d, secs in practice_log().items() if secs >= _ACTIVE_DAY_S}
    return days


def record_activity(day: date | None = None):
    """A song step or other practice finished today (lessons use record_session)."""
    key = (day or date.today()).isoformat()
    dates = list(storage.get("activity_dates", []))
    if key not in dates:
        dates.append(key)
        storage.set("activity_dates", dates)


def completed_lessons() -> set[str]:
    return set(storage.get("completed_lessons", []))


def mark_complete(lesson_id: str):
    done = list(completed_lessons())
    if lesson_id not in done:
        done.append(lesson_id)
        storage.set("completed_lessons", done)


def is_complete(lesson_id: str) -> bool:
    return lesson_id in completed_lessons()


def lessons_completed_count() -> int:
    return len(completed_lessons())


def record_session(lesson_id: str):
    dates = storage.get("lesson_dates", [])
    dates.append(date.today().isoformat())
    storage.set("lesson_dates", dates)


def streak() -> int:
    dates = active_days()
    if not dates:
        return 0
    today = date.today()
    # Count consecutive days ending today; fall back to yesterday if nothing today
    for start in [today, today - timedelta(days=1)]:
        count = 0
        d = start
        while d.isoformat() in dates:
            count += 1
            d -= timedelta(days=1)
        if count:
            return count
    return 0


def weekly_lessons() -> list[float]:
    dates_raw = storage.get("lesson_dates", [])
    today     = date.today()
    monday    = today - timedelta(days=today.weekday())
    return [float(dates_raw.count((monday + timedelta(days=i)).isoformat())) for i in range(7)]


def record_practice_session(accuracy: float, note_count: int, bpm: int):
    sessions = storage.get("practice_sessions", [])
    sessions.append({
        "date":     date.today().isoformat(),
        "accuracy": round(accuracy, 4),
        "notes":    note_count,
        "bpm":      bpm,
    })
    storage.set("practice_sessions", sessions)


def practice_sessions() -> list[dict]:
    return storage.get("practice_sessions", [])


def practice_sessions_total() -> int:
    return len(practice_sessions())


def practice_accuracy_avg(last_n: int = 10) -> float:
    sessions = practice_sessions()
    if not sessions:
        return 0.0
    recent = sessions[-last_n:]
    return sum(s["accuracy"] for s in recent) / len(recent)


def weekly_practice_sessions() -> list[float]:
    sessions = practice_sessions()
    today  = date.today()
    monday = today - timedelta(days=today.weekday())
    counts = [0.0] * 7
    for s in sessions:
        try:
            d = date.fromisoformat(s["date"])
            day_idx = (d - monday).days
            if 0 <= day_idx < 7:
                counts[day_idx] += 1.0
        except (ValueError, KeyError):
            pass
    return counts


def course_complete(course_id: str) -> bool:
    from pianove.lesson_loader import list_courses
    done = completed_lessons()
    for c in list_courses():
        if c["id"] == course_id:
            return all(lid in done for lid in c["lessons"])
    return False

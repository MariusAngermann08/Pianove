from datetime import date, timedelta
from pianove.state import storage


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
    dates = set(storage.get("lesson_dates", []))
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

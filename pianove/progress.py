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
    """Append today's date to lesson_dates (used for streak + weekly chart)."""
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
    """Lessons completed per day for the current Mon–Sun week."""
    dates_raw = storage.get("lesson_dates", [])
    today     = date.today()
    monday    = today - timedelta(days=today.weekday())
    return [float(dates_raw.count((monday + timedelta(days=i)).isoformat())) for i in range(7)]


def course_complete(course_id: str) -> bool:
    from pianove.lesson_loader import list_courses
    done = completed_lessons()
    for c in list_courses():
        if c["id"] == course_id:
            return all(lid in done for lid in c["lessons"])
    return False

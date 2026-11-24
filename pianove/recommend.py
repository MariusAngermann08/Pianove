"""What the answer to "How much have you played piano so far?" changes: the course the
app suggests first, the level sight-reading practice starts at, and whether Home points
you at your own pieces."""
from __future__ import annotations

_COURSE = {"none": "beginner_path", "basics": "beginner_path",
           "simple": "melody_explorer", "advanced": "melody_explorer"}
_LEVEL = {"none": "beginner", "basics": "beginner",
          "simple": "intermediate", "advanced": "advanced"}


def experience() -> str:
    from pianove.state import experience_state
    return str(experience_state.value or "none")


def course_id() -> str:
    return _COURSE.get(experience(), "beginner_path")


def practice_level() -> str:
    return _LEVEL.get(experience(), "beginner")


def suggests_songs() -> bool:
    """Players who can already play pieces are pointed at the Songs tab too."""
    return experience() in ("simple", "advanced")


def ordered_courses(courses: list[dict]) -> list[dict]:
    """The suggested course first, the rest in their usual order."""
    first = course_id()
    return sorted(courses, key=lambda c: c["id"] != first)

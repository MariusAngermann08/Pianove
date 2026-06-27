import json
from pathlib import Path

_BUILTIN_LESSONS = Path(__file__).parent / "lessons"
_BUILTIN_COURSES = Path(__file__).parent / "courses"
_USER_LESSONS    = Path.home() / ".pianove" / "packages" / "lessons"
_USER_COURSES    = Path.home() / ".pianove" / "packages" / "courses"


def _read_json(path: Path) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _locale_str(bundle_dir: Path, key: str) -> str:
    from pianove.i18n import language_state
    for lang in [language_state.value, "en"]:
        lf = bundle_dir / f"{lang}.json"
        if lf.exists():
            data = _read_json(lf)
            if key in data:
                return data[key]
    return key


def _scan_dirs(builtin: Path, user: Path) -> dict[str, Path]:
    dirs: dict[str, Path] = {}
    for base in [builtin, user]:
        if not base.exists():
            continue
        for d in sorted(base.iterdir()):
            if d.is_dir() and (d / "meta.json").exists():
                dirs[d.name] = d  # user shadows built-in by same name
    return dirs


def _lesson_info(d: Path) -> dict:
    meta = _read_json(d / "meta.json")
    return {
        "id":          meta["id"],
        "path":        d,
        "meta":        meta,
        "title":       _locale_str(d, "title"),
        "description": _locale_str(d, "description"),
    }


def list_lessons() -> list[dict]:
    return [_lesson_info(d) for d in _scan_dirs(_BUILTIN_LESSONS, _USER_LESSONS).values()]


def list_courses() -> list[dict]:
    result = []
    for d in _scan_dirs(_BUILTIN_COURSES, _USER_COURSES).values():
        meta = _read_json(d / "meta.json")
        result.append({
            "id":          meta["id"],
            "path":        d,
            "meta":        meta,
            "title":       _locale_str(d, "title"),
            "description": _locale_str(d, "description"),
            "lessons":     meta.get("lessons", []),
        })
    return result


def load_lesson(lesson_id: str) -> dict | None:
    dirs = _scan_dirs(_BUILTIN_LESSONS, _USER_LESSONS)
    d = dirs.get(lesson_id)
    if d is None:
        return None
    info = _lesson_info(d)
    info["steps"] = _read_json(d / "steps.json")
    return info


def standalone_lessons() -> list[dict]:
    in_courses: set[str] = set()
    for course in list_courses():
        in_courses.update(course["lessons"])
    return [l for l in list_lessons() if l["id"] not in in_courses]

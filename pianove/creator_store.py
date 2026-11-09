"""Lessons and courses made in the app: the user's own folders in ~/.pianove/packages.

The lesson loader already scans these folders, so whatever is saved here shows up in the
Lessons tab straight away. Built-in lessons are never changed: to edit one, duplicate it
first (it gets a new id, so its progress stays separate).

A lesson being edited is a "draft": {"id", "meta", "strings": {lang: {...}}, "steps"}.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unicodedata
import zipfile
from pathlib import Path

from pianove import lesson_loader as _ll
from pianove import exercise_format as ef
from pianove.creator_notes import parse_chord, parse_note, in_range, split_words

LOCALES = ("en", "de")
DIFFICULTIES = ("beginner", "intermediate", "advanced")
CLEFS = ("treble", "bass", "grand")
PKG_EXT = ".pianove-pkg"
ID_RE = re.compile(r"^[a-z0-9_]{1,64}$")
COPY_SUFFIX = {"en": " (copy)", "de": " (Kopie)"}

_MAX_PKG_BYTES = 20 * 1024 * 1024
_MANIFEST = "pianove-package.json"


class PackageError(Exception):
    """A package that can't be imported; `code` names why (for a translated message)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


# ── where things live (read from lesson_loader, so tests can point it elsewhere) ──────

def _user_lessons() -> Path:
    return _ll._USER_LESSONS


def _user_courses() -> Path:
    return _ll._USER_COURSES


def _builtin_lessons() -> Path:
    return _ll._BUILTIN_LESSONS


def _builtin_courses() -> Path:
    return _ll._BUILTIN_COURSES


def is_own_lesson(lesson_id: str) -> bool:
    return (_user_lessons() / lesson_id / "meta.json").exists()


def is_builtin_lesson(lesson_id: str) -> bool:
    return (_builtin_lessons() / lesson_id / "meta.json").exists()


def is_own_course(course_id: str) -> bool:
    return (_user_courses() / course_id / "meta.json").exists()


# ── files ─────────────────────────────────────────────────────────────────────────────

def _read_json(path: Path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def dumps(obj, indent: int = 0, width: int = 92) -> str:
    """JSON the way the built-in lessons are written: short lists and objects on one
    line (a bar of notes, a translated text), longer ones spread over several."""
    flat = json.dumps(obj, ensure_ascii=False, separators=(", ", ": "))
    if not isinstance(obj, (list, dict)) or not obj or len(flat) + indent <= width:
        return flat
    pad, inner = " " * indent, " " * (indent + 2)
    if isinstance(obj, list):
        items = [inner + dumps(v, indent + 2, width) for v in obj]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    items = [inner + json.dumps(k, ensure_ascii=False) + ": " + dumps(v, indent + 2, width)
             for k, v in obj.items()]
    return "{\n" + ",\n".join(items) + "\n" + pad + "}"


def _write_json(path: Path, data) -> None:
    """Write to a temporary file next to the target, then rename it into place: a crash
    halfway never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(dumps(data) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── ids ───────────────────────────────────────────────────────────────────────────────

def slugify(title: str, fallback: str = "lesson") -> str:
    s = str(title).replace("ß", "ss")
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40].strip("_")
    return s or fallback


def _lesson_taken(i: str) -> bool:
    return is_own_lesson(i) or is_builtin_lesson(i)


def _course_taken(i: str) -> bool:
    return is_own_course(i) or (_builtin_courses() / i / "meta.json").exists()


def unique_id(base: str, taken) -> str:
    if not taken(base):
        return base
    n = 2
    while taken(f"{base}_{n}"):
        n += 1
    return f"{base}_{n}"


# ── lessons ───────────────────────────────────────────────────────────────────────────

def _starter_steps(title: str) -> list:
    return [
        {
            "type": "scene",
            "title": {lang: title for lang in LOCALES},
            "beats": [{
                "title": {"en": "Listen", "de": "Hör zu"},
                "say": {"en": "", "de": ""},
                "play": ["C4", "D4", "E4"],
                "tempo": 76,
                "try": "play",
            }],
        },
        {"type": "exercise", "time": [4, 4], "bars": [["C4", "D4", "E4", "F4"]]},
    ]


def new_lesson(title: str, author: str = "") -> str:
    """Create a lesson folder with a first scene and exercise; returns its id."""
    title = str(title).strip() or "Untitled lesson"
    lesson_id = unique_id(slugify(title), _lesson_taken)
    draft = {
        "id": lesson_id,
        "meta": {
            "id": lesson_id,
            "version": "1.0.0",
            "author": str(author).strip(),
            "difficulty": "beginner",
            "tags": [],
            "locales": list(LOCALES),
            "estimated_minutes": 5,
        },
        "strings": {lang: {"title": title, "description": ""} for lang in LOCALES},
        "steps": _starter_steps(title),
    }
    save_draft(draft)
    return lesson_id


def load_draft(lesson_id: str) -> dict:
    """An own lesson, ready to edit. Built-in lessons are duplicated first."""
    d = _user_lessons() / lesson_id
    meta = _read_json(d / "meta.json")
    if not isinstance(meta, dict):
        raise KeyError(lesson_id)
    strings = {}
    langs = list(dict.fromkeys(list(meta.get("locales") or []) + list(LOCALES)))
    for lang in langs:
        data = _read_json(d / f"{lang}.json", {})
        strings[lang] = data if isinstance(data, dict) else {}
    steps = _read_json(d / "steps.json", [])
    return {"id": lesson_id, "meta": meta, "strings": strings,
            "steps": steps if isinstance(steps, list) else []}


def save_draft(draft: dict) -> None:
    lesson_id = draft["id"]
    if not ID_RE.match(lesson_id):
        raise ValueError(f"bad lesson id: {lesson_id!r}")
    d = _user_lessons() / lesson_id
    meta = dict(draft["meta"])
    meta["id"] = lesson_id
    _write_json(d / "meta.json", meta)
    for lang, data in draft.get("strings", {}).items():
        if not re.match(r"^[a-z]{2,3}$", lang):
            continue
        old = _read_json(d / f"{lang}.json", {})
        merged = {**(old if isinstance(old, dict) else {}), **data}
        if merged or lang in (meta.get("locales") or []):
            _write_json(d / f"{lang}.json", merged)
    _write_json(d / "steps.json", draft.get("steps", []))


def duplicate_lesson(lesson_id: str, author: str = "") -> str:
    """Copy any lesson (built-in or own) under a new id; returns the new id."""
    src = _ll._scan_dirs(_builtin_lessons(), _user_lessons()).get(lesson_id)
    if src is None:
        raise KeyError(lesson_id)
    new_id = unique_id(f"{lesson_id}_copy", _lesson_taken)
    dst = _user_lessons() / new_id
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    meta = _read_json(dst / "meta.json", {})
    meta["id"] = new_id
    meta["based_on"] = lesson_id
    if author:
        meta["author"] = str(author).strip()
    _write_json(dst / "meta.json", meta)
    for lang, suffix in COPY_SUFFIX.items():
        f = dst / f"{lang}.json"
        data = _read_json(f)
        if isinstance(data, dict) and data.get("title"):
            data["title"] = data["title"] + suffix
            _write_json(f, data)
    return new_id


def delete_lesson(lesson_id: str) -> bool:
    if not ID_RE.match(lesson_id) or not is_own_lesson(lesson_id):
        return False
    shutil.rmtree(_user_lessons() / lesson_id)
    return True


def _info_with_mtime(d: Path) -> dict | None:
    try:
        info = _ll._lesson_info(d)
    except (OSError, ValueError, KeyError):
        return None
    try:
        info["mtime"] = max(p.stat().st_mtime for p in d.iterdir())
    except (OSError, ValueError):
        info["mtime"] = 0.0
    return info


def list_own_lessons() -> list[dict]:
    base = _user_lessons()
    if not base.exists():
        return []
    out = []
    for d in base.iterdir():
        if d.is_dir() and (d / "meta.json").exists():
            info = _info_with_mtime(d)
            if info:
                info["replaces_builtin"] = is_builtin_lesson(d.name)
                steps = _read_json(d / "steps.json", [])
                info["n_steps"] = len(steps) if isinstance(steps, list) else 0
                out.append(info)
    out.sort(key=lambda i: -i["mtime"])
    return out


def list_builtin_lessons() -> list[dict]:
    base = _builtin_lessons()
    out = [_ll._lesson_info(d) for d in sorted(base.iterdir())
           if d.is_dir() and (d / "meta.json").exists()] if base.exists() else []
    return sorted(out, key=lambda i: i["title"].lower())


# ── courses ───────────────────────────────────────────────────────────────────────────

def new_course(title: str, author: str = "") -> str:
    title = str(title).strip() or "Untitled course"
    course_id = unique_id(slugify(title, "course"), _course_taken)
    save_course({
        "id": course_id,
        "meta": {"id": course_id, "version": "1.0.0", "author": str(author).strip(),
                 "difficulty": "beginner", "lessons": []},
        "strings": {lang: {"title": title, "description": ""} for lang in LOCALES},
    })
    return course_id


def load_course(course_id: str) -> dict:
    d = _user_courses() / course_id
    meta = _read_json(d / "meta.json")
    if not isinstance(meta, dict):
        raise KeyError(course_id)
    meta.setdefault("lessons", [])
    strings = {}
    for lang in LOCALES:
        data = _read_json(d / f"{lang}.json", {})
        strings[lang] = data if isinstance(data, dict) else {}
    return {"id": course_id, "meta": meta, "strings": strings}


def save_course(draft: dict) -> None:
    course_id = draft["id"]
    if not ID_RE.match(course_id):
        raise ValueError(f"bad course id: {course_id!r}")
    d = _user_courses() / course_id
    meta = dict(draft["meta"])
    meta["id"] = course_id
    meta["lessons"] = [str(x) for x in meta.get("lessons", [])]
    _write_json(d / "meta.json", meta)
    for lang, data in draft.get("strings", {}).items():
        old = _read_json(d / f"{lang}.json", {})
        _write_json(d / f"{lang}.json", {**(old if isinstance(old, dict) else {}), **data})


def delete_course(course_id: str) -> bool:
    if not ID_RE.match(course_id) or not is_own_course(course_id):
        return False
    shutil.rmtree(_user_courses() / course_id)
    return True


def list_own_courses() -> list[dict]:
    base = _user_courses()
    if not base.exists():
        return []
    out = []
    for d in base.iterdir():
        if d.is_dir() and (d / "meta.json").exists():
            meta = _read_json(d / "meta.json", {})
            out.append({
                "id": d.name, "path": d, "meta": meta,
                "title": _ll._locale_str(d, "title"),
                "lessons": list(meta.get("lessons", [])),
                "mtime": (d / "meta.json").stat().st_mtime,
            })
    out.sort(key=lambda c: -c["mtime"])
    return out


# ── checking a lesson ─────────────────────────────────────────────────────────────────
# A problem is (where, code, args): where is ("lesson",), ("step", i), ("beat", i, j) or
# ("bar", i, k); the editor shows code as a translated sentence. Problems never stop a
# save (a half-done lesson is a normal draft), they are shown so they get fixed.

def _text(v, lang: str) -> str:
    if isinstance(v, dict):
        return str(v.get(lang) or "").strip()
    return str(v or "").strip()


def _check_notes(problems, where, values, chords_ok=True):
    for v in values:
        midis = parse_chord(v) if chords_ok else ([parse_note(v)] if parse_note(v) is not None else None)
        if midis is None:                     # (a chord where one key belongs is a bad note too)
            problems.append((where, "bad_note", {"note": str(v)}))
        elif any(not in_range(m) for m in midis):
            problems.append((where, "out_of_range", {"note": str(v)}))


def validate(draft: dict) -> list[tuple]:
    problems: list[tuple] = []
    meta = draft.get("meta", {})
    langs = [lang for lang in (meta.get("locales") or LOCALES)]
    strings = draft.get("strings", {})
    for lang in langs:
        if not str(strings.get(lang, {}).get("title") or "").strip():
            problems.append((("lesson",), "missing_title", {"lang": lang.upper()}))

    steps = draft.get("steps", [])
    if not steps:
        problems.append((("lesson",), "no_steps", {}))
    elif steps[-1].get("type") != "exercise":
        problems.append((("lesson",), "last_not_exercise", {}))

    for i, step in enumerate(steps):
        kind = step.get("type")
        if kind == "scene":
            beats = step.get("beats", [])
            if not beats:
                problems.append((("step", i), "no_beats", {}))
            for j, b in enumerate(beats):
                w = ("beat", i, j)
                for field in ("say", "try_say"):
                    vals = {lang: _text(b.get(field), lang) for lang in langs}
                    if any(vals.values()):
                        for lang, v in vals.items():
                            if not v:
                                problems.append((w, f"missing_{field}", {"lang": lang.upper()}))
                if not any(_text(b.get("say"), lang) for lang in langs):
                    problems.append((w, "empty_say", {}))
                play = b.get("play", [])
                _check_notes(problems, w, play)
                tr = b.get("try")
                if isinstance(tr, list):
                    _check_notes(problems, w, tr)
                elif tr == "play" and not play:
                    problems.append((w, "try_without_play", {}))
                _check_notes(problems, w, b.get("mark", []), chords_ok=False)
                if isinstance(b.get("labels"), list):
                    _check_notes(problems, w, b["labels"], chords_ok=False)
                for side, fm in (b.get("hand") or {}).items():
                    _check_notes(problems, w, list(fm or {}), chords_ok=False)
                    if any(str(f) not in ("1", "2", "3", "4", "5") for f in (fm or {}).values()):
                        problems.append((w, "bad_finger", {}))
                if b.get("fingers") is not None and len(b["fingers"]) != len(play):
                    problems.append((w, "fingers_mismatch", {}))
                tempo = b.get("tempo", 76)
                if not isinstance(tempo, (int, float)) or not 20 <= tempo <= 240:
                    problems.append((w, "bad_tempo", {}))
                st = b.get("staff")
                if st:
                    if st.get("clef", "treble") not in CLEFS:
                        problems.append((w, "bad_clef", {}))
                    if not -7 <= int(st.get("key", 0)) <= 7:
                        problems.append((w, "bad_key", {}))
                    if not st.get("notes"):
                        problems.append((w, "empty_staff", {}))
                    _check_notes(problems, w, st.get("notes", []))
        elif kind == "exercise":
            w = ("step", i)
            time = step.get("time", [4, 4])
            ok_time = (isinstance(time, list) and len(time) == 2
                       and all(isinstance(x, int) for x in time)
                       and 1 <= time[0] <= 12 and time[1] in (2, 4, 8))
            if not ok_time:
                problems.append((w, "bad_time", {}))
            bars = step.get("bars", [])
            if not bars:
                problems.append((w, "no_bars", {}))
            if step.get("clef", "treble") not in ("treble", "bass"):
                problems.append((w, "bad_clef", {}))
            typed = "types" in step
            if typed and not ef.has_types(step):
                problems.append((w, "bad_types", {}))
                typed = False
            types = ef.types_of(step)
            for k, bar in enumerate(bars):
                wb = ("bar", i, k)
                if not bar:
                    problems.append((wb, "empty_bar", {"bar": k + 1}))
                elif ok_time and typed and ef.used(types[k]) > ef.bar_length(time) + 1e-6:
                    problems.append((wb, "bar_too_full", {"bar": k + 1}))
                elif ok_time and not typed and len(bar) > time[0] * 4:
                    problems.append((wb, "bar_too_full", {"bar": k + 1}))
                _check_notes(problems, wb, [e for e in bar if not ef.is_rest(e)])
        else:
            problems.append((("step", i), "unknown_step", {"type": str(kind)}))
    return problems


# ── packages (.pianove-pkg: a zip with lessons/<id>/ and courses/<id>/ folders) ───────

def export_package(kind: str, item_id: str, dest_dir) -> Path:
    """Zip an own lesson, or an own course with the own lessons it lists (built-in
    lessons are on every install already). Returns the package's path."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    folders: list[tuple[str, Path]] = []
    if kind == "lesson":
        if not is_own_lesson(item_id):
            raise KeyError(item_id)
        folders.append((f"lessons/{item_id}", _user_lessons() / item_id))
    elif kind == "course":
        if not is_own_course(item_id):
            raise KeyError(item_id)
        folders.append((f"courses/{item_id}", _user_courses() / item_id))
        for lid in load_course(item_id)["meta"].get("lessons", []):
            if is_own_lesson(lid):
                folders.append((f"lessons/{lid}", _user_lessons() / lid))
    else:
        raise ValueError(kind)

    out = dest_dir / f"{item_id}{PKG_EXT}"
    fd, tmp = tempfile.mkstemp(dir=dest_dir, suffix=".tmp")
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(_MANIFEST, json.dumps({"format": 1, "kind": kind, "id": item_id}))
            for arc_base, folder in folders:
                for f in sorted(folder.rglob("*")):
                    if f.is_file() and not f.name.startswith("."):
                        zf.write(f, f"{arc_base}/{f.relative_to(folder).as_posix()}")
        os.replace(tmp, out)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return out


def _package_groups(names: list[str]) -> dict[tuple[str, str], str]:
    """(kind, id) → the folder prefix inside the zip, for every lesson or course in it.
    Reads three layouts: lessons/<id>/ and courses/<id>/ (what Pianove writes), a single
    <id>/ folder, or a folder's files at the zip's root."""
    groups: dict[tuple[str, str], str] = {}
    for n in names:
        parts = n.split("/")
        if len(parts) >= 3 and parts[0] in ("lessons", "courses") and parts[2] == "meta.json":
            groups[(parts[0][:-1], parts[1])] = f"{parts[0]}/{parts[1]}/"
    if groups:
        return groups
    metas = [n for n in names if n.endswith("meta.json")]
    if "meta.json" in metas:
        return {("?", ""): ""}
    tops = {n.split("/")[0] for n in metas if n.count("/") == 1}
    if len(tops) == 1:
        top = tops.pop()
        return {("?", top): f"{top}/"}
    raise PackageError("no_lesson")


def import_package(path) -> dict:
    """Install a package into the user's folders. Lessons or courses with the same id as
    an own one are replaced (a newer version of it); returns what was installed."""
    try:
        zf = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as e:
        raise PackageError("not_a_package", str(e))
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if sum(i.file_size for i in infos) > _MAX_PKG_BYTES:
            raise PackageError("too_big")
        names = []
        for i in infos:
            n = i.filename.replace("\\", "/")
            if n.startswith("/") or ".." in n.split("/") or ":" in n:
                raise PackageError("unsafe_path", n)
            names.append(n)
        groups = _package_groups([n for n in names if n != _MANIFEST])

        result = {"lessons": [], "courses": [], "replaced_builtin": []}
        staged: list[tuple[str, str, Path]] = []
        with tempfile.TemporaryDirectory() as tmp:
            for (kind, gid), prefix in groups.items():
                meta = json.loads(zf.read(prefix + "meta.json").decode("utf-8"))
                if not isinstance(meta, dict):
                    raise PackageError("bad_meta", prefix)
                item_id = str(meta.get("id") or gid)
                if kind == "?":
                    kind = "course" if isinstance(meta.get("lessons"), list) else "lesson"
                if not ID_RE.match(item_id) or (gid and gid != item_id):
                    raise PackageError("bad_id", item_id)
                if kind == "lesson" and prefix + "steps.json" not in names:
                    raise PackageError("no_steps", item_id)
                stage = Path(tmp) / kind / item_id
                for n in names:
                    if n.startswith(prefix) and n != prefix:
                        target = stage / n[len(prefix):]
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(zf.read(n))
                staged.append((kind, item_id, stage))

            # each staged folder is complete: move them into place
            for kind, item_id, stage in staged:
                base = _user_lessons() if kind == "lesson" else _user_courses()
                base.mkdir(parents=True, exist_ok=True)
                dst = base / item_id
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.move(str(stage), str(dst))
                result["lessons" if kind == "lesson" else "courses"].append(item_id)
                if kind == "lesson" and is_builtin_lesson(item_id):
                    result["replaced_builtin"].append(item_id)
    return result


# ── an exercise from a MusicXML file ──────────────────────────────────────────────────

def exercise_from_musicxml(path, hand: str = "right") -> dict:
    """{"time", "bars", "types"} of one hand of a piece, with its note values, rests and
    chords. A tied note keeps its first part (an exercise has no ties)."""
    from pianove.song_store import _parse_musicxml
    parsed = _parse_musicxml(str(path))
    h = "lh" if hand == "left" else "rh"
    time = parsed.get("time") or [4, 4]
    time = [int(time[0]), int(time[1])]
    full = ef.bar_length(time)
    pitch_bars = parsed.get(f"bars_{h}") or []
    type_bars = parsed.get(f"types_{h}") or []
    onset_bars = parsed.get(f"onsets_{h}") or []
    tie_bars = parsed.get(f"ties_{h}") or []
    bars, types = [], []
    for i, bar in enumerate(pitch_bars):
        n = len(bar)
        tys = type_bars[i] if i < len(type_bars) and len(type_bars[i]) == n else ["quarter"] * n
        ons = onset_bars[i] if i < len(onset_bars) and len(onset_bars[i]) == n else [float(k) for k in range(n)]
        ties = tie_bars[i] if i < len(tie_bars) and len(tie_bars[i]) == n else [False] * n
        groups: dict[float, tuple[list[str], str]] = {}
        for p, t, o, tied in zip(bar, tys, ons, ties):
            if tied:
                continue                          # a tie's second half isn't struck again
            t = t if ef.is_type(t) else "quarter"
            ps, t0 = groups.setdefault(round(float(o), 4), ([], t))
            if p not in ps:
                ps.append(p)
        entries, values, pos = [], [], 0.0
        starts = sorted(groups)
        for k, o in enumerate(starts):
            if o > pos + 1e-6:                    # silence before this note: rests
                for r in ef.fill_rests(o - pos):
                    entries.append(ef.REST)
                    values.append(r)
            ps, t = groups[o]
            room = (starts[k + 1] if k + 1 < len(starts) else full) - o
            if ef.quarters(t) > room + 1e-6:      # overlaps the next note (another voice)
                fit = ef.fill_rests(room)
                t = fit[0] if fit else t
            entries.append("+".join(ps))
            values.append(t)
            pos = o + ef.quarters(t)
        if not entries and full:
            entries, values = [ef.REST] * len(ef.fill_rests(full)), ef.fill_rests(full)
        bars.append(entries)
        types.append(values)
    # no silent bars at the start or the end
    def silent(b):
        return all(ef.is_rest(e) for e in b)
    while bars and silent(bars[0]):
        bars.pop(0), types.pop(0)
    while bars and silent(bars[-1]):
        bars.pop(), types.pop()
    return {"time": time, "bars": bars, "types": types}


def notes_from_text(text: str) -> list[str]:
    return split_words(text)

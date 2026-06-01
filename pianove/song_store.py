"""
Song store — import MusicXML files, persist metadata + extracted bars,
serve bars back to the lesson engine.

Storage layout:
  ~/.pianove/songs/
    index.json          ← list of song metadata dicts
    files/<id>.xml      ← copied MusicXML source
"""

import os
import json
import shutil
import uuid
import xml.etree.ElementTree as ET

_STORE_DIR  = os.path.expanduser("~/.pianove/songs")
_FILES_DIR  = os.path.join(_STORE_DIR, "files")
_INDEX_FILE = os.path.join(_STORE_DIR, "index.json")

# Difficulty heuristic thresholds (avg notes/bar after range weighting)
_DIFF_EASY   = 3.5
_DIFF_MEDIUM = 6.0

# MusicXML type name → beat duration (in quarter-note units)
_TYPE_BEATS = {
    "whole": 4.0, "half": 2.0, "quarter": 1.0,
    "eighth": 0.5, "16th": 0.25,
    "dotted-whole": 6.0, "dotted-half": 3.0, "dotted-quarter": 1.5,
    "dotted-eighth": 0.75,
}


# ────────────────────────────────────────────── helpers

def _ensure_dirs():
    os.makedirs(_FILES_DIR, exist_ok=True)


def _load_index() -> list[dict]:
    if not os.path.exists(_INDEX_FILE):
        return []
    try:
        with open(_INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_index(index: list[dict]):
    _ensure_dirs()
    with open(_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


# ────────────────────────────────────────────── XML parsing

def _tag(el):
    import re
    return re.sub(r'\{[^}]+\}', '', el.tag)


def _find(el, tag):
    for child in el:
        if _tag(child) == tag:
            return child
    return None


def _findall(el, tag):
    return [c for c in el if _tag(c) == tag]


def _text(el, tag, default=None):
    child = _find(el, tag)
    return child.text.strip() if (child is not None and child.text) else default


_FIFTHS_TO_KEY = {
    0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#",
    -1: "F", -2: "Bb", -3: "Eb", -4: "Ab", -5: "Db", -6: "Gb", -7: "Cb",
}

_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

def _pitch_to_midi(pitch: str) -> int:
    name = pitch[0].upper()
    rest = pitch[1:]
    acc = 0
    if rest and rest[0] == "#":
        acc, rest = 1, rest[1:]
    elif rest and rest[0] == "b":
        acc, rest = -1, rest[1:]
    return (int(rest) + 1) * 12 + _SEMITONES[name] + acc


def _parse_musicxml(filepath: str) -> dict:
    """
    Parse MusicXML and return:
      {
        title, composer,
        key, time,
        bars_rh: list[list[str]],   # treble staff pitch strings per bar
        bars_lh: list[list[str]],   # bass staff pitch strings per bar
      }
    """
    import zipfile, re

    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".mxl":
        with zipfile.ZipFile(filepath) as zf:
            xml_path = None
            if "META-INF/container.xml" in zf.namelist():
                container = ET.parse(zf.open("META-INF/container.xml")).getroot()
                for el in container.iter():
                    if _tag(el) == "rootfile":
                        xml_path = el.get("full-path")
                        break
            if xml_path is None:
                for name in sorted(zf.namelist()):
                    if name.endswith(".xml") and "META-INF" not in name:
                        xml_path = name
                        break
            root = ET.parse(zf.open(xml_path)).getroot()
    else:
        root = ET.parse(filepath).getroot()

    # Navigate to score-partwise
    if _tag(root) != "score-partwise":
        for el in root.iter():
            if _tag(el) == "score-partwise":
                root = el
                break

    # Metadata
    work_el  = _find(root, "work")
    id_el    = _find(root, "identification")
    title    = (_text(work_el, "work-title") or _text(root, "movement-title") or "Untitled")
    composer = ""
    if id_el is not None:
        for c in _findall(id_el, "creator"):
            if c.get("type", "").lower() == "composer" and c.text:
                composer = c.text.strip()
                break

    # First part only
    parts    = [el for el in root.iter() if _tag(el) == "part"]
    part     = parts[0]
    measures = _findall(part, "measure")

    # Attributes from first measure
    first_attrs = _find(measures[0], "attributes")
    key  = "C"
    time = (4, 4)
    n_staves = 1
    if first_attrs is not None:
        key_el = _find(first_attrs, "key")
        if key_el is not None:
            try:
                fifths = int(_text(key_el, "fifths", "0"))
                key = _FIFTHS_TO_KEY.get(fifths, "C")
            except (ValueError, TypeError):
                pass
        time_el = _find(first_attrs, "time")
        if time_el is not None:
            try:
                time = (int(_text(time_el, "beats", "4")),
                        int(_text(time_el, "beat-type", "4")))
            except (ValueError, TypeError):
                pass
        staves_el = _find(first_attrs, "staves")
        if staves_el is not None:
            try:
                n_staves = int(staves_el.text)
            except (ValueError, TypeError):
                pass

    # Determine primary voice per staff (first voice encountered)
    primary_voice: dict[int, str] = {}

    bars_rh: list[list[str]] = []
    bars_lh: list[list[str]] = []

    for measure in measures:
        bar_rh: list[str] = []
        bar_lh: list[str] = []

        for note_el in _findall(measure, "note"):
            if _find(note_el, "grace") is not None:
                continue
            if _find(note_el, "chord") is not None:
                continue
            if _find(note_el, "time-modification") is not None:
                continue
            if _find(note_el, "rest") is not None:
                continue

            ntype_el = _find(note_el, "type")
            if ntype_el is None or ntype_el.text not in (
                "whole", "half", "quarter", "eighth", "16th"
            ):
                continue

            staff_idx = 0
            try:
                staff_idx = int(_text(note_el, "staff", "1")) - 1
            except (ValueError, TypeError):
                pass

            voice = _text(note_el, "voice", "1")
            if staff_idx not in primary_voice:
                primary_voice[staff_idx] = voice
            elif voice != primary_voice[staff_idx]:
                continue

            pitch_el = _find(note_el, "pitch")
            if pitch_el is None:
                continue
            step   = _text(pitch_el, "step", "C")
            octave = _text(pitch_el, "octave", "4")
            try:
                alter = float(_text(pitch_el, "alter", "0"))
            except (ValueError, TypeError):
                alter = 0.0
            acc   = "#" if alter >= 0.5 else ("b" if alter <= -0.5 else "")
            pitch = f"{step}{acc}{octave}"

            if staff_idx == 0:
                bar_rh.append(pitch)
            else:
                bar_lh.append(pitch)

        bars_rh.append(bar_rh)
        bars_lh.append(bar_lh)

    return {
        "title":    title,
        "composer": composer,
        "key":      key,
        "time":     list(time),
        "bars_rh":  bars_rh,
        "bars_lh":  bars_lh,
    }


# ────────────────────────────────────────────── difficulty

def _compute_difficulty(bars_rh: list[list[str]], bars_lh: list[list[str]]) -> str:
    all_notes = [p for bar in bars_rh + bars_lh for p in bar]
    if not all_notes:
        return "beginner"
    avg_per_bar = len(all_notes) / max(1, len(bars_rh))
    midis = [_pitch_to_midi(p) for p in all_notes]
    pitch_range = (max(midis) - min(midis)) / 12.0
    score = avg_per_bar * (1 + pitch_range * 0.15)
    if score < _DIFF_EASY:
        return "beginner"
    elif score < _DIFF_MEDIUM:
        return "intermediate"
    return "advanced"


# ────────────────────────────────────────────── public API

def list_songs() -> list[dict]:
    """Return list of song metadata dicts (id, title, composer, difficulty, n_bars)."""
    return _load_index()


def import_song(filepath: str) -> dict:
    """
    Parse a MusicXML file, copy it into the store, and append to the index.
    Returns the new song metadata dict.
    Raises ValueError on parse errors.
    """
    _ensure_dirs()
    parsed = _parse_musicxml(filepath)

    song_id  = str(uuid.uuid4())[:8]
    dest_ext = os.path.splitext(filepath)[1].lower() or ".xml"
    dest     = os.path.join(_FILES_DIR, f"{song_id}{dest_ext}")
    shutil.copy2(filepath, dest)

    difficulty = _compute_difficulty(parsed["bars_rh"], parsed["bars_lh"])
    n_bars     = len(parsed["bars_rh"])

    entry = {
        "id":         song_id,
        "title":      parsed["title"],
        "composer":   parsed["composer"],
        "key":        parsed["key"],
        "time":       parsed["time"],
        "difficulty": difficulty,
        "n_bars":     n_bars,
        "filepath":   dest,
        "bars_rh":    parsed["bars_rh"],
        "bars_lh":    parsed["bars_lh"],
    }

    index = _load_index()
    index.append(entry)
    _save_index(index)
    return entry


def delete_song(song_id: str):
    """Remove a song from the index and delete its file."""
    index = _load_index()
    entry = next((s for s in index if s["id"] == song_id), None)
    if entry and os.path.exists(entry.get("filepath", "")):
        try:
            os.remove(entry["filepath"])
        except OSError:
            pass
    _save_index([s for s in index if s["id"] != song_id])


def get_song(song_id: str) -> dict | None:
    """Return a single song entry or None."""
    return next((s for s in _load_index() if s["id"] == song_id), None)


def get_song_bars(song_id: str, hand: str = "right") -> list[list[str]]:
    """
    Return bars as list[list[str]] for the lesson engine.
      hand="right" → treble staff only
      hand="left"  → bass staff only
      hand="both"  → treble + bass notes concatenated per bar
    """
    song = get_song(song_id)
    if song is None:
        return [["C4", "D4", "E4", "F4"]]

    bars_rh = song.get("bars_rh", [])
    bars_lh = song.get("bars_lh", [])

    if hand == "left":
        return [bar for bar in bars_lh if bar]

    if hand == "both":
        combined = []
        for i in range(len(bars_rh)):
            rh = bars_rh[i] if i < len(bars_rh) else []
            lh = bars_lh[i] if i < len(bars_lh) else []
            merged = rh + lh
            if merged:
                combined.append(merged)
        return combined if combined else bars_rh

    # default: right hand
    return [bar for bar in bars_rh if bar]

"""Note names for the lesson editor: reading and writing "C4", "F#4", "Bb3" and chords
like "C4+E4+G4", grouping keys struck together into chords, and cutting a run of notes
into bars."""
from __future__ import annotations

import re

_NOTE_RE = re.compile(r"^([A-Ga-g])(#|b)?(-?\d)$")
_SEMIS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

LOWEST, HIGHEST = 21, 108          # A0 .. C8, the keys of a piano
CHORD_WINDOW = 0.04                # keys struck this close together (s) make one chord


def parse_note(text: str) -> int | None:
    """MIDI number of a single note name, or None if it isn't one."""
    m = _NOTE_RE.match(str(text).strip())
    if not m:
        return None
    letter, acc, octave = m.groups()
    midi = (int(octave) + 1) * 12 + _SEMIS[letter.upper()] + (1 if acc == "#" else -1 if acc == "b" else 0)
    return midi if 0 <= midi <= 127 else None


def parse_chord(text: str) -> list[int] | None:
    """MIDI numbers of "C4" or "C4+E4+G4", or None if any part isn't a note."""
    parts = [p.strip() for p in str(text).split("+")]
    if not parts or any(not p for p in parts):
        return None
    out = [parse_note(p) for p in parts]
    return None if any(m is None for m in out) else out


def note_name(midi: int, flats: bool = False) -> str:
    names = _FLATS if flats else _SHARPS
    return f"{names[midi % 12]}{midi // 12 - 1}"


def chord_name(midis, flats: bool = False) -> str:
    return "+".join(note_name(m, flats) for m in sorted(set(midis)))


def in_range(midi: int) -> bool:
    return LOWEST <= midi <= HIGHEST


def group_chords(events, window: float = CHORD_WINDOW) -> list[list[int]]:
    """Key presses [(time, midi), ...] in order → chords: each key joins the chord of the
    first key struck no more than `window` seconds before it."""
    out: list[list[int]] = []
    start = None
    for t, m in events:
        if out and start is not None and t - start <= window:
            if m not in out[-1]:
                out[-1].append(m)
        else:
            out.append([m])
            start = t
    return [sorted(c) for c in out]


def split_bars(notes: list[str], per_bar: int) -> list[list[str]]:
    """A run of notes cut into bars of `per_bar` notes (the last may be shorter)."""
    per_bar = max(1, int(per_bar))
    return [notes[i:i + per_bar] for i in range(0, len(notes), per_bar)]


def split_words(text: str) -> list[str]:
    """Notes typed into a field: separated by spaces or commas."""
    return [w for w in re.split(r"[\s,]+", str(text).strip()) if w]

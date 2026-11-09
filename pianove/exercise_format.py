"""An exercise's music: bars of notes, rests, chords, ties and triplets, for one hand or
both.

    {"type": "exercise", "time": [3, 4], "clef": "treble", "tempo": 90,
     "bars":  [["E4~", "E4", "G4"], ["C4+E4", "r"]],
     "types": [["quarter", "quarter", "quarter"], ["half", "quarter"]],
     "lh":    {"bars": [["C3"], ["G2"]], "types": [["dotted_half"], ["dotted_half"]]}}

- "r" is a rest, "C4+E4" a chord, "E4~" a note tied to the same note in the next entry.
- A value is whole … thirty_second, "dotted_…" (×1.5) or "triplet_…" (×2/3; three
  triplet eighths take one quarter).
- `types` is optional: without it (lessons written before it existed) a bar's notes share
  the bar evenly, as they always have.
- `lh` is the left hand on a bass staff: the exercise then shows a grand staff.
- `tempo` is in quarter notes per minute.
"""
from __future__ import annotations

from pianove.creator_notes import parse_note

REST = "r"
TIE = "~"
DEFAULT_TEMPO = 80
_Q = {"whole": 4.0, "half": 2.0, "quarter": 1.0, "eighth": 0.5, "sixteenth": 0.25,
      "thirty_second": 0.125}
# rests that fill a gap, longest first
_FILL = [("whole", 4.0), ("half", 2.0), ("quarter", 1.0), ("eighth", 0.5), ("sixteenth", 0.25),
         ("thirty_second", 0.125)]


# ── entries ───────────────────────────────────────────────────────────────────────────

def is_rest(entry) -> bool:
    return str(entry).strip().lower() in ("r", "rest")


def notes_of(entry) -> list[tuple[str, bool]]:
    """(pitch, tied to the next entry) for each note of an entry: "C4~+E4" → [("C4", True),
    ("E4", False)]."""
    if is_rest(entry):
        return []
    out = []
    for p in str(entry).split("+"):
        p = p.strip()
        if p:
            out.append((p.rstrip(TIE).strip(), p.endswith(TIE)))
    return out


def join_notes(notes) -> str:
    return "+".join(p + (TIE if tied else "") for p, tied in notes)


def pitches_of(entry) -> list[str]:
    return [p for p, _ in notes_of(entry)]


# ── values ────────────────────────────────────────────────────────────────────────────

def is_type(t) -> bool:
    t = str(t)
    if t.startswith("triplet_"):
        return t[8:] in _Q
    return t.replace("dotted_", "", 1) in _Q


def is_triplet(t: str) -> bool:
    return str(t).startswith("triplet_")


def written(t: str) -> str:
    """The value as written on the staff (a triplet eighth is drawn as an eighth)."""
    return t[8:] if is_triplet(t) else t


def quarters(t: str) -> float:
    """Length of a value in quarter notes ("dotted_half" → 3, "triplet_eighth" → 1/3)."""
    if is_triplet(t):
        return _Q[t[8:]] * 2 / 3
    base = t.replace("dotted_", "", 1)
    return _Q[base] * (1.5 if t.startswith("dotted_") else 1.0)


def bar_length(time) -> float:
    """Length of a bar in quarter notes: 4 in 4/4, 3 in 6/8."""
    return time[0] * 4 / time[1]


def even_type(n: int, beats: int) -> str:
    """The value a bar's n notes get when nothing says how long they are (the way exercise
    bars have always been played: n ≤ beats → quarters, then eighths, then sixteenths)."""
    if n <= beats:
        return "quarter"
    if n <= beats * 2:
        return "eighth"
    return "sixteenth"


def used(types: list[str]) -> float:
    return sum(quarters(t) for t in types)


def fill_rests(gap: float) -> list[str]:
    """Rest values that fill a gap of `gap` quarter notes."""
    out = []
    for name, q in _FILL:
        while gap >= q - 1e-6:
            out.append(name)
            gap -= q
    return out


# ── an exercise ───────────────────────────────────────────────────────────────────────

def time_of(step: dict) -> list:
    tm = step.get("time") or [4, 4]
    try:
        tm = [int(tm[0]), int(tm[1])]
    except (TypeError, ValueError, IndexError):
        tm = [4, 4]
    return tm if tm[0] > 0 and tm[1] > 0 else [4, 4]


def tempo_of(step: dict) -> int:
    try:
        return max(20, min(240, int(step.get("tempo") or DEFAULT_TEMPO)))
    except (TypeError, ValueError):
        return DEFAULT_TEMPO


def has_lh(step: dict) -> bool:
    return isinstance(step.get("lh"), dict)


def _types_valid(bars, types) -> bool:
    return (isinstance(types, list) and len(types) == len(bars)
            and all(isinstance(t, list) and len(t) == len(b) and all(is_type(x) for x in t)
                    for t, b in zip(types, bars)))


def _types_for(bars, types, beats) -> list[list[str]]:
    if _types_valid(bars, types):
        return [list(t) for t in types]
    return [[even_type(len(b), beats)] * len(b) for b in bars]


def has_types(step: dict) -> bool:
    return _types_valid(step.get("bars") or [], step.get("types"))


def types_of(step: dict) -> list[list[str]]:
    """A value for every entry of every bar (right hand / single staff): the stored ones,
    or even ones."""
    return _types_for(step.get("bars") or [], step.get("types"), time_of(step)[0])


def parts(step: dict) -> list[tuple[list, list]]:
    """(bars, types) of each staff: the right hand (or the only staff), then the left."""
    beats = time_of(step)[0]
    out = [(step.get("bars") or [], types_of(step))]
    if has_lh(step):
        lh = step["lh"]
        bars = lh.get("bars") or []
        out.append((bars, _types_for(bars, lh.get("types"), beats)))
    return out


def staff_music(bars: list, types: list) -> dict:
    """One staff as the lesson player reads a piece, per bar: every sounding note (a
    chord's notes share their start; rests are the gaps) with its written value, where it
    starts (quarters from the bar's start), how long it sounds (a tie adds the notes it
    continues), whether it only continues a tie (drawn, not struck again) and whether it
    is a triplet note."""
    out = {k: [] for k in ("pitches", "types", "onsets", "durs", "ties", "trip")}
    open_ties: dict[int, tuple[int, int]] = {}      # midi → (bar, index) of the struck note
    for b, (bar, tys) in enumerate(zip(bars, types)):
        row = {k: [] for k in out}
        pos = 0.0
        for entry, t in zip(bar, tys):
            d = quarters(t)
            still_open: dict[int, tuple[int, int]] = {}
            for p, tied in notes_of(entry):
                m = parse_note(p)
                src = open_ties.get(m) if m is not None else None
                row["pitches"].append(p)
                row["types"].append(written(t))
                row["onsets"].append(round(pos, 6))
                row["durs"].append(round(d, 6))
                row["ties"].append(src is not None)
                row["trip"].append(is_triplet(t))
                if src is not None:                   # sounds on: the struck note lasts longer
                    sb, si = src
                    target = row["durs"] if sb == b else out["durs"][sb]
                    target[si] = round(target[si] + d, 6)
                here = (b, len(row["pitches"]) - 1)
                if tied and m is not None:
                    still_open[m] = src or here
            open_ties = still_open                    # a tie only reaches the next entry
            pos += d
        for k in out:
            out[k].append(row[k])
    return out


def music(step: dict, staff: int = 0):
    """(pitches, written types, onsets) per bar of one staff."""
    ps = parts(step)
    if staff >= len(ps):
        return [], [], []
    m = staff_music(*ps[staff])
    return m["pitches"], m["types"], m["onsets"]

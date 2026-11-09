"""An exercise's music: bars of notes, rests and chords, and how long each one lasts.

    {"type": "exercise", "time": [3, 4], "clef": "treble",
     "bars":  [["E4", "G4", "G4"], ["C4+E4", "r"]],
     "types": [["quarter", "quarter", "quarter"], ["half", "quarter"]]}

"r" is a rest and "C4+E4" a chord. `types` is optional: without it (lessons written
before it existed) a bar's notes share the bar evenly, as they always have.
"""
from __future__ import annotations

REST = "r"
BASES = ["whole", "half", "quarter", "eighth", "sixteenth", "thirty_second"]
_Q = {"whole": 4.0, "half": 2.0, "quarter": 1.0, "eighth": 0.5, "sixteenth": 0.25,
      "thirty_second": 0.125}
# rests that fill a gap, longest first
_FILL = [("whole", 4.0), ("half", 2.0), ("quarter", 1.0), ("eighth", 0.5), ("sixteenth", 0.25),
         ("thirty_second", 0.125)]


def is_rest(entry) -> bool:
    return str(entry).strip().lower() in ("r", "rest")


def is_type(t) -> bool:
    t = str(t)
    return t.replace("dotted_", "", 1) in _Q


def quarters(t: str) -> float:
    """Length of a note value in quarter notes ("dotted_half" → 3)."""
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


def time_of(step: dict) -> list:
    tm = step.get("time") or [4, 4]
    try:
        tm = [int(tm[0]), int(tm[1])]
    except (TypeError, ValueError, IndexError):
        tm = [4, 4]
    return tm if tm[0] > 0 and tm[1] > 0 else [4, 4]


def has_types(step: dict) -> bool:
    types, bars = step.get("types"), step.get("bars") or []
    return (isinstance(types, list) and len(types) == len(bars)
            and all(isinstance(t, list) and len(t) == len(b) and all(is_type(x) for x in t)
                    for t, b in zip(types, bars)))


def types_of(step: dict) -> list[list[str]]:
    """A note value for every entry of every bar: the stored ones, or even ones."""
    bars = step.get("bars") or []
    if has_types(step):
        return [list(t) for t in step["types"]]
    beats = time_of(step)[0]
    return [[even_type(len(b), beats)] * len(b) for b in bars]


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


def music(step: dict):
    """(pitches, types, onsets) per bar, as the lesson player reads a piece: one entry per
    sounding note (a chord's notes share their start), rests left out (they are the
    gaps), onsets in quarter notes from the start of the bar."""
    pitches, types, onsets = [], [], []
    for bar, tys in zip(step.get("bars") or [], types_of(step)):
        bp, bt, bo, pos = [], [], [], 0.0
        for entry, t in zip(bar, tys):
            if not is_rest(entry):
                for p in str(entry).split("+"):
                    p = p.strip()
                    if p:
                        bp.append(p)
                        bt.append(t)
                        bo.append(round(pos, 4))
            pos += quarters(t)
        pitches.append(bp)
        types.append(bt)
        onsets.append(bo)
    return pitches, types, onsets

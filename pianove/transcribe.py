"""Writing down what was played: key presses (with the time they were struck and let go)
against a metronome become bars of an exercise, with note values, rests, chords, ties
over bar lines and triplets.

Notes are placed on a grid of sixteenths; a beat whose notes sit clearly better on
thirds of the beat is written as a triplet. A note lasts until the next one starts, or
until it was let go if that is a good deal earlier (then a rest follows).
"""
from __future__ import annotations

from pianove import exercise_format as ef
from pianove.creator_notes import note_name

CHORD = 0.12          # beats: keys struck this close together make a chord
_STRAIGHT = 0.25      # the straight grid: sixteenths (in beats)
_VALUES = [("whole", 4.0), ("dotted_half", 3.0), ("half", 2.0), ("dotted_quarter", 1.5),
           ("quarter", 1.0), ("dotted_eighth", 0.75), ("eighth", 0.5), ("sixteenth", 0.25)]
_TRIP = [("triplet_half", 4 / 3), ("triplet_quarter", 2 / 3), ("triplet_eighth", 1 / 3)]


def _snap(x: float, step: float) -> float:
    return round(x / step) * step


def _beat_grid(onsets: list[float]) -> dict[int, str]:
    """Per beat: "trip" when its notes sit clearly better on thirds than on sixteenths."""
    by_beat: dict[int, list[float]] = {}
    for x in onsets:
        by_beat.setdefault(int(x + 1e-6 + 0.0625), []).append(x)
    out = {}
    for b, xs in by_beat.items():
        inner = [x - b for x in xs if abs(x - round(x)) > 0.09]     # notes off the beat itself
        if not inner:
            continue
        err_s = sum(abs(x - _snap(x, _STRAIGHT)) for x in inner)
        err_t = sum(abs(x - _snap(x, 1 / 3)) for x in inner)
        if err_t + 0.04 * len(inner) < err_s * 0.6:
            out[b] = "trip"
    return out


def _split(length: float, trip: bool) -> list[str]:
    """Values that add up to `length` beats (tied together when there are several)."""
    if trip:
        for name, q in _TRIP:
            if abs(length - q) < 1e-3:
                return [name]
        out, left = [], length
        for name, q in _TRIP:
            while left >= q - 1e-3:
                out.append(name)
                left -= q
        if left > 1e-3:
            out.extend(_split(left, False))
        return out
    out, left = [], length
    for name, q in _VALUES:
        while left >= q - 1e-6:
            out.append(name)
            left -= q
    return out


def _rest_values(length: float) -> list[str]:
    out = []
    for name, q in _VALUES:
        if "dotted" in name:
            continue
        while length >= q - 1e-6:
            out.append(name)
            length -= q
    return out


def quantize(presses, bpm: float, time=(4, 4), start: float = 0.0):
    """presses: [(struck s, let go s or None, midi)], times since `start` is beat 0.
    Returns (bars, types) of an exercise staff."""
    beat_s = 60.0 / bpm
    bar_q = ef.bar_length(time)
    raw = sorted(((t - start) / beat_s, (off - start) / beat_s if off is not None else None, m)
                 for t, off, m in presses if t >= start - beat_s * 0.25)
    if not raw:
        return [], []
    # chords: keys struck together
    groups: list[dict] = []
    for on, off, m in raw:
        if groups and on - groups[-1]["on"] <= CHORD:
            g = groups[-1]
            if m not in g["notes"]:
                g["notes"].append(m)
            if off is not None:
                g["off"] = max(g["off"] or off, off)
        else:
            groups.append({"on": max(0.0, on), "off": off, "notes": [m]})
    trip_beats = _beat_grid([g["on"] for g in groups])

    def place(x):
        b = int(x + 1e-6 + 0.0625)
        return _snap(x, 1 / 3) if trip_beats.get(b) else _snap(x, _STRAIGHT)

    for g in groups:
        g["q"] = place(g["on"])
    # two notes on one grid point: the later one moves to the next
    for a, b in zip(groups, groups[1:]):
        if b["q"] <= a["q"] + 1e-6:
            b["q"] = a["q"] + (1 / 3 if trip_beats.get(int(a["q"] + 1e-6)) else _STRAIGHT)
    # how long each lasts: to the next note, or to its release when that is clearly earlier
    timeline = []                  # (start, length, notes or None for a rest)
    for i, g in enumerate(groups):
        nxt = groups[i + 1]["q"] if i + 1 < len(groups) else None
        end = nxt
        if g["off"] is not None:
            rel = max(g["q"] + _STRAIGHT, place(g["off"]))
            if end is None or rel < end - 0.4:
                end = rel
        if end is None:
            end = g["q"] + 1.0
        if nxt is None:                   # the last note (often still held at Done): whole beats
            end = g["q"] + max(1.0, round(end - g["q"]))
        timeline.append((g["q"], end - g["q"], sorted(g["notes"])))
        if nxt is not None and end < nxt - 1e-6:
            timeline.append((end, nxt - end, None))
    if timeline[0][0] > 1e-6:
        timeline.insert(0, (0.0, timeline[0][0], None))
    total = timeline[-1][0] + timeline[-1][1]
    n_bars = max(1, int(-(-total // bar_q)))
    # into bars: a note over a bar line is split and tied
    bars: list[list[str]] = [[] for _ in range(n_bars)]
    types: list[list[str]] = [[] for _ in range(n_bars)]
    for st, ln, notes in timeline:
        pos, left = st, ln
        while left > 1e-6:
            k = int(pos / bar_q + 1e-9)
            room = (k + 1) * bar_q - pos
            piece = min(left, room)
            trip = bool(trip_beats.get(int(pos + 1e-6))) and abs(piece * 3 - round(piece * 3)) < 1e-3 \
                and abs(piece * 4 - round(piece * 4)) > 1e-3
            vals = _split(piece, trip) if notes else _rest_values(piece)
            for vi, v in enumerate(vals):
                last_piece = left - piece <= 1e-6 and vi == len(vals) - 1
                if notes:
                    tied = not last_piece
                    bars[k].append(ef.join_notes([(note_name(m), tied) for m in notes]))
                else:
                    bars[k].append(ef.REST)
                types[k].append(v)
            pos += piece
            left -= piece
    # the last bar: no rests trailing after the music
    while bars and bars[-1] and ef.is_rest(bars[-1][-1]):
        bars[-1].pop()
        types[-1].pop()
    return bars, types


def split_hands(presses, split: int = 60):
    """Presses below middle C go to the left hand, the rest to the right."""
    right = [p for p in presses if p[2] >= split]
    left = [p for p in presses if p[2] < split]
    return right, left

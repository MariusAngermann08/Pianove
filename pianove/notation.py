"""Small notation helpers shared by the lesson player and the exercise editor: grouping
triplet notes under a bracket, and linking tied notes so PyLute draws the tie."""
from __future__ import annotations

# three triplet notes fill one of these (written length in quarters): 3 sixteenths, 3
# eighths, 3 quarters, 3 halves
_COMPLETE = (0.75, 1.5, 3.0, 6.0)


def _written_q(ev) -> float:
    from pylute.durations import get_value
    t = getattr(ev, "type", None)
    if t is None and getattr(ev, "notes", None):
        t = ev.notes[0].type
    try:
        return get_value(t) * 4
    except KeyError:
        return 0.0


def group_tuplets(bar_obj, staff) -> None:
    """Runs of events marked _trip (notes, chords or rests) become PyLute Tuplets of 3:2
    once their written lengths add up to three of a value; an unfinished run stays as it
    is. Each tuplet takes the room its members took."""
    from pylute.tuplet import Tuplet
    out, run, w = [], [], 0.0

    def flush(complete: bool):
        nonlocal run, w
        if complete and len(run) > 1:
            tup = Tuplet(run, 3, 2, staff=staff)
            tup._layout_dur = sum(getattr(e, "_layout_dur", None) or _written_q(e) / 4 * 2 / 3
                                  for e in run)
            out.append(tup)
        else:
            out.extend(run)
        run, w = [], 0.0

    for ev in bar_obj.events:
        if getattr(ev, "_trip", False):
            run.append(ev)
            w += _written_q(ev)
            if any(abs(w - c) < 1e-6 for c in _COMPLETE):
                flush(True)
            elif w > 6.0:
                flush(False)
        else:
            flush(False)
            out.append(ev)
    flush(False)
    bar_obj.events[:] = out


def link_tie(src_note, note) -> None:
    """Draw a tie from src_note to note (both PyLute Notes)."""
    src_note.tied_to = note
    note.tied_from = True

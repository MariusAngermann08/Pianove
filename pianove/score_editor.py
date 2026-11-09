"""A score editor for an exercise, in the manner of MuseScore's note input.

ScoreModel is the editing (no drawing, so it can be tested): one or two staves, a
selection, a note value to enter with, and operations that keep bars from overflowing
(what doesn't fit moves on to the next bar). ScoreCanvas draws the exercise with PyLute,
the same notation the lesson player shows, and turns clicks, drags and keys into model
operations.

Keys (with the score clicked): A–G enter a note, Shift+A–G add it to the chord, 3–7 pick
a value (sixteenth … whole, as in MuseScore), "." a dot, Ctrl+3 triplets, 0 a rest, T or
+ a tie, ↑/↓ a semitone, Ctrl+↑/↓ an octave, Alt+↑/↓ the other staff, ←/→ move, Delete
removes, Ctrl+Z / Ctrl+Y undo and redo, Space plays. A note dragged up or down moves
along the staff. A MIDI keyboard or the keys on screen enter notes too; keys pressed
together make a chord.
"""
from __future__ import annotations

import copy
import re
import time as _time

import pygame
from pylay import PygameCanvas, iOSTheme, ColorPalette
from pylay.core.element import UIElement
from pylay.core import _dirty

from pianove import exercise_format as ef
from pianove.creator_notes import parse_note, note_name, in_range, CHORD_WINDOW

VALUES = ["whole", "half", "quarter", "eighth", "sixteenth"]
_LETTERS = "CDEFGAB"
_LETTER_PC = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
_KEY_VALUE = {pygame.K_3: "sixteenth", pygame.K_4: "eighth", pygame.K_5: "quarter",
              pygame.K_6: "half", pygame.K_7: "whole",
              pygame.K_KP3: "sixteenth", pygame.K_KP4: "eighth", pygame.K_KP5: "quarter",
              pygame.K_KP6: "half", pygame.K_KP7: "whole"}
_BLUE = (10, 132, 255)
_PLAYING = (40, 170, 90)
_SG = 9                      # PyLute: gap between the staves of a system, in staff spaces
_PITCH_RE = re.compile(r"^([A-Ga-g])(#|b)?(-?\d)$")


def _room(quarters: float) -> float:
    """How much room (in PyLute's whole-note units) an entry gets: less than its length
    for long notes and more for short ones, as engravers space music, so a run of short
    notes stays readable."""
    return max(quarters, 1e-3) ** 0.6 / 4


def _sort_notes(notes):
    return sorted(notes, key=lambda n: parse_note(n[0]) or 0)


def key_spelling(key: int) -> dict:
    """Letter → accidental a key signature gives it (2 → {"F": "#", "C": "#"})."""
    if key > 0:
        return {n: "#" for n in "FCGDAEB"[:key]}
    if key < 0:
        return {n: "b" for n in "BEADGCF"[:-key]}
    return {}


def shift_step(pitch: str, steps: int, key: int = 0) -> str | None:
    """A pitch moved `steps` lines-and-spaces up the staff, spelled in the key."""
    m = _PITCH_RE.match(pitch.strip())
    if not m:
        return None
    letter, _, octave = m.groups()
    idx = int(octave) * 7 + _LETTERS.index(letter.upper()) + steps
    new_letter, new_oct = _LETTERS[idx % 7], idx // 7
    out = f"{new_letter}{key_spelling(key).get(new_letter, '')}{new_oct}"
    midi = parse_note(out)
    return out if midi is not None and in_range(midi) else None


# ── the editing ───────────────────────────────────────────────────────────────────────

class ScoreModel:
    """Edits an exercise step in place. staff: 0 (right hand, or the only staff) or 1 (left
    hand). sel = (bar, index) in that staff: the selected entry, or index -1 for the start
    of the bar. New notes go in after the selection."""

    def __init__(self, step: dict, on_change=None):
        self.step = step
        step.setdefault("bars", [])
        self._types = [ef.types_of(step)]
        if ef.has_lh(step):
            self._types.append(ef.parts(step)[1][1])
        self.staff = 0
        self.sel: tuple[int, int] = (0, len(step["bars"][0]) - 1) if step["bars"] else (0, -1)
        self.value = "quarter"
        self.dot = False
        self.triplet = False
        self.chord = False            # the next note entered joins the selected chord
        self.on_change = on_change
        self._undo: list = []
        self._redo: list = []
        self._last_entry = -1.0       # when a note was last entered (for chords from MIDI)
        self._drag = None
        # the selection is the note just entered: a value picked now is for the next notes
        # (as in MuseScore's note input); a note picked by a click or an arrow takes it
        self.entering = False
        self.version = 0

    # ── state ──
    @property
    def n_staves(self) -> int:
        return 2 if ef.has_lh(self.step) else 1

    def staff_bars(self, s: int) -> list:
        return self.step["bars"] if s == 0 else self.step["lh"].setdefault("bars", [])

    def staff_types(self, s: int) -> list:
        return self._types[s]

    @property
    def bars(self) -> list:
        return self.staff_bars(self.staff)

    @property
    def types(self) -> list:
        return self._types[self.staff]

    @property
    def time(self) -> list:
        return ef.time_of(self.step)

    @property
    def bar_len(self) -> float:
        return ef.bar_length(self.time)

    def entered_value(self) -> str:
        if self.triplet:
            return f"triplet_{self.value}"
        return f"dotted_{self.value}" if self.dot and self.value != "whole" else self.value

    def selected(self):
        k, j = self.sel
        if 0 <= k < len(self.bars) and 0 <= j < len(self.bars[k]):
            return self.bars[k][j]
        return None

    def used(self, k: int) -> float:
        return ef.used(self.types[k]) if k < len(self.types) else 0.0

    # ── undo ──
    def _snapshot(self):
        return (copy.deepcopy({k: self.step.get(k) for k in ("bars", "time", "lh", "clef")}),
                copy.deepcopy(self._types), self.sel, self.staff)

    def _begin(self):
        self._undo.append(self._snapshot())
        del self._undo[:-100]
        self._redo.clear()

    def _pad(self):
        """Every staff has as many bars."""
        if self.n_staves < 2:
            return
        n = max(len(self.staff_bars(s)) for s in (0, 1))
        for s in (0, 1):
            while len(self.staff_bars(s)) < n:
                self.staff_bars(s).append([])
            while len(self._types[s]) < n:
                self._types[s].append([])

    def _commit(self):
        self._pad()
        self.step["types"] = self._types[0]
        if self.n_staves > 1:
            self.step["lh"]["types"] = self._types[1]
        self.version += 1
        if self.on_change:
            self.on_change()

    def _restore(self, snap):
        data, types, sel, staff = snap
        for k, v in data.items():
            if v is None:
                self.step.pop(k, None)
            else:
                self.step[k] = v
        self._types, self.sel, self.staff = types, sel, min(staff, len(types) - 1)
        self._commit()

    def undo(self):
        if self._undo:
            self._redo.append(self._snapshot())
            self._restore(self._undo.pop())

    def redo(self):
        if self._redo:
            self._undo.append(self._snapshot())
            self._restore(self._redo.pop())

    # ── keeping bars full but not overfull ──
    def _reflow(self, k: int):
        """Entries that don't fit bar k move to the start of the next bar (made if need be),
        and so on down the piece. An entry longer than a whole bar stays where it is."""
        bars, types = self.bars, self.types
        i = max(0, k)
        while i < len(bars):
            while ef.used(types[i]) > self.bar_len + 1e-6 and len(bars[i]) > 1:
                at = len(bars[i]) - 1
                e, t = bars[i].pop(), types[i].pop()
                if i + 1 == len(bars):
                    bars.append([])
                    types.append([])
                bars[i + 1].insert(0, e)
                types[i + 1].insert(0, t)
                if self.sel == (i, at):
                    self.sel = (i + 1, 0)
                elif self.sel[0] == i + 1:
                    self.sel = (i + 1, self.sel[1] + 1)
            i += 1

    def _ensure_bar(self):
        if not self.bars:
            self.bars.append([])
            self.types.append([])
            self.sel = (0, -1)

    # ── staves ──
    def set_staff(self, s: int):
        s = max(0, min(self.n_staves - 1, s))
        if s != self.staff:
            self.staff = s
            k = min(self.sel[0], max(0, len(self.bars) - 1))
            self.sel = (k, len(self.bars[k]) - 1 if k < len(self.bars) else -1)
            self._last_entry = -1.0
            self.version += 1

    def set_hands(self, both: bool):
        """Two staves (right hand over left) or one."""
        if both == (self.n_staves == 2):
            return
        self._begin()
        if both:
            n = len(self.step["bars"])
            self.step["lh"] = {"bars": [[] for _ in range(n)], "types": [[] for _ in range(n)]}
            self._types = self._types[:1] + [[[] for _ in range(n)]]
            self.step.pop("clef", None)
        else:
            self.step.pop("lh", None)
            self._types = self._types[:1]
            self.staff = 0
        self._commit()

    # ── entering ──
    def insert(self, entry: str, value: str | None = None):
        self._begin()
        self._ensure_bar()
        k, j = self.sel
        k = min(k, len(self.bars) - 1)
        self.bars[k].insert(j + 1, entry)
        self.types[k].insert(j + 1, value or self.entered_value())
        self.sel = (k, j + 1)
        self._reflow(k)
        self._last_entry = _time.monotonic()
        self.entering = True
        self._commit()

    def rest(self):
        self.insert(ef.REST)

    def add_to_chord(self, midi: int) -> bool:
        cur = self.selected()
        if cur is None or ef.is_rest(cur):
            return False
        parts = ef.parts_of(cur)
        if any(parse_note(p) is None for p, _, _ in parts):
            return False
        if midi in [parse_note(p) for p, _, _ in parts]:
            return True
        self._begin()
        k, j = self.sel
        self.bars[k][j] = ef.join_parts(_sort_notes(parts + [(note_name(midi), None, False)]))
        self._last_entry = _time.monotonic()
        self._commit()
        return True

    def _reference(self) -> int:
        """The pitch a letter's octave is chosen near: the selected note, or the last note
        before it (or the middle of the staff)."""
        k, j = self.sel
        for kk in range(min(k, len(self.bars) - 1), -1, -1):
            start = j if kk == k else len(self.bars[kk]) - 1
            for jj in range(start, -1, -1):
                midis = [parse_note(p) for p in ef.pitches_of(self.bars[kk][jj])]
                if midis and None not in midis:
                    return midis[-1]
        bass = self.staff == 1 or self.step.get("clef") == "bass"
        return 50 if bass else 71

    def letter(self, ch: str, add: bool = False):
        pc = _LETTER_PC.get(ch.lower())
        if pc is None:
            return
        if add or self.chord:
            cur = self.selected()
            midis = [parse_note(p) for p in ef.pitches_of(cur)] if cur is not None else []
            if midis and None not in midis:
                top = max(midis)
                m = top + ((pc - top) % 12 or 12)            # the next such key above the chord
                if in_range(m) and self.add_to_chord(m):
                    return
        ref = self._reference()
        m = min((o * 12 + 12 + pc for o in range(0, 9)), key=lambda x: (abs(x - ref), x))
        if in_range(m):
            self.insert(note_name(m))

    def key_note(self, midi: int, now: float | None = None):
        """A key played (MIDI, microphone or on screen): a new note, or part of the chord
        just entered when struck together with it."""
        now = _time.monotonic() if now is None else now
        cur = self.selected()
        if cur is not None and (self.chord or 0 <= now - self._last_entry <= CHORD_WINDOW):
            if self.add_to_chord(midi):
                self._last_entry = now
                return
        if in_range(midi):
            self.insert(note_name(midi))
            self._last_entry = now

    # ── changing what is selected ──
    def set_value(self, value: str):
        self.value = value
        if value == "whole":
            self.dot = False
        self._apply_value()

    def toggle_dot(self):
        self.dot = not self.dot and self.value != "whole"
        if self.dot:
            self.triplet = False
        self._apply_value()

    def toggle_triplet(self):
        self.triplet = not self.triplet
        if self.triplet:
            self.dot = False
        self._apply_value()

    def _apply_value(self):
        k, j = self.sel
        if self.entering:
            return
        if self.selected() is not None and self.types[k][j] != self.entered_value():
            self._begin()
            self.types[k][j] = self.entered_value()
            self._reflow(k)
            self._commit()

    def _next_pos(self):
        """(bar, index) of the entry after the selection, or None."""
        k, j = self.sel
        if j + 1 < len(self.bars[k]):
            return (k, j + 1)
        for kk in range(k + 1, len(self.bars)):
            if self.bars[kk]:
                return (kk, 0)
        return None

    def tie(self):
        """Tie the selected notes to the next entry; a next entry without them gets them
        (the same notes, as long as the selected ones), as MuseScore does. Tied already:
        untie."""
        cur = self.selected()
        if cur is None or ef.is_rest(cur):
            return
        parts = ef.parts_of(cur)
        notes = [(p, tied) for p, _, tied in parts]
        self._begin()
        k, j = self.sel
        if all(tied for _, tied in notes):
            self.bars[k][j] = ef.join_parts([(p, f, False) for p, f, _ in parts])
            self._commit()
            return
        self.bars[k][j] = ef.join_parts([(p, f, True) for p, f, _ in parts])
        nxt = self._next_pos()
        want = {parse_note(p) for p, _ in notes}
        has = {parse_note(p) for p in ef.pitches_of(self.bars[nxt[0]][nxt[1]])} if nxt else set()
        if not want <= has:
            self.bars[k].insert(j + 1, ef.join_notes([(p, False) for p, _ in notes]))
            self.types[k].insert(j + 1, self.types[k][j])
            self.sel = (k, j + 1)
            self._reflow(k)
        else:
            self.sel = nxt
        self._commit()

    def transpose(self, semis: int):
        cur = self.selected()
        if cur is None or ef.is_rest(cur):
            return
        parts = ef.parts_of(cur)
        midis = [parse_note(p) for p, _, _ in parts]
        if None in midis or not all(in_range(m + semis) for m in midis):
            return
        self._begin()
        k, j = self.sel
        moved = [(note_name(m + semis, flats=semis < 0), f, tied) for m, (_, f, tied) in zip(midis, parts)]
        self.bars[k][j] = ef.join_parts(_sort_notes(moved))
        self._commit()

    # ── fingers ──
    def set_finger(self, f: int):
        """Finger f for the selected note; in a chord, for its next note without one (low
        to high), starting over once all have one."""
        cur = self.selected()
        if cur is None or ef.is_rest(cur):
            return
        parts = ef.parts_of(cur)
        free = [i for i, (_, g, _) in enumerate(parts) if g is None]
        if not free:
            parts = [(p, None, t) for p, _, t in parts]
            free = list(range(len(parts)))
        i = free[0]
        p, _, t = parts[i]
        parts[i] = (p, f, t)
        self._begin()
        k, j = self.sel
        self.bars[k][j] = ef.join_parts(parts)
        self._commit()

    def clear_fingers(self, everywhere: bool = False):
        self._begin()
        spots = ([(s, k, j) for s in range(self.n_staves) for k, b in enumerate(self.staff_bars(s))
                  for j in range(len(b))] if everywhere else [(self.staff, *self.sel)])
        for s, k, j in spots:
            bars = self.staff_bars(s)
            if 0 <= k < len(bars) and 0 <= j < len(bars[k]) and not ef.is_rest(bars[k][j]):
                bars[k][j] = ef.join_parts([(p, None, t) for p, _, t in ef.parts_of(bars[k][j])])
        self._commit()

    def suggest_fingering(self):
        """Fingers for every note, from Pianove's fingering planner (the right hand on the
        treble staff, the left on the bass staff); fingers already written stay."""
        from pianove.fingering import Step, finger_hand
        self._begin()
        sec = 60.0 / ef.tempo_of(self.step)
        starts = self.bar_starts()
        for s in range(self.n_staves):
            bars, types = self.staff_bars(s), self._types[s]
            sm = ef.staff_music(bars, types)
            spots, steps = [], []
            for k, (bar, tys) in enumerate(zip(bars, types)):
                pos, ni = starts[k], 0
                for j, (e, t) in enumerate(zip(bar, tys)):
                    midis, length = [], ef.quarters(t)
                    for p in ef.pitches_of(e):
                        if not sm["ties"][k][ni] and parse_note(p) is not None:
                            midis.append(parse_note(p))
                            length = max(length, sm["durs"][k][ni])
                        ni += 1
                    if midis:
                        spots.append((k, j))
                        steps.append(Step(tuple(sorted(midis)), pos * sec, length * sec))
                    pos += ef.quarters(t)
            bass = s == 1 or (self.n_staves == 1 and self.step.get("clef") == "bass")
            plan = finger_hand(steps, "left" if bass else "right") if steps else []
            for (k, j), fingers in zip(spots, plan):
                parts = ef.parts_of(bars[k][j])
                bars[k][j] = ef.join_parts([(p, f if f is not None else fingers.get(parse_note(p)), t)
                                            for p, f, t in parts])
        self._commit()

    # dragging a note along the staff: one undo step for the whole drag
    def drag_start(self):
        cur = self.selected()
        self._drag = {"entry": cur, "steps": 0, "began": False} if cur and not ef.is_rest(cur) else None

    def drag_to(self, steps: int, key: int = 0):
        d = self._drag
        if d is None or steps == d["steps"]:
            return
        moved = []
        for p, f, tied in ef.parts_of(d["entry"]):
            q = shift_step(p, steps, key)
            if q is None:
                return
            moved.append((q, f, tied))
        if not d["began"]:
            self._begin()
            d["began"] = True
        k, j = self.sel
        self.bars[k][j] = ef.join_parts(_sort_notes(moved))
        d["steps"] = steps
        self._commit()

    def drag_end(self):
        self._drag = None

    def delete(self):
        k, j = self.sel
        if self.selected() is not None:
            self._begin()
            del self.bars[k][j]
            del self.types[k][j]
            self.sel = (k, j - 1)
            self._commit()
        elif j < 0 and k > 0:                 # at the start of a bar: select the bar before's last
            self.sel = (k - 1, len(self.bars[k - 1]) - 1)
            self.version += 1

    def positions(self) -> list[tuple[int, int]]:
        out = []
        for k, bar in enumerate(self.bars):
            out.append((k, -1))
            out.extend((k, j) for j in range(len(bar)))
        return out

    def move(self, delta: int):
        pos = self.positions()
        if not pos:
            return
        i = pos.index(self.sel) if self.sel in pos else 0
        self.sel = pos[max(0, min(len(pos) - 1, i + delta))]
        self._last_entry = -1.0
        self.entering = False
        self.version += 1

    def select(self, k: int, j: int, staff: int | None = None):
        if staff is not None:
            self.staff = max(0, min(self.n_staves - 1, staff))
        self.sel = (k, j)
        self._last_entry = -1.0          # a key played next is a new note, not part of this one
        self.entering = False
        self.version += 1

    # ── bars ──
    def add_bar(self):
        self._begin()
        k = self.sel[0] if self.bars else -1
        for s in range(self.n_staves):
            self.staff_bars(s).insert(k + 1, [])
            self._types[s].insert(k + 1, [])
        self.sel = (k + 1, -1)
        self._commit()

    def delete_bar(self):
        n = len(self.bars)
        if n <= 1:
            if any(self.staff_bars(s) and self.staff_bars(s)[0] for s in range(self.n_staves)):
                self._begin()
                for s in range(self.n_staves):
                    self.staff_bars(s)[:] = [[]]
                    self._types[s][:] = [[]]
                self.sel = (0, -1)
                self._commit()
            return
        self._begin()
        k = min(self.sel[0], n - 1)
        for s in range(self.n_staves):
            if k < len(self.staff_bars(s)):
                del self.staff_bars(s)[k]
                del self._types[s][k]
        k = max(0, k - 1)
        self.sel = (k, len(self.bars[k]) - 1)
        self._commit()

    def set_time(self, tm: list):
        """A new time signature: each staff's entries are put into bars of the new length."""
        self._begin()
        self.step["time"] = list(tm)
        for s in range(self.n_staves):
            bars, types = self.staff_bars(s), self._types[s]
            flat = [(e, t) for b, ts in zip(bars, types) for e, t in zip(b, ts)]
            sel_flat = (sum(len(b) for b in bars[:self.sel[0]]) + self.sel[1]) if s == self.staff else None
            nb, nt, cur = [[]], [[]], 0.0
            for e, t in flat:
                if nb[-1] and cur + ef.quarters(t) > self.bar_len + 1e-6:
                    nb.append([])
                    nt.append([])
                    cur = 0.0
                nb[-1].append(e)
                nt[-1].append(t)
                cur += ef.quarters(t)
            bars[:] = nb
            types[:] = nt
            if sel_flat is not None:                 # the same entry stays selected
                n = sel_flat
                for k, b in enumerate(nb):
                    if n < len(b):
                        self.sel = (k, n)
                        break
                    n -= len(b)
                else:
                    self.sel = (len(nb) - 1, len(nb[-1]) - 1)
        self._commit()

    def insert_bars(self, staves: list[tuple[list, list]]):
        """Bars written down from playing, one (bars, types) per staff: after the selected
        bar (or in place of an empty piece)."""
        staves = [(b, t) for b, t in staves][:self.n_staves]
        n = max((len(b) for b, _ in staves), default=0)
        if not n:
            return
        self._begin()
        empty = all(not any(self.staff_bars(s)) for s in range(self.n_staves))
        at = 0 if empty else min(self.sel[0], max(len(self.staff_bars(s)) for s in range(self.n_staves)) - 1) + 1
        for s in range(self.n_staves):
            bars, types = (staves[s] if s < len(staves) else ([], []))
            bars = [list(b) for b in bars] + [[] for _ in range(n - len(bars))]
            types = [list(t) for t in types] + [[] for _ in range(n - len(types))]
            target_b, target_t = self.staff_bars(s), self._types[s]
            if empty:
                target_b[:] = bars
                target_t[:] = types
            else:
                target_b[at:at] = bars
                target_t[at:at] = types
        last = (at + n - 1) if not empty else n - 1
        self.sel = (last, len(self.bars[last]) - 1 if last < len(self.bars) else -1)
        self._commit()

    def replace_all(self, tm, bars, types, lh: dict | None = None):
        self._begin()
        self.step["time"] = list(tm)
        self.step["bars"] = [list(b) for b in bars]
        self._types = [[list(t) for t in types]]
        if lh:
            self.step["lh"] = {"bars": [list(b) for b in lh["bars"]], "types": [list(t) for t in lh["types"]]}
            self._types.append([list(t) for t in lh["types"]])
            self.step.pop("clef", None)
        else:
            self.step.pop("lh", None)
        self.staff = 0
        self.sel = (0, len(self.bars[0]) - 1) if self.bars else (0, -1)
        self._commit()

    def clear(self):
        self._begin()
        for s in range(self.n_staves):
            self.staff_bars(s)[:] = [[]]
            self._types[s][:] = [[]]
        self.sel = (0, -1)
        self._commit()

    # ── playing ──
    def bar_starts(self) -> list[float]:
        """Where each bar starts (quarters): a bar lasts its time signature, or longer when
        a staff overfills it."""
        n = max(len(self.staff_bars(s)) for s in range(self.n_staves))
        out, q = [], 0.0
        for k in range(n):
            out.append(q)
            q += max([self.bar_len] + [ef.used(self._types[s][k]) for s in range(self.n_staves)
                                       if k < len(self._types[s])])
        return out

    def schedule(self, bpm: float | None = None):
        """(start s, end s, midis, (staff, bar, index)) of every entry struck from the
        selection on, on every staff; a tied note sounds through the notes it ties to."""
        sec = 60.0 / (bpm or ef.tempo_of(self.step))
        starts = self.bar_starts()
        if not starts:
            return []
        k0, j0 = self.sel
        k0 = min(k0, len(starts) - 1)
        q0 = starts[k0] + sum(ef.quarters(t) for t in self.types[k0][:max(0, j0)])
        out = []
        for s in range(self.n_staves):
            bars, types = self.staff_bars(s), self._types[s]
            sm = ef.staff_music(bars, types)
            for k, (bar, tys) in enumerate(zip(bars, types)):
                pos, ni = starts[k], 0
                for j, (e, t) in enumerate(zip(bar, tys)):
                    midis, length = [], ef.quarters(t)
                    for p, _ in ef.notes_of(e):
                        if not sm["ties"][k][ni] and parse_note(p) is not None:
                            midis.append(parse_note(p))
                            length = max(length, sm["durs"][k][ni])
                        ni += 1
                    if midis and pos >= q0 - 1e-6:
                        out.append(((pos - q0) * sec, (pos - q0 + length) * sec * 0.95, midis, (s, k, j)))
                    pos += ef.quarters(t)
        out.sort(key=lambda e: e[0])
        return out


# ── drawing it ────────────────────────────────────────────────────────────────────────

class ScoreCanvas(PygameCanvas):
    """The exercise on a page of music paper. Its height follows the music.

    min_space: the smallest gap between staff lines (px) before a line holds fewer bars;
    touch: a finger is less exact than a mouse pointer (larger hit areas)."""

    def __init__(self, model: ScoreModel, key_fn=None, problems_fn=None, min_space: int = 13,
                 touch: bool = False, **kw):
        kw.setdefault("width", 1.0)
        kw.setdefault("height", 200)
        super().__init__(draw_border=False, **kw)
        self.model = model
        self.key_fn = key_fn or (lambda: 0)
        self.problems_fn = problems_fn or (lambda: set())
        self.min_space = min_space
        self.touch = touch
        self.focused = False
        self._built = None
        self._paper: pygame.Surface | None = None
        self._map: dict = {}           # (staff, bar, index) → PyLute event
        self._score = None
        self._play = None
        self.playing_at: frozenset = frozenset()
        self._press = None             # a press on a note: {"y", "dragging"}
        self._audition_off = None

    # ── building the score ──
    def _event_for(self, staff, e, t, where, bad):
        from pylute.note import Note
        from pylute.rest import Rest
        from pylute.chord import Chord
        w = ef.written(t) if ef.is_type(t) else "quarter"
        names = ef.pitches_of(e)
        notes = []
        if ef.is_rest(e) or not names or any(parse_note(p) is None for p in names):
            ev = Rest(rtype=w, staff=staff)          # (an unreadable note shows as a rest)
        else:
            notes = [Note(ntype=w, pitch=p, staff=staff) for p in names]
            ev = notes[0] if len(notes) == 1 else Chord(notes, staff=staff)
            m = self.model
            ev.color = (_PLAYING if where in self.playing_at else
                        _BLUE if (m.staff, *m.sel) == where else
                        (200, 40, 40) if where[1] in bad else None)
        if ef.is_type(t) and ef.is_triplet(t):
            ev._trip = True
        return ev, notes

    def _build(self, width: int):
        from pylute.score import Score
        from pylute.rest import Rest
        from pianove.notation import group_tuplets, link_tie
        m = self.model
        n_st = m.n_staves
        n_bars = max(1, max(len(m.staff_bars(s)) for s in range(n_st)))
        clefs = ["treble", "bass"] if n_st == 2 else [m.step.get("clef", "treble")]
        score = Score(surface=None, staffs=n_st, bars=n_bars, clef_types=clefs,
                      key=self.key_fn(), time=m.time, bars_per_system=None)
        score.justify_last = False
        score.min_space = self.min_space
        bad = self.problems_fn()
        self._map = {}
        ties = []                                # (from note, to note)
        for s in range(n_st):
            staff = score.staffs[s]
            bars, types = m.staff_bars(s), m.staff_types(s)
            prev_tied: dict = {}                 # midi → note of the entry before, tied on
            for k in range(n_bars):
                obj = staff.bars[k]
                bar = bars[k] if k < len(bars) else []
                tys = types[k] if k < len(types) else []
                for j, (e, t) in enumerate(zip(bar, tys)):
                    ev, notes = self._event_for(staff, e, t, (s, k, j), bad)
                    ev._layout_dur = _room(ef.quarters(t) if ef.is_type(t) else 1.0)
                    obj.events.append(ev)
                    self._map[(s, k, j)] = ev
                    now = {}
                    for note, (p, tied) in zip(notes, ef.notes_of(e)):
                        src = prev_tied.get(parse_note(p))
                        if src is not None:
                            ties.append((src, note))
                        if tied:
                            now[parse_note(p)] = note
                    prev_tied = now
                gap = m.bar_len - ef.used(tys) if tys else 0
                if not bar:
                    r = Rest(rtype="whole", staff=staff)
                    r._layout_dur = _room(m.bar_len)
                    obj.events.append(r)
                    prev_tied = {}
                elif gap > 1e-3:
                    trip = ef.is_triplet(tys[-1])
                    unit = ef.quarters(tys[-1]) if trip else 0
                    n_r = round(gap / unit) if trip else 0
                    finish = trip and n_r > 0 and abs(n_r * unit - gap) < 1e-3
                    for rt in ([ef.written(tys[-1])] * n_r if finish else ef.fill_rests(gap)):
                        r = Rest(rtype=rt, staff=staff)
                        r._trip = finish                 # rests that finish a triplet
                        r._layout_dur = _room(ef.quarters(("triplet_" if finish else "") + rt))
                        obj.events.append(r)
                    prev_tied = {}
                group_tuplets(obj, staff)
        score._on_resize(width)
        # a short phrase on a wide page would be drawn huge: keep the staff to a normal size
        cap = max(self.min_space + 3, 17)
        if score._space() > cap:
            from pylute.score import _ML
            cost = score._system_cost(score.bars_per_system)
            score._on_resize(max(200, min(width, int(cap * (2 * _ML + 5.5 + cost) + 40))))
        line_of = {k: i for i, bars in enumerate(score._layout_systems()) for k in bars}
        bar_of = {id(n): k for (s, k, j), ev in self._map.items()
                  for n in (getattr(ev, "notes", None) or [ev])}
        for src, dst in ties:
            if line_of.get(bar_of.get(id(src))) == line_of.get(bar_of.get(id(dst))):
                link_tie(src, dst)               # (a tie over a line break is left out)
        h = score.total_content_height()             # (as laid out above: no new resize)
        sp_ = score._space()                         # no empty paper under the last line
        h = min(h, int(score.system_y_tops()[-1] + score.system_height() + sp_ * (5 if n_st == 1 else 6)))
        # drawn at the width laid out (Score.draw would lay a wider surface out again)
        paper = pygame.Surface((score._last_size or width, max(1, h)))
        paper.fill((255, 255, 255))
        score.surface = paper
        for st in score.staffs:
            st.surface = paper
        if score.brace:
            score.brace.surface = paper
        score.draw()
        self._score, self._paper = score, paper
        self._draw_fingers(paper)
        self._built = (m.version, width, self.playing_at)
        if h != self.height_spec:
            self.height_spec = h
            self.request_layout()

    def _fresh(self):
        w = max(200, self.rect.width)
        if self._built != (self.model.version, w, self.playing_at):
            self._build(w)

    def layout(self, parent_rect=None, skip_self: bool = False):
        super().layout(parent_rect, skip_self=skip_self)
        if self.rect.width > 50:
            self._fresh()

    # ── where things are ──
    def _space(self) -> float:
        return self._score.staffs[0].space if self._score else 10

    def _lines(self):
        """[(top line y of each staff, [bar indices])] per line of music."""
        s = self._score
        sp = self._space()
        return [([y + i * sp * _SG for i in range(len(s.staffs))], bars)
                for y, bars in zip(s.system_y_tops(), s._layout_systems())]

    def _box(self, staff: int, k: int):
        sp = self._space()
        for tops, bars in self._lines():
            if k in bars:
                b = self._score.staffs[0].bars[k]
                return pygame.Rect(int(b.bar_start_x), int(tops[staff] - sp * 3), int(b.barspace), int(sp * 10))
        return None

    def hit(self, pos):
        """(staff, bar, index) at a point on the paper: an entry, or index -1 for the start
        of a bar."""
        if self._score is None:
            return None
        x, y = pos
        sp = self._space()
        reach = sp * (1.2 if self.touch else 0.8)
        for tops, bars in self._lines():
            if not (tops[0] - sp * 5 <= y <= tops[-1] + sp * 9):
                continue
            s = min(range(len(tops)), key=lambda i: abs(tops[i] + sp * 2 - y))
            for k in bars:
                b = self._score.staffs[0].bars[k]
                if not (b.bar_start_x <= x < b.bar_start_x + b.barspace):
                    continue
                n = len(self.model.staff_bars(s)[k]) if k < len(self.model.staff_bars(s)) else 0
                evs = [(j, self._map[(s, k, j)].offset) for j in range(n) if (s, k, j) in self._map]
                if not evs or x < evs[0][1] - reach:
                    return (s, k, -1)
                return (s, k, min(evs, key=lambda e: abs(e[1] + sp * 0.6 - x))[0])
        return None

    def place_at(self, pos):
        """A note for a tap on an empty spot of the staff: (staff, bar, pitch), or None
        when the tap is on or near a note (that selects it instead)."""
        if self._score is None:
            return None
        x, y = pos
        sp = self._space()
        for tops, bars in self._lines():
            if not (tops[0] - sp * 4 <= y <= tops[-1] + sp * 8):
                continue
            s = min(range(len(tops)), key=lambda i: abs(tops[i] + sp * 2 - y))
            for k in bars:
                b = self._score.staffs[0].bars[k]
                if not (b.bar_start_x <= x < b.bar_start_x + b.barspace):
                    continue
                n = len(self.model.staff_bars(s)[k]) if k < len(self.model.staff_bars(s)) else 0
                xs = [self._map[(s, k, j)].offset for j in range(n) if (s, k, j) in self._map]
                if xs and x < max(xs) + sp * 2.2:
                    return None                       # among the notes: a selection
                clef = "bass" if (s == 1 or (self.model.n_staves == 1 and
                                             self.model.step.get("clef") == "bass")) else "treble"
                base = 2 * 7 + 4 if clef == "bass" else 4 * 7 + 2       # bottom line: G2 / E4
                steps = int(round((tops[s] + 4 * sp - y) / (sp / 2)))
                idx = base + steps
                letter, octave = _LETTERS[idx % 7], idx // 7
                pitch = f"{letter}{key_spelling(self.key_fn()).get(letter, '')}{octave}"
                m = parse_note(pitch)
                if m is None or not in_range(m):
                    return None
                return (s, k, pitch)
        return None

    def _draw_fingers(self, paper):
        """Finger numbers over the notes of the right hand, under those of the left."""
        sp = self._space()
        f = pygame.font.Font(None, max(10, int(sp * 1.5)))
        tops_of = {k: tops for tops, bars in self._lines() for k in bars}
        m = self.model
        for (s, k, j), ev in self._map.items():
            bars = m.staff_bars(s)
            if k >= len(bars) or j >= len(bars[k]):
                continue
            fingers = [g for g in ef.fingers_of(bars[k][j]) if g]
            if not fingers or k not in tops_of:
                continue
            tops = tops_of[k]
            x = ev.offset + sp * 0.6
            for i, g in enumerate(reversed(fingers) if s == 0 else fingers):
                ts = f.render(str(g), True, (40, 70, 150))
                if s == 0:
                    y = tops[0] - sp * 1.4 - i * sp * 1.1
                else:
                    y = tops[s] + 4 * sp + sp * 1.4 + i * sp * 1.1
                paper.blit(ts, ts.get_rect(center=(int(x), int(y))))

    # ── drawing ──
    def draw_content(self, surface, rect):
        self._fresh()
        if self._paper is None:
            return
        surface.fill((255, 255, 255), rect)          # paper all the way down while it resizes
        surface.blit(self._paper, rect.topleft)
        sp = self._space()
        m = self.model
        k, j = m.sel
        ev = self._map.get((m.staff, k, j))
        box = self._box(m.staff, k)
        if box is not None:
            box = box.move(rect.left, rect.top)
            if ev is not None:
                x = rect.left + ev.offset + sp * 1.7
                band = pygame.Surface((int(sp * 2.4), box.height), pygame.SRCALPHA)
                band.fill((*_BLUE, 34))
                surface.blit(band, (rect.left + ev.offset - sp * 0.5, box.top))
            else:
                x = box.left + sp * 0.8
            pygame.draw.line(surface, _BLUE, (x, box.top + sp), (x, box.bottom - sp), 2)
        col = iOSTheme.accent if self.focused else iOSTheme.fill_tertiary
        pygame.draw.rect(surface, col, rect, width=2 if self.focused else 1, border_radius=6)

    # ── input ──
    def handle_content_event(self, event) -> bool:
        from pianove import creator_ui
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            inside = self.rect.collidepoint(event.pos)
            self.focused = inside
            _dirty.mark()
            if not inside:
                return False
            local = (event.pos[0] - self.rect.left, event.pos[1] - self.rect.top)
            spot = self.place_at(local)
            if spot is not None:                         # an empty spot: a note there
                s, k, pitch = spot
                m = self.model
                m.select(k, len(m.staff_bars(s)[k]) - 1 if k < len(m.staff_bars(s)) else -1, staff=s)
                m.insert(ef.join_notes([(pitch, False)]))
                self._audition()
                return True
            at = self.hit(local)
            if at is not None:
                s, k, j = at
                self.model.select(k, j, staff=s)
                self._sync_palette()
                cur = self.model.selected()
                if cur is not None and not ef.is_rest(cur):
                    self._sound_on([parse_note(p) for p in ef.pitches_of(cur)])
                    self._press = {"y": event.pos[1], "dragging": False}
                    creator_ui.CAPTURE = self            # a drag moves the note, not the page
            return True
        if event.type == pygame.MOUSEMOTION and self._press is not None:
            if not getattr(event, "buttons", (1, 0, 0))[0]:
                self._end_press()
                return False
            dy = event.pos[1] - self._press["y"]
            half = self._space() / 2
            if not self._press["dragging"] and abs(dy) > max(4, half * 0.8):
                self._press["dragging"] = True
                self.model.drag_start()
            if self._press["dragging"]:
                before = self.model.selected()
                self.model.drag_to(int(round(-dy / half)), self.key_fn())
                if self.model.selected() != before:
                    self._audition()
                _dirty.mark()
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._press is not None:
            self._end_press()
            return True
        if event.type == pygame.KEYDOWN and self.focused:
            return self._key(event)
        return False

    def _end_press(self):
        from pianove import creator_ui
        self.model.drag_end()
        self._press = None
        if creator_ui.CAPTURE is self:
            creator_ui.CAPTURE = None
        self._sound_off()

    def _sync_palette(self):
        """The palette shows the selected entry's value (as MuseScore does)."""
        m = self.model
        if m.selected() is not None:
            t = m.types[m.sel[0]][m.sel[1]]
            m.triplet = ef.is_triplet(t)
            m.dot = t.startswith("dotted_")
            base = ef.written(t).replace("dotted_", "", 1)
            if base in VALUES:
                m.value = base
        _dirty.mark()

    def _key(self, ev) -> bool:
        m = self.model
        ctrl = ev.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
        shift = ev.mod & pygame.KMOD_SHIFT
        alt = ev.mod & pygame.KMOD_ALT
        k = ev.key
        name = pygame.key.name(k)
        if ctrl and k == pygame.K_z:
            m.redo() if shift else m.undo()
        elif ctrl and k == pygame.K_y:
            m.redo()
        elif ctrl and k in (pygame.K_3, pygame.K_KP3):
            m.toggle_triplet()
        elif alt and k in (pygame.K_UP, pygame.K_DOWN):
            m.set_staff(0 if k == pygame.K_UP else 1)
        elif k in (pygame.K_UP, pygame.K_DOWN):
            m.transpose((12 if ctrl else 1) * (1 if k == pygame.K_UP else -1))
            self._audition()
        elif k in (pygame.K_LEFT, pygame.K_RIGHT):
            m.move(1 if k == pygame.K_RIGHT else -1)
            self._sync_palette()
        elif k in (pygame.K_DELETE, pygame.K_BACKSPACE):
            m.delete()
        elif k in _KEY_VALUE:
            m.set_value(_KEY_VALUE[k])
        elif k in (pygame.K_PERIOD, pygame.K_KP_PERIOD):
            m.toggle_dot()
        elif k in (pygame.K_0, pygame.K_KP0):
            m.rest()
        elif k in (pygame.K_t, pygame.K_PLUS, pygame.K_KP_PLUS) or (k == pygame.K_EQUALS and shift):
            m.tie()
        elif k == pygame.K_SPACE:
            self.toggle_play()
        elif k == pygame.K_ESCAPE:
            self.focused = False
        elif len(name) == 1 and name in _LETTER_PC and not ctrl:
            m.letter(name, add=bool(shift))
            self._audition()
        else:
            return False
        _dirty.mark()
        return True

    # ── sound ──
    def _sound_on(self, midis):
        from pianove.creator_ui import _sound
        self._sound_off()
        midis = [x for x in midis if x is not None]
        for x in midis:
            _sound(x, True)
        self._audition_off = (_time.monotonic() + 0.5, midis)

    def _sound_off(self):
        from pianove.creator_ui import _sound
        if self._audition_off:
            for x in self._audition_off[1]:
                _sound(x, False)
            self._audition_off = None

    def _audition(self):
        cur = self.model.selected()
        if cur is not None and not ef.is_rest(cur):
            self._sound_on([parse_note(p) for p in ef.pitches_of(cur)])

    def toggle_play(self):
        if self._play is not None:
            self.stop()
            return
        events = self.model.schedule()
        if events:
            self._play = {"t": 0.0, "events": events, "on": {}}
            _dirty.mark()

    def stop(self):
        from pianove.creator_ui import _sound
        if self._play:
            for x in list(self._play["on"]):
                _sound(x, False)
        self._play = None
        self.playing_at = frozenset()
        _dirty.mark()

    @property
    def is_playing(self) -> bool:
        return self._play is not None

    def update_content(self, dt):
        from pianove.creator_ui import TextBox, _sound
        if self.focused and TextBox._focused is not None:
            self.focused = False
            _dirty.mark()
        if self._audition_off and _time.monotonic() > self._audition_off[0] and self._press is None:
            self._sound_off()
        if self._play is None:
            return
        p = self._play
        p["t"] += dt
        t = p["t"]
        now = set()
        for start, end, midis, where in p["events"]:
            if start <= t < end:
                now.add(where)
                for x in midis:
                    if x not in p["on"]:
                        _sound(x, True)
                        p["on"][x] = end
        for x, end in list(p["on"].items()):
            if t >= end:
                _sound(x, False)
                del p["on"][x]
        if frozenset(now) != self.playing_at:
            self.playing_at = frozenset(now)
            _dirty.mark()
        if t > max(e[1] for e in p["events"]) + 0.1:
            self.stop()

    def update(self, dt):
        self.update_content(dt)
        UIElement.update(self, dt)


# ── palette buttons ───────────────────────────────────────────────────────────────────

_GLYPHS = {"whole": "", "half": "", "quarter": "", "eighth": "",
           "sixteenth": "", "dot": "", "rest": ""}
_glyph_fonts: dict = {}


def _glyph_font(size: int):
    if size not in _glyph_fonts:
        import pygame.freetype
        from pylute.font import FONT_PATH
        pygame.freetype.init()
        _glyph_fonts[size] = pygame.freetype.Font(FONT_PATH, size)
    return _glyph_fonts[size]


class GlyphButton(UIElement):
    """A square button showing a music glyph (a note value, the dot, a rest)."""

    def __init__(self, glyph: str, on_click, active_fn=lambda: False, size: int = 40):
        from pianove.creator_ui import px
        super().__init__(width=px(size), height=px(size))
        self.glyph, self.on_click, self.active_fn = glyph, on_click, active_fn
        self._pressed = False

    def on_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self._pressed = True
            return True
        if event.type == pygame.MOUSEMOTION and self._pressed and not self.rect.collidepoint(event.pos):
            self._pressed = False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._pressed:
            self._pressed = False
            if self.rect.collidepoint(event.pos):
                self.on_click()
                _dirty.mark()
            return True
        return False

    def _bg(self, surface):
        r = self.rect
        active = self.active_fn()
        pygame.draw.rect(surface, ColorPalette.BLUE if active else iOSTheme.fill, r,
                         border_radius=max(4, r.height // 4))
        return (255, 255, 255) if active else tuple(iOSTheme.label)[:3]

    def render(self, surface):
        fg = self._bg(surface)
        f = _glyph_font(max(8, int(self.rect.height * 0.62)))
        g = _GLYPHS[self.glyph]
        ink = f.get_rect(g)                  # the glyph's ink, centred in the button
        ink.center = self.rect.center
        f.render_to(surface, ink, g, fg)


class TextToggle(GlyphButton):
    """A palette button with a word on it (its text may change: Play / Stop)."""

    def __init__(self, text_fn, on_click, active_fn=lambda: False, size: int = 40, alt_text: str = ""):
        from pianove.creator_ui import px, text_w
        super().__init__("dot", on_click, active_fn, size=size)
        self.text_fn = text_fn
        widest = max(text_w(text_fn(), 13), text_w(alt_text, 13) if alt_text else 0)
        self.width_spec = max(px(size), widest + px(24))

    def render(self, surface):
        from pianove.creator_ui import font
        fg = self._bg(surface)
        ts = font(13, bold=True).render(self.text_fn(), True, fg)
        surface.blit(ts, ts.get_rect(center=self.rect.center))


# ── playing along with a metronome ────────────────────────────────────────────────────

class Recorder:
    """Records what is played into a ScoreModel: a bar of metronome clicks to count in,
    then the clicks go on while you play; Done writes it down (see transcribe.py) after
    the selected bar. With two staves, keys below middle C go to the left hand."""

    def __init__(self, model: ScoreModel):
        self.model = model
        self.state = "idle"             # idle → count (the count-in bar) → rec
        self.presses: list[list] = []
        self.held: dict[int, int] = {}
        self._clicks_off: list = []
        self.beat = 0

    @property
    def active(self) -> bool:
        return self.state != "idle"

    def start(self, now: float | None = None):
        now = _time.monotonic() if now is None else now
        m = self.model
        self.beat_s = 60.0 / ef.tempo_of(m.step)
        self.beats_per_bar = m.time[0] * 4 / m.time[1]
        self.t_count = now
        self.t0 = now + self.beats_per_bar * self.beat_s      # the first beat of the music
        self.presses, self.held = [], {}
        self.state = "count"
        self.beat = -1

    def key_down(self, midi: int, now: float | None = None):
        now = _time.monotonic() if now is None else now
        if not self.active or now < self.t0 - self.beat_s * 0.5:
            return                                             # too early for the music
        self.held[midi] = len(self.presses)
        self.presses.append([now, None, midi])

    def key_up(self, midi: int, now: float | None = None):
        now = _time.monotonic() if now is None else now
        i = self.held.pop(midi, None)
        if i is not None:
            self.presses[i][1] = now

    def tick(self, now: float | None = None):
        from pianove.creator_ui import _sound
        now = _time.monotonic() if now is None else now
        for when, m in list(self._clicks_off):
            if now >= when:
                _sound(m, False)
                self._clicks_off.remove((when, m))
        if not self.active:
            return
        b = int((now - self.t_count) / self.beat_s)
        if b != self.beat:
            self.beat = b
            down = (b % max(1, int(round(self.beats_per_bar)))) == 0
            click = 96 if down else 89                         # a high key: the metronome
            _sound(click, True)
            self._clicks_off.append((now + 0.06, click))
            _dirty.mark()
        if self.state == "count" and now >= self.t0:
            self.state = "rec"

    def count_text(self) -> str:
        """The beat being counted in ("1" … "4"), or "" once the music runs."""
        if self.state != "count":
            return ""
        return str(max(0, self.beat) % max(1, int(round(self.beats_per_bar))) + 1)

    def stop(self, now: float | None = None, keep: bool = True) -> bool:
        """Done: the playing written down (keep) or thrown away. True if notes were added."""
        from pianove.transcribe import quantize, split_hands
        now = _time.monotonic() if now is None else now
        for m in list(self.held):
            self.key_up(m, now)
        self.state = "idle"
        if not keep or not self.presses:
            return False
        m = self.model
        bpm = ef.tempo_of(m.step)
        if m.n_staves == 2:
            right, left = split_hands([tuple(p) for p in self.presses])
            staves = [quantize(right, bpm, m.time, start=self.t0) if right else ([], []),
                      quantize(left, bpm, m.time, start=self.t0) if left else ([], [])]
        else:
            staves = [quantize([tuple(p) for p in self.presses], bpm, m.time, start=self.t0)]
        m.insert_bars(staves)
        return True

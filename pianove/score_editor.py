"""A score editor for an exercise, in the manner of MuseScore's note input.

ScoreModel is the editing (no drawing, so it can be tested): a selection, a note value to
enter with, and operations that keep bars from overflowing (what doesn't fit moves on to
the next bar). ScoreCanvas draws the exercise with PyLute, the same notation the lesson
player shows, and turns clicks and keys into model operations.

Keys (with the score clicked): A–G enter a note, Shift+A–G add it to the chord, 3–7 pick
a value (sixteenth … whole, as in MuseScore), "." a dot, 0 a rest, ↑/↓ a semitone,
Ctrl+↑/↓ an octave, ←/→ move, Delete removes, Ctrl+Z / Ctrl+Y undo and redo, Space
plays. A MIDI keyboard or the keys on screen enter notes too; keys pressed together
make a chord.
"""
from __future__ import annotations

import copy
import time as _time

import pygame
from pylay import PygameCanvas, iOSTheme, ColorPalette
from pylay.core.element import UIElement
from pylay.core import _dirty

from pianove import exercise_format as ef
from pianove.creator_notes import parse_chord, note_name, chord_name, in_range, CHORD_WINDOW

VALUES = ["whole", "half", "quarter", "eighth", "sixteenth"]
_LETTER_PC = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
_KEY_VALUE = {pygame.K_3: "sixteenth", pygame.K_4: "eighth", pygame.K_5: "quarter",
              pygame.K_6: "half", pygame.K_7: "whole",
              pygame.K_KP3: "sixteenth", pygame.K_KP4: "eighth", pygame.K_KP5: "quarter",
              pygame.K_KP6: "half", pygame.K_KP7: "whole"}
_BLUE = (10, 132, 255)
_PLAYING = (40, 170, 90)
_BPM = 80


# ── the editing ───────────────────────────────────────────────────────────────────────

class ScoreModel:
    """Edits an exercise step in place. sel = (bar, index): the selected entry, or index -1
    for the start of the bar (nothing selected). New notes go in after the selection."""

    def __init__(self, step: dict, on_change=None):
        self.step = step
        step.setdefault("bars", [])
        self.types = ef.types_of(step)
        self.sel: tuple[int, int] = (0, len(step["bars"][0]) - 1) if step["bars"] else (0, -1)
        self.value = "quarter"
        self.dot = False
        self.chord = False            # the next note entered joins the selected chord
        self.on_change = on_change
        self._undo: list = []
        self._redo: list = []
        self._last_entry = -1.0       # when a note was last entered (for chords from MIDI)
        self.version = 0

    # ── state ──
    @property
    def bars(self) -> list:
        return self.step["bars"]

    @property
    def time(self) -> list:
        return ef.time_of(self.step)

    @property
    def bar_len(self) -> float:
        return ef.bar_length(self.time)

    def entered_value(self) -> str:
        return f"dotted_{self.value}" if self.dot and self.value != "whole" else self.value

    def selected(self):
        k, j = self.sel
        if 0 <= k < len(self.bars) and 0 <= j < len(self.bars[k]):
            return self.bars[k][j]
        return None

    def used(self, k: int) -> float:
        return ef.used(self.types[k]) if k < len(self.types) else 0.0

    def _snapshot(self):
        return copy.deepcopy(self.bars), copy.deepcopy(self.types), self.sel, copy.deepcopy(self.step.get("time"))

    def _begin(self):
        self._undo.append(self._snapshot())
        del self._undo[:-100]
        self._redo.clear()

    def _commit(self):
        self.step["bars"] = self.bars
        self.step["types"] = self.types
        self.version += 1
        if self.on_change:
            self.on_change()

    def _restore(self, snap):
        bars, types, sel, tm = snap
        self.step["bars"], self.types, self.sel = bars, types, sel
        if tm is not None:
            self.step["time"] = tm
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
        i = max(0, k)
        while i < len(self.bars):
            while self.used(i) > self.bar_len + 1e-6 and len(self.bars[i]) > 1:
                at = len(self.bars[i]) - 1
                e, t = self.bars[i].pop(), self.types[i].pop()
                if i + 1 == len(self.bars):
                    self.bars.append([])
                    self.types.append([])
                self.bars[i + 1].insert(0, e)
                self.types[i + 1].insert(0, t)
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
        self._commit()

    def rest(self):
        self.insert(ef.REST)

    def add_to_chord(self, midi: int) -> bool:
        cur = self.selected()
        if cur is None or ef.is_rest(cur):
            return False
        notes = parse_chord(cur)
        if notes is None or midi in notes:
            return notes is not None
        self._begin()
        names = [p.strip() for p in str(cur).split("+")] + [note_name(midi)]
        names.sort(key=lambda p: parse_chord(p)[0])
        k, j = self.sel
        self.bars[k][j] = "+".join(names)
        self._last_entry = _time.monotonic()
        self._commit()
        return True

    def _reference(self) -> int:
        """The pitch a letter's octave is chosen near: the selected note, or the last note
        before it."""
        k, j = self.sel
        for kk in range(min(k, len(self.bars) - 1), -1, -1):
            start = j if kk == k else len(self.bars[kk]) - 1
            for jj in range(start, -1, -1):
                e = self.bars[kk][jj]
                if not ef.is_rest(e) and parse_chord(e):
                    return parse_chord(e)[-1]
        return 67 if self.step.get("clef", "treble") == "treble" else 50

    def letter(self, ch: str, add: bool = False):
        pc = _LETTER_PC.get(ch.lower())
        if pc is None:
            return
        if add or self.chord:
            cur = self.selected()
            top = max(parse_chord(cur)) if cur and not ef.is_rest(cur) and parse_chord(cur) else None
            if top is not None:
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
        self._apply_value()

    def _apply_value(self):
        k, j = self.sel
        if self.selected() is not None and self.types[k][j] != self.entered_value():
            self._begin()
            self.types[k][j] = self.entered_value()
            self._reflow(k)
            self._commit()

    def transpose(self, semis: int):
        cur = self.selected()
        if cur is None or ef.is_rest(cur):
            return
        notes = parse_chord(cur)
        if notes is None or not all(in_range(m + semis) for m in notes):
            return
        self._begin()
        flats = semis < 0
        k, j = self.sel
        self.bars[k][j] = chord_name([m + semis for m in notes], flats=flats)
        self._commit()

    def delete(self):
        k, j = self.sel
        if self.selected() is not None:
            self._begin()
            del self.bars[k][j]
            del self.types[k][j]
            self.sel = (k, j - 1)
            if j - 1 < 0 and k > 0 and not self.bars[k]:
                self.sel = (k, -1)
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
        self.version += 1

    def select(self, k: int, j: int):
        self.sel = (k, j)
        self._last_entry = -1.0          # a key played next is a new note, not part of this one
        self.version += 1

    # ── bars ──
    def add_bar(self):
        self._begin()
        k = self.sel[0] if self.bars else -1
        self.bars.insert(k + 1, [])
        self.types.insert(k + 1, [])
        self.sel = (k + 1, -1)
        self._commit()

    def delete_bar(self):
        if len(self.bars) <= 1:
            if self.bars and self.bars[0]:
                self._begin()
                self.bars[0], self.types[0] = [], []
                self.sel = (0, -1)
                self._commit()
            return
        self._begin()
        k = min(self.sel[0], len(self.bars) - 1)
        del self.bars[k]
        del self.types[k]
        k = max(0, k - 1)
        self.sel = (k, len(self.bars[k]) - 1)
        self._commit()

    def set_time(self, tm: list):
        """A new time signature: the entries are put into bars of the new length."""
        self._begin()
        self.step["time"] = list(tm)
        flat = [(e, t) for b, ts in zip(self.bars, self.types) for e, t in zip(b, ts)]
        sel_flat = sum(len(b) for b in self.bars[:self.sel[0]]) + self.sel[1]
        bars, types, cur = [[]], [[]], 0.0
        for e, t in flat:
            if bars[-1] and cur + ef.quarters(t) > self.bar_len + 1e-6:
                bars.append([])
                types.append([])
                cur = 0.0
            bars[-1].append(e)
            types[-1].append(t)
            cur += ef.quarters(t)
        self.step["bars"], self.types = bars, types
        # the same entry stays selected
        n = sel_flat
        for k, b in enumerate(bars):
            if n < len(b):
                self.sel = (k, n)
                break
            n -= len(b)
        else:
            self.sel = (len(bars) - 1, len(bars[-1]) - 1)
        self._commit()

    def replace_all(self, tm, bars, types):
        self._begin()
        self.step["time"] = list(tm)
        self.step["bars"], self.types = [list(b) for b in bars], [list(t) for t in types]
        self.sel = (0, len(self.bars[0]) - 1) if self.bars else (0, -1)
        self._commit()

    def clear(self):
        self._begin()
        self.step["bars"], self.types = [[]], [[]]
        self.sel = (0, -1)
        self._commit()

    # ── playing ──
    def schedule(self, bpm: float = _BPM):
        """(start s, end s, midis, (bar, index)) of every entry from the selection on. A bar
        that isn't full is silent for the rest of its length."""
        k0, j0 = self.sel
        sec = 60.0 / bpm
        out, q = [], 0.0
        for k in range(max(0, k0), len(self.bars)):
            bar, tys = self.bars[k], self.types[k]
            first = max(0, j0) if k == k0 else 0
            before = sum(ef.quarters(t) for t in tys[:first])
            pos = q
            for j in range(first, len(bar)):
                d = ef.quarters(tys[j])
                if not ef.is_rest(bar[j]):
                    out.append((pos * sec, (pos + d) * sec * 0.95, parse_chord(bar[j]) or [], (k, j)))
                pos += d
            q += max(self.bar_len - before, pos - q)
        return out


# ── drawing it ────────────────────────────────────────────────────────────────────────

class ScoreCanvas(PygameCanvas):
    """The exercise on a page of music paper. Its height follows the music."""

    def __init__(self, model: ScoreModel, key_fn=None, problems_fn=None, **kw):
        kw.setdefault("width", 1.0)
        kw.setdefault("height", 200)
        super().__init__(draw_border=False, **kw)
        self.model = model
        self.key_fn = key_fn or (lambda: 0)
        self.problems_fn = problems_fn or (lambda: set())
        self.focused = False
        self._built = None             # (version, width) the paper was drawn for
        self._paper: pygame.Surface | None = None
        self._map: dict = {}           # (bar, index) → PyLute event
        self._score = None
        self._play = None              # {"t", "events", "on"}
        self.playing_at = None
        self.on_play_change = None

    # ── building the score ──
    def _build(self, width: int):
        from pylute.score import Score
        from pylute.note import Note
        from pylute.rest import Rest
        from pylute.chord import Chord
        m = self.model
        bars = m.bars or [[]]
        types = m.types or [[]]
        clef = m.step.get("clef", "treble")
        score = Score(surface=None, staffs=1, bars=len(bars), clef_types=[clef],
                      key=self.key_fn(), time=m.time, bars_per_system=None)
        staff = score.staffs[0]
        bad = self.problems_fn()
        self._map = {}
        for k, (bar, tys) in enumerate(zip(bars, types)):
            obj = staff.bars[k]
            for j, (e, t) in enumerate(zip(bar, tys)):
                t = t if ef.is_type(t) else "quarter"
                if ef.is_rest(e):
                    ev = Rest(rtype=t, staff=staff)
                else:
                    names = [p.strip() for p in str(e).split("+") if p.strip()]
                    if any(parse_chord(p) is None for p in names) or not names:
                        ev = Rest(rtype=t, staff=staff)          # unreadable: shown as a rest
                    else:
                        notes = [Note(ntype=t, pitch=p, staff=staff) for p in names]
                        ev = notes[0] if len(notes) == 1 else Chord(notes, staff=staff)
                        col = (_PLAYING if self.playing_at == (k, j) else
                               _BLUE if m.sel == (k, j) else
                               (200, 40, 40) if k in bad else None)
                        ev.color = col
                obj.events.append(ev)
                self._map[(k, j)] = ev
            gap = m.bar_len - ef.used(tys)
            if not bar:
                r = Rest(rtype="whole", staff=staff)
                r._layout_dur = m.bar_len / 4
                obj.events.append(r)
            elif gap > 0.124:
                for rt in ef.fill_rests(gap):
                    obj.events.append(Rest(rtype=rt, staff=staff))
        score._on_resize(width)
        h = score.total_content_height(width)
        paper = pygame.Surface((width, max(1, h)))
        paper.fill((255, 255, 255))
        score.surface = paper
        staff.surface = paper
        score.draw()
        self._score, self._paper = score, paper
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

    def _systems(self):
        """[(y of the staff's top line, [bar indices])] per line of music."""
        s = self._score
        return list(zip(s.system_y_tops(), s._layout_systems()))

    def _bar_box(self, k: int):
        sp = self._space()
        for y, bars in self._systems():
            if k in bars:
                b = self._score.staffs[0].bars[k]
                return pygame.Rect(int(b.bar_start_x), int(y - sp * 3), int(b.barspace), int(sp * 10))
        return None

    def hit(self, pos) -> tuple[int, int] | None:
        """The entry (or bar start) at a point on the paper."""
        if self._score is None:
            return None
        x, y = pos
        sp = self._space()
        for top, bars in self._systems():
            if not (top - sp * 4 <= y <= top + sp * 8):
                continue
            for k in bars:
                if k >= len(self.model.bars):
                    continue
                b = self._score.staffs[0].bars[k]
                if b.bar_start_x <= x < b.bar_start_x + b.barspace:
                    evs = [(j, self._map[(k, j)].offset) for j in range(len(self.model.bars[k]))
                           if (k, j) in self._map]
                    if not evs or x < evs[0][1] - sp * 0.6:
                        return (k, -1)
                    nearest = min(evs, key=lambda e: abs(e[1] + sp * 0.6 - x))
                    return (k, nearest[0])
        return None

    # ── drawing ──
    def draw_content(self, surface, rect):
        self._fresh()
        if self._paper is None:
            return
        surface.fill((255, 255, 255), rect)          # paper all the way down while it resizes
        surface.blit(self._paper, rect.topleft)
        sp = self._space()
        k, j = self.model.sel
        ev = self._map.get((k, j))
        box = self._bar_box(k) if k < len(self.model.bars) else None
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
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            inside = self.rect.collidepoint(event.pos)
            self.focused = inside
            _dirty.mark()
            if inside:
                at = self.hit((event.pos[0] - self.rect.left, event.pos[1] - self.rect.top))
                if at is not None:
                    self.model.select(*at)
                    cur = self.model.selected()
                    if cur is not None and not ef.is_rest(cur):
                        from pianove.creator_ui import _sound
                        for m in parse_chord(cur) or []:
                            _sound(m, True)
                        self._click_notes = parse_chord(cur) or []
                    self._sync_palette()
                return True
            return False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and getattr(self, "_click_notes", None):
            from pianove.creator_ui import _sound
            for m in self._click_notes:
                _sound(m, False)
            self._click_notes = None
            return False
        if event.type == pygame.KEYDOWN and self.focused:
            return self._key(event)
        return False

    def _sync_palette(self):
        """The palette shows the selected entry's value (as MuseScore does)."""
        k, j = self.model.sel
        if self.model.selected() is not None:
            t = self.model.types[k][j]
            self.model.dot = t.startswith("dotted_")
            self.model.value = t.replace("dotted_", "", 1) if t.replace("dotted_", "", 1) in VALUES else self.model.value
        _dirty.mark()

    def _key(self, ev) -> bool:
        m = self.model
        ctrl = ev.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
        shift = ev.mod & pygame.KMOD_SHIFT
        k = ev.key
        name = pygame.key.name(k)
        if ctrl and k == pygame.K_z:
            m.redo() if shift else m.undo()
        elif ctrl and k == pygame.K_y:
            m.redo()
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

    def _audition(self):
        cur = self.model.selected()
        if cur is not None and not ef.is_rest(cur):
            from pianove.creator_ui import _sound
            for n in parse_chord(cur) or []:
                _sound(n, True)
            self._audition_off = (_time.monotonic() + 0.4, parse_chord(cur) or [])

    # ── playing ──
    def toggle_play(self):
        if self._play is not None:
            self.stop()
            return
        events = self.model.schedule()
        if not events:
            return
        self._play = {"t": 0.0, "events": events, "on": {}}
        if self.on_play_change:
            self.on_play_change(True)

    def stop(self):
        from pianove.creator_ui import _sound
        if self._play:
            for m in list(self._play["on"]):
                _sound(m, False)
        self._play = None
        self.playing_at = None
        _dirty.mark()
        if self.on_play_change:
            self.on_play_change(False)

    @property
    def is_playing(self) -> bool:
        return self._play is not None

    def update_content(self, dt):
        from pianove.creator_ui import TextBox, _sound
        if self.focused and TextBox._focused is not None:
            self.focused = False
            _dirty.mark()
        off = getattr(self, "_audition_off", None)
        if off and _time.monotonic() > off[0]:
            for n in off[1]:
                _sound(n, False)
            self._audition_off = None
        if self._play is None:
            return
        p = self._play
        p["t"] += dt
        t = p["t"]
        at = None
        for start, end, midis, where in p["events"]:
            if start <= t < end:
                at = where
                for m in midis:
                    if m not in p["on"]:
                        _sound(m, True)
                        p["on"][m] = end
        for m, end in list(p["on"].items()):
            if t >= end:
                _sound(m, False)
                del p["on"][m]
        if at != self.playing_at:
            self.playing_at = at
            _dirty.mark()
        if t > p["events"][-1][1] + 0.1:
            self.stop()

    def update(self, dt):
        self.update_content(dt)
        UIElement.update(self, dt)


# ── a palette button with a note glyph ────────────────────────────────────────────────

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

    def render(self, surface):
        r = self.rect
        active = self.active_fn()
        bg = ColorPalette.BLUE if active else iOSTheme.fill
        pygame.draw.rect(surface, bg, r, border_radius=max(4, r.height // 4))
        fg = (255, 255, 255) if active else tuple(iOSTheme.label)[:3]
        f = _glyph_font(max(8, int(r.height * 0.62)))
        g = _GLYPHS[self.glyph]
        ink = f.get_rect(g)                  # the glyph's ink, centred in the button
        ink.center = r.center
        f.render_to(surface, ink, g, fg)


class TextToggle(GlyphButton):
    """A palette button with a word on it (its text may change: Play / Stop)."""

    def __init__(self, text_fn, on_click, active_fn=lambda: False):
        from pianove.creator_ui import px, text_w
        super().__init__("dot", on_click, active_fn)
        self.text_fn = text_fn
        self.width_spec = max(px(40), text_w(text_fn(), 13) + px(24), text_w("■ " + text_fn(), 13) + px(24))

    def render(self, surface):
        from pianove.creator_ui import font
        r = self.rect
        active = self.active_fn()
        pygame.draw.rect(surface, ColorPalette.BLUE if active else iOSTheme.fill, r,
                         border_radius=max(4, r.height // 4))
        fg = (255, 255, 255) if active else iOSTheme.label
        ts = font(13, bold=True).render(self.text_fn(), True, fg)
        surface.blit(ts, ts.get_rect(center=r.center))

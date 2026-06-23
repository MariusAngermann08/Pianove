import pygame as pg
from .font import get_font
from .pitch import pitch_to_step, parse_pitch
from .note import NOTEHEAD_BLACK, WHOLE, AUG_DOT, ACCIDENTAL_GLYPHS, GLYPHS as NOTE_GLYPHS, STEM_SPACES

DEBUG = "[OpenScore-Debug]"


class Chord:
    def __init__(self, notes: list, staff=None):
        self.notes  = sorted(notes, key=lambda n: _step(n), reverse=True)
        self.staff  = staff
        self.offset = 0
        self.beamed = False
        self.color  = None  # None = per-note

        for n in self.notes:
            n.staff = staff

    @property
    def type(self):
        return self.notes[0].type

    @property
    def pitch(self):
        return self.notes[0].pitch

    @property
    def _base_type(self):
        return self.notes[0]._base_type

    @property
    def _is_dotted(self):
        return self.notes[0]._is_dotted

    # tie lives on the top note
    @property
    def tied_to(self):
        return self.notes[0].tied_to

    @tied_to.setter
    def tied_to(self, v):
        self.notes[0].tied_to = v

    @property
    def tied_from(self):
        return self.notes[0].tied_from

    @tied_from.setter
    def tied_from(self, v):
        self.notes[0].tied_from = v

    def _stem_dir(self):
        if self._base_type == "whole":
            return "up"
        # median note decides direction
        steps = [_step(n) for n in self.notes]
        median = steps[len(steps) // 2]
        return "up" if median < 4 else "down"

    def _y_center(self):
        # outermost note in stem direction for beam geometry
        if self._stem_dir() == "up":
            return min(_yc(n, self.staff) for n in self.notes)
        return max(_yc(n, self.staff) for n in self.notes)

    def _stem_x(self):
        font = get_font()
        hr   = font.get_rect(NOTEHEAD_BLACK)
        if self._stem_dir() == "up":
            return int(self.offset + hr.x + hr.width - 1)
        return int(self.offset + hr.x + 1)

    def _stem_tip_y(self):
        if self._stem_dir() == "up":
            outer = min(_yc(n, self.staff) for n in self.notes)
            return outer - self.staff.space * STEM_SPACES
        else:
            outer = max(_yc(n, self.staff) for n in self.notes)
            return outer + self.staff.space * STEM_SPACES

    def draw(self):
        if not self.staff:
            print(f"{DEBUG} <Chord> object needs :staff: to be drawn")
            return

        font     = get_font()
        space    = self.staff.space
        stem_dir = self._stem_dir()
        head_ref = font.get_rect(WHOLE)
        surface  = self.staff.surface

        sorted_notes = sorted(self.notes, key=lambda n: _step(n))
        offsets = _compute_head_offsets(sorted_notes, self.staff, stem_dir, font)

        for note in self.notes:
            note.offset = self.offset + offsets.get(id(note), 0)
            note._draw_ledger_lines(_yc(note, self.staff), head_ref, _color(note, self.color))

        self._draw_accidentals(font, sorted_notes, offsets)

        for note in self.notes:
            x_off = offsets.get(id(note), 0)
            yc    = _yc(note, self.staff)
            col   = _color(note, self.color)

            if self.beamed:
                hr    = font.get_rect(NOTEHEAD_BLACK)
                pos_y = int(yc - hr.height / 2)
                font.render_to(surface, (int(self.offset + x_off), pos_y), NOTEHEAD_BLACK, col)
            else:
                glyph = NOTE_GLYPHS.get((self._base_type, stem_dir),
                                        NOTE_GLYPHS.get((self._base_type, "up"), NOTEHEAD_BLACK))
                gh    = font.get_rect(glyph).height
                if stem_dir == "up":
                    pos_y = int(yc - gh + head_ref.height / 2)
                else:
                    pos_y = int(yc - head_ref.height / 2)
                font.render_to(surface, (int(self.offset + x_off), pos_y), glyph, col)

            if note._is_dotted:
                note._draw_dot(font, yc)

    def _draw_accidentals(self, font, sorted_notes, offsets):
        space = self.staff.space
        pending = []
        for note in sorted_notes:
            name, written_acc, _ = parse_pitch(note.pitch)
            acc = note._resolve_accidental(name, written_acc)
            if acc:
                pending.append((note, acc))

        if not pending:
            return

        acc_col   = {}
        acc_width = font.get_rect(ACCIDENTAL_GLYPHS.get("#", chr(0xE262))).width + int(space * 0.2)
        columns   = []  # (top_y, bot_y) per column, right to left
        for note, acc in reversed(pending):
            yc   = _yc(note, self.staff)
            h    = font.get_rect(ACCIDENTAL_GLYPHS[acc]).height
            top  = yc - h / 2 - 2
            bot  = yc + h / 2 + 2
            placed = False
            for ci, (ct, cb) in enumerate(columns):
                if top > cb or bot < ct:
                    columns[ci] = (min(ct, top), max(cb, bot))
                    acc_col[id(note)] = ci
                    placed = True
                    break
            if not placed:
                acc_col[id(note)] = len(columns)
                columns.append((top, bot))

        max_col = max(acc_col.values()) if acc_col else 0
        for note, acc in pending:
            ci      = acc_col.get(id(note), 0)
            x_shift = -(max_col - ci) * acc_width
            note._draw_accidental(font, _yc(note, self.staff), acc,
                                   _color(note, self.color), x_offset=x_shift)


def _step(note):
    clef = getattr(note.staff, "clef_type", "treble") if note.staff else "treble"
    return pitch_to_step(note.pitch, clef)


def _yc(note, staff):
    clef = getattr(staff, "clef_type", "treble")
    step = pitch_to_step(note.pitch, clef)
    return staff.position[1] + 4 * staff.space - step * (staff.space / 2)


def _color(note, chord_color):
    if chord_color is not None:
        return tuple(chord_color)
    if note.color is not None:
        return tuple(note.color)
    return (0, 0, 0)


def _compute_head_offsets(sorted_notes, staff, stem_dir, font):
    # 2nd intervals: one notehead has to move right so they don't overlap
    hr = font.get_rect(NOTEHEAD_BLACK)
    nw = hr.width
    offsets = {id(n): 0 for n in sorted_notes}
    steps   = [_step(n) for n in sorted_notes]

    i = 0
    while i < len(steps) - 1:
        diff = abs(steps[i + 1] - steps[i])
        if diff == 1:
            if stem_dir == "up":
                offsets[id(sorted_notes[i + 1])] = nw
            else:
                offsets[id(sorted_notes[i])] = nw
            i += 2  # skip both so we don't triple-offset
        else:
            i += 1

    return offsets

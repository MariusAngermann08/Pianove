import pygame as pg
from .font import get_font
from .pitch import pitch_to_step, parse_pitch

DEBUG = "[OpenScore-Debug]"

ACCIDENTAL_GLYPHS = {
    "#": chr(0xE262),
    "b": chr(0xE260),
    "n": chr(0xE261),
}

GLYPHS = {
    ("whole",         "up"):   chr(0xE1D2),
    ("whole",         "down"): chr(0xE1D2),
    ("half",          "up"):   chr(0xE1D3),
    ("half",          "down"): chr(0xE1D4),
    ("quarter",       "up"):   chr(0xE1D5),
    ("quarter",       "down"): chr(0xE1D6),
    ("eighth",        "up"):   chr(0xE1D7),
    ("eighth",        "down"): chr(0xE1D8),
    ("sixteenth",     "up"):   chr(0xE1D9),
    ("sixteenth",     "down"): chr(0xE1DA),
    ("thirty_second", "up"):   chr(0xE1DB),
    ("thirty_second", "down"): chr(0xE1DC),
}

WHOLE          = chr(0xE1D2)
NOTEHEAD_BLACK = chr(0xE0A4)
AUG_DOT        = chr(0xE1E7)
STEM_SPACES    = 3.5


class Note:
    def __init__(self, ntype="whole", pitch="C4", staff=None):
        self.type   = ntype
        self.pitch  = pitch
        self.staff  = staff
        self.offset = 0
        self.beamed = False
        self.color  = None  # None = black
        self.tied_to   = None
        self.tied_from = False
        self.expressions: list = []

    @property
    def _base_type(self):
        return self.type[7:] if self.type.startswith("dotted_") else self.type

    @property
    def _is_dotted(self):
        return self.type.startswith("dotted_")

    def _stem_dir(self, voice=1):
        if self._base_type == "whole":
            return "up"
        if voice == 2:
            return "down"
        clef = getattr(self.staff, "clef_type", "treble")
        return "up" if pitch_to_step(self.pitch, clef) < 4 else "down"

    def _y_center(self):
        clef = getattr(self.staff, "clef_type", "treble")
        step = pitch_to_step(self.pitch, clef)
        return self.staff.position[1] + 4 * self.staff.space - step * (self.staff.space / 2)

    def _stem_x(self):
        font = get_font()
        hr   = font.get_rect(NOTEHEAD_BLACK)
        if self._stem_dir() == "up":
            return int(self.offset + hr.x + hr.width - 1)
        return int(self.offset + hr.x + 1)

    def _stem_tip_y(self):
        y = self._y_center()
        d = self.staff.space * STEM_SPACES
        return y - d if self._stem_dir() == "up" else y + d

    def _draw_ledger_lines(self, y_center, head_rect, color=(0, 0, 0)):
        clef     = getattr(self.staff, "clef_type", "treble")
        step     = pitch_to_step(self.pitch, clef)
        surface  = self.staff.surface
        half_spc = self.staff.space / 2
        margin   = head_rect.width * 0.15
        lx = int(self.offset + head_rect.x - margin)
        lw = int(head_rect.width + 2 * margin)

        if step <= -2:
            for s in range(-2, step - 1, -2):
                y = int(self.staff.position[1] + 4 * self.staff.space - s * half_spc)
                pg.draw.line(surface, color, (lx, y), (lx + lw, y), 2)
        elif step >= 10:
            for s in range(10, step + 2, 2):
                y = int(self.staff.position[1] + 4 * self.staff.space - s * half_spc)
                pg.draw.line(surface, color, (lx, y), (lx + lw, y), 2)

    def _resolve_accidental(self, note_name, written_acc):
        shown = getattr(self, "_shown_acc", None)
        if shown is not None:                 # worked out for the whole bar (Bar.draw)
            return shown
        key_notes = getattr(self.staff.score, "key_notes", {}) if self.staff else {}
        key_acc   = key_notes.get(note_name, "")
        if written_acc == key_acc:
            return ""
        if not written_acc and key_acc:
            return "n"  # natural cancels the key signature
        return written_acc

    def _draw_accidental(self, font, y_center, acc, color=(0, 0, 0), x_offset=0):
        if acc not in ACCIDENTAL_GLYPHS:
            return
        acc_char = ACCIDENTAL_GLYPHS[acc]
        acc_rect = font.get_rect(acc_char)
        font.render_to(self.staff.surface,
                       (int(self.offset) - acc_rect.width + x_offset,
                        int(y_center - acc_rect.height / 2)),
                       acc_char, color)

    def _draw_dot(self, font, y_center):
        clef = getattr(self.staff, "clef_type", "treble")
        step = pitch_to_step(self.pitch, clef)
        # dot moves up a half-step if notehead sits on a line
        dot_yc = y_center - self.staff.space / 2 if step % 2 == 0 else y_center
        hr  = font.get_rect(NOTEHEAD_BLACK)
        dr  = font.get_rect(AUG_DOT)
        dot_x = int(self.offset + hr.x + hr.width + 3)
        dot_y = int(dot_yc - dr.height / 2)
        font.render_to(self.staff.surface, (dot_x, dot_y), AUG_DOT, "Black")

    def draw(self):
        if not self.staff:
            print(f"{DEBUG} <Note> object needs :staff: to be drawn")
            return

        font     = get_font()
        y_center = self._y_center()
        name, written_acc, _ = parse_pitch(self.pitch)
        acc = self._resolve_accidental(name, written_acc)
        head_ref = font.get_rect(WHOLE)
        color = tuple(self.color) if self.color is not None else (0, 0, 0)

        self._draw_ledger_lines(y_center, head_ref, color)
        self._draw_accidental(font, y_center, acc, color)

        if self.beamed:
            hr    = font.get_rect(NOTEHEAD_BLACK)
            pos_y = int(y_center - hr.height / 2)
            font.render_to(self.staff.surface, (int(self.offset), pos_y), NOTEHEAD_BLACK, color)
        else:
            stem_dir = self._stem_dir()
            glyph    = GLYPHS.get((self._base_type, stem_dir), GLYPHS.get((self._base_type, "up"), NOTEHEAD_BLACK))
            glyph_h  = font.get_rect(glyph).height

            if stem_dir == "up":
                pos_y = int(y_center - glyph_h + head_ref.height / 2)
            else:
                pos_y = int(y_center - head_ref.height / 2)

            font.render_to(self.staff.surface, (int(self.offset), pos_y), glyph, color)

        if self._is_dotted:
            self._draw_dot(font, y_center)

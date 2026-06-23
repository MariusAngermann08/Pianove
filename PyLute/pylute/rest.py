from .font import get_font

DEBUG = "[OpenScore-Debug]"

GLYPHS = {
    "whole":         chr(0xE4E3),
    "half":          chr(0xE4E4),
    "quarter":       chr(0xE4E5),
    "eighth":        chr(0xE4E6),
    "sixteenth":     chr(0xE4E7),
    "thirty_second": chr(0xE4E8),
}

AUG_DOT = chr(0xE1E7)


class Rest:
    def __init__(self, rtype="quarter", staff=None):
        self.type   = rtype
        self.staff  = staff
        self.offset = 0

    @property
    def _base_type(self):
        return self.type[7:] if self.type.startswith("dotted_") else self.type

    @property
    def _is_dotted(self):
        return self.type.startswith("dotted_")

    def _line_y(self, step):
        return self.staff.position[1] + 4 * self.staff.space - step * (self.staff.space / 2)

    def _draw_dot(self, font, rest_y):
        import pygame as pg
        dr    = font.get_rect(AUG_DOT)
        glyph = GLYPHS.get(self._base_type, "")
        gw = font.get_rect(glyph).width if glyph else int(self.staff.space * 1.2)
        dot_x = int(self.offset + gw + 3)
        dot_y = int(rest_y - dr.height / 2)
        font.render_to(self.staff.surface, (dot_x, dot_y), AUG_DOT, "Black")

    def draw(self):
        if not self.staff:
            print(f"{DEBUG} <Rest> object needs :staff: to be drawn")
            return

        font  = get_font()
        glyph = GLYPHS.get(self._base_type)
        if not glyph:
            return

        glyph_h = font.get_rect(glyph).height

        if self._base_type == "whole":
            pos_y = int(self._line_y(6))
        elif self._base_type == "half":
            pos_y = int(self._line_y(4) - glyph_h)
        else:
            pos_y = int(self._line_y(4) - glyph_h / 2)

        font.render_to(self.staff.surface, (int(self.offset), pos_y), glyph, "Black")

        if self._is_dotted:
            self._draw_dot(font, pos_y + glyph_h / 2)

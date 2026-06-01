from .font import get_font

DEBUG = "[OpenScore-Debug]"

GLYPHS = {
    "whole":     "",
    "half":      "",
    "quarter":   "",
    "eighth":    "",
    "sixteenth": "",
}

class Rest:
    def __init__(self, rtype="quarter", staff=None):
        self.type   = rtype
        self.staff  = staff
        self.offset = 0

    def _line_y(self, step):
        return self.staff.position[1] + 4 * self.staff.space - step * (self.staff.space / 2)

    def draw(self):
        if not self.staff:
            print(f"{DEBUG} <Rest> object needs :staff: to be drawn")
            return

        font  = get_font()
        glyph = GLYPHS.get(self.type)
        if not glyph:
            return

        glyph_h = font.get_rect(glyph).height

        if self.type == "whole":
            pos_y = int(self._line_y(6))
        elif self.type == "half":
            pos_y = int(self._line_y(4) - glyph_h)
        else:
            pos_y = int(self._line_y(4) - glyph_h / 2)

        font.render_to(self.staff.surface, (int(self.offset), pos_y), glyph, "Black")

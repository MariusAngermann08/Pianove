from .font import get_font

DEBUG = "[OpenScore-Debug]"

GLYPHS = {
    "treble": "",
    "bass":   "",
}

class Clef:
    def __init__(self, ctype="treble", staff=None):
        self.type  = ctype
        self.staff = staff

    def draw(self, x):
        if not self.staff:
            print(f"{DEBUG} <Clef> object needs :staff: to be drawn")
            return

        font  = get_font()
        glyph = GLYPHS.get(self.type)
        if not glyph:
            return

        if self.type == "treble":
            pos_y = self.staff.position[1] - 2 * (self.staff.space / 2)
        else:
            rect  = font.get_rect(glyph)
            f_y   = self.staff.position[1] + self.staff.space
            pos_y = f_y - rect.height * 0.35

        font.render_to(self.staff.surface, (int(x), int(pos_y)), glyph, "Black")

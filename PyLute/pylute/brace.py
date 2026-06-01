from .font import get_font, get_font_size, make_font

class Brace:
    GLYPH = ""

    def __init__(self, staves, surface):
        self.staves  = staves
        self.surface = surface
        self._font   = None
        self._pos_x  = None
        self._pos_y  = None

    def _build(self):
        top = self.staves[0]
        bot = self.staves[-1]
        span     = bot.position[1] + 4 * bot.space - top.position[1]
        natural_h = get_font().get_rect(self.GLYPH).height
        if natural_h == 0:
            return
        scaled_font  = make_font(int(get_font_size() * span / natural_h))
        glyph_rect   = scaled_font.get_rect(self.GLYPH)
        self._font   = scaled_font
        self._pos_x  = top.position[0] - glyph_rect.width - 4
        self._pos_y  = top.position[1]

    def reset(self):
        self._font  = None
        self._pos_x = None
        self._pos_y = None

    def draw(self):
        if len(self.staves) < 2:
            return
        if self._font is None:
            self._build()
        if self._font is None:
            return
        self._font.render_to(self.surface, (int(self._pos_x), int(self._pos_y)), self.GLYPH, "Black")

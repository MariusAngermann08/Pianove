from .font import get_font

DEBUG = "[OpenScore-Debug]"

# SMuFL time signature digits: U+E080 (0) through U+E089 (9)
DIGITS = {str(i): chr(0xE080 + i) for i in range(10)}


class TimeSignature:
    def __init__(self, staff=None):
        self.staff    = staff
        self._width   = None

    @property
    def width(self):
        if self._width is None:
            font = get_font()
            time = self.staff.score.time
            top_w = sum(font.get_rect(DIGITS[d]).width for d in str(time[0]))
            bot_w = sum(font.get_rect(DIGITS[d]).width for d in str(time[1]))
            self._width = max(top_w, bot_w)
        return self._width

    def draw(self, x):
        if not self.staff:
            print(f"{DEBUG} <TimeSignature> object needs :staff: to be drawn")
            return


        # get link to bravura font
        font  = get_font()
        time  = self.staff.score.time
        total = self.width
        spc   = self.staff.space

        for number, top_y in [
            (time[0], self.staff.position[1] + spc * 0.5),
            (time[1], self.staff.position[1] + spc * 2.5),
        ]:
            digits = str(number)
            num_w  = sum(font.get_rect(DIGITS[d]).width for d in digits)
            cx     = x + (total - num_w) / 2
            for d in digits:
                glyph = DIGITS[d]
                font.render_to(self.staff.surface, (int(cx), int(top_y)), glyph, "Black")
                cx += font.get_rect(glyph).width

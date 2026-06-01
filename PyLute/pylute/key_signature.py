from .font import get_font

# Diatonic step positions for accidentals within each clef.
# Step 0 = bottom staff line.
SHARP_STEPS = {
    "treble": [8, 5, 9, 6, 3, 7, 4],
    "bass":   [6, 3, 7, 4, 1, 5, 2],
}
FLAT_STEPS = {
    "treble": [4, 7, 3, 6, 2, 5, 1],
    "bass":   [2, 5, 1, 4, 7, 3, 6],
}

# Major key name → signed accidental count (+sharps, -flats)
KEY_ACCIDENTALS = {
    "C": 0,
    "G": 1,  "D": 2,  "A": 3,  "E": 4,  "B": 5,  "F#": 6,  "C#": 7,
    "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7,
}

SHARP_GLYPH = ""
FLAT_GLYPH  = ""

def parse_key(key):
    """"G" -> 1, "Bb" -> -2, 0 -> 0, etc."""
    if isinstance(key, int):
        return key
    return KEY_ACCIDENTALS.get(key, 0)


class KeySignature:
    def __init__(self, accidentals=0, staff=None):
        self.accidentals = accidentals
        self.staff = staff
        self._width = None

    @property
    def width(self):
        if self._width is None:
            n = abs(self.accidentals)
            if n == 0:
                self._width = 0
            else:
                font  = get_font()
                glyph = SHARP_GLYPH if self.accidentals > 0 else FLAT_GLYPH
                self._width = n * (font.get_rect(glyph).width + 2)
        return self._width

    def draw(self, x):
        if not self.staff or self.accidentals == 0:
            return

        font  = get_font()
        clef  = getattr(self.staff, "clef_type", "treble")
        n     = abs(self.accidentals)

        if self.accidentals > 0:
            steps = SHARP_STEPS.get(clef, SHARP_STEPS["treble"])[:n]
            glyph = SHARP_GLYPH
        else:
            steps = FLAT_STEPS.get(clef, FLAT_STEPS["treble"])[:n]
            glyph = FLAT_GLYPH

        rect     = font.get_rect(glyph)
        acc_step = rect.width + 2

        for step in steps:
            y_center = self.staff.position[1] + 4 * self.staff.space - step * (self.staff.space / 2)
            pos_y = int(y_center - rect.height / 2)
            font.render_to(self.staff.surface, (int(x), pos_y), glyph, "Black")
            x += acc_step

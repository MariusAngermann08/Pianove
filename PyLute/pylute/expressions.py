import pygame as pg

DYNAMIC_GLYPHS = {
    "pppp": chr(0xE529),
    "ppp":  chr(0xE52A),
    "pp":   chr(0xE52B),
    "p":    chr(0xE520),
    "mp":   chr(0xE52C),
    "mf":   chr(0xE52D),
    "f":    chr(0xE522),
    "ff":   chr(0xE52F),
    "fff":  chr(0xE530),
    "ffff": chr(0xE531),
    "sf":   chr(0xE523),
    "sfz":  chr(0xE524),
    "sfp":  chr(0xE525),
    "rfz":  chr(0xE527),
    "fz":   chr(0xE526),
    "fp":   chr(0xE534),
}

ARTICULATION_GLYPHS = {
    "staccato":      chr(0xE4A2),
    "accent":        chr(0xE4A0),
    "tenuto":        chr(0xE4A4),
    "marcato":       chr(0xE4AC),
    "fermata":       chr(0xE4C0),
    "staccatissimo": chr(0xE4A6),
    "stress":        chr(0xE4B8),
    "unstress":      chr(0xE4BA),
}

# maps musicxml tag names to our internal names
_XML_ARTICULATIONS = {
    "staccato":      "staccato",
    "accent":        "accent",
    "strong-accent": "marcato",
    "tenuto":        "tenuto",
    "staccatissimo": "staccatissimo",
    "stress":        "stress",
    "unstress":      "unstress",
}

_XML_DYNAMICS = {"pp", "p", "mp", "mf", "f", "ff", "fff", "ffff",
                 "ppp", "pppp", "sf", "sfz", "sfp", "rfz", "fz", "fp"}


class Dynamic:
    def __init__(self, mark: str, staff=None, above: bool = False):
        self.mark   = mark.lower()
        self.staff  = staff
        self.above  = above
        self.offset = 0  # filled in by bar before draw

    def draw(self):
        if not self.staff:
            return
        from .font import get_font
        font  = get_font()
        space = self.staff.space
        glyph = DYNAMIC_GLYPHS.get(self.mark)
        if not glyph:
            return
        gh = font.get_rect(glyph).height
        if self.above:
            y = int(self.staff.position[1] - space * 1.5 - gh)
        else:
            y = int(self.staff.position[1] + 4 * space + space * 1.5)
        font.render_to(self.staff.surface, (int(self.offset), y), glyph, (0, 0, 0))


class Articulation:
    def __init__(self, mark: str, staff=None, above: bool = True):
        self.mark   = mark.lower()
        self.staff  = staff
        self.above  = above
        self.offset = 0
        self.note_y = 0  # set by bar before draw

    def draw(self):
        if not self.staff:
            return
        from .font import get_font
        font  = get_font()
        space = self.staff.space
        glyph = ARTICULATION_GLYPHS.get(self.mark)
        if not glyph:
            return
        gh = font.get_rect(glyph).height
        gw = font.get_rect(glyph).width
        if self.above:
            y = int(self.note_y - space * 1.2 - gh)
        else:
            y = int(self.note_y + space * 0.8)
        font.render_to(self.staff.surface,
                       (int(self.offset) - gw // 2, y),
                       glyph, (0, 0, 0))

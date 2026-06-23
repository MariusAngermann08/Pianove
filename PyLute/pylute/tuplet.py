import pygame as pg
from .font import get_font
from .durations import get_value, VALUES

DEBUG = "[OpenScore-Debug]"


class Tuplet:
    def __init__(self, notes: list, actual: int = 3, normal: int = 2, staff=None):
        self.notes  = notes
        self.actual = actual
        self.normal = normal
        self.staff  = staff
        self.offset = 0  # set by calculateMetrics
        self.beamed = False
        self.color  = None

        for n in self.notes:
            n.staff = staff

    @property
    def type(self):
        return self.notes[0].type if self.notes else "quarter"

    @property
    def _base_type(self):
        t = self.type
        return t[7:] if t.startswith("dotted_") else t

    @property
    def _is_dotted(self):
        return self.type.startswith("dotted_")

    def total_duration(self) -> float:
        if not self.notes:
            return 0.0
        base_dur = get_value(self.notes[0].type)
        return base_dur * self.actual * (self.normal / self.actual)

    # stubs so Bar beam code doesn't crash on a Tuplet
    def _stem_dir(self):
        return self.notes[0]._stem_dir() if self.notes else "up"

    def _y_center(self):
        return self.notes[0]._y_center() if self.notes else 0

    def _stem_x(self):
        return self.notes[0]._stem_x() if self.notes else 0

    def _stem_tip_y(self):
        return self.notes[0]._stem_tip_y() if self.notes else 0

    def draw(self):
        if not self.staff or not self.notes:
            return

        for note in self.notes:
            note.staff = self.staff
            note.draw()

        self._draw_bracket()

    def _draw_bracket(self):
        if not self.notes:
            return
        import pygame as pg
        pg.font.init()
        surface  = self.staff.surface
        space    = self.staff.space
        font_sz  = max(9, int(space * 1.5))
        ui_font  = pg.font.SysFont("Arial", font_sz)

        label    = str(self.actual)
        surf_lbl = ui_font.render(label, True, (0, 0, 0))
        lw, lh   = surf_lbl.get_size()

        stem_dir = self._stem_dir()
        x1 = self.notes[0].offset
        x2 = self.notes[-1].offset + int(space * 1.2)
        mid_x = (x1 + x2) // 2

        if stem_dir == "up":
            tip_y     = min(n._stem_tip_y() for n in self.notes) - int(space * 0.5)
            bracket_y = int(tip_y) - lh - 2
        else:
            tip_y     = max(n._stem_tip_y() for n in self.notes) + int(space * 0.5)
            bracket_y = int(tip_y) + 2

        surface.blit(surf_lbl, (mid_x - lw // 2, bracket_y))

        arm_y = bracket_y + lh // 2
        gap   = lw // 2 + 3
        if x2 - x1 > lw + 12:
            pg.draw.line(surface, (0, 0, 0), (int(x1), arm_y), (mid_x - gap, arm_y), 1)
            pg.draw.line(surface, (0, 0, 0), (mid_x + gap, arm_y), (int(x2), arm_y), 1)
            tick = int(space * 0.3)
            pg.draw.line(surface, (0, 0, 0), (int(x1), arm_y), (int(x1), arm_y - tick), 1)
            pg.draw.line(surface, (0, 0, 0), (int(x2), arm_y), (int(x2), arm_y - tick), 1)

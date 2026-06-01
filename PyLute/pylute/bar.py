import pygame as pg
from .durations import get_value
from .font import get_font
from .pitch import parse_pitch as _parse_pitch

DEBUG = "[OpenScore-Debug]"

BEAM_H   = 4   # beam rectangle height in px
BEAM_GAP = 3   # gap between primary / secondary beams

def _flag_glyphs():
    return {
        ("eighth",    "up"):   chr(0xE240),
        ("eighth",    "down"): chr(0xE241),
        ("sixteenth", "up"):   chr(0xE242),
        ("sixteenth", "down"): chr(0xE243),
    }
FLAG_GLYPHS = _flag_glyphs()


class Bar:
    def __init__(self, staff=None, index=0):
        self.staff  = staff
        self.index  = index
        self.events = []
        self.barspace    = 0
        self.bar_start_x = 0
        self.system_bar_count   = None
        self.system_local_index = None
        self.updateTimeSignature()

    def updateTimeSignature(self):
        if self.staff:
            self.time = self.staff.score.time
        else:
            print(f"{DEBUG} <Bar> object needs :staff: to update its time signature")

    def spaceAvailable(self):
        used = sum(get_value(e.type) for e in self.events)
        return (self.time[0] / self.time[1]) - used

    # ---------------------------------------------------- accidental pre-space

    def _acc_pre(self, event):
        """Pixels to advance before event.offset to clear its accidental glyph."""
        from .note import Note, ACCIDENTAL_GLYPHS
        if not isinstance(event, Note) or not event.staff:
            return 0
        name, written_acc, _ = _parse_pitch(event.pitch)
        key_notes = getattr(event.staff.score, "key_notes", {})
        key_acc   = key_notes.get(name, "")
        if written_acc == key_acc:
            acc = ""
        elif not written_acc and key_acc:
            acc = "n"
        else:
            acc = written_acc
        if not acc or acc not in ACCIDENTAL_GLYPHS:
            return 0
        glyph = ACCIDENTAL_GLYPHS[acc]
        if not glyph:
            return 0
        font  = get_font()
        space = event.staff.space
        return font.get_rect(glyph).width + int(space * 0.35)

    # ------------------------------------------------------------ layout

    def calculateMetrics(self, bar_start_x=None, barspace=None, frontal_offset=None):
        if bar_start_x is not None:
            self.bar_start_x = bar_start_x
            self.barspace    = barspace
        else:
            if frontal_offset is None:
                frontal_offset = self.staff.score.frontal_offset
            n_bars    = self.system_bar_count   if self.system_bar_count   is not None else len(self.staff.bars)
            local_idx = self.system_local_index if self.system_local_index is not None else self.index
            avail          = self.staff.length - frontal_offset
            self.barspace  = avail / n_bars
            self.bar_start_x = self.staff.position[0] + frontal_offset + self.barspace * local_idx

        barindent    = self.barspace * 0.1
        usable_space = self.barspace - 2 * barindent

        count = len(self.events)
        if count == 0:
            return

        # Pre-margins for accidentals: reserve measured glyph width + small gap
        pres      = [self._acc_pre(e) for e in self.events]
        total_acc = sum(pres)
        # Shrink the beat-width proportionally so total bar width stays fixed
        adj_usable = max(usable_space - total_acc, usable_space * 0.45)

        if count == 1:
            pre = pres[0]
            self.events[0].offset = (self.bar_start_x + barindent + pre
                                     + (adj_usable - pre) / 2)
            return

        total_duration = sum(get_value(e.type) for e in self.events)
        beat_width = adj_usable / total_duration
        x = self.bar_start_x + barindent
        for pre, event in zip(pres, self.events):
            x += pre
            event.offset = x
            x += get_value(event.type) * beat_width

    # --------------------------------------------------------------- beaming

    def _find_beam_groups(self):
        """Group consecutive flagged notes within the same beat.

        Beat boundary = 1/time[1] whole-note fraction (one quarter in 4/4).
        Single-note groups get a flag glyph; multi-note groups share a beam.
        """
        from .note import Note
        beat_dur = 1.0 / self.time[1]   # e.g. 0.25 for 4/4
        groups, current = [], []
        pos          = 0.0
        group_beat   = -1

        for event in self.events:
            dur  = get_value(event.type)
            beat = int(pos / beat_dur + 1e-9)

            if isinstance(event, Note) and event._base_type in ("eighth", "sixteenth"):
                if current and beat != group_beat:
                    groups.append(current)
                    current = []
                if not current:
                    group_beat = beat
                current.append(event)
            else:
                if current:
                    groups.append(current)
                    current = []
                group_beat = -1

            pos += dur

        if current:
            groups.append(current)
        return groups

    def _draw_beams(self, groups):
        from .note import NOTEHEAD_BLACK, STEM_SPACES as _ST
        if not groups:
            return
        font    = get_font()
        surface = self.staff.surface
        space   = self.staff.space

        for group in groups:
            stem_dir  = group[0]._stem_dir()
            stem_sign = -1 if stem_dir == "up" else 1   # direction away from noteheads

            # ── isolated note: draw stem + flag glyph ────────────────────────
            if len(group) == 1:
                note = group[0]
                sx   = note._stem_x()
                yc   = int(note._y_center())
                ty   = int(note._stem_tip_y())
                if stem_dir == "up":
                    pg.draw.line(surface, (0, 0, 0), (sx, ty), (sx, yc), 2)
                else:
                    pg.draw.line(surface, (0, 0, 0), (sx, yc), (sx, ty), 2)
                flag = FLAG_GLYPHS.get((note._base_type, stem_dir))
                if flag:
                    fr = font.get_rect(flag)
                    fy = ty if stem_dir == "up" else ty - fr.height
                    font.render_to(surface, (sx, fy), flag, "Black")
                continue

            # ── multi-note group: sloped beam ─────────────────────────────────
            x1 = group[0]._stem_x()
            x2 = group[-1]._stem_x()
            dx = max(x2 - x1, 1)

            # Natural beam edge for each endpoint (outer note stem tip)
            y_start = group[0]._y_center()  + stem_sign * space * _ST
            y_end   = group[-1]._y_center() + stem_sign * space * _ST

            # Clamp slope: max 2 staff spaces across the full group width.
            # Also snap near-horizontal slopes to flat.
            dy     = y_end - y_start
            max_dy = space * 2.0
            dy     = max(min(dy, max_dy), -max_dy)
            if abs(dy) < space * 0.5:
                dy = 0.0
            y_end = y_start + dy

            # Push the beam away from noteheads so every stem is at least _ST long.
            shift = 0.0
            for note in group:
                nx = note._stem_x()
                t  = (nx - x1) / dx
                by = y_start + t * dy
                yc = note._y_center()
                if stem_dir == "up":
                    need = yc - space * _ST
                    if by > need:
                        shift = max(shift, by - need)
                else:
                    need = yc + space * _ST
                    if by < need:
                        shift = max(shift, need - by)

            # stem_sign is -1 for "up" → subtract shift (beam moves up)
            #             +1 for "down" → add shift (beam moves down)
            y_start += stem_sign * shift
            y_end   += stem_sign * shift

            # Draw stems
            for note in group:
                nx = note._stem_x()
                t  = (nx - x1) / dx
                by = int(y_start + t * dy)
                yc = int(note._y_center())
                if stem_dir == "up":
                    pg.draw.line(surface, (0, 0, 0), (nx, by), (nx, yc), 2)
                else:
                    pg.draw.line(surface, (0, 0, 0), (nx, yc), (nx, by), 2)

            # Draw beam(s) as filled polygons — 1 beam for eighths, 2 for sixteenths.
            n_beams = 2 if any(n._base_type == "sixteenth" for n in group) else 1
            for i in range(n_beams):
                gap = i * (BEAM_H + BEAM_GAP)
                if stem_dir == "up":
                    t1 = int(y_start) + gap
                    b1 = t1 + BEAM_H
                    t2 = int(y_end)   + gap
                    b2 = t2 + BEAM_H
                else:
                    b1 = int(y_start) - gap
                    t1 = b1 - BEAM_H
                    b2 = int(y_end)   - gap
                    t2 = b2 - BEAM_H
                pg.draw.polygon(surface, (0, 0, 0),
                                [(x1, t1), (x2, t2), (x2, b2), (x1, b1)])

    # ------------------------------------------------------------------- draw

    def draw(self):
        if not self.staff:
            print(f"{DEBUG} <Bar> object needs :staff: to be drawn")
            return

        groups = self._find_beam_groups()
        for event in self.events:
            if hasattr(event, "beamed"):
                event.beamed = False
        for group in groups:
            for note in group:
                note.beamed = True

        for event in self.events:
            event.draw()

        self._draw_beams(groups)

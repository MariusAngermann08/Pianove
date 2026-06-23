import pygame as pg
from .durations import get_value
from .font import get_font
from .pitch import parse_pitch as _parse_pitch

DEBUG = "[OpenScore-Debug]"

BEAM_H   = 4
BEAM_GAP = 3


def _event_duration(event):
    from .tuplet import Tuplet
    if isinstance(event, Tuplet):
        return event.total_duration()
    return get_value(event.type)


FLAG_GLYPHS = {
    ("eighth",        "up"):   chr(0xE240),
    ("eighth",        "down"): chr(0xE241),
    ("sixteenth",     "up"):   chr(0xE242),
    ("sixteenth",     "down"): chr(0xE243),
    ("thirty_second", "up"):   chr(0xE244),
    ("thirty_second", "down"): chr(0xE245),
}


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
        used = sum(_event_duration(e) for e in self.events)
        return (self.time[0] / self.time[1]) - used

    def _acc_pre(self, event):
        from .note import Note, ACCIDENTAL_GLYPHS
        from .chord import Chord
        if isinstance(event, Chord):
            event = event.notes[0]
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

        pres      = [self._acc_pre(e) for e in self.events]
        total_acc = sum(pres)
        adj_usable = max(usable_space - total_acc, usable_space * 0.45)

        if count == 1:
            pre = pres[0]
            self.events[0].offset = (self.bar_start_x + barindent + pre
                                     + (adj_usable - pre) / 2)
            return

        total_duration = sum(_event_duration(e) for e in self.events)
        beat_width = adj_usable / total_duration
        x = self.bar_start_x + barindent
        for pre, event in zip(pres, self.events):
            x += pre
            event.offset = x
            dur = _event_duration(event)
            from .tuplet import Tuplet
            if isinstance(event, Tuplet) and event.notes:
                # spread tuplet notes evenly within their allocated space
                note_w = (dur * beat_width) / max(len(event.notes), 1)
                for i, n in enumerate(event.notes):
                    n.offset = x + i * note_w
            x += dur * beat_width

    def _find_beam_groups(self):
        from .note import Note
        from .chord import Chord
        BEAMABLE = ("eighth", "sixteenth", "thirty_second")
        beat_dur = 1.0 / self.time[1]  # e.g. 0.25 in 4/4
        groups, current = [], []
        pos        = 0.0
        group_beat = -1

        for event in self.events:
            dur  = get_value(event.type)
            beat = int(pos / beat_dur + 1e-9)
            is_beamable = (
                (isinstance(event, Note)  and event._base_type in BEAMABLE) or
                (isinstance(event, Chord) and event._base_type in BEAMABLE)
            )
            if is_beamable:
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
            stem_sign = -1 if stem_dir == "up" else 1  # which way the stem points

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

            x1 = group[0]._stem_x()
            x2 = group[-1]._stem_x()
            dx = max(x2 - x1, 1)

            y_start = group[0]._y_center()  + stem_sign * space * _ST
            y_end   = group[-1]._y_center() + stem_sign * space * _ST

            # clamp slope, snap near-flat to flat
            dy     = y_end - y_start
            max_dy = space * 2.0
            dy     = max(min(dy, max_dy), -max_dy)
            if abs(dy) < space * 0.5:
                dy = 0.0
            y_end = y_start + dy

            # push beam so all stems stay at minimum length
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

            y_start += stem_sign * shift
            y_end   += stem_sign * shift

            for note in group:
                nx = note._stem_x()
                t  = (nx - x1) / dx
                by = int(y_start + t * dy)
                yc = int(note._y_center())
                if stem_dir == "up":
                    pg.draw.line(surface, (0, 0, 0), (nx, by), (nx, yc), 2)
                else:
                    pg.draw.line(surface, (0, 0, 0), (nx, yc), (nx, by), 2)

            n_beams = (3 if any(n._base_type == "thirty_second" for n in group)
                       else 2 if any(n._base_type == "sixteenth" for n in group)
                       else 1)
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

    def _draw_expressions(self):
        from .note import Note
        from .chord import Chord
        from .tuplet import Tuplet

        def _notes_in(event):
            if isinstance(event, (Chord, Tuplet)):
                return event.notes
            if isinstance(event, Note):
                return [event]
            return []

        for event in self.events:
            for note in _notes_in(event):
                if not hasattr(note, "expressions"):
                    continue
                for expr in note.expressions:
                    expr.staff  = self.staff
                    expr.offset = note.offset
                    if hasattr(expr, "note_y"):
                        expr.note_y = note._y_center()
                    expr.draw()

    def _draw_ties(self):
        from .note import Note, NOTEHEAD_BLACK
        from .chord import Chord
        surface = self.staff.surface
        space   = self.staff.space
        font    = get_font()
        hr      = font.get_rect(NOTEHEAD_BLACK)
        nw      = hr.width

        for event in self.events:
            notes_to_check = event.notes if isinstance(event, Chord) else [event]
            for note in notes_to_check:
                if not isinstance(note, Note):
                    continue
                target = note.tied_to
                if target is None:
                    continue
                x1 = int(note.offset + nw / 2)
                x2 = int(target.offset + nw / 2)
                from .pitch import pitch_to_step
                clef  = getattr(self.staff, "clef_type", "treble")
                step  = pitch_to_step(note.pitch, clef)
                yc    = self.staff.position[1] + 4 * space - step * (space / 2)
                # curves below for stem-up, above for stem-down
                stem_dir = note._stem_dir()
                cy_off   = int(space * 0.6)
                ctrl_y   = int(yc) + cy_off if stem_dir == "up" else int(yc) - cy_off
                mid_x    = (x1 + x2) // 2
                # fake bezier with two lines through control point
                th = max(1, int(space * 0.12))
                for dy in range(th):
                    pg.draw.line(surface, (0, 0, 0), (x1, int(yc) + dy), (mid_x, ctrl_y + dy), 1)
                    pg.draw.line(surface, (0, 0, 0), (mid_x, ctrl_y + dy), (x2, int(yc) + dy), 1)

    def draw(self):
        if not self.staff:
            print(f"{DEBUG} <Bar> object needs :staff: to be drawn")
            return

        groups = self._find_beam_groups()
        for event in self.events:
            if hasattr(event, "beamed"):
                event.beamed = False
        for group in groups:
            for ev in group:
                ev.beamed = True

        for event in self.events:
            from .chord import Chord
            from .tuplet import Tuplet
            if isinstance(event, Chord):
                event.staff = self.staff
                for n in event.notes:
                    n.staff = self.staff
            elif isinstance(event, Tuplet):
                event.staff = self.staff
                for n in event.notes:
                    n.staff = self.staff
            event.draw()

        self._draw_beams(groups)
        self._draw_ties()
        self._draw_expressions()

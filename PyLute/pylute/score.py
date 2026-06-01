import pygame as pg
from .staff import Staff
from .bar import Bar
from .note import Note
from .rest import Rest
from .clef import Clef, GLYPHS as CLEF_GLYPHS
from .key_signature import KeySignature, parse_key
from .time_signature import TimeSignature
from .brace import Brace
from .durations import get_value
from . import font as _font_mod

_SHARP_NAMES = ["F", "C", "G", "D", "A", "E", "B"]
_FLAT_NAMES  = ["B", "E", "A", "D", "G", "C", "F"]

# All geometry is derived from `space` (pixels between staff lines).
# These multipliers keep proportions consistent at any size.
_ML   = 5    # margin_left   = space * _ML
_MT   = 4    # margin_top    = space * _MT
_SG   = 9    # staff_gap     = space * _SG   (prevents stem/beam cross-staff bleed)
_SYSG = 6    # system_gap    = space * _SYSG
_FS   = 3.5  # font_size     = space * _FS

_BPS_MAX   = 5    # auto bars_per_system upper limit
_BPS_MIN   = 2    # auto bars_per_system lower limit
_MIN_SPACE = 13   # minimum readable staff spacing (px) for auto-bps


class Score:
    def __init__(self, surface=None, staffs=1, length=500, bars=3,
                 clef_types=None, key="C", time=(4, 4),
                 bars_per_system=None):
        self.surface         = surface
        self.time            = list(time)
        self.key_accidentals = parse_key(key)
        self._bps_override   = bars_per_system          # None → auto each resize
        self.bars_per_system = bars_per_system or 5     # working value

        # Metadata rendered above the first system
        self.title     = ""
        self.subtitle  = ""
        self.composer  = ""
        self.lyricist  = ""
        self.copyright = ""

        self.staffs          = []
        self.clefs           = []
        self.key_signatures  = []
        self.time_signatures = []

        if clef_types is None:
            clef_types = ["treble"] * staffs

        for i in range(staffs):
            ctype = clef_types[i] if i < len(clef_types) else "treble"
            staff = Staff(self.surface, self)
            staff.position  = [100, 100 + i * 180]
            staff.length    = length
            staff.clef_type = ctype
            staff.updateLines()

            for j in range(bars):
                staff.bars.append(Bar(staff=staff, index=j))

            self.staffs.append(staff)
            self.clefs.append(Clef(ctype=ctype, staff=staff))
            self.key_signatures.append(KeySignature(accidentals=self.key_accidentals, staff=staff))
            self.time_signatures.append(TimeSignature(staff=staff))

        self.brace = Brace(self.staffs, self.surface) if staffs > 1 else None

        self._frontal_offset      = None
        self._frontal_offset_cont = None
        self._clef_x_offset       = None
        self._keysig_x_offset     = None
        self._timesig_x_offset    = None
        self._last_size           = None   # tracks last canvas width

    # ---------------------------------------------------------------- key info

    @property
    def key_notes(self):
        if self.key_accidentals > 0:
            return {n: "#" for n in _SHARP_NAMES[:self.key_accidentals]}
        if self.key_accidentals < 0:
            return {n: "b" for n in _FLAT_NAMES[:abs(self.key_accidentals)]}
        return {}

    # -------------------------------------------------------------- responsive

    @property
    def frontal_offset(self):
        if self._frontal_offset is None:
            self._compute_layout()
        return self._frontal_offset

    def _space(self):
        return self.staffs[0].space if self.staffs else 20

    def _bar_cost(self, k):
        """Beat-cost coefficient for bar k (space-independent)."""
        beats = self.time[0]
        if not self.staffs or k >= len(self.staffs[0].bars):
            return beats * 3
        n = max(len(s.bars[k].events) for s in self.staffs)
        return max(beats * 3, n * 2)

    def _system_cost(self, bps):
        """Max total bar-cost across all systems for a given bars_per_system."""
        beats  = self.time[0]
        n_bars = len(self.staffs[0].bars) if self.staffs else 0
        if n_bars == 0:
            return bps * beats * 3
        return max(
            sum(self._bar_cost(k) for k in range(i, min(i + bps, n_bars)))
            for i in range(0, n_bars, bps)
        )

    def _space_for_bps(self, w, bps):
        """Unclamped staff-space that would result from a given bars_per_system."""
        denom = 2 * _ML + 5.5 + self._system_cost(bps)
        return (w - 40) / denom if denom > 0 else 8.0

    def _auto_bps(self, w):
        """Largest bars_per_system where space stays >= _MIN_SPACE."""
        for bps in range(_BPS_MAX, _BPS_MIN - 1, -1):
            if self._space_for_bps(w, bps) >= _MIN_SPACE:
                return bps
        return _BPS_MIN

    def _compute_space(self, w):
        denom = 2 * _ML + 5.5 + self._system_cost(self.bars_per_system)
        return max(8, min(28, int((w - 40) / denom)))

    def _on_resize(self, w, h=None):
        if self._bps_override is None:
            self.bars_per_system = self._auto_bps(w)
        space   = self._compute_space(w)
        font_sz  = int(space * _FS)
        ml       = space * _ML

        _font_mod.set_font_size(font_sz)

        for staff in self.staffs:
            staff.space  = space
            staff.length = max(200, w - 2 * ml)

        # Invalidate all cached measurements
        self._frontal_offset      = None
        self._frontal_offset_cont = None
        for ks in self.key_signatures:
            ks._width = None
        for ts in self.time_signatures:
            ts._width = None
        if self.brace:
            self.brace.reset()

        self._last_size = w

    def _compute_layout(self):
        font    = _font_mod.get_font()
        margin  = 15
        gap     = 6
        end_gap = 15

        clef_w  = max(font.get_rect(CLEF_GLYPHS[s.clef_type]).width
                      for s in self.staffs) if self.staffs else 60
        key_w   = self.key_signatures[0].width  if self.key_signatures  else 0
        time_w  = self.time_signatures[0].width if self.time_signatures else 0

        self._clef_x_offset    = margin
        self._keysig_x_offset  = margin + clef_w + gap
        self._timesig_x_offset = margin + clef_w + gap + key_w + (gap if key_w else 0)
        self._frontal_offset   = (margin + clef_w + gap
                                  + key_w + (gap if key_w else 0)
                                  + time_w + end_gap)
        self._frontal_offset_cont = (margin + clef_w + gap
                                     + key_w + (gap if key_w else 0)
                                     + end_gap)

    # ------------------------------------------------------------------ layout

    def _min_bar_width(self, bar_index):
        space  = self._space()
        beats  = self.time[0]
        # Beat-based floor: every beat gets at least 3 staff-spaces.
        # This matches standard engraving spacing (~5 bars/system in 4/4).
        beat_min  = beats * space * 3
        # Event-based floor: denser bars get more room.
        # Take the busiest staff so no voice gets cramped.
        max_events = max(len(s.bars[bar_index].events) for s in self.staffs)
        event_min  = max_events * space * 2.0
        return max(int(beat_min), int(event_min))

    def _layout_systems(self, first_fo=None, cont_fo=None):
        """Slice bars into fixed groups of bars_per_system (last group may be smaller)."""
        if not self.staffs:
            return []
        n_bars = len(self.staffs[0].bars)
        if n_bars == 0:
            return [[]]
        bps = self.bars_per_system
        return [list(range(i, min(i + bps, n_bars))) for i in range(0, n_bars, bps)]

    # ------------------------------------------------------------ metadata

    def _meta_fonts(self, space):
        """Return (title_font, subtitle_font, small_font) sized to current space."""
        import pygame
        pygame.font.init()
        return (
            pygame.font.SysFont("Arial", max(12, int(space * 4.0)), bold=True),
            pygame.font.SysFont("Arial", max(10, int(space * 2.2)), bold=False),
            pygame.font.SysFont("Arial", max(9,  int(space * 1.8)), bold=False),
        )

    def _metadata_height(self, space):
        """Extra vertical space above the first system for title/composer block."""
        if not any([self.title, self.subtitle, self.composer,
                    self.lyricist, self.copyright]):
            return 0
        tf, sf, xf = self._meta_fonts(space)
        h = space * 2   # top padding
        if self.title:
            h += tf.get_linesize() + int(space * 0.4)
        if self.subtitle:
            h += sf.get_linesize() + int(space * 0.3)
        if self.composer or self.lyricist:
            h += sf.get_linesize() + int(space * 0.6)
        return h

    def _draw_metadata(self, space, ml, staff_length):
        """Render title/subtitle/composer block above the first system."""
        if not any([self.title, self.subtitle, self.composer,
                    self.lyricist, self.copyright]):
            return
        tf, sf, xf = self._meta_fonts(space)
        BLACK = (0, 0, 0)
        cx    = ml + staff_length // 2   # horizontal centre
        y     = int(space * 2)

        if self.title:
            surf = tf.render(self.title, True, BLACK)
            self.surface.blit(surf, surf.get_rect(centerx=cx, top=y))
            y += tf.get_linesize() + int(space * 0.4)

        if self.subtitle:
            surf = sf.render(self.subtitle, True, BLACK)
            self.surface.blit(surf, surf.get_rect(centerx=cx, top=y))
            y += sf.get_linesize() + int(space * 0.3)

        # Composer right-aligned, lyricist left-aligned, on the same row
        right_x = ml + staff_length
        if self.composer:
            surf = sf.render(self.composer, True, BLACK)
            self.surface.blit(surf, surf.get_rect(right=right_x, top=y))
        if self.lyricist:
            surf = sf.render(self.lyricist, True, BLACK)
            self.surface.blit(surf, surf.get_rect(left=ml, top=y))

    # ----------------------------------------------------------- page breaks

    def _draw_page_breaks(self, canvas_w, total_h, space):
        """Draw subtle A4-portrait page-separator guides."""
        import pygame
        page_h = int(canvas_w * 297 / 210)
        if page_h < 1 or page_h >= total_h:
            return

        pygame.font.init()
        label_font = pygame.font.SysFont("Arial", max(9, int(space * 1.4)))
        line_color  = (190, 190, 210)
        label_color = (200, 200, 218)
        dash, gap   = 7, 5

        y = page_h
        page = 2
        while y < total_h:
            x = 0
            while x < canvas_w:
                pg.draw.line(self.surface, line_color,
                             (x, y), (min(x + dash, canvas_w), y), 1)
                x += dash + gap
            label = f"p. {page}"
            surf  = label_font.render(label, True, label_color)
            self.surface.blit(surf, (canvas_w - surf.get_width() - 6, y + 2))
            y    += page_h
            page += 1

    # --------------------------------------------------------- content height

    def total_content_height(self, canvas_w=None):
        """Pixel height needed to render all systems. Used by ScrollableCanvas."""
        if canvas_w is not None:
            self._on_resize(canvas_w)
        if self._frontal_offset is None:
            self._compute_layout()
        space      = self._space()
        n_staves   = len(self.staffs)
        sys_height = (n_staves - 1) * space * _SG + 4 * space
        systems    = self._layout_systems(self._frontal_offset, self._frontal_offset_cont)
        meta_h     = self._metadata_height(space)
        return int(meta_h + space * _MT + len(systems) * (sys_height + space * _SYSG) + space * 2)

    def system_height(self) -> int:
        """Pixel height of a single system (staff lines + inter-staff gaps)."""
        space = self._space()
        return int((len(self.staffs) - 1) * space * _SG + 4 * space)

    def system_y_tops(self) -> list:
        """Y coordinate of the top of each system, in the full-score coordinate space."""
        if self._frontal_offset is None:
            self._compute_layout()
        space    = self._space()
        meta_h   = self._metadata_height(space)
        sys_h    = self.system_height()
        sysg     = space * _SYSG
        mt       = space * _MT
        systems  = self._layout_systems()
        return [int(meta_h + mt + i * (sys_h + sysg)) for i in range(len(systems))]

    # ------------------------------------------------------------------- draw

    def draw(self):
        # Responsive: sync geometry to current window size
        if self.surface:
            w = self.surface.get_width()
            if w != self._last_size:
                self._on_resize(w)

        if self._frontal_offset is None:
            self._compute_layout()

        n_staves = len(self.staffs)
        if n_staves == 0:
            return

        space      = self._space()
        ml         = space * _ML
        mt         = space * _MT
        sg         = space * _SG
        sysg       = space * _SYSG
        staff_span = 4 * space
        sys_height = (n_staves - 1) * sg + staff_span
        meta_h     = self._metadata_height(space)

        system_groups = self._layout_systems(self._frontal_offset, self._frontal_offset_cont)
        n_systems     = len(system_groups)

        # Title / composer block above first system
        if meta_h:
            self._draw_metadata(space, ml, self.staffs[0].length)

        for sys_idx, bar_indices in enumerate(system_groups):
            is_first = (sys_idx == 0)
            fo       = self._frontal_offset if is_first else self._frontal_offset_cont
            y_top    = meta_h + mt + sys_idx * (sys_height + sysg)
            n_in_sys = len(bar_indices)

            # Position staves
            for i, staff in enumerate(self.staffs):
                staff.position[0] = ml
                staff.position[1] = y_top + i * sg
                staff.updateLines()

            # Staff lines
            for staff in self.staffs:
                staff.draw_lines()

            # Left-edge system barline
            if n_staves > 1:
                lx    = self.staffs[0].position[0]
                top_y = self.staffs[0].position[1]
                bot_y = self.staffs[-1].position[1] + staff_span
                pg.draw.line(self.surface, (0, 0, 0), (lx, top_y), (lx, bot_y), 2)

            # Clef + key sig + time sig (time sig on first system only)
            for staff, clef, ks, ts in zip(self.staffs, self.clefs,
                                            self.key_signatures, self.time_signatures):
                sx = staff.position[0]
                clef.draw(x=sx + self._clef_x_offset)
                ks.draw(x=sx + self._keysig_x_offset)
                if is_first:
                    ts.draw(x=sx + self._timesig_x_offset)

            # Brace (rebuilt each system — staff y-positions changed)
            if self.brace:
                self.brace.reset()
                self.brace.draw()

            # Proportional bar geometry: each bar gets width ∝ its minimum width
            min_ws     = [self._min_bar_width(j) for j in bar_indices]
            total_min  = sum(min_ws)
            avail      = self.staffs[0].length - fo
            ml_pos     = self.staffs[0].position[0]
            bar_geom   = []   # (bar_start_x, barspace) per bar in system
            cx = ml_pos + fo
            for mw in min_ws:
                bsp = avail * mw / total_min
                bar_geom.append((cx, bsp))
                cx += bsp

            # Bars
            for staff in self.staffs:
                for local_idx, global_idx in enumerate(bar_indices):
                    bar = staff.bars[global_idx]
                    bsx, bsp = bar_geom[local_idx]
                    bar.calculateMetrics(bar_start_x=bsx, barspace=bsp)
                    bar.draw()

            # Barlines
            is_last_sys = (sys_idx == n_systems - 1)
            top_y = self.staffs[0].position[1]
            bot_y = self.staffs[-1].position[1] + staff_span
            span  = n_staves > 1

            for local_idx, global_idx in enumerate(bar_indices):
                bar  = self.staffs[0].bars[global_idx]
                x    = bar.bar_start_x + bar.barspace
                by   = top_y
                ey   = bot_y if span else top_y + staff_span
                is_last = is_last_sys and (local_idx == n_in_sys - 1)

                if is_last:
                    pg.draw.line(self.surface, (0, 0, 0), (x - 4, by), (x - 4, ey), 1)
                    pg.draw.rect(self.surface, (0, 0, 0), (x, by, 3, ey - by))
                else:
                    pg.draw.line(self.surface, (0, 0, 0), (x, by), (x, ey), 2)

        # (page-break guides removed — pager handles A4 navigation)

    # ------------------------------------------------------------------ notes

    def addNote(self, ntype="whole", pitch="C4", staff_index=0):
        if not self.staffs:
            print("staff list empty")
            return
        staff  = self.staffs[staff_index]
        needed = get_value(ntype)
        for bar in staff.bars:
            if bar.spaceAvailable() >= needed:
                bar.events.append(Note(ntype=ntype, pitch=pitch, staff=staff))
                self._last_size = None   # density changed — recompute space on next draw
                return
        print("no space left on that staff")

    def addRest(self, rtype="quarter", staff_index=0):
        if not self.staffs:
            print("staff list empty")
            return
        staff  = self.staffs[staff_index]
        needed = get_value(rtype)
        for bar in staff.bars:
            if bar.spaceAvailable() >= needed:
                bar.events.append(Rest(rtype=rtype, staff=staff))
                self._last_size = None   # density changed — recompute space on next draw
                return
        print("no space left on that staff")

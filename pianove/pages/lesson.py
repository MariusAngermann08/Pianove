import pygame
from pylay import FloatLayout, VStack, Label, Button, State, Switch, iOSTheme, EmojiIcon, ColorPalette, SlideReveal
from pylay.widgets.pygame_canvas import PygameCanvas
from pylay.core.physics import Spring
from pylute.score import Score
from pylute.note import Note as _PluteNote
from pianove.midi.panel import WHITE_NOTES, BLACK_NOTES, BLACK_INDICES
import pianove.context as ctx
from pianove.i18n import t
from pianove.ui_utils import ui_dims

_GREEN      = pygame.Color(52, 199, 89)
_RED        = pygame.Color(255, 59, 48)
_ORANGE     = pygame.Color(255, 149, 0)
_BLUE       = pygame.Color(0, 122, 255)
_PX_PER_BAR = 300
_KB_H       = 130       # keyboard canvas height when visible
_BPM        = 80        # performance mode tempo
_SECTION_SZ = 4         # bars per practice section
_PREP_BARS  = 2         # silent count-in bars before performance

_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# Adaptive regression — tracks wrong-note ratio over a rolling window.
# When the ratio hits the threshold the tracker fires and resets itself.
_WRONG_WINDOW    = 8     # rolling window size (notes)
_WRONG_THRESH    = 0.40  # 40 % wrong in the window → trigger regression


class _WrongTracker:
    def __init__(self):
        self._history: list[int] = []   # 0=correct, 1=wrong

    def record(self, correct: bool) -> bool:
        """Record a note event. Returns True if regression should trigger."""
        self._history.append(0 if correct else 1)
        if len(self._history) > _WRONG_WINDOW:
            self._history.pop(0)
        if len(self._history) >= _WRONG_WINDOW:
            if sum(self._history) / len(self._history) >= _WRONG_THRESH:
                self._history.clear()
                return True
        return False

    def reset(self):
        self._history.clear()


def _bars_from_song_or_lesson(lesson: dict) -> list[list[str]]:
    """Return bars for the current context — song mode or lesson mode."""
    if ctx.current_song_id:
        from pianove.song_store import get_song_bars
        return get_song_bars(ctx.current_song_id, ctx.current_song_hand)
    return _bars_from_lesson(lesson)


def _pitch_to_midi(pitch_str: str) -> int:
    name = pitch_str[0].upper()
    rest = pitch_str[1:]
    acc  = 0
    if rest and rest[0] == "#":
        acc, rest = 1, rest[1:]
    elif rest and rest[0] == "b":
        acc, rest = -1, rest[1:]
    return (int(rest) + 1) * 12 + _SEMITONES[name] + acc


def _bars_from_lesson(lesson: dict) -> list[list[str]]:
    for step in lesson.get("steps", []):
        if step.get("type") == "exercise":
            return step.get("bars", [])
    return [["C4", "D4", "E4", "F4"]]


def _split_sections(bars: list[list[str]]) -> list[list[list[str]]]:
    return [bars[i:i + _SECTION_SZ] for i in range(0, len(bars), _SECTION_SZ)]


def _next_in_course() -> tuple[str, int] | None:
    if not ctx.current_course_id:
        return None
    from pianove.lesson_loader import list_courses
    for course in list_courses():
        if course["id"] == ctx.current_course_id:
            lessons  = course["lessons"]
            next_idx = ctx.current_course_index + 1
            if next_idx < len(lessons):
                return lessons[next_idx], next_idx
    return None


def _nav_back():
    ctx.lesson_current_idx = 0
    ctx.lesson_section_idx = 0
    ctx.lesson_completed   = False
    ctx.lesson_phase       = "practice"
    if ctx.current_song_id:
        ctx.router.navigate("song_setup", "left")
    else:
        ctx.router.navigate("home", "left")


def _do_restart():
    ctx.lesson_current_idx = 0
    ctx.lesson_section_idx = 0
    ctx.lesson_completed   = False
    ctx.lesson_phase       = "practice"
    ctx.router.refresh()


# ── Staff view ────────────────────────────────────────────────────────────────

class _StaffView(PygameCanvas):
    """
    Scrolling staff strip.
    Practice phase: playhead springs to each note on correct press.
    Performance phase: playhead moves continuously at BPM via lerp each frame.
    Content is vertically centred when it fits within the canvas height.
    """

    def __init__(self, bars: list[list[str]], phase: str,
                 initial_idx: int = 0, on_advance=None, **kwargs):
        super().__init__(draw_border=False, **kwargs)
        self.clips_to_bounds = True

        # In performance mode, prepend _PREP_BARS whole-rest bars as a count-in.
        # PyLute renders proper rest symbols; no MIDI is expected during them.
        if phase == "performance":
            beat_dur             = 60.0 / _BPM
            self._prep_duration  = _PREP_BARS * 4 * beat_dur
            self._prep_elapsed   = 0.0
            self._in_prep        = True
            n_prep = _PREP_BARS
        else:
            self._prep_duration  = 0.0
            self._prep_elapsed   = 0.0
            self._in_prep        = False
            n_prep = 0

        n_bars = n_prep + len(bars)
        self._n_bars = n_bars
        self._score  = Score(
            surface=None, staffs=1, bars=n_bars,
            clef_types=["treble"], key="C", time=(4, 4),
            bars_per_system=n_bars,
        )
        for _ in range(n_prep):
            self._score.addRest(rtype="whole", staff_index=0)
        for bar_pitches in bars:
            for pitch in bar_pitches:
                self._score.addNote(ntype="quarter", pitch=pitch, staff_index=0)

        # _note_list contains only Note objects — rests are skipped so current_idx
        # and expected_midi() never reference a rest event.
        self._note_list = [
            ev
            for bar in self._score.staffs[0].bars
            for ev in bar.events
            if isinstance(ev, _PluteNote)
        ]

        self.current_idx: int = min(initial_idx, len(self._note_list))
        for i in range(self.current_idx):
            self._note_list[i].color = _GREEN

        self._phase      = phase
        self._on_advance = on_advance
        self._perf_timer = 0.0
        self._perf_hit   = False

        self._dirty      = True
        self._strip_w    = 0
        self._offscreen: pygame.Surface | None = None
        self._note_xs:   list[float] = []

        self._scroll = Spring(value=0.0, response=0.55, damping_fraction=0.88)
        self._ph     = Spring(value=0.0, response=0.35, damping_fraction=0.82)

    @property
    def total_notes(self) -> int:
        return len(self._note_list)

    def expected_midi(self) -> int | None:
        if self._in_prep:
            return None
        if self.current_idx >= len(self._note_list):
            return None
        return _pitch_to_midi(self._note_list[self.current_idx].pitch)

    # ── Practice ──────────────────────────────────────────────────────────────

    def advance(self):
        if self.current_idx >= len(self._note_list):
            return
        self._note_list[self.current_idx].color = _GREEN
        self._dirty = True
        self.current_idx += 1
        self._update_spring_targets()

    def mark_wrong(self):
        if self.current_idx < len(self._note_list):
            self._note_list[self.current_idx].color = _RED
            self._dirty = True

    # ── Performance ───────────────────────────────────────────────────────────

    def mark_hit(self):
        if self.current_idx < len(self._note_list):
            self._perf_hit = True
            self._note_list[self.current_idx].color = _GREEN
            self._dirty = True

    # ── Shared ────────────────────────────────────────────────────────────────

    def restart(self):
        for note in self._note_list:
            note.color = None
        self._dirty      = True
        self.current_idx = 0
        self._perf_timer = 0.0
        self._perf_hit   = False
        if self._phase == "performance":
            self._prep_elapsed = 0.0
            self._in_prep      = True
        self._ph.snap_to(0.0)
        self._scroll.snap_to(0.0)
        self._scroll.target = 0.0

    # ── Internal ──────────────────────────────────────────────────────────────

    def _update_spring_targets(self):
        idx = self.current_idx
        if idx >= len(self._note_xs):
            return
        target_x   = self._note_xs[idx]
        vw         = max(1, self.rect.width)
        max_scroll = max(0.0, self._strip_w - vw)
        self._ph.target     = target_x
        self._scroll.target = min(max_scroll, max(0.0, target_x - vw * 0.30))

    def _build_offscreen(self):
        vw = max(1, self.rect.width)
        self._strip_w = max(vw, self._n_bars * _PX_PER_BAR)
        self._score._on_resize(self._strip_w)
        h = self._score.total_content_height(self._strip_w)
        self._offscreen = pygame.Surface((self._strip_w, h))
        self._offscreen.fill((255, 255, 255))
        self._score.surface = self._offscreen
        for staff in self._score.staffs:
            staff.surface = self._offscreen
        self._score.draw()
        self._note_xs = [
            ev.offset
            for bar in self._score.staffs[0].bars
            for ev in bar.events
            if isinstance(ev, _PluteNote)
        ]
        if self._note_xs:
            snap_x = self._note_xs[min(self.current_idx, len(self._note_xs) - 1)]
            self._ph.snap_to(snap_x)
            vw = max(1, self.rect.width)
            self._scroll.snap_to(max(0.0, snap_x - vw * 0.30))
        self._dirty = False

    def _redraw_offscreen(self):
        self._offscreen.fill((255, 255, 255))
        self._score.draw()
        self._dirty = False

    def update_content(self, dt: float):
        if self._offscreen is None:
            self._build_offscreen()
        elif self._dirty:
            self._redraw_offscreen()

        self._scroll.update(dt)
        self._ph.update(dt)

        # Prep countdown: sweep playhead through the 2 rest bars before notes start
        if self._in_prep:
            self._prep_elapsed += dt
            # Move playhead linearly through the prep-bar area
            if self._strip_w > 0 and self._n_bars > 0:
                bar_w   = self._strip_w / self._n_bars
                prep_end_x = _PREP_BARS * bar_w
                frac    = min(1.0, self._prep_elapsed / self._prep_duration)
                ph_x    = frac * prep_end_x
                self._ph.snap_to(ph_x)
                vw            = max(1, self.rect.width)
                max_scroll    = max(0.0, self._strip_w - vw)
                self._scroll.target = min(max_scroll, max(0.0, ph_x - vw * 0.30))
            if self._prep_elapsed >= self._prep_duration:
                self._in_prep = False
                self._perf_timer = 0.0
            return

        if self._phase == "performance" and self.current_idx < len(self._note_list):
            self._perf_timer += dt
            note_dur = 60.0 / _BPM

            if self._note_xs:
                idx   = min(self.current_idx, len(self._note_xs) - 1)
                x_cur = self._note_xs[idx]
                if idx + 1 < len(self._note_xs):
                    x_nxt = self._note_xs[idx + 1]
                else:
                    gap   = (self._note_xs[-1] - self._note_xs[-2]) if len(self._note_xs) > 1 else 60
                    x_nxt = x_cur + gap
                frac = min(1.0, self._perf_timer / note_dur)
                ph_x = x_cur + (x_nxt - x_cur) * frac
                self._ph.snap_to(ph_x)

                vw         = max(1, self.rect.width)
                max_scroll = max(0.0, self._strip_w - vw)
                self._scroll.target = min(max_scroll, max(0.0, ph_x - vw * 0.30))

            if self._perf_timer >= note_dur:
                self._perf_timer -= note_dur
                if not self._perf_hit and self.current_idx < len(self._note_list):
                    self._note_list[self.current_idx].color = _ORANGE
                    self._dirty = True
                self.current_idx += 1
                self._perf_hit = False
                if self._on_advance:
                    self._on_advance(self.current_idx)

    def draw_content(self, surface: pygame.Surface, rect: pygame.Rect):
        if self._offscreen is None:
            return

        off_w = self._offscreen.get_width()
        off_h = self._offscreen.get_height()
        vw, vh = rect.width, rect.height

        surface.fill((255, 255, 255), rect)

        scroll = max(0, min(int(self._scroll.value), max(0, off_w - vw)))

        if off_h <= vh:
            # Vertically centre the score content within the canvas
            y_offset = (vh - off_h) // 2
            surface.blit(self._offscreen,
                         (rect.left, rect.top + y_offset),
                         pygame.Rect(scroll, 0, vw, off_h))
            ph_top = rect.top + y_offset + 4
            ph_bot = rect.top + y_offset + off_h - 4
        else:
            # Content taller than canvas: keep staff lines centred
            space        = self._score.staffs[0].space if self._score.staffs else 20
            staff_top_y  = space * 4
            staff_bot_y  = staff_top_y + space * 4
            staff_center = (staff_top_y + staff_bot_y) // 2
            y_src  = max(0, min(off_h - vh, staff_center - vh // 2))
            blit_h = min(vh, off_h - y_src)
            surface.blit(self._offscreen, rect.topleft,
                         pygame.Rect(scroll, y_src, vw, blit_h))
            ph_top = rect.top + 4
            ph_bot = rect.bottom - 4

        ph_sx = rect.left + int(self._ph.value) - scroll
        if rect.left <= ph_sx <= rect.right:
            pygame.draw.line(surface, _BLUE,
                             (ph_sx, ph_top), (ph_sx, ph_bot), 2)


# ── Lesson piano widget ───────────────────────────────────────────────────────

class _LessonPiano:
    """
    Draws the keyboard and processes MIDI input.
    Always instantiated so MIDI is active even when the keyboard is hidden.
    """
    def __init__(self, staff_view: _StaffView, advance_fn, wrong_fn):
        from pianove.state import midi_panel
        self._panel   = midi_panel
        self._sv      = staff_view
        self._advance = advance_fn
        self._wrong   = wrong_fn
        self._prev    = frozenset()

    def update(self, dt: float, rect: pygame.Rect):
        self._panel.update(dt, rect)
        current   = frozenset(self._panel.active_notes)
        new_notes = current - self._prev
        for note in new_notes:
            self._handle_note(note)
        self._prev = current

    def reset_midi_state(self):
        self._prev = frozenset()

    def handle_event(self, event: pygame.event.Event, rect: pygame.Rect) -> bool:
        return False

    def _handle_note(self, note_num: int):
        expected = self._sv.expected_midi()
        if expected is None:
            return
        if note_num == expected:
            if self._sv._phase == "practice":
                self._advance()
            else:
                self._sv.mark_hit()
        elif self._sv._phase == "practice":
            self._wrong()

    def draw(self, surface: pygame.Surface, rect: pygame.Rect):
        expected = self._sv.expected_midi()
        active   = self._panel.active_notes

        margin_x = max(8, int(rect.width * 0.02))
        status_h = max(16, int(rect.height * 0.14))
        top      = rect.top + max(3, int(rect.height * 0.02))
        key_h    = max(40, rect.bottom - status_h - top - 4)
        avail_w  = max(60, rect.width - margin_x * 2)
        white_w  = avail_w / len(WHITE_NOTES)
        black_w  = white_w / 2
        black_h  = key_h * (200 / 300)

        def _active(n):  return self._panel._note_active(n, active)
        def _exp(n):     return expected is not None and n == expected

        def _wc(note):
            if _active(note): return (190, 60, 60)
            if _exp(note):    return (120, 180, 255)
            return (255, 255, 255)

        def _bc(note):
            if _active(note): return (140, 45, 45)
            if _exp(note):    return (30, 100, 200)
            return (0, 0, 0)

        surface.fill(iOSTheme.tertiary_background, rect)

        white_keys = [
            (pygame.Rect(int(rect.left + margin_x + i * white_w), int(top),
                         int(white_w), int(key_h)), _wc(note))
            for i, note in enumerate(WHITE_NOTES)
        ]
        black_keys = [
            (pygame.Rect(int(rect.left + margin_x + idx * white_w + white_w - black_w / 2),
                         int(top), int(black_w), int(black_h)), _bc(note))
            for idx, note in zip(BLACK_INDICES, BLACK_NOTES)
        ]

        for kr, col in white_keys:
            pygame.draw.rect(surface, col, kr)
            pygame.draw.rect(surface, (0, 0, 0), kr, 2)
        for kr, col in black_keys:
            pygame.draw.rect(surface, col, kr, border_radius=10)
            pygame.draw.rect(surface, (0, 0, 0), kr, 2, border_radius=10)

        connected = self._panel.midi_in is not None
        label_txt = (t("midi_connected", name=self._panel.midi_in.name)
                     if connected else t("midi_none"))
        label_col = (52, 199, 89) if connected else (180, 100, 100)
        font = pygame.font.SysFont(None, max(14, status_h - 2))
        ls   = font.render(label_txt, True, label_col)
        surface.blit(ls, (rect.left + margin_x,
                          rect.bottom - status_h + (status_h - ls.get_height()) // 2))


# ── Completion view ───────────────────────────────────────────────────────────

def _build_completion(lesson_title: str) -> FloatLayout:
    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    main = VStack(spacing=0, padding=0, width=1.0, height=1.0)
    root.add_child(main)

    nav = FloatLayout(width=1.0, height=52,
                      background_color=iOSTheme.secondary_background)
    nav.add_child(Button(text=t("back"), on_click=_nav_back,
                         anchor="left", x=12, y=0,
                         width=72, height=34, font_size=14,
                         background_color=iOSTheme.fill, text_color=iOSTheme.label,
                         border_radius=8))
    nav.add_child(Label(text=lesson_title, font_size=16, bold=True, color=iOSTheme.label,
                        anchor="center", x=0, y=0))
    main.add_child(nav)
    main.add_child(FloatLayout(width=1.0, height=1,
                               background_color=pygame.Color(120, 120, 128, 60)))

    body = VStack(spacing=20, padding=40, width=1.0, height=1.0)
    body.add_child(EmojiIcon("🏆", size=72, color=_ORANGE, anchor="center", x=0, y=0))
    body.add_child(Label(text=t("lesson_well_done"), font_size=30, bold=True,
                         color=iOSTheme.label, anchor="center", x=0, y=0))
    body.add_child(Label(text=lesson_title, font_size=15,
                         color=iOSTheme.secondary_label, anchor="center", x=0, y=0))

    btn_row = FloatLayout(width=1.0, height=50)
    btn_row.add_child(Button(text=t("lesson_play_again"), on_click=_do_restart,
                             anchor="left", x=16, y=0, width=0.42, height=44, font_size=14,
                             background_color=iOSTheme.fill, text_color=iOSTheme.label,
                             border_radius=12))
    nxt = None if ctx.current_song_id else _next_in_course()
    if nxt:
        next_id, next_idx = nxt
        def _go_next():
            ctx.current_lesson_id    = next_id
            ctx.current_course_index = next_idx
            ctx.lesson_current_idx   = 0
            ctx.lesson_section_idx   = 0
            ctx.lesson_completed     = False
            ctx.lesson_phase         = "practice"
            ctx.router.refresh()
        btn_row.add_child(Button(text=t("lesson_next"), on_click=_go_next,
                                 anchor="right", x=16, y=0, width=0.42, height=44, font_size=14,
                                 background_color=_GREEN,
                                 text_color=pygame.Color(255, 255, 255),
                                 border_radius=12))
    body.add_child(btn_row)
    main.add_child(body)
    return root


# ── Page builder ──────────────────────────────────────────────────────────────

def build():
    from pianove.lesson_loader import load_lesson

    lesson_id    = ctx.current_lesson_id
    keyboard_vis = ctx.lesson_keyboard_vis
    phase        = ctx.lesson_phase
    section_idx  = ctx.lesson_section_idx
    initial_idx  = ctx.lesson_current_idx

    lesson = load_lesson(lesson_id)
    if lesson is None:
        lesson = {"title": lesson_id, "steps": []}

    # In song mode, pull title from the song store instead
    if ctx.current_song_id:
        from pianove.song_store import get_song
        _song = get_song(ctx.current_song_id)
        lesson_title = _song["title"] if _song else ctx.current_song_id
    else:
        lesson_title = lesson.get("title", lesson_id)

    all_bars     = _bars_from_song_or_lesson(lesson)
    sections     = _split_sections(all_bars)
    n_sections   = len(sections)

    section_idx = min(section_idx, n_sections - 1)

    active_bars = sections[section_idx] if phase == "practice" else all_bars
    n_notes     = sum(len(b) for b in active_bars)

    # Completion screen
    if ctx.lesson_completed and initial_idx >= n_notes:
        return _build_completion(lesson_title)

    # ── Layout dimensions ─────────────────────────────────────────────────────
    win_h   = ctx.ui.height if ctx.ui else 768
    NAV_H   = 52 + 1 + 44 + 1    # nav + sep + controls + sep = 98 px
    # Staff always fills the entire remaining space; piano is a SlideReveal overlay.
    staff_h = max(180, win_h - NAV_H)

    # ── Forward refs ──────────────────────────────────────────────────────────
    _sv        = [None]   # _StaffView
    _slide_ref = [None]   # SlideReveal

    def _save():
        ctx.lesson_current_idx = _sv[0].current_idx if _sv[0] else initial_idx

    def _on_kb_toggle(val: bool):
        # No page rebuild — just animate the SlideReveal in/out
        ctx.lesson_keyboard_vis = val
        if _slide_ref[0]:
            _slide_ref[0].reveal(val)

    def _on_restart():
        ctx.lesson_current_idx = 0
        ctx.lesson_section_idx = 0
        ctx.lesson_completed   = False
        ctx.lesson_phase       = "practice"
        ctx.router.refresh()

    wrong_tracker = _WrongTracker()

    def _advance_section():
        next_sec = section_idx + 1
        ctx.lesson_current_idx = 0
        if next_sec >= n_sections:
            ctx.lesson_phase       = "performance"
            ctx.lesson_section_idx = 0
        else:
            ctx.lesson_section_idx = next_sec
        ctx.router.refresh()

    def _step_back_section():
        """Regress one practice section (or restart section 0)."""
        prev = max(0, section_idx - 1)
        ctx.lesson_section_idx = prev
        ctx.lesson_current_idx = 0
        ctx.lesson_phase       = "practice"
        ctx.router.refresh()

    def _restart_section():
        """Restart current section (used in performance regression)."""
        ctx.lesson_section_idx = section_idx
        ctx.lesson_current_idx = 0
        ctx.lesson_phase       = "practice"
        ctx.router.refresh()

    def _complete_lesson():
        from pianove.progress import mark_complete, record_session
        if not ctx.current_song_id:
            mark_complete(lesson_id)
            record_session(lesson_id)
        ctx.lesson_completed = True
        ctx.router.refresh()

    counter_state = State(
        f"{initial_idx + 1} / {n_notes}" if initial_idx < n_notes else ""
    )

    def _do_note_advance(new_idx: int):
        ctx.lesson_current_idx = new_idx
        if new_idx >= n_notes:
            if phase == "practice":
                _advance_section()
            else:
                _complete_lesson()
        else:
            counter_state.value = f"{new_idx + 1} / {n_notes}"

    def _do_advance():
        if _sv[0]:
            _sv[0].advance()
            wrong_tracker.record(True)
            _do_note_advance(_sv[0].current_idx)

    def _do_wrong():
        if _sv[0]:
            _sv[0].mark_wrong()
            if wrong_tracker.record(False):
                if phase == "practice":
                    _step_back_section()
                else:
                    _restart_section()

    if phase == "performance":
        phase_label = t("lesson_final_go")
    elif n_sections > 1:
        phase_label = t("lesson_section_of", n=section_idx + 1, total=n_sections)
    else:
        phase_label = t("lesson_practice")

    # ── Build tree ────────────────────────────────────────────────────────────
    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    main = VStack(spacing=0, padding=0, width=1.0, height=1.0)
    root.add_child(main)

    # Nav bar
    nav = FloatLayout(width=1.0, height=52,
                      background_color=iOSTheme.secondary_background)
    nav.add_child(Button(text=t("back"), on_click=_nav_back,
                         anchor="left", x=12, y=0,
                         width=72, height=34, font_size=14,
                         background_color=iOSTheme.fill, text_color=iOSTheme.label,
                         border_radius=8))
    nav.add_child(Label(text=lesson_title, font_size=16, bold=True,
                        color=iOSTheme.label, anchor="center", x=0, y=0))
    nav.add_child(Label(text=counter_state, font_size=13,
                        color=iOSTheme.secondary_label,
                        anchor="right", x=14, y=0, width=100, height=52))
    main.add_child(nav)
    main.add_child(FloatLayout(width=1.0, height=1,
                               background_color=pygame.Color(120, 120, 128, 60)))

    # Controls bar
    controls = FloatLayout(width=1.0, height=44,
                           background_color=iOSTheme.secondary_background)
    controls.add_child(Label(text=phase_label, font_size=13,
                             color=iOSTheme.secondary_label,
                             anchor="left", x=16, y=0, width=240, height=44))
    controls.add_child(Button(text="↺", on_click=_on_restart,
                              anchor="right", x=126, y=0,
                              width=36, height=32, font_size=18,
                              background_color=iOSTheme.fill, text_color=iOSTheme.label,
                              border_radius=8))
    controls.add_child(Label(text="Piano", font_size=13,
                             color=iOSTheme.secondary_label,
                             anchor="right", x=80, y=0, width=42, height=44))
    controls.add_child(Switch(value=keyboard_vis, on_change=_on_kb_toggle,
                              anchor="right", x=8, y=0,
                              width=51, height=31, active_color=ColorPalette.BLUE))
    main.add_child(controls)
    main.add_child(FloatLayout(width=1.0, height=1,
                               background_color=pygame.Color(120, 120, 128, 60)))

    # Staff — always the full remaining height, centred content handled in draw_content
    staff_view = _StaffView(
        bars=active_bars, phase=phase,
        initial_idx=initial_idx, on_advance=_do_note_advance,
        width=1.0, height=staff_h,
    )
    _sv[0] = staff_view
    main.add_child(staff_view)

    # Piano — always instantiated so MIDI is active regardless of visibility.
    # Wrapped in SlideReveal for animated show/hide without a full page rebuild.
    piano        = _LessonPiano(staff_view, _do_advance, _do_wrong)
    piano_canvas = PygameCanvas(target=piano, draw_border=False,
                                width=1.0, height=1.0)
    slide = SlideReveal(
        child=piano_canvas,
        max_height=_KB_H,
        visible=keyboard_vis,
        anchor="bottom_left", x=0, y=0, width=1.0,
    )
    _slide_ref[0] = slide
    root.add_child(slide)

    return root

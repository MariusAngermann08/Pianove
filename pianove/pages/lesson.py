import pygame
from pylay import FloatLayout, VStack, Label, Button, State, Switch, iOSTheme, EmojiIcon, ColorPalette, SlideReveal
from pylay.widgets.pygame_canvas import PygameCanvas
from pylay.core.physics import Spring
from pylute.score import Score
from pylute.note import Note as _PluteNote
from pylute.rest import Rest as _PluteRest
from pylute.chord import Chord as _PluteChord
import pianove.context as ctx
from pianove.i18n import t
from pianove.ui_utils import ui_dims
from pianove.components import ORANGE, GREEN, RED, PURPLE
from pianove.fingering import key_x as _key_x
from pianove.hands import HandsOverlay, KeyboardGeometry

_GREEN  = GREEN
_RED    = RED
_ORANGE = ORANGE
_PURPLE = PURPLE
_BLUE   = ColorPalette.BLUE
_PX_PER_BAR = 300
_KB_H       = 130       # keyboard canvas height when visible
_BPM        = 80        # default performance tempo
_SECTION_SZ = 4         # bars per practice section
_PREP_BARS  = 2         # silent count-in bars before performance


def _kb_h_hands() -> int:
    """Keyboard canvas height with the hands: below the keys, room for the backs of the
    hands down to a little of their sleeves. The hands scale with the keys."""
    from pianove.state import midi_panel
    from pianove.hands import sleeve_depth
    win_w = ctx.ui.width if ctx.ui else 1024
    win_h = ctx.ui.height if ctx.ui else 768
    u = (win_w - 2 * max(8, int(win_w * 0.02))) / max(1, len(midi_panel._white_notes) or 36)
    status_h = max(16, int(_KB_H * 0.14))
    key_h = _KB_H - status_h - max(3, int(_KB_H * 0.02)) - 4
    fingertips = max(3, int(_KB_H * 0.02)) + key_h * 0.81      # the white keys' fingertip line
    want = fingertips + (sleeve_depth() + 0.45) * u              # down to a little of the sleeve
    return int(min(_kb_h_hands_max(), max(236, want)))


def _kb_h_hands_max() -> int:
    """The most the keyboard panel ever takes with the hands: a third of the window (but
    always room for the keys and the fingers)."""
    return max(236, int((ctx.ui.height if ctx.ui else 768) * 0.33))


_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# Adaptive regression — tracks wrong-note ratio over a rolling window.
# When the ratio hits the threshold the tracker fires and resets itself.
_WRONG_WINDOW    = 8     # rolling window size (notes)
_WRONG_THRESH    = 0.40  # 40 % wrong in the window → trigger regression


class _WrongTracker:
    def __init__(self):
        self._history: list[int] = []   # 0=correct, 1=wrong

    def record(self, correct: bool) -> bool:
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


_REST_STEPS = [("half", 2.0), ("quarter", 1.0), ("eighth", 0.5), ("sixteenth", 0.25),
               ("thirty_second", 0.125)]


def _even_type(n: int, beats: int) -> str:
    if n <= beats:
        return "quarter"
    if n <= beats * 2:
        return "eighth"
    return "sixteenth"


def _bar_types(tlist, i: int, pitches: list[str], time: tuple, olist=None) -> list[str]:
    """Real note values (from an imported song) when they fit the bar, otherwise
    evenly spaced notes. With stored positions, chord notes share their start."""
    from pylute.durations import get_value
    if tlist is not None and i < len(tlist) and len(tlist[i]) == len(pitches):
        try:
            bar_w = time[0] / time[1] + 1e-6
            if olist is not None and i < len(olist) and len(olist[i]) == len(pitches):
                if max(o / 4 + get_value(x) for o, x in zip(olist[i], tlist[i])) <= bar_w:
                    return list(tlist[i])
            elif sum(get_value(x) for x in tlist[i]) <= bar_w:
                return list(tlist[i])
        except KeyError:
            pass
    return [_even_type(len(pitches), time[0])] * len(pitches)


def _bar_len_q(bar_lens, i: int, time: tuple) -> float:
    if bar_lens is not None and i < len(bar_lens) and bar_lens[i]:
        return float(bar_lens[i])
    return time[0] * 4 / time[1]


def _bar_positions(tlist, olist, i: int, ntypes: list[str], bar_len: float) -> list[float]:
    """Where each note of bar i starts, in quarter notes: the stored positions when they
    are consistent with the note values, otherwise one note after another."""
    from pylute.durations import get_value
    if (olist is not None and i < len(olist) and len(olist[i]) == len(ntypes)
            and tlist is not None and i < len(tlist) and list(tlist[i]) == ntypes):
        pos, cur, prev, ok = list(olist[i]), 0.0, None, True
        for p, t in zip(pos, ntypes):
            if prev is not None and abs(p - prev) < 1e-6:
                continue                           # another note of the same chord
            if p < cur - 1e-6:                     # overlaps the previous note
                ok = False
                break
            cur, prev = p + get_value(t) * 4, p
        if ok and cur <= bar_len + 1e-6:
            return pos
    out, cur = [], 0.0
    for t in ntypes:
        out.append(cur)
        cur += get_value(t) * 4
    return out


def _bar_notes(tl, ol, meta, si: int, i: int, pitches: list[str], time: tuple, blen: float):
    """Bar i's notes on one staff: (types, positions, lengths in quarters, tie
    continuations, velocities). A song imported with real lengths is taken as written;
    otherwise the values and positions are checked and, if need be, evened out."""
    from pylute.durations import get_value, VALUES
    n = len(pitches)

    def per_bar(key):
        lst = ((meta or {}).get(key) or (None, None))[si]
        return lst[i] if lst is not None and i < len(lst) and len(lst[i]) == n else None

    lengths = per_bar("durs")
    if (lengths is not None and tl is not None and i < len(tl) and len(tl[i]) == n
            and ol is not None and i < len(ol) and len(ol[i]) == n):
        nt = [x if x in VALUES else "sixteenth" for x in tl[i]]
        return (nt, list(ol[i]), list(lengths), list(per_bar("ties") or [False] * n),
                list(per_bar("vels") or [None] * n))
    nt = _bar_types(tl, i, pitches, time, ol)
    return (nt, _bar_positions(tl, ol, i, nt, blen), [get_value(x) * 4 for x in nt],
            [False] * n, [None] * n)


def _seconds_fn(tempos, bpm: float):
    """Quarter-note position from the start → seconds, through the tempo changes."""
    import bisect
    pts = sorted((float(q), float(b)) for q, b in (tempos or []) if b)
    if not pts or pts[0][0] > 0:
        pts.insert(0, (0.0, pts[0][1] if pts else float(bpm)))
    cum = [0.0]
    for (q0, b0), (q1, _) in zip(pts, pts[1:]):
        cum.append(cum[-1] + (q1 - q0) * 60.0 / b0)
    qs = [q for q, _ in pts]

    def sec(q: float) -> float:
        i = max(0, bisect.bisect_right(qs, q) - 1)
        return cum[i] + (q - pts[i][0]) * 60.0 / pts[i][1]
    return sec


def _step_positions(bars, bass_bars, types, bass_types, onsets, bass_onsets, bar_lens, time,
                    meta=None) -> list[float]:
    """Distinct start positions (quarter notes from the first bar) of every struck note on
    both staves. Notes that start together form one step."""
    starts, bar_start = set(), 0.0
    for i in range(len(bars)):
        blen = _bar_len_q(bar_lens, i, time)
        for si, staff_bars, tl, ol in ((0, bars, types, onsets), (1, bass_bars, bass_types, bass_onsets)):
            if staff_bars is None or i >= len(staff_bars) or not staff_bars[i]:
                continue
            _, positions, _, ties, _ = _bar_notes(tl, ol, meta, si, i, staff_bars[i], time, blen)
            for p, tied in zip(positions, ties):
                if not tied:
                    starts.add(round(bar_start + p, 4))
        bar_start += blen
    return sorted(starts)


def _plan_fingering(step_list, step_pos, bpm, hands_of) -> list[dict]:
    """Finger every note: per step, {"right": {midi: finger}, "left": {midi: finger}}."""
    from pianove.fingering import Step, finger_hand
    from pylute.durations import get_value
    q = 60.0 / max(1, bpm)
    plan: list[dict] = [{} for _ in step_list]
    for si, hand in hands_of.items():
        idx, steps = [], []
        for i, step in enumerate(step_list):
            notes = [n for n in step if getattr(n, "_si", 0) == si]
            if not notes:
                continue
            hold = min(get_value(n.type) * 4 for n in notes) * q
            idx.append(i)
            steps.append(Step(tuple(_pitch_to_midi(n.pitch) for n in notes), step_pos[i] * q, hold))
        for i, fingers in zip(idx, finger_hand(steps, hand)):
            plan[i][hand] = fingers
    return plan


def _bars_from_song_or_lesson(lesson: dict) -> list[list[str]]:
    if ctx.practice_mode and ctx.practice_bars is not None:
        return ctx.practice_bars
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
    steps = lesson.get("steps", [])
    # Try the current step first; fall back to first exercise found
    candidates = []
    if ctx.lesson_step_idx < len(steps):
        candidates = [steps[ctx.lesson_step_idx]] + steps
    else:
        candidates = steps
    for step in candidates:
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


def _listen_on(t: float, midi: int, velocity: int):
    """Strike a key for listen mode (t: when it was due, in the piece's seconds)."""
    from pianove.sound_engine_fs import play_raw
    play_raw(midi, velocity)


def _listen_off(t: float, midi: int):
    from pianove.sound_engine_fs import stop
    stop(midi)


def _listen_clock() -> float:
    import time
    return time.perf_counter()


_LISTEN_THREADED = True       # tests and recordings drive the player frame by frame instead


class _Player:
    """Plays a piece on Pianove's piano by itself, on its own clock: a worker thread
    strikes and releases each key when it is due, however busy the screen is. The
    screen asks it where the music is."""

    def __init__(self, events: list, total: float):
        import threading
        self._events = events             # (time s, 0 = release / 1 = strike, key, velocity, staff)
        self._times = [e[0] for e in events]
        self.total = total
        self.playing = False
        self._offset = 0.0                # piece time when last started or moved
        self._t0 = 0.0                    # clock time then
        self._i = 0                       # the next event
        self.sounding: dict[int, int] = {}   # key → staff
        self._lock = threading.RLock()
        self._thread = None
        self._alive = True

    def position(self) -> float:
        if not self.playing:
            return self._offset
        return min(self.total, self._offset + (_listen_clock() - self._t0))

    def play(self):
        with self._lock:
            if self._offset >= self.total - 1e-3:
                self._seek(0.0)
            self._t0 = _listen_clock()
            self.playing = True
        if _LISTEN_THREADED and self._thread is None:
            import threading
            self._thread = threading.Thread(target=self._run, daemon=True, name="listen-player")
            self._thread.start()

    def pause(self):
        with self._lock:
            self._offset = self.position()
            self.playing = False
            self._release_all()

    def seek(self, t: float):
        with self._lock:
            self._seek(t)

    def _seek(self, t: float):
        import bisect
        self._release_all()
        self._offset = max(0.0, min(self.total, t))
        self._t0 = _listen_clock()
        self._i = bisect.bisect_left(self._times, self._offset)

    def close(self):
        self._alive = False
        self.pause()

    def _release_all(self):
        for m in list(self.sounding):
            _listen_off(self._offset, m)
        self.sounding.clear()

    def advance(self):
        """Strike and release every key that is due by now."""
        with self._lock:
            if not self.playing:
                return
            t = self.position()
            while self._i < len(self._events) and self._events[self._i][0] <= t:
                et, kind, m, vel, si = self._events[self._i]
                self._i += 1
                if kind:
                    if m in self.sounding:
                        _listen_off(et, m)             # the same key struck again
                    _listen_on(et, m, vel)
                    self.sounding[m] = si
                elif m in self.sounding:
                    _listen_off(et, m)
                    del self.sounding[m]
            if t >= self.total:
                self._offset = self.total
                self.playing = False
                self._release_all()

    def _run(self):
        import time
        nap = _short_sleep()
        while self._alive:
            if self.playing:
                self.advance()
                nap(0.001)
            else:
                time.sleep(0.02)


def _short_sleep():
    """A sleep that wakes after about a millisecond. Windows' ordinary one (as Python 3.10
    uses it) wakes only every 15.6 ms, too coarse for fast notes: there a
    high-resolution waitable timer does it."""
    import sys
    import time
    if sys.platform != "win32":
        return time.sleep
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32")
        k.CreateWaitableTimerExW.restype = wintypes.HANDLE
        k.CreateWaitableTimerExW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD]
        k.SetWaitableTimer.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong), wintypes.LONG,
                                       ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL]
        k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        timer = k.CreateWaitableTimerExW(None, None, 0x00000002, 0x1F0003)   # HIGH_RESOLUTION
        if not timer:
            return time.sleep
    except Exception:
        return time.sleep

    def nap(seconds: float):
        due = ctypes.c_longlong(-int(seconds * 1e7))  # relative, in 100 ns
        k.SetWaitableTimer(timer, ctypes.byref(due), 0, None, None, False)
        k.WaitForSingleObject(timer, 0xFFFFFFFF)
    return nap


# The score view that is playing the piece in listen mode, so its sound stops when the
# page goes away
_LISTENING: list = [None]


def _stop_listening():
    sv, _LISTENING[0] = _LISTENING[0], None
    if sv is not None:
        sv.stop_listening()


def _nav_back():
    _stop_listening()
    ctx.lesson_step_idx    = 0
    ctx.lesson_current_idx = 0
    ctx.lesson_section_idx = 0
    ctx.lesson_completed   = False
    ctx.lesson_phase       = "practice"
    if ctx.practice_mode:
        ctx.practice_mode  = False
        ctx.practice_bars  = None
        ctx.router.navigate("home", "left")
    elif ctx.current_song_id:
        ctx.router.navigate("song_setup", "left")
    else:
        ctx.router.navigate("home", "left")


def _do_restart():
    ctx.lesson_step_idx    = 0
    ctx.lesson_current_idx = 0
    ctx.lesson_section_idx = 0
    ctx.lesson_completed   = False
    ctx.lesson_phase       = "practice"
    ctx.router.refresh()


class _StaffView(PygameCanvas):
    def __init__(self, bars: list[list[str]], phase: str,
                 initial_idx: int = 0, on_advance=None,
                 bpm: int = _BPM, clef: str = "treble",
                 bass_bars: list[list[str]] | None = None,
                 time: tuple = (4, 4),
                 types: list[list[str]] | None = None,
                 bass_types: list[list[str]] | None = None,
                 onsets: list[list[float]] | None = None,
                 bass_onsets: list[list[float]] | None = None,
                 bar_lens: list[float] | None = None, meta: dict | None = None, **kwargs):
        super().__init__(draw_border=False, **kwargs)
        self.clips_to_bounds = True
        self._bpm  = bpm
        self._hits = 0

        # In performance mode, prepend _PREP_BARS whole-rest bars as a count-in.
        # PyLute renders proper rest symbols; no MIDI is expected during them.
        if phase == "performance":
            beat_dur             = 60.0 / self._bpm
            self._prep_duration  = _PREP_BARS * time[0] * beat_dur
            self._prep_elapsed   = 0.0
            self._in_prep        = True
            n_prep = _PREP_BARS
        else:
            self._prep_duration  = 0.0
            self._prep_elapsed   = 0.0
            self._in_prep        = False
            n_prep = 0

        n_staves   = 2 if bass_bars is not None else 1
        clef_types = ["treble", "bass"] if bass_bars is not None else [clef]

        n_bars = n_prep + len(bars)
        self._n_bars = n_bars
        self._score  = Score(
            surface=None, staffs=n_staves, bars=n_bars,
            clef_types=clef_types, key="C", time=time,
            bars_per_system=n_bars,
        )

        # Populate all bars directly so notes never overflow between bars.
        st0 = self._score.staffs[0]
        st1 = self._score.staffs[1] if n_staves > 1 else None
        from pylute.durations import get_value as _dur

        for prep_i in range(n_prep):
            st0.bars[prep_i].events.append(_PluteRest(rtype="whole", staff=st0))
            if st1:
                st1.bars[prep_i].events.append(_PluteRest(rtype="whole", staff=st1))

        def _fill(staff, bar_obj, pitches, ntypes, positions, lengths, blen):
            """Place notes at their positions, in time order across all voices: notes
            starting together become a chord. Each event takes the room up to the next one
            (_layout_dur), and rests fill only where nothing sounds."""
            def rests(gap):
                out = []
                for rname, rq in _REST_STEPS:
                    while gap >= rq - 1e-6:
                        out.append(_PluteRest(rtype=rname, staff=staff))
                        gap -= rq
                return out, gap

            groups: list[tuple[float, list[int]]] = []
            for k in sorted(range(len(pitches)), key=lambda k: positions[k]):
                if groups and abs(positions[k] - groups[-1][0]) < 1e-6:
                    groups[-1][1].append(k)
                else:
                    groups.append((positions[k], [k]))
            placed, sounding = [], 0.0
            if groups and groups[0][0] > 1e-6:                # silence at the start of the bar
                lead, left = rests(groups[0][0])
                if not lead:
                    lead = [_PluteRest(rtype="thirty_second", staff=staff)]
                lead[-1]._layout_dur = (_dur(lead[-1].type) * 4 + left) / 4 if left > 1e-6 else None
                if len(lead) == 1 and left > 1e-6:
                    lead[-1]._layout_dur = groups[0][0] / 4
                bar_obj.events.extend(lead)
            for gi, (pos, ks) in enumerate(groups):
                notes = [_PluteNote(ntype=ntypes[k], pitch=pitches[k], staff=staff) for k in ks]
                event = notes[0] if len(notes) == 1 else _PluteChord(notes, staff=staff)
                bar_obj.events.append(event)
                for note, k in zip(notes, ks):
                    note._event = event            # the drawn event, for the playhead position
                    placed.append((pos, note, k))
                sounding = max(sounding, max(pos + lengths[k] for k in ks))
                nxt = groups[gi + 1][0] if gi + 1 < len(groups) else max(blen, pos)
                quiet = max(pos, min(sounding, nxt))           # where silence begins before nxt
                fill, left = rests(nxt - quiet) if nxt - quiet > 0.124 else ([], nxt - quiet)
                event._layout_dur = max(1e-3, quiet - pos + left) / 4
                bar_obj.events.extend(fill)
            return placed

        # Every note with its start position (quarter notes from the first real bar)
        timed: list[tuple[float, int, _PluteNote]] = []
        bar_start = 0.0
        for rel_i in range(len(bars)):
            blen = _bar_len_q(bar_lens, rel_i, time)
            for si, staff, staff_bars, tl, ol in ((0, st0, bars, types, onsets),
                                                  (1, st1, bass_bars, bass_types, bass_onsets)):
                if staff is None or staff_bars is None:
                    continue
                bar_obj = staff.bars[n_prep + rel_i]
                pitches = staff_bars[rel_i] if rel_i < len(staff_bars) else []
                if not pitches:
                    bar_obj.events.append(_PluteRest(rtype="whole", staff=staff))
                    continue
                nt, positions, lengths, ties, vels = _bar_notes(tl, ol, meta, si, rel_i, pitches, time, blen)
                for pos, note, k in _fill(staff, bar_obj, pitches, nt, positions, lengths, blen):
                    note._si = si
                    note._bar = n_prep + rel_i
                    note._len_q = lengths[k]
                    note._vel = vels[k]
                    note._tied = ties[k]
                    if not ties[k]:                    # a tied note sounds on, it is not struck again
                        timed.append((round(bar_start + pos, 4), si, note))
            bar_start += blen

        # Room per bar: enough for the busier bars of this piece to stay readable (every
        # bar of the strip gets the same width)
        busy = sorted(max(len(st.bars[b].events) for st in self._score.staffs)
                      for b in range(n_prep, n_bars)) or [0]
        self._px_per_bar = max(_PX_PER_BAR, 24 * busy[int(len(busy) * 0.85)] + 70)

        # _step_list: notes that start at the same moment, on either staff, form one step.
        # _step_beats: how long each step lasts, in quarter notes (used by performance mode).
        timed.sort(key=lambda e: (e[0], e[1]))
        self._step_list: list[list[_PluteNote]] = []
        step_pos: list[float] = []
        for pos, _, note in timed:
            if step_pos and abs(pos - step_pos[-1]) < 1e-4:
                self._step_list[-1].append(note)
            else:
                self._step_list.append([note])
                step_pos.append(pos)
        self._step_beats = [(step_pos[i + 1] if i + 1 < len(step_pos) else bar_start) - step_pos[i]
                            for i in range(len(step_pos))]
        # seconds, through the piece's tempo changes (timed play and listening)
        self._sec = _seconds_fn((meta or {}).get("tempos") if phase != "practice" else None, bpm)
        self._step_secs = [self._sec(step_pos[i] + self._step_beats[i]) - self._sec(step_pos[i])
                           for i in range(len(step_pos))]

        # Fingering: the treble staff is the right hand and the bass staff the left; a single
        # staff belongs to the hand its clef suggests
        hands_of = ({0: "right", 1: "left"} if n_staves > 1
                    else {0: "left" if clef == "bass" else "right"})
        from pianove.state import beta_features_state
        if beta_features_state.value:                   # the hands are a beta feature
            self.finger_plan = _plan_fingering(self._step_list, step_pos, bpm, hands_of)
        else:
            self.finger_plan = [{} for _ in self._step_list]
        self.bottom_inset = None          # → px hidden at the bottom (the keyboard panel)

        self.current_idx: int = min(initial_idx, len(self._step_list))
        for i in range(self.current_idx):
            for note in self._step_list[i]:
                note.color = _GREEN

        self._phase      = phase
        self._on_advance = on_advance
        self._perf_timer = 0.0
        self._perf_hit   = False
        self.on_tick     = None           # listen mode: (time, length, playing) every frame
        if phase == "listen":
            self._setup_listen(step_pos, bar_start)

        self._dirty      = True
        self._dirty_bars: set[int] = set()   # bars whose notes changed colour
        self._ink: tuple[int, int] | None = None
        self._full_redraw = True
        self._strip_w    = 0
        self._offscreen: pygame.Surface | None = None
        self._note_xs:   list[float] = []

        self._scroll = Spring(value=0.0, response=0.55, damping_fraction=0.88)
        self._ph     = Spring(value=0.0, response=0.35, damping_fraction=0.82)

    @property
    def total_notes(self) -> int:
        return len(self._step_list)

    def expected_midis(self) -> frozenset[int]:
        if self._in_prep or self.current_idx >= len(self._step_list):
            return frozenset()
        midis = set()
        for ev in self._step_list[self.current_idx]:
            if isinstance(ev, _PluteChord):
                midis.update(_pitch_to_midi(n.pitch) for n in ev.notes)
            else:
                midis.add(_pitch_to_midi(ev.pitch))
        return frozenset(midis)

    def upcoming_midis(self) -> frozenset[int]:
        """The keys to show on the keyboard: the current step's, also during the count-in,
        so the player sees where to start."""
        if self.current_idx >= len(self._step_list):
            return frozenset()
        return frozenset(_pitch_to_midi(n.pitch) for n in self._step_list[self.current_idx])

    def expected_midi(self) -> int | None:
        m = self.expected_midis()
        return next(iter(m)) if m else None

    def advance(self):
        if self.current_idx >= len(self._step_list):
            return
        for note in self._step_list[self.current_idx]:
            note.color = _GREEN
        self._touch(self._step_list[self.current_idx])
        self.current_idx += 1
        self._update_spring_targets()

    def mark_wrong(self):
        if self.current_idx < len(self._step_list):
            for note in self._step_list[self.current_idx]:
                note.color = _RED
            self._touch(self._step_list[self.current_idx])

    @property
    def hits(self) -> int:
        return self._hits

    def mark_hit(self):
        if self.current_idx < len(self._step_list):
            self._perf_hit = True
            self._hits += 1
            for note in self._step_list[self.current_idx]:
                note.color = _GREEN
            self._touch(self._step_list[self.current_idx])

    def restart(self):
        for step in self._step_list:
            for note in step:
                note.color = None
        self._dirty      = True
        self._full_redraw = True
        self.current_idx = 0
        self._perf_timer = 0.0
        self._perf_hit   = False
        if self._phase == "performance":
            self._prep_elapsed = 0.0
            self._in_prep      = True
        self._ph.snap_to(0.0)
        self._scroll.snap_to(0.0)
        self._scroll.target = 0.0

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
        self._strip_w = max(vw, self._n_bars * self._px_per_bar)
        self._score._on_resize(self._strip_w)
        h = self._score.total_content_height(self._strip_w)
        self._offscreen = pygame.Surface((self._strip_w, h))
        self._offscreen.fill((255, 255, 255))
        self._score.surface = self._offscreen
        for staff in self._score.staffs:
            staff.surface = self._offscreen
        if self._score.brace:
            self._score.brace.surface = self._offscreen
        self._score.draw()
        self._ink = None
        self._full_redraw = False
        self._dirty_bars.clear()
        # One x per step: the leftmost note of the step
        self._note_xs = [min(getattr(n, "_event", n).offset for n in step) for step in self._step_list]
        if self._note_xs:
            snap_x = self._note_xs[min(self.current_idx, len(self._note_xs) - 1)]
            self._ph.snap_to(snap_x)
            vw = max(1, self.rect.width)
            self._scroll.snap_to(max(0.0, snap_x - vw * 0.30))
        self._dirty = False

    def _ink_extent(self) -> tuple[int, int]:
        """The rows of the score that have anything drawn on them (worked out once)."""
        if self._ink is None:
            import numpy as np
            off = self._offscreen
            narrow = pygame.transform.smoothscale(off, (max(1, off.get_width() // 16), off.get_height()))
            rows = np.nonzero(pygame.surfarray.array3d(narrow).min(axis=2).min(axis=0) < 245)[0]
            self._ink = (int(rows[0]), int(rows[-1])) if len(rows) else (0, off.get_height())
        return self._ink

    def _touch(self, notes):
        """These notes changed colour: their bars need drawing again."""
        self._dirty_bars.update(getattr(n, "_bar", 0) for n in notes)
        self._dirty = True

    def _redraw_offscreen(self):
        if self._full_redraw or len(self._dirty_bars) > 4:
            self._offscreen.fill((255, 255, 255))
            self._score.draw()
        else:
            for i in sorted(self._dirty_bars):
                self._redraw_bar(i)
        self._dirty_bars.clear()
        self._full_redraw = False
        self._dirty = False

    def _redraw_bar(self, i: int):
        """Draw one bar again, in place: much quicker than the whole score, which matters
        in timed play, where every note played recolours its bar. The bar's neighbours are
        drawn too, for the ties that cross its bar lines. Text glyphs ignore the clip, so
        whatever lies beside the bar is kept and put back afterwards: nothing outside the
        bar is drawn twice."""
        surf = self._offscreen
        staffs = self._score.staffs
        bars = staffs[0].bars
        bar = bars[i]
        x0 = int(bar.bar_start_x) + 2
        x1 = int(bar.bar_start_x + bar.barspace) + 3
        h = surf.get_height()
        rect = pygame.Rect(x0, 0, max(1, x1 - x0), h)
        pad = int(staffs[0].space * 3)
        left_x = max(0, int(bars[i - 1].bar_start_x) - pad) if i > 0 else max(0, x0 - pad)
        right_x = min(surf.get_width(), int(bars[i + 1].bar_start_x + bars[i + 1].barspace) + pad
                      if i + 1 < len(bars) else x1 + pad)
        beside = [(left_x, surf.subsurface((left_x, 0, x0 - left_x, h)).copy())] if x0 > left_x else []
        if right_x > x1:
            beside.append((x1, surf.subsurface((x1, 0, right_x - x1, h)).copy()))
        old = surf.get_clip()
        surf.set_clip(rect)
        surf.fill((255, 255, 255), rect)
        for staff in staffs:
            staff.draw_lines()
        for staff in staffs:
            for j in (i - 1, i, i + 1):
                if 0 <= j < len(staff.bars):
                    staff.bars[j].draw()
        # the bar lines, as Score.draw makes them
        span = 4 * staffs[0].space
        top, bot = staffs[0].position[1], staffs[-1].position[1] + span
        last = len(staffs[0].bars) - 1
        for j in (i - 1, i):
            if 0 <= j <= last:
                b = staffs[0].bars[j]
                x = b.bar_start_x + b.barspace
                if j == last:
                    pygame.draw.line(surf, (0, 0, 0), (x - 4, top), (x - 4, bot), 1)
                    pygame.draw.rect(surf, (0, 0, 0), (x, top, 3, bot - top))
                else:
                    pygame.draw.line(surf, (0, 0, 0), (x, top), (x, bot), 2)
        surf.set_clip(old)
        for x, strip in beside:
            surf.blit(strip, (x, 0))

    # ── Listen mode: Pianove plays the piece itself ──────────────────────────────

    def _setup_listen(self, step_pos: list[float], end_q: float):
        """The timeline of the piece in seconds: when each step starts, and when each of
        its notes is struck and let go (by the player, on its own clock)."""
        sec = self._sec
        self._step_t = [sec(p) for p in step_pos]
        self._step_ends = []
        events = []
        for p, t0, step in zip(step_pos, self._step_t, self._step_list):
            ends = []
            for n in step:
                end = max(t0 + 0.03, t0 + (sec(p + n._len_q) - t0) * 0.96)
                ends.append(end)
                m = _pitch_to_midi(n.pitch)
                vel = n._vel or (82 if n._si == 0 else 74)
                events.append((t0, 1, m, vel, n._si))
                events.append((end, 0, m, 0, n._si))
            self._step_ends.append(ends)
        events.sort(key=lambda e: (e[0], e[1]))          # at the same moment: release first
        self.total_time = sec(end_q)
        self._player = _Player(events, self.total_time)
        self._next = 0                                    # steps shown as started
        self._lit: dict = {}                              # note → ends at (drawn blue)
        _LISTENING[0] = self

    @property
    def listen_t(self) -> float:
        return self._player.position()

    @property
    def playing(self) -> bool:
        return self._player.playing

    @property
    def sounding(self) -> dict[int, int]:
        """The keys sounding now → the staff each belongs to (0 treble, 1 bass)."""
        return dict(self._player.sounding) if self._phase == "listen" else {}

    def _unlight(self):
        for note in self._lit:
            note.color = None
        if self._lit:
            self._touch(list(self._lit))
        self._lit.clear()

    def stop_listening(self):
        self._player.close()
        self._unlight()

    def toggle_play(self):
        if self._player.playing:
            self._player.pause()
            self._unlight()
        else:
            if self._player.position() >= self.total_time - 1e-3:
                self.seek(0.0)
            self._player.play()

    def seek(self, t: float):
        """Jump to a moment of the piece. Notes already under way there are not struck
        again; the next ones play as the time comes."""
        import bisect
        self._player.seek(t)
        self._unlight()
        t = self._player.position()
        self._next = bisect.bisect_left(self._step_t, t - 1e-6)
        self.current_idx = max(0, min(len(self._step_list) - 1, self._next - 1 if self._next else 0))
        self._place_playhead(snap=True)

    def _place_playhead(self, snap: bool = False):
        """The playhead glides between the steps' x positions with the time."""
        if not self._note_xs:
            return
        t = self._player.position()
        i = self._next - 1
        if i < 0:
            x = self._note_xs[0] * min(1.0, t / max(1e-3, self._step_t[0])) if self._step_t else 0
        else:
            t0 = self._step_t[i]
            t1 = self._step_t[i + 1] if i + 1 < len(self._step_t) else self.total_time
            x0 = self._note_xs[i]
            x1 = self._note_xs[i + 1] if i + 1 < len(self._note_xs) else x0 + 60
            x = x0 + (x1 - x0) * min(1.0, (t - t0) / max(1e-3, t1 - t0))
        vw = max(1, self.rect.width)
        target = min(max(0.0, self._strip_w - vw), max(0.0, x - vw * 0.30))
        self._ph.snap_to(x)
        if snap:
            self._scroll.snap_to(target)
        self._scroll.target = target

    def _listen_update(self, dt: float):
        """The screen follows the music: notes light up while they sound."""
        if not _LISTEN_THREADED:
            self._player.advance()
        t = self._player.position()
        if self._player.playing:
            started = []
            while self._next < len(self._step_t) and self._step_t[self._next] <= t:
                for note, end in zip(self._step_list[self._next], self._step_ends[self._next]):
                    note.color = _BLUE
                    self._lit[note] = end
                    started.append(note)
                self.current_idx = self._next
                self._next += 1
            if started:
                self._touch(started)
        done = [n for n, end in self._lit.items() if end <= t or not self._player.playing]
        for note in done:
            note.color = None
            del self._lit[note]
        if done:
            self._touch(done)
        if self._player.playing or not self._note_xs or self._ph.value == 0:
            self._place_playhead()
        if self.on_tick:
            self.on_tick(t, self.total_time, self._player.playing)

    def handle_content_event(self, event: pygame.event.Event) -> bool:
        if self._phase != "listen" or event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_SPACE:
            self.toggle_play()
        elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.seek(self.listen_t + (5.0 if event.key == pygame.K_RIGHT else -5.0))
        elif event.key == pygame.K_HOME:
            self.seek(0.0)
        else:
            return False
        return True

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

        if self._phase == "listen":
            self._listen_update(dt)
            return

        if self._phase == "performance" and self.current_idx < len(self._step_list):
            self._perf_timer += dt
            note_dur = self._step_secs[self.current_idx]

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
                if not self._perf_hit and self.current_idx < len(self._step_list):
                    for note in self._step_list[self.current_idx]:
                        note.color = _ORANGE
                    self._touch(self._step_list[self.current_idx])
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
        # the keyboard panel covers the bottom: centre the score in what is left
        view_h = max(vh // 2, vh - int(self.bottom_inset())) if self.bottom_inset else vh

        if off_h <= view_h:
            # Vertically centre what is drawn (notes far above or below the staves
            # included) within the visible part of the canvas
            ink_top, ink_bot = self._ink_extent()
            y_offset = view_h // 2 - (ink_top + ink_bot) // 2
            y_offset = max(4 - ink_top, min(view_h - 4 - ink_bot, y_offset))   # keep the ink in view
            src_y = max(0, -y_offset)
            surface.blit(self._offscreen,
                         (rect.left, rect.top + max(0, y_offset)),
                         pygame.Rect(scroll, src_y, vw, off_h - src_y))
            ph_top = rect.top + y_offset + 4
            ph_bot = rect.top + y_offset + off_h - 4
        else:
            # Content taller than canvas: centre the whole system
            space      = self._score.staffs[0].space if self._score.staffs else 20
            n_st       = len(self._score.staffs)
            sys_h      = (n_st - 1) * space * 9 + space * 4  # _SG=9, staff_span=4
            staff_top_y  = int(space * 4)                     # _MT=4
            staff_bot_y  = staff_top_y + int(sys_h)
            staff_center = (staff_top_y + staff_bot_y) // 2
            # centre what is actually drawn (notes far above or below the staves included),
            # as far as the staves themselves stay in view
            ink_top, ink_bot = self._ink_extent()
            lo = staff_bot_y + 6 - view_h // 2
            hi = staff_top_y - 6 + view_h // 2
            if lo <= hi:
                staff_center = min(hi, max(lo, (ink_top + ink_bot) // 2))
            y_src  = max(0, min(off_h - view_h, staff_center - view_h // 2))
            blit_h = min(vh, off_h - y_src)
            surface.blit(self._offscreen, rect.topleft,
                         pygame.Rect(scroll, y_src, vw, blit_h))
            ph_top = rect.top + 4
            ph_bot = rect.bottom - 4

        ph_sx = rect.left + int(self._ph.value) - scroll
        if rect.left <= ph_sx <= rect.right:
            pygame.draw.line(surface, _BLUE,
                             (ph_sx, ph_top), (ph_sx, ph_bot), 2)


class _LessonPiano:
    def __init__(self, staff_view: _StaffView, advance_fn, wrong_fn, reveal_fn=None):
        from pianove.state import midi_panel
        self._panel   = midi_panel
        self._sv      = staff_view
        self._advance = advance_fn
        self._wrong   = wrong_fn
        self._reveal  = reveal_fn         # → px of the panel currently shown
        self.fit_panel = None             # → keeps the panel's height fitted to the keyboard
        # Key presses from before this page (the previous section) do not count
        self._panel.take_note_ons()
        self._pressed_this_step: set[int] = set()
        from pianove.state import hand_tone_state
        self._hands   = HandsOverlay(staff_view.finger_plan,
                                     memory=(ctx.current_song_id or ctx.current_lesson_id,
                                             ctx.current_song_hand, ctx.practice_mode),
                                     skin=hand_tone_state.value)
        self._status_font: pygame.font.Font | None = None
        self._kb_cache = None

    def update(self, dt: float, rect: pygame.Rect):
        self._panel.update(dt, rect)
        if self.fit_panel:
            self.fit_panel()
        # every press counts, even a key let go and pressed again within one frame
        for note in self._panel.take_note_ons():
            self._handle_note(note)

        # In timed play the hands move on before the next note is due
        sv, lead, step_time = self._sv, 0.0, 0.0
        if sv._phase == "performance" and not sv._in_prep and sv.current_idx < len(sv._step_beats):
            step_time = sv._step_secs[sv.current_idx]
            lead = sv._perf_timer / step_time if step_time > 0 else 0.0
        if sv._phase == "listen":
            # the hands play what sounds; while playing they move on in time like a player
            step = max(0, sv._next - 1)
            if sv.playing and sv._next < len(sv._step_t):
                t0 = sv._step_t[step] if sv._next else 0.0
                step_time = max(1e-3, sv._step_t[sv._next] - t0)
                lead = min(1.0, max(0.0, (sv.listen_t - t0) / step_time))
            self._hands.update(dt, step, frozenset(sv.sounding), lead, step_time)
            return
        self._hands.update(dt, sv.current_idx, frozenset(self._panel.active_notes), lead, step_time)

    def handle_event(self, event: pygame.event.Event, rect: pygame.Rect) -> bool:
        return False

    def _handle_note(self, note_num: int):
        if self._sv._phase == "listen":
            return                                    # listening: the keys are only played back
        expected = self._sv.expected_midis()
        if not expected:
            return
        if note_num in expected:
            self._pressed_this_step.add(note_num)
            if self._pressed_this_step >= expected:
                # All notes in this step have been pressed — advance
                self._pressed_this_step.clear()
                if self._sv._phase == "practice":
                    self._advance()
                else:
                    self._sv.mark_hit()
        elif self._sv._phase == "practice":
            self._pressed_this_step.clear()
            self._wrong()

    def draw(self, surface: pygame.Surface, rect: pygame.Rect):
        expected = self._sv.upcoming_midis()   # frozenset[int]
        active   = self._panel.active_notes
        idx      = self._sv.current_idx
        sounding = self._sv.sounding           # listen mode: the keys Pianove is playing
        if self._sv._phase == "listen":
            expected, active = frozenset(), frozenset(sounding)

        # The panel opens from the bottom; above _KB_H it is the hands' room
        shown    = self._reveal() if self._reveal else rect.height
        hands_h  = max(0, shown - _KB_H)
        hands_on = hands_h > 1

        # Expand keyboard range to include all expected notes (and where the hands go next)
        for m in (expected | self._hands.keys_needed(idx)) if hands_on else expected:
            self._panel._expand_for_note(m)

        margin_x = max(8, int(rect.width * 0.02))
        status_h = max(16, int(_KB_H * 0.14))
        top      = rect.bottom - shown + max(3, int(_KB_H * 0.02))
        key_h    = max(40, _KB_H - status_h - max(3, int(_KB_H * 0.02)) - 4)
        avail_w  = max(60, rect.width - margin_x * 2)
        white_notes   = self._panel._white_notes
        black_notes   = self._panel._black_notes
        black_indices = self._panel._black_indices
        white_w  = avail_w / max(1, len(white_notes))
        black_w  = white_w * 0.58
        black_h  = key_h * 0.62

        def _active(n): return n in active
        def _exp(n):    return n in expected

        def _hand_col(note):
            return self._hands.colour_of(note, idx) if hands_on else None

        def _played(note):
            """A key Pianove plays, in the colour of the hand playing it."""
            from pianove.hands import ACCENT
            side = "left" if sounding.get(note) == 1 or (sounding.get(note) == 0 and
                                                        ctx.current_song_hand == "left") else "right"
            return ACCENT[side]

        def _wc(note):
            if note in sounding: return tuple(int(255 - (255 - c) * 0.75) for c in _played(note))
            if _active(note): return (190, 60, 60)
            if _exp(note):
                acc = _hand_col(note)          # the colour of the hand that plays it
                if acc:
                    return tuple(int(255 - (255 - c) * 0.5) for c in acc)
                return (120, 180, 255)
            return (255, 255, 255)

        def _bc(note):
            if note in sounding: return tuple(int(c * 0.9) for c in _played(note))
            if _active(note): return (140, 45, 45)
            if _exp(note):
                acc = _hand_col(note)
                if acc:
                    return tuple(int(c * 0.85) for c in acc)
                return (30, 100, 200)
            return (0, 0, 0)

        surface.fill(iOSTheme.tertiary_background, rect)

        white_keys = [
            (pygame.Rect(int(rect.left + margin_x + i * white_w), int(top),
                         max(2, int(white_w) - 1), int(key_h)), _wc(note))
            for i, note in enumerate(white_notes)
        ]
        black_keys = [
            (pygame.Rect(int(rect.left + margin_x + idx * white_w + white_w - black_w / 2),
                         int(top), max(2, int(black_w)), int(black_h)), _bc(note))
            for idx, note in zip(black_indices, black_notes)
        ]

        # the keys, drawn again only when one of them changes colour
        key = (rect.size, rect.topleft, tuple(white_keys), tuple(black_keys))
        if self._kb_cache is None or self._kb_cache[0] != key:
            x0 = min((kr.left for kr, _ in white_keys), default=rect.left)
            y0 = int(top)
            surf = pygame.Surface((max(1, rect.right - x0), max(1, int(key_h) + 1)))
            surf.fill(iOSTheme.tertiary_background)
            for kr, col in white_keys:
                r = kr.move(-x0, -y0)
                pygame.draw.rect(surf, col, r)
                pygame.draw.rect(surf, (80, 80, 80), r, 1)
            for kr, col in black_keys:
                pygame.draw.rect(surf, col, kr.move(-x0, -y0), border_radius=4)
            self._kb_cache = (key, surf, (x0, y0))
        surface.blit(self._kb_cache[1], self._kb_cache[2])

        if hands_on and white_notes:
            kb = KeyboardGeometry(left=rect.left + margin_x, white_w=white_w, top=top,
                                  key_h=key_h, black_h=black_h,
                                  first_white_x=_key_x(white_notes[0]), bottom=rect.bottom - 2)
            self._hands.draw(surface, kb, alpha=min(1.0, hands_h / ((_kb_h_hands() - _KB_H) * 0.7)))

        # the MIDI (or microphone) status, on top of everything (a sleeve may pass beneath it)
        connected = self._panel.connected
        label_txt = self._panel.status_text()
        label_col = (52, 199, 89) if connected else (180, 100, 100)
        if self._status_font is None:
            self._status_font = pygame.font.SysFont(None, max(14, status_h - 2))
        ls = self._status_font.render(label_txt, True, label_col)
        pos = (rect.left + margin_x, rect.bottom - status_h + (status_h - ls.get_height()) // 2)
        if hands_on:
            pill = pygame.Surface((ls.get_width() + 12, ls.get_height() + 4), pygame.SRCALPHA)
            pygame.draw.rect(pill, (*iOSTheme.tertiary_background[:3], 225), pill.get_rect(),
                             border_radius=pill.get_height() // 2)
            surface.blit(pill, (pos[0] - 6, pos[1] - 2))
        surface.blit(ls, pos)
        if connected and self._panel.input_mode == "mic":
            from pianove.midi.panel import draw_level_meter
            draw_level_meter(surface, pygame.Rect(pos[0] + ls.get_width() + 10,
                                                  pos[1] + ls.get_height() // 2 - 3, 80, 6),
                             self._panel.input_level)


def _clock(t: float, total: float) -> str:
    return f"{int(t) // 60}:{int(t) % 60:02d} / {int(total) // 60}:{int(total) % 60:02d}"


def _add_transport(controls: FloatLayout, sv_ref: list, right_w: int):
    """Listen mode's transport in the controls bar: play/pause, a timeline to jump
    anywhere in the piece, and the time."""
    from pylay import Slider
    win_w = ctx.ui.width if ctx.ui else 1024
    x_play, time_w = 150, 96
    slider_w = max(80, win_w - (x_play + 44) - time_w - right_w - 16)

    def _draw_play(surface: pygame.Surface, rect: pygame.Rect):
        sv = sv_ref[0]
        pygame.draw.rect(surface, iOSTheme.fill, rect, border_radius=8)
        c, (cx, cy) = iOSTheme.label, rect.center
        if sv is not None and sv.playing:
            for dx in (-5, 2):
                pygame.draw.rect(surface, c, pygame.Rect(cx + dx, cy - 7, 4, 14), border_radius=1)
        else:
            pygame.draw.polygon(surface, c, [(cx - 4, cy - 8), (cx - 4, cy + 8), (cx + 8, cy)])

    def _press_play(event: pygame.event.Event, rect: pygame.Rect) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and rect.collidepoint(event.pos):
            if sv_ref[0] is not None:
                sv_ref[0].toggle_play()
            return True
        return False

    controls.add_child(PygameCanvas(on_draw=_draw_play, on_event=_press_play, draw_border=False,
                                    anchor="left", x=x_play, y=0, width=36, height=32))
    pos_state = State(0.0)
    time_state = State(_clock(0, 0))

    def _seek(v: float):
        if sv_ref[0] is not None:
            sv_ref[0].seek(v * sv_ref[0].total_time)

    slider = Slider(value=pos_state, on_change=_seek,
                    anchor="left", x=x_play + 44, y=0, width=slider_w, height=32)
    controls.add_child(slider)
    controls.add_child(Label(text=time_state, font_size=13, color=iOSTheme.secondary_label,
                             anchor="left", x=x_play + 52 + slider_w, y=0, width=time_w, height=44))

    def _tick(t: float, total: float, playing: bool):
        if not slider.is_dragging and total > 0 and abs(pos_state.value - t / total) > 1e-4:
            pos_state.value = t / total
        txt = _clock(t, total)
        if txt != time_state.value:
            time_state.value = txt

    def _hook():
        if sv_ref[0] is not None:
            sv_ref[0].on_tick = _tick
            time_state.value = _clock(0, sv_ref[0].total_time)
    _TRANSPORT_HOOKS.append(_hook)


_TRANSPORT_HOOKS: list = []


def _build_practice_completion(hits: int, total: int, bpm: int) -> FloatLayout:
    accuracy = hits / total if total > 0 else 0.0
    pct      = int(accuracy * 100)
    acc_color = (
        _GREEN  if pct >= 80 else
        _ORANGE if pct >= 50 else
        _RED
    )

    def _try_again():
        ctx.lesson_current_idx = 0
        ctx.lesson_section_idx = 0
        ctx.lesson_completed   = False
        ctx.lesson_phase       = "performance"
        ctx.router.refresh()

    def _new_session():
        ctx.practice_mode  = False
        ctx.practice_bars  = None
        ctx.lesson_completed = False
        ctx.lesson_phase   = "practice"
        ctx.router.navigate("home", "left")

    win_h  = ctx.ui.height if ctx.ui else 768
    body_h = max(100, win_h - 52 - 1)  # nav + divider

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
    nav.add_child(Label(text=t("practice_session_done"), font_size=16, bold=True,
                        color=iOSTheme.label, anchor="center", x=0, y=0))
    main.add_child(nav)
    main.add_child(FloatLayout(width=1.0, height=1,
                               background_color=pygame.Color(120, 120, 128, 60)))

    body = VStack(spacing=16, padding=40, width=1.0, height=body_h)

    body.add_child(EmojiIcon("🎯", size=64, color=acc_color,
                             anchor="center", x=0, y=0))
    body.add_child(Label(text=f"{pct}%", font_size=56, bold=True,
                         color=acc_color, anchor="center", x=0, y=0, height=68))
    body.add_child(Label(text=t("practice_accuracy_label"), font_size=14,
                         color=iOSTheme.secondary_label,
                         anchor="center", x=0, y=0))

    # Stats row: notes + BPM
    stats_row = FloatLayout(width=1.0, height=64)
    for val, lbl, x in [
        (str(hits),  t("practice_hits"),  0.08),
        (str(total), t("practice_notes"), 0.38),
        (str(bpm),   t("practice_bpm"),   0.68),
    ]:
        col = VStack(spacing=2, padding=10, anchor="top_left", x=x, y=0,
                     width=0.26, height=1.0,
                     background_color=iOSTheme.secondary_background,
                     border_radius=10)
        col.add_child(Label(text=val, font_size=20, bold=True,
                            color=iOSTheme.label, height=28))
        col.add_child(Label(text=lbl, font_size=11,
                            color=iOSTheme.secondary_label, height=16))
        stats_row.add_child(col)
    body.add_child(stats_row)

    btn_row = FloatLayout(width=1.0, height=50)
    btn_row.add_child(Button(text=t("practice_try_again"), on_click=_try_again,
                             anchor="left", x=16, y=0, width=0.42, height=44, font_size=14,
                             background_color=iOSTheme.fill, text_color=iOSTheme.label,
                             border_radius=12))
    btn_row.add_child(Button(text=t("practice_new_session"), on_click=_new_session,
                             anchor="right", x=-16, y=0, width=0.42, height=44, font_size=14,
                             background_color=_PURPLE,
                             text_color=pygame.Color(255, 255, 255),
                             border_radius=12))
    body.add_child(btn_row)
    main.add_child(body)
    return root


def _step_nav(lesson_title: str) -> FloatLayout:
    nav = FloatLayout(width=1.0, height=52,
                      background_color=iOSTheme.secondary_background)
    nav.add_child(Button(text=t("back"), on_click=_nav_back,
                         anchor="left", x=12, y=0,
                         width=72, height=34, font_size=14,
                         background_color=iOSTheme.fill,
                         text_color=iOSTheme.label, border_radius=8))
    nav.add_child(Label(text=lesson_title, font_size=16, bold=True,
                        color=iOSTheme.label, anchor="center", x=0, y=0))
    return nav


def _build_text_step(step: dict, lesson_title: str,
                     step_idx: int, total_steps: int) -> FloatLayout:
    def _advance():
        ctx.lesson_step_idx    = step_idx + 1
        ctx.lesson_current_idx = 0
        ctx.lesson_section_idx = 0
        ctx.lesson_phase       = "practice"
        ctx.router.refresh()

    win_h   = ctx.ui.height if ctx.ui else 768
    body_h  = max(100, win_h - 52 - 1 - 72)  # nav + divider + btn_row

    root = FloatLayout(width=1.0, height=1.0,
                       background_color=iOSTheme.background)
    main = VStack(spacing=0, padding=0, width=1.0, height=1.0)
    root.add_child(main)

    main.add_child(_step_nav(lesson_title))
    main.add_child(FloatLayout(width=1.0, height=1,
                               background_color=pygame.Color(120, 120, 128, 60)))

    body = VStack(spacing=18, padding=40, width=1.0, height=body_h)

    if total_steps > 1:
        body.add_child(Label(
            text=t("step_of", n=step_idx + 1, total=total_steps),
            font_size=12, color=iOSTheme.secondary_label,
        ))

    emoji = step.get("emoji", "")
    if emoji:
        body.add_child(EmojiIcon(emoji, size=64))

    title = step.get("title", "")
    if title:
        body.add_child(Label(text=title, font_size=24, bold=True,
                             color=iOSTheme.label, wrap_width=520))

    body_text = step.get("body", "")
    if body_text:
        body.add_child(Label(text=body_text, font_size=16,
                             color=iOSTheme.secondary_label, wrap_width=520))

    main.add_child(body)

    btn_row = FloatLayout(width=1.0, height=72)
    btn_row.add_child(Button(
        text=t("step_continue"), on_click=_advance,
        anchor="right", x=-24, y=0, width=180, height=44, font_size=15,
        background_color=_GREEN,
        text_color=pygame.Color(255, 255, 255), border_radius=12,
    ))
    main.add_child(btn_row)
    return root


def _build_notation_demo_step(step: dict, lesson_title: str,
                               step_idx: int, total_steps: int) -> FloatLayout:
    def _advance():
        ctx.lesson_step_idx    = step_idx + 1
        ctx.lesson_current_idx = 0
        ctx.lesson_section_idx = 0
        ctx.lesson_phase       = "practice"
        ctx.router.refresh()

    win_h   = ctx.ui.height if ctx.ui else 768
    staff_h = max(160, min(280, win_h // 3))
    body_h  = max(100, win_h - 52 - 1 - 72)  # nav + divider + btn_row

    root = FloatLayout(width=1.0, height=1.0,
                       background_color=iOSTheme.background)
    main = VStack(spacing=0, padding=0, width=1.0, height=1.0)
    root.add_child(main)

    main.add_child(_step_nav(lesson_title))
    main.add_child(FloatLayout(width=1.0, height=1,
                               background_color=pygame.Color(120, 120, 128, 60)))

    body = VStack(spacing=16, padding=24, width=1.0, height=body_h)

    if total_steps > 1:
        body.add_child(Label(
            text=t("step_of", n=step_idx + 1, total=total_steps),
            font_size=12, color=iOSTheme.secondary_label,
        ))

    title = step.get("title", "")
    if title:
        body.add_child(Label(text=title, font_size=18, bold=True,
                             color=iOSTheme.label))

    caption = step.get("caption", "")
    if caption:
        body.add_child(Label(text=caption, font_size=14,
                             color=iOSTheme.secondary_label, wrap_width=600))

    # Read-only staff — no MIDI piano, playhead at rest
    bars  = step.get("bars", [["C4", "E4", "G4", "C5"]])
    clef  = step.get("clef", "treble")
    bass  = step.get("bass_bars", None)
    staff = _StaffView(
        bars=bars, phase="practice",
        initial_idx=0, on_advance=None,
        bpm=_BPM, clef=clef, bass_bars=bass,
        width=1.0, height=staff_h,
    )
    body.add_child(staff)

    main.add_child(body)

    btn_row = FloatLayout(width=1.0, height=72)
    btn_row.add_child(Button(
        text=t("step_got_it"), on_click=_advance,
        anchor="right", x=-24, y=0, width=180, height=44, font_size=15,
        background_color=_BLUE,
        text_color=pygame.Color(255, 255, 255), border_radius=12,
    ))
    main.add_child(btn_row)
    return root


def _build_completion(lesson_title: str) -> FloatLayout:
    win_h  = ctx.ui.height if ctx.ui else 768
    body_h = max(100, win_h - 52 - 1)  # nav + divider

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

    body = VStack(spacing=20, padding=40, width=1.0, height=body_h)
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
            ctx.lesson_step_idx      = 0
            ctx.lesson_current_idx   = 0
            ctx.lesson_section_idx   = 0
            ctx.lesson_completed     = False
            ctx.lesson_phase         = "practice"
            ctx.router.refresh()
        btn_row.add_child(Button(text=t("lesson_next"), on_click=_go_next,
                                 anchor="right", x=-16, y=0, width=0.42, height=44, font_size=14,
                                 background_color=_GREEN,
                                 text_color=pygame.Color(255, 255, 255),
                                 border_radius=12))
    body.add_child(btn_row)
    main.add_child(body)
    return root


def build():
    from pianove.lesson_loader import load_lesson

    _stop_listening()                                 # a page rebuilt while listening falls silent

    lesson_id    = ctx.current_lesson_id
    keyboard_vis = ctx.lesson_keyboard_vis
    if ctx.lesson_hands_vis is None:
        from pianove.state import storage
        ctx.lesson_hands_vis = bool(storage.get("show_hands", True))
    from pianove.state import beta_features_state
    beta         = bool(beta_features_state.value)  # the hands are a beta feature
    hands_vis    = ctx.lesson_hands_vis and beta
    section_idx  = ctx.lesson_section_idx
    initial_idx  = ctx.lesson_current_idx

    # Practice (go) mode: skip all lesson loading, force performance phase
    is_practice = ctx.practice_mode
    bpm         = ctx.practice_bpm if is_practice else _BPM

    if is_practice:
        clef = ctx.practice_clef
    elif ctx.current_song_id:
        clef = "bass" if ctx.current_song_hand == "left" else "treble"
    else:
        clef = "treble"

    if is_practice:
        phase        = "performance"
        ctx.lesson_phase = "performance"
        lesson_title = t("practice_title")
        lesson       = {"title": lesson_title, "steps": []}
        song_time    = (4, 4)
    else:
        phase  = ctx.lesson_phase
        lesson = load_lesson(lesson_id)
        if lesson is None:
            lesson = {"title": lesson_id, "steps": []}
        if ctx.current_song_id:
            from pianove.song_store import get_song
            _song = get_song(ctx.current_song_id)
            lesson_title = _song["title"] if _song else ctx.current_song_id
            song_time    = tuple(_song["time"]) if _song and "time" in _song else (4, 4)
        else:
            lesson_title = lesson.get("title", lesson_id)
            song_time    = (4, 4)

    # Non-exercise steps (text, notation_demo) are handled before the full
    # exercise layout is built.  Songs and practice-go mode bypass step routing.
    if not is_practice and not ctx.current_song_id:
        steps       = lesson.get("steps", [])
        step_idx    = max(0, min(ctx.lesson_step_idx, len(steps)))
        total_steps = len(steps)
        if step_idx < total_steps:
            current_step = steps[step_idx]
            stype = current_step.get("type", "exercise")
            if stype == "text":
                return _build_text_step(current_step, lesson_title,
                                        step_idx, total_steps)
            if stype == "notation_demo":
                return _build_notation_demo_step(current_step, lesson_title,
                                                  step_idx, total_steps)
    else:
        step_idx    = ctx.lesson_step_idx
        steps       = lesson.get("steps", [])
        total_steps = len(steps)

    all_bars = _bars_from_song_or_lesson(lesson)
    if not all_bars:
        all_bars = [["C4", "E4", "G4", "C5"]]

    sections   = _split_sections(all_bars)
    n_sections = len(sections)
    section_idx = max(0, min(section_idx, n_sections - 1))
    active_bars = sections[section_idx] if phase == "practice" else all_bars

    # Real note values, positions and bar lengths for imported songs
    # (None for lessons and for songs imported before rhythms were stored)
    active_types = active_onsets = active_lens = None
    _both_lh_types = _both_lh_onsets = None
    rhythm = {}
    meta = None                     # real lengths, ties, loudness and tempo changes, per staff
    if ctx.current_song_id and not is_practice:
        from pianove.song_store import get_song_rhythm
        rhythm = get_song_rhythm(ctx.current_song_id)
        if rhythm.get("bpm"):
            bpm = int(round(rhythm["bpm"]))          # songs play at their own tempo

        def _for_view(lst):
            if lst is None or len(lst) != len(all_bars):
                return None
            return _split_sections(lst)[section_idx] if phase == "practice" else lst

        hand_key = {"right": "rh", "left": "lh"}.get(ctx.current_song_hand)
        if hand_key:
            active_types  = _for_view(rhythm.get(f"types_{hand_key}"))
            active_onsets = _for_view(rhythm.get(f"onsets_{hand_key}"))
            meta = {k: (_for_view(rhythm.get(f"{k}_{hand_key}")), None) for k in ("durs", "ties", "vels")}
            meta["tempos"] = rhythm.get("tempos")
        active_lens = _for_view(rhythm.get("bar_lens"))

    # For "both hands" song mode, split into treble/bass for grand-staff display
    _both_lh_bars = None
    if ctx.current_song_id and ctx.current_song_hand == "both":
        from pianove.song_store import get_song_bars_split
        rh_all, lh_all = get_song_bars_split(ctx.current_song_id)
        if rh_all:
            if phase == "practice":
                start         = section_idx * _SECTION_SZ
                end           = start + _SECTION_SZ
                active_bars   = rh_all[start:end] or [["C4"]]
                _both_lh_bars = lh_all[start:end] if lh_all else []
            else:
                start, end    = 0, len(rh_all)
                active_bars   = rh_all
                _both_lh_bars = lh_all

            def _cut(lst):
                return lst[start:end] if lst else None

            active_types,  _both_lh_types  = _cut(rhythm.get("types_rh")), _cut(rhythm.get("types_lh"))
            active_onsets, _both_lh_onsets = _cut(rhythm.get("onsets_rh")), _cut(rhythm.get("onsets_lh"))
            active_lens = _cut(rhythm.get("bar_lens"))
            meta = {k: (_cut(rhythm.get(f"{k}_rh")), _cut(rhythm.get(f"{k}_lh")))
                    for k in ("durs", "ties", "vels")}
            meta["tempos"] = rhythm.get("tempos")
    # One step per distinct start position, across both staves (matches _StaffView)
    n_notes = len(_step_positions(active_bars, _both_lh_bars, active_types, _both_lh_types,
                                  active_onsets, _both_lh_onsets, active_lens, song_time, meta))

    # Completion screen
    if ctx.lesson_completed and initial_idx >= n_notes:
        if is_practice:
            return _build_practice_completion(
                ctx.practice_last_hits, ctx.practice_last_total, bpm
            )
        return _build_completion(lesson_title)

    win_h   = ctx.ui.height if ctx.ui else 768
    NAV_H   = 52 + 1 + 44 + 1    # nav + sep + controls + sep = 98 px
    # Staff always fills the entire remaining space; piano is a SlideReveal overlay.
    staff_h = max(180, win_h - NAV_H)

    _sv        = [None]   # _StaffView
    _slide_ref = [None]   # SlideReveal

    def _save():
        ctx.lesson_current_idx = _sv[0].current_idx if _sv[0] else initial_idx

    def _on_kb_toggle(val: bool):
        # No page rebuild — just animate the SlideReveal in/out
        ctx.lesson_keyboard_vis = val
        if _slide_ref[0]:
            _slide_ref[0].reveal(val)

    def _on_hands_toggle(val: bool):
        # The panel grows to make room for the hands
        from pianove.state import storage
        ctx.lesson_hands_vis = val
        storage.set("show_hands", bool(val))
        if _slide_ref[0]:
            _slide_ref[0].set_max_height(_kb_h_hands() if val else _KB_H)

    def _on_restart():
        if phase == "listen":
            if _sv[0]:
                _sv[0].seek(0.0)
            return
        ctx.lesson_step_idx    = 0
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
        prev = max(0, section_idx - 1)
        ctx.lesson_section_idx = prev
        ctx.lesson_current_idx = 0
        ctx.lesson_phase       = "practice"
        ctx.router.refresh()

    def _restart_section():
        ctx.lesson_section_idx = section_idx
        ctx.lesson_current_idx = 0
        ctx.lesson_phase       = "practice"
        ctx.router.refresh()

    def _complete_lesson():
        from pianove.progress import mark_complete, record_session, record_practice_session
        if is_practice:
            total = _sv[0].total_notes if _sv[0] else 1
            hits  = _sv[0].hits        if _sv[0] else 0
            record_practice_session(
                accuracy   = hits / total if total > 0 else 0.0,
                note_count = total,
                bpm        = bpm,
            )
            ctx.practice_last_hits  = hits
            ctx.practice_last_total = total
            ctx.lesson_completed = True
            ctx.router.refresh()
            return

        # For lessons: advance to the next step if one exists, otherwise finish
        next_step = step_idx + 1
        if not ctx.current_song_id and next_step < total_steps:
            ctx.lesson_step_idx    = next_step
            ctx.lesson_current_idx = 0
            ctx.lesson_section_idx = 0
            ctx.lesson_phase       = "practice"
            ctx.lesson_completed   = False
            ctx.router.refresh()
        else:
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

    if is_practice:
        phase_label = t("practice_go_label", bpm=bpm)
    elif phase == "performance" and ctx.current_song_id:
        phase_label = f"{t('song_play_along')}  {bpm} BPM"
    elif phase == "listen":
        phase_label = f"{t('song_listen')}  {bpm} BPM"
        counter_state.value = ""
    elif phase == "performance":
        phase_label = t("lesson_final_go")
    elif n_sections > 1:
        phase_label = t("lesson_section_of", n=section_idx + 1, total=n_sections)
    else:
        phase_label = t("lesson_practice")

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
                        anchor="right", x=-14, y=0, width=100, height=52))
    main.add_child(nav)
    main.add_child(FloatLayout(width=1.0, height=1,
                               background_color=pygame.Color(120, 120, 128, 60)))

    # Controls bar
    controls = FloatLayout(width=1.0, height=44,
                           background_color=iOSTheme.secondary_background)
    controls.add_child(Label(text=phase_label, font_size=13,
                             color=iOSTheme.secondary_label,
                             anchor="left", x=16, y=0, width=240, height=44))
    if phase == "listen":
        _add_transport(controls, _sv, right_w=270 if beta else 150)
    controls.add_child(Button(text="↺", on_click=_on_restart,
                              anchor="right", x=-252 if beta else -134, y=0,
                              width=36, height=32, font_size=18,
                              background_color=iOSTheme.fill, text_color=iOSTheme.label,
                              border_radius=8))
    if beta:
        controls.add_child(Label(text=t("hands"), font_size=13,
                                 color=iOSTheme.secondary_label,
                                 anchor="right", x=-192, y=0, width=52, height=44))
        controls.add_child(Switch(value=hands_vis, on_change=_on_hands_toggle,
                                  anchor="right", x=-134, y=0,
                                  width=51, height=31, active_color=ColorPalette.BLUE))
    controls.add_child(Label(text="Piano", font_size=13,
                             color=iOSTheme.secondary_label,
                             anchor="right", x=-80, y=0, width=42, height=44))
    controls.add_child(Switch(value=keyboard_vis, on_change=_on_kb_toggle,
                              anchor="right", x=-8, y=0,
                              width=51, height=31, active_color=ColorPalette.BLUE))
    main.add_child(controls)
    main.add_child(FloatLayout(width=1.0, height=1,
                               background_color=pygame.Color(120, 120, 128, 60)))

    # Staff — always the full remaining height, centred content handled in draw_content
    staff_view = _StaffView(
        bars=active_bars, phase=phase,
        initial_idx=initial_idx, on_advance=_do_note_advance,
        bpm=bpm, clef=clef, bass_bars=_both_lh_bars, time=song_time,
        types=active_types, bass_types=_both_lh_types,
        onsets=active_onsets, bass_onsets=_both_lh_onsets, bar_lens=active_lens, meta=meta,
        width=1.0, height=staff_h,
    )
    _sv[0] = staff_view
    while _TRANSPORT_HOOKS:
        _TRANSPORT_HOOKS.pop()()
    staff_view.bottom_inset = lambda: _slide_ref[0].reveal_height if _slide_ref[0] else 0
    main.add_child(staff_view)

    # Piano — always instantiated so MIDI is active regardless of visibility.
    # Wrapped in SlideReveal for animated show/hide without a full page rebuild.
    piano        = _LessonPiano(staff_view, _do_advance, _do_wrong,
                                reveal_fn=lambda: _slide_ref[0].reveal_height if _slide_ref[0] else _KB_H)
    piano_canvas = PygameCanvas(target=piano, draw_border=False,
                                width=1.0, height=1.0)
    slide = SlideReveal(
        child=piano_canvas,
        max_height=_kb_h_hands_max(),
        visible=keyboard_vis,
        anchor="bottom_left", x=0, y=0, width=1.0,
    )
    slide.set_max_height(_kb_h_hands() if hands_vis else _KB_H, animate=False)

    def _fit_panel():
        if beta and ctx.lesson_hands_vis and slide._max_h != _kb_h_hands():
            slide.set_max_height(_kb_h_hands())
    piano.fit_panel = _fit_panel
    _slide_ref[0] = slide
    root.add_child(slide)

    return root

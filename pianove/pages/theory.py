"""Theory, shown rather than told: a lesson's "scene" step.

A scene is a short series of beats. Each beat says one thing (a line or two of text) and
shows it on a keyboard: keys named or marked, a hand placed with its finger numbers, a
few notes on a staff, played by the hand while the notes light up on the staff and on the
keys. A beat can end with "now you": the player presses the keys (on their piano, or by
tapping the keys on screen) and the hand plays along with them.

steps.json:
    {"type": "scene", "title": {"en": ..., "de": ...},
     "beats": [{
        "title":   {"en": ..., "de": ...},          # small heading over the text (optional)
        "say":     {"en": ..., "de": ...},          # what this beat explains
        "labels":  "white" | "C" | ["C4", "E4"] | "hand",   # names on the keys
        "mark":    ["C#4", "D#4"],                  # keys lit softly (a group, a pattern)
        "hand":    {"right": {"C4": 1, "D4": 2, ...}},      # where the hand rests, finger → key
        "numbers": true,                            # the finger numbers over their keys
        "staff":   {"clef": "treble" | "bass" | "grand", "notes": ["C4", "D4"],
                    "under": "names" | "count", "key": 1, "time": [3, 4]},
        "play":    ["C4", "D4", "E4+G4"],           # the hand plays these, one after another
        "fingers": [1, 2, "3+5"],                   # with these fingers (the hand moves along)
        "side":    "right" | "left",                # the hand that plays them (default: right)
        "accent":  3,                               # every third note stronger (a waltz's ONE)
        "velocities": [96, 96, 52, 52],             # or how strongly each one is played
        "tempo":   80,
        "try":     ["C4"] | "play",                 # then the player plays them
        "try_say": {"en": ..., "de": ...}
     }, ...]}
"""
from __future__ import annotations

import math

import pygame
from pylay import FloatLayout, VStack, Button, iOSTheme, ColorPalette
from pylay.widgets.pygame_canvas import PygameCanvas
from pylay.core import font_loader, _dirty
import pianove.context as ctx
from pianove.i18n import t, language_state
from pianove.components import GREEN, RED
from pianove.fingering import key_x as _key_x
from pianove.hands import HandsOverlay, KeyboardGeometry, ACCENT, sleeve_depth

_LETTERS = "CDEFGAB"
_SEMIS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_WHITE_PC = {0, 2, 4, 5, 7, 9, 11}
_NAMES_SHARP = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"]

_LEAD_IN = 0.9            # seconds after a beat begins before the hand starts to play

# where a key signature's sharps and flats go, in order
_SHARP_POS = {"treble": ["F5", "C5", "G5", "D5", "A4", "E5", "B4"],
              "bass":   ["F3", "C3", "G3", "D3", "A2", "E3", "B2"]}
_FLAT_POS = {"treble": ["B4", "E5", "A4", "D5", "G4", "C5", "F4"],
             "bass":   ["B2", "E3", "A2", "D3", "G2", "C3", "F2"]}
_MAX_WHITE = 24           # never more keys than this (they would get too small to read)
_MIN_WHITE = 10


def _note_name(pc: int) -> str:
    """A key's name in the app's language (German calls B "H")."""
    name = _NAMES_SHARP[pc]
    return "H" if name == "B" and language_state.value == "de" else name


def _loc(v) -> str:
    """A text in the app's language: {"en": ..., "de": ...} or a plain string."""
    if isinstance(v, dict):
        return v.get(language_state.value) or v.get("en") or next(iter(v.values()), "")
    return v or ""


def _midi(p: str) -> int:
    name, rest = p[0].upper(), p[1:]
    acc = 0
    while rest and rest[0] in "#b♯♭":
        acc += 1 if rest[0] in "#♯" else -1
        rest = rest[1:]
    return (int(rest) + 1) * 12 + _SEMIS[name] + acc


def _chord(p) -> tuple[int, ...]:
    return tuple(sorted(_midi(x.strip()) for x in str(p).split("+") if x.strip()))


def _step_of(p: str) -> tuple[int, int]:
    """(diatonic step: C-1 = 0, one per letter; accidental -1/0/+1) of a written pitch."""
    name, rest = p[0].upper(), p[1:]
    acc = 0
    while rest and rest[0] in "#b♯♭":
        acc += 1 if rest[0] in "#♯" else -1
        rest = rest[1:]
    return (int(rest) + 1) * 7 + _LETTERS.index(name), acc


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _mix(a, b, k: float):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


class _Beat:
    def __init__(self, raw: dict, scene_title: str):
        self.title = _loc(raw.get("title")) or scene_title
        self.say = _loc(raw.get("say"))
        self.try_say = _loc(raw.get("try_say"))
        self.hand: dict[str, dict[int, int]] = {
            side: {_midi(p): int(f) for p, f in fm.items()}
            for side, fm in (raw.get("hand") or {}).items() if fm}
        self.numbers = bool(raw.get("numbers"))
        self.labels = raw.get("labels")
        self.mark = {_midi(p) for p in raw.get("mark", [])}
        self.play = [_chord(p) for p in raw.get("play", [])]
        self.tempo = float(raw.get("tempo", 76))
        self.accent = int(raw.get("accent", 0))
        self.velocities = raw.get("velocities")
        self.side = raw.get("side") or next(iter(self.hand), "right")
        # a finger for each note played: the hand moves with them (a scale's thumb under)
        self.fingers = None
        if raw.get("fingers"):
            self.fingers = [dict(zip(ev, (int(f) for f in str(fs).split("+"))))
                            for ev, fs in zip(self.play, raw["fingers"])]
        tr = raw.get("try")
        self.tries = self.play[:] if tr == "play" else [_chord(p) for p in (tr or [])]
        self.try_fingers = self.fingers if tr == "play" else None
        st = raw.get("staff")
        self.staff = None
        if st:
            notes = []
            for p in st.get("notes", []):
                parts = [x.strip() for x in str(p).split("+") if x.strip()]
                notes.append([(x, _midi(x)) for x in parts])
            self.staff = {"clef": st.get("clef", "treble"), "notes": notes,
                          "under": st.get("under") or ("names" if st.get("names") else None),
                          "key": int(st.get("key", 0)), "time": st.get("time")}

    def side_of(self, m: int) -> str | None:
        for side, fm in self.hand.items():
            if m in fm:
                return side
        return self.side if self.fingers else None

    def finger_of(self, k: int, m: int, tries: bool = False) -> int | None:
        """The finger that plays key m in play (or try) event k."""
        fl = self.try_fingers if tries else self.fingers
        if fl is not None and k < len(fl):
            return fl[k].get(m)
        side = self.side_of(m)
        return self.hand.get(side, {}).get(m) if side else None

    def notes(self) -> set[int]:
        out = set(self.mark)
        for fm in self.hand.values():
            out.update(fm)
        for ev in self.play + self.tries:
            out.update(ev)
        if self.staff:
            out.update(m for ch in self.staff["notes"] for _, m in ch)
        if isinstance(self.labels, list):
            out.update(_midi(p) for p in self.labels)
        return out


class Scene:
    """The canvas of a scene step: keyboard, hands, staff and text, and its timeline."""

    def __init__(self, raw: dict, on_finished=None):
        self.title = _loc(raw.get("title"))
        self.beats = [_Beat(b, self.title) for b in raw.get("beats", [])] or [_Beat({}, self.title)]
        self.on_finished = on_finished
        self.on_change = None                 # → the page updates its buttons
        from pianove.state import midi_panel
        self._panel = midi_panel
        self._panel.take_note_ons()           # presses from before this page don't count
        self.idx = 0
        self._fonts: dict = {}
        self._text_cache: dict = {}
        self._kb_cache = None
        self._staff_font = None
        self._has_staff = any(b.staff for b in self.beats)
        self._grand = any(b.staff and b.staff["clef"] == "grand" for b in self.beats)
        self._has_hands = any(b.hand or b.fingers for b in self.beats)
        lo = min((m for b in self.beats for m in b.notes()), default=60)
        hi = max((m for b in self.beats for m in b.notes()), default=72)
        self._lo, self._hi = lo, hi
        self._touch: dict[int, int] = {}      # finger/mouse id → key held on screen
        from pylay.core.physics import Spring
        # the staff's room: the keyboard moves up into it while a beat shows no staff
        self._staff_k = Spring(value=1.0 if self.beats[0].staff else 0.0,
                               response=0.45, damping_fraction=0.9)
        self._key_rects: list = []
        self._start_beat(0)

    # ── the timeline ─────────────────────────────────────────────────────────────

    @property
    def beat(self) -> _Beat:
        return self.beats[self.idx]

    def _start_beat(self, i: int):
        self._stop_sounds()
        self.idx = max(0, min(i, len(self.beats) - 1))
        b = self.beat
        self.t = 0.0
        self.playing = -1                     # which play event sounds (-1: none)
        self.sounding: dict[int, float] = {}  # key → seconds left
        # "demo": the hand plays; "try": the player's turn; "show": nothing to wait for;
        # "done": the player played it all
        self.phase = "demo" if b.play else "try" if b.tries else "show"
        self.try_i = 0                        # the event of b.tries to be played next
        self.hits: set[int] = set()           # keys of the current try event pressed so far
        self.flash: dict[int, tuple] = {}     # key → (colour, time left): right/wrong
        self.done_t = None                    # when the player had played it all
        self.lit_staff: dict[int, tuple] = {} # staff note index → colour
        plan = [dict(b.hand)]
        for k, ev in enumerate(b.play):
            plan.append(self._plan_for(ev, k))
        for k, ev in enumerate(b.tries):
            plan.append(self._plan_for(ev, k, tries=True))
        self._plan_try0 = 1 + len(b.play)
        old = getattr(self, "_hands", None)
        self._hands = HandsOverlay(plan, memory=("scene", id(self)),
                                   skin=self._skin())
        if old is not None:
            self._hands._renderer = old._renderer
        if old is not None:
            for s, h in self._hands.hands.items():
                h.alpha.value = old.hands[s].alpha.value     # fades from where it was
        if self.on_change:
            self.on_change()

    def _skin(self):
        from pianove.state import hand_tone_state
        return hand_tone_state.value

    def _plan_for(self, ev, k: int, tries: bool = False) -> dict:
        b = self.beat
        out: dict[str, dict[int, int]] = {}
        for m in ev:
            side, f = b.side_of(m), b.finger_of(k, m, tries)
            if side and f:
                out.setdefault(side, {})[m] = f
        if (b.try_fingers if tries else b.fingers) is None:
            # the other fingers of a playing hand stay over their keys
            for side in list(out):
                for m, f in b.hand[side].items():
                    if f not in out[side].values():
                        out[side].setdefault(m, f)
        return out

    def replay(self):
        self._start_beat(self.idx)

    def next(self):
        if self.idx + 1 < len(self.beats):
            self._start_beat(self.idx + 1)
        else:
            self._stop_sounds()
            if self.on_finished:
                self.on_finished()

    def back(self):
        if self.idx > 0:
            self._start_beat(self.idx - 1)

    @property
    def waiting_for_player(self) -> bool:
        return self.phase == "try"

    def _set_phase(self, phase: str):
        self.phase = phase
        if self.on_change:
            self.on_change()

    def _sound(self, m: int, on: bool, velocity: int = 80):
        try:
            from pianove import sound_engine_fs as se
            if on:
                se.play(m, velocity)
            else:
                se.stop(m)
        except Exception:
            pass

    def _stop_sounds(self):
        for m in list(getattr(self, "sounding", {})):
            self._sound(m, False)
        if hasattr(self, "sounding"):
            self.sounding.clear()

    def update(self, dt: float, rect: pygame.Rect):
        self._panel.update(dt, rect)
        b = self.beat
        self.t += dt
        beat_len = 60.0 / b.tempo

        for m in list(self.sounding):
            self.sounding[m] -= dt
            if self.sounding[m] <= 0:
                del self.sounding[m]
                self._sound(m, False)
        for m in list(self.flash):
            c, left = self.flash[m]
            if left - dt <= 0:
                del self.flash[m]
            else:
                self.flash[m] = (c, left - dt)

        # the demo: the hand plays, the notes light up
        if self.phase == "demo":
            k = int((self.t - _LEAD_IN) // beat_len) if self.t >= _LEAD_IN else -1
            if k != self.playing and 0 <= k < len(b.play):
                self.playing = k
                vel = 80 if not b.accent else (104 if k % b.accent == 0 else 56)
                if b.velocities and k < len(b.velocities):
                    vel = int(b.velocities[k])
                for m in b.play[k]:
                    self._sound(m, True, vel)
                    self.sounding[m] = beat_len * 0.85
                    self._tell_mic(m)
                self.lit_staff = {k: ACCENT[b.side_of(b.play[k][0]) or "right"]}
            elif k >= len(b.play):
                self.playing = -1
                self.lit_staff = {}
                self._set_phase("try" if b.tries else "show")

        # the player's turn
        for m in self._panel.take_note_ons():
            self._player_note(m)
        if (self.phase == "done" and self.t - self.done_t > 1.4
                and self.idx + 1 < len(self.beats)):
            self.next()                               # played it: on to the next thing
            return

        # the hands
        held = set(self._panel.active_notes) | set(self._touch.values())
        if self.playing >= 0:
            step, active = 1 + self.playing, frozenset(self.sounding)
        elif self.waiting_for_player:
            step, active = self._plan_try0 + self.try_i, frozenset(held)
        else:
            step, active = 0, frozenset(held | set(self.sounding))
        self._hands.update(dt, step, active, glow=self._glowing(step))
        self._staff_k.target = 1.0 if b.staff else 0.0
        self._staff_k.update(dt)
        if self._moving(held):
            _dirty.mark()

    def _moving(self, held) -> bool:
        """Whether the next frame looks different: text and keys still coming in, the
        hand playing or moving, keys pressed or glowing, the player's keys pulsing."""
        if self.t < 2.5 or self.phase in ("demo", "try") or self.sounding or self.flash or held:
            return True
        if self.phase == "done" or abs(self._staff_k.value - self._staff_k.target) > 1e-3:
            return True
        for h in self._hands.hands.values():
            if any(abs(sp.value - sp.target) > 1e-3 for sp in (h.hx, h.hy, h.th, h.alpha)):
                return True
        return False

    def _glowing(self, step: int) -> dict | None:
        """Of a hand's fingers resting on their keys, only the one that plays now glows
        (all of them while the hand's position is being shown)."""
        b = self.beat
        if step == 0:
            return None if b.numbers else {}
        tries = step >= self._plan_try0
        k = step - (self._plan_try0 if tries else 1)
        evs = b.tries if tries else b.play
        ev = evs[k] if k < len(evs) else ()
        if tries:
            ev = tuple(m for m in ev if m not in self.hits)
        out: dict[str, set] = {}
        for m in ev:
            side, f = b.side_of(m), b.finger_of(k, m, tries)
            if side and f:
                out.setdefault(side, set()).add(f)
        return out

    def _tell_mic(self, m: int):
        mic = getattr(self._panel, "mic", None)
        if mic is not None and getattr(self._panel, "input_mode", "") == "mic":
            try:
                mic.mute(m, 1.2)
            except Exception:
                pass

    def _player_note(self, m: int):
        if not self.waiting_for_player:
            return
        want = self.beat.tries[self.try_i]
        if m in want:
            self.hits.add(m)
            self.flash[m] = (GREEN, 0.5)
            if self.hits >= set(want):
                k = self.try_i
                if self.beat.staff and k < len(self.beat.staff["notes"]):
                    self.lit_staff[k] = GREEN
                self.try_i += 1
                self.hits = set()
                if self.try_i >= len(self.beat.tries):
                    self.done_t = self.t
                    self._set_phase("done")
        else:
            self.flash[m] = (RED, 0.5)

    # ── touch: the keys on screen can be played ──────────────────────────────────

    def handle_event(self, event: pygame.event.Event, rect: pygame.Rect) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            m = self._key_at(event.pos)
            if m is not None:
                self._touch[0] = m
                self._sound(m, True)
                self._player_note(m)
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            m = self._touch.pop(0, None)
            if m is not None:
                self._sound(m, False)
                return True
        return False

    def _key_at(self, pos):
        for kr, m, black in self._key_rects:          # black keys first (they lie on top)
            if kr.collidepoint(pos):
                return m
        return None

    # ── drawing ──────────────────────────────────────────────────────────────────

    def _font(self, pt: int, bold=False):
        k = (pt, bold)
        if k not in self._fonts:
            self._fonts[k] = font_loader.load_font(pt, bold=bold)
        return self._fonts[k]

    def _text(self, txt: str, pt: int, color, bold=False):
        k = (txt, pt, tuple(color)[:3], bold)
        s = self._text_cache.get(k)
        if s is None:
            if len(self._text_cache) > 300:
                self._text_cache.clear()
            font = self._font(pt, bold)
            if "♯" in txt or "♭" in txt:
                s = self._with_accidentals(txt, font, color)
            else:
                s = font.render(txt, True, color)
            self._text_cache[k] = s
        return s

    def _with_accidentals(self, txt: str, font, color) -> pygame.Surface:
        """Text with ♯ and ♭ in it: those two drawn with the music font."""
        import re
        import pygame.freetype
        from pylute.font import FONT_PATH
        h = font.get_linesize()
        acc_font = pygame.freetype.Font(FONT_PATH, int(h * 0.95))
        parts = []
        for piece in re.split("([♯♭])", txt):
            if not piece:
                continue
            if piece in "♯♭":
                surf, _ = acc_font.render(piece, color)
                parts.append((surf, int(h * 0.5 - surf.get_height() * 0.5 - h * 0.06)))
            else:
                parts.append((font.render(piece, True, color), 0))
        out = pygame.Surface((sum(p.get_width() for p, _ in parts) + 1, h), pygame.SRCALPHA)
        x = 0
        for p, y in parts:
            out.blit(p, (x, y))
            x += p.get_width() + (1 if y else 0)
        return out

    def _wrap(self, txt: str, pt: int, width: int, bold=False) -> list[str]:
        font = self._font(pt, bold)
        lines = []
        for para in txt.split("\n"):
            line = ""
            for w in para.split(" "):
                trial = (line + " " + w).strip()
                if font.size(trial)[0] <= width or not line:
                    line = trial
                else:
                    lines.append(line)
                    line = w
            lines.append(line)
        return lines

    def _layout(self, rect: pygame.Rect):
        """Where everything goes: the text on top, then the staff, then the keyboard with
        the hands below it. The keys are as large as the room allows."""
        W, H = rect.width, rect.height
        pad = max(12, int(W * 0.025))
        small = H < 430
        cap_pt = 15 if small else 17
        cap_h = (2 if small else 3) * int(self._font(cap_pt).get_linesize()) + (20 if small else 34)
        staff_h = 0
        if self._has_staff:
            staff_h = int(max(84, min(H * (0.34 if self._grand else 0.24), 220 if self._grand else 150)))
        room = max(80, H - cap_h - staff_h - 8 - (30 if self._has_staff else 0))
        sd = sleeve_depth() if self._has_hands else 0.0
        # the hands need room down to the wrist; the sleeve may run off the bottom
        per_u = 3.8 * 0.81 + (sd * 0.62 if self._has_hands else 3.8 * 0.19 + 0.3)
        from pylay.core.scale import scaled_px
        u_by_h = min(room / per_u, scaled_px(64))       # keys no larger than a real piano's look
        lo_w = self._white_index(self._lo)
        hi_w = self._white_index(self._hi)
        need = hi_w - lo_w + 1 + 2
        u = min(u_by_h, (W - 2 * pad) / max(_MIN_WHITE, need))
        n = int(min(_MAX_WHITE, max(need, _MIN_WHITE, (W - 2 * pad) // max(1, u))))
        u = min(u_by_h, (W - 2 * pad) / n)
        # the keys shown: the content in the middle, starting on a C where that fits
        first = (lo_w + hi_w) // 2 - n // 2
        for shift in range(0, 4):
            for cand in (first - shift, first + shift):
                if cand % 7 == 0 and cand <= lo_w - 1 and cand + n - 1 >= hi_w + 1:
                    first = cand
                    break
            else:
                continue
            break
        first = min(first, lo_w - 1)
        first = max(first, hi_w + 1 - (n - 1))
        kb_w = u * n
        left = rect.left + (W - kb_w) / 2
        key_h = u * 3.8
        bubble = (u * 0.6 + 10) if self._has_hands else 0
        top = rect.top + cap_h + (staff_h + bubble) * self._staff_k.value + 4 + bubble * (1 - self._staff_k.value) * 0.5
        return {"pad": pad, "cap_pt": cap_pt, "cap_h": cap_h, "staff_h": staff_h, "u": u,
                "n": n, "first": first, "left": left, "top": top, "key_h": key_h,
                "black_h": key_h * 0.62, "small": small}

    @staticmethod
    def _white_index(m: int) -> int:
        octave, pc = divmod(m, 12)
        while pc not in _WHITE_PC:
            pc -= 1
        return octave * 7 + sorted(_WHITE_PC).index(pc)

    @staticmethod
    def _white_midi(wi: int) -> int:
        octave, k = divmod(wi, 7)
        return octave * 12 + sorted(_WHITE_PC)[k]

    def _key_colour(self, m: int, white: bool):
        b = self.beat
        base = (255, 255, 255) if white else (24, 24, 28)
        if m in self.flash:
            c, left = self.flash[m]
            return _mix(base, c, 0.85 if white else 0.9)
        if m in self.sounding or m in self._touch.values() or m in self._panel.active_notes:
            side = b.side_of(m) or "right"
            return _mix(base, ACCENT[side], 0.55 if white else 0.8)
        if self.waiting_for_player:
            want = self.beat.tries[self.try_i]
            if m in want and m not in self.hits:
                pulse = 0.5 + 0.5 * math.sin(self.t * 5.0)
                side = b.side_of(m) or "right"
                return _mix(base, ACCENT[side], (0.25 + 0.3 * pulse) if white else (0.45 + 0.35 * pulse))
        if m in b.mark:
            k = _ease((self.t - 0.25) / 0.5)
            return _mix(base, (120, 180, 255) if white else (40, 110, 220), (0.45 if white else 0.75) * k)
        return base

    def _labelled(self, m: int) -> bool:
        lab = self.beat.labels
        if lab is None:
            return False
        if lab == "white":
            return m % 12 in _WHITE_PC
        if lab == "hand":
            return any(m in fm for fm in self.beat.hand.values())
        if isinstance(lab, str):
            return m % 12 == _SEMIS.get(lab.upper()[:1], -1) and len(lab) == 1
        return m in {_midi(p) for p in lab}

    def draw(self, surface: pygame.Surface, rect: pygame.Rect):
        L = self._layout(rect)
        surface.fill(iOSTheme.background, rect)
        self._draw_caption(surface, rect, L)
        if L["staff_h"] and self.beat.staff:
            self._draw_staff(surface, pygame.Rect(rect.left, rect.top + L["cap_h"], rect.width, L["staff_h"]), L)
        self._draw_keyboard(surface, rect, L)

    def _draw_caption(self, surface, rect, L):
        b = self.beat
        k = _ease(self.t / 0.45)
        y = rect.top + (10 if L["small"] else 18) + int((1 - k) * 10)
        title = b.title.upper() if b.title else ""
        if title:
            ts = self._text(title, 11, ColorPalette.BLUE, bold=True)
            ts.set_alpha(int(255 * k))
            surface.blit(ts, (rect.centerx - ts.get_width() // 2, y))
            y += ts.get_height() + 4
        say = b.say
        colour = iOSTheme.label
        if self.waiting_for_player:
            say = b.try_say or t("scene_your_turn")
            colour = ColorPalette.BLUE
        elif self.phase == "done":
            say, colour = t("scene_great"), GREEN
        width = min(rect.width - 2 * L["pad"], 760)
        for line in self._wrap(say, L["cap_pt"], width):
            s = self._text(line, L["cap_pt"], colour)
            s.set_alpha(int(255 * k))
            surface.blit(s, (rect.centerx - s.get_width() // 2, y))
            y += self._font(L["cap_pt"]).get_linesize()

    # the staff ───────────────────────────────────────────────────────────────────

    def _music_font(self, size: int):
        if self._staff_font is None or self._staff_font[0] != size:
            import pygame.freetype
            from pylute.font import FONT_PATH
            f = pygame.freetype.Font(FONT_PATH, size)
            f.origin = True
            self._staff_font = (size, f)
        return self._staff_font[1]

    def _draw_staff(self, surface, area: pygame.Rect, L):
        b = self.beat
        if not b.staff:
            return
        st = b.staff
        grand = st["clef"] == "grand"
        sp = max(6, min(13, int(area.height / (17 if grand else 9))))
        width = min(area.width - 2 * L["pad"], max(260, 150 + 70 * max(1, len(st["notes"]))))
        x0 = area.centerx - width // 2
        ink = iOSTheme.label
        line_col = _mix(iOSTheme.background[:3], ink[:3], 0.55)
        font = self._music_font(sp * 4)
        k_in = _ease(self.t / 0.5)

        staves = []                                   # (clef, bottom line y, bottom step)
        if grand:
            mid = area.top + area.height // 2
            staves = [("treble", mid - sp * 1.5, 37), ("bass", mid + sp * 5.5, 25)]
        else:
            bottom = area.top + area.height // 2 + sp * 2
            staves = [(st["clef"], bottom, 37 if st["clef"] == "treble" else 25)]   # E4 / G2
        key, time_sig = st["key"], st["time"]
        head = sp * 4.2                               # the clef
        for clef, by, bottom_step in staves:
            for i in range(5):
                y = int(by - i * sp)
                pygame.draw.line(surface, line_col, (x0, y), (x0 + width, y), max(1, sp // 8))
            gy = by - sp if clef == "treble" else by - 3 * sp
            font.render_to(surface, (x0 + sp * 0.6, gy), "\uE050" if clef == "treble" else "\uE062", ink)
            x = x0 + sp * 3.6
            for name in (_SHARP_POS if key > 0 else _FLAT_POS)[clef][:abs(key)]:
                step, _ = _step_of(name)
                font.render_to(surface, (x, by - (step - bottom_step) * sp / 2),
                               "\uE262" if key > 0 else "\uE260", ink)
                x += sp * 1.0
            if time_sig:
                x += sp * 0.4
                for digit, line in ((time_sig[0], 3), (time_sig[1], 1)):
                    font.render_to(surface, (x, by - line * sp), chr(0xE080 + int(digit)), ink)
                x += sp * 2.0
            head = max(head, x - x0)
        key_acc = {n[0]: (1 if key > 0 else -1) for n in (_SHARP_POS if key > 0 else _FLAT_POS)["treble"][:abs(key)]}
        if grand:
            pygame.draw.line(surface, line_col, (x0, staves[0][1] - 4 * sp), (x0, staves[1][1]), 2)
            pygame.draw.line(surface, line_col, (x0 + width, staves[0][1] - 4 * sp), (x0 + width, staves[1][1]), 2)

        notes = st["notes"]
        if not notes:
            return
        start = x0 + head + sp * 0.8
        gap = (width - head - sp * 1.6) / max(1, len(notes))
        if time_sig:                                  # bar lines after every bar's notes
            per = int(time_sig[0])
            for j in range(per, len(notes), per):
                bx = start + gap * j
                pygame.draw.line(surface, line_col, (bx, staves[0][1] - 4 * sp), (bx, staves[-1][1]),
                                 max(1, sp // 7))
        names_font_pt = 11
        for i, chord in enumerate(notes):
            appear = _ease((self.t - 0.15 - i * 0.07) / 0.35) * k_in
            if appear <= 0:
                continue
            cx = start + gap * (i + 0.5)
            colour = self.lit_staff.get(i)
            col = colour if colour else ink
            if len(chord) > 1:
                self._draw_chord(surface, font, chord, cx, staves, grand, sp, appear, col, colour, line_col, key_acc)
                continue
            for name, m in chord:
                step, acc = _step_of(name)
                clef_i = 0
                if grand:
                    clef_i = 0 if m >= 60 else 1
                _, by, bottom_step = staves[clef_i]
                pos = step - bottom_step                 # 0: on the bottom line
                y = by - pos * sp / 2 + (1 - appear) * sp
                # ledger lines
                for lp in range(-2, pos - 1, -2) if pos <= -2 else range(10, pos + 1, 2):
                    ly = by - lp * sp / 2
                    pygame.draw.line(surface, line_col, (cx - sp * 0.95, ly), (cx + sp * 0.95, ly), max(1, sp // 8))
                if colour:                                # a glow behind the note that sounds
                    glow = pygame.Surface((sp * 4, sp * 4), pygame.SRCALPHA)
                    pygame.draw.circle(glow, (*colour[:3], 60), (sp * 2, sp * 2), sp * 2)
                    surface.blit(glow, (cx - sp * 2, y - sp * 2))
                glyph = "\uE1D5" if pos < 4 else "\uE1D6"   # stem up below the middle line
                head_w = sp * 1.18
                font.render_to(surface, (cx - head_w / 2, y), glyph, col)
                written = key_acc.get(name[0].upper(), 0)
                if acc != written:                    # what the key signature doesn't say
                    font.render_to(surface, (cx - head_w / 2 - sp * 1.2, y),
                                   "\uE262" if acc > 0 else "\uE260" if acc < 0 else "\uE261", col)
                if st["under"] and name is chord[0][0]:
                    if st["under"] == "count" and time_sig:
                        letter = str(i % int(time_sig[0]) + 1)
                    else:
                        letter = _note_name(_SEMIS[name[0].upper()]) + ("♯" if acc > 0 else "♭" if acc < 0 else "")
                    ts = self._text(letter, names_font_pt + (2 if st["under"] == "count" and letter == "1" else 0),
                                    col if colour else iOSTheme.secondary_label, bold=True)
                    ny = (staves[-1][1] + sp * 2.2) if not grand or clef_i == 1 else (staves[0][1] + sp * 1.6)
                    surface.blit(ts, (cx - ts.get_width() // 2, ny))

    def _draw_chord(self, surface, font, chord, cx, staves, grand, sp, appear, col, colour, line_col, key_acc):
        """Notes struck together: their heads on one stem (one per staff)."""
        by_staff: dict[int, list] = {}
        for name, m in chord:
            by_staff.setdefault(0 if not grand or m >= 60 else 1, []).append(name)
        head_w = sp * 1.18
        for clef_i, names in by_staff.items():
            _, by, bottom_step = staves[clef_i]
            ys = []
            for name in names:
                step, acc = _step_of(name)
                pos = step - bottom_step
                y = by - pos * sp / 2 + (1 - appear) * sp
                ys.append((pos, y))
                for lp in range(-2, pos - 1, -2) if pos <= -2 else range(10, pos + 1, 2):
                    ly = by - lp * sp / 2
                    pygame.draw.line(surface, line_col, (cx - sp * 0.95, ly), (cx + sp * 0.95, ly), max(1, sp // 8))
                if acc != key_acc.get(name[0].upper(), 0):
                    font.render_to(surface, (cx - head_w / 2 - sp * 1.2, y),
                                   "\uE262" if acc > 0 else "\uE260" if acc < 0 else "\uE261", col)
            if colour:
                lo_y, hi_y = max(y for _, y in ys), min(y for _, y in ys)
                glow = pygame.Surface((int(sp * 3.2), int(lo_y - hi_y + sp * 3.2)), pygame.SRCALPHA)
                pygame.draw.rect(glow, (*colour[:3], 60), glow.get_rect(), border_radius=int(sp * 1.6))
                surface.blit(glow, (cx - sp * 1.6, hi_y - sp * 1.6))
            for _, y in ys:
                font.render_to(surface, (cx - head_w / 2, y), "\uE0A4", col)
            up = sum(p for p, _ in ys) / len(ys) < 4
            lw = max(1, int(sp * 0.13))
            if up:
                x = cx + head_w / 2 - lw
                pygame.draw.line(surface, col, (x, max(y for _, y in ys) - sp * 0.15),
                                 (x, min(y for _, y in ys) - sp * 3.3), lw)
            else:
                x = cx - head_w / 2 + lw / 2
                pygame.draw.line(surface, col, (x, min(y for _, y in ys) + sp * 0.15),
                                 (x, max(y for _, y in ys) + sp * 3.3), lw)

    # the keyboard and the hands ───────────────────────────────────────────────────

    def _draw_keyboard(self, surface, rect, L):
        u, n, first, left, top = L["u"], L["n"], L["first"], L["left"], L["top"]
        key_h, black_h = L["key_h"], L["black_h"]
        bw = u * 0.58
        whites = [self._white_midi(first + i) for i in range(n)]
        self._key_rects = []
        blacks = []
        for i, m in enumerate(whites):
            if (m + 1) % 12 not in _WHITE_PC and i < n - 1:
                blacks.append((i, m + 1))

        # keys (as a picture, drawn again only when one of them changes colour)
        x0, y0 = int(left), int(top)
        white_rects = [(pygame.Rect(int(left + i * u), y0, max(2, int(u) - 1), int(key_h)), m, False)
                       for i, m in enumerate(whites)]
        black_rects = [(pygame.Rect(int(left + (i + 1) * u - bw / 2), y0, max(2, int(bw)), int(black_h)), m, True)
                       for i, m in blacks]
        self._key_rects = black_rects + white_rects
        cols = (tuple(self._key_colour(m, True) for _, m, _ in white_rects),
                tuple(self._key_colour(m, False) for _, m, _ in black_rects))
        ck = (x0, y0, round(u, 2), n, first, int(key_h), cols)
        if self._kb_cache is None or self._kb_cache[0] != ck:
            pic = pygame.Surface((int(u * n) + 2, int(key_h) + 1), pygame.SRCALPHA)
            rw, rb = max(2, int(u * 0.12)), max(2, int(u * 0.1))
            for (r, m, _), col in zip(white_rects, cols[0]):
                r = r.move(-x0, -y0)
                pygame.draw.rect(pic, col, r, border_bottom_left_radius=rw, border_bottom_right_radius=rw)
                pygame.draw.rect(pic, (150, 150, 156), r, 1,
                                 border_bottom_left_radius=rw, border_bottom_right_radius=rw)
            pygame.draw.rect(pic, (60, 60, 66), pygame.Rect(0, 0, int(u * n), max(2, int(u * 0.12))))
            for (r, m, _), col in zip(black_rects, cols[1]):
                r = r.move(-x0, -y0)
                pygame.draw.rect(pic, col, r, border_bottom_left_radius=rb, border_bottom_right_radius=rb)
                hi = r.inflate(-max(2, int(bw * 0.3)), 0)
                hi.height = max(2, int(black_h * 0.08))
                hi.bottom = r.bottom - max(2, int(black_h * 0.05))
                pygame.draw.rect(pic, _mix(col, (255, 255, 255), 0.18), hi, border_radius=2)
            self._kb_cache = (ck, pic)
        surface.blit(self._kb_cache[1], (x0, y0))

        # the hands
        if whites:
            kb = KeyboardGeometry(left=left, white_w=u, top=top, key_h=key_h, black_h=black_h,
                                  first_white_x=_key_x(whites[0]), bottom=rect.bottom - 2)
            self._hands.draw(surface, kb)

        # names on the keys (over the fingers resting on them): a little pill on each,
        # popping in one after another
        b = self.beat
        pt = 12 if u >= 34 else 10
        order = [m for m in whites if self._labelled(m)] + [m for _, m in blacks if self._labelled(m)]
        for j, m in enumerate(order):
            k = _ease((self.t - 0.2 - j * 0.05) / 0.3)
            if k <= 0:
                continue
            white = m % 12 in _WHITE_PC
            name = _note_name(m % 12)
            if white:
                cx = left + (whites.index(m) + 0.5) * u
                cy = top + key_h - u * 0.55
            else:
                i = next(i for i, mm in blacks if mm == m)
                cx = left + (i + 1) * u
                cy = top + black_h - u * 0.45
            side = b.side_of(m)
            fill = ACCENT[side] if side else ((70, 70, 78) if white else (235, 235, 240))
            ts = self._text(name, pt, (255, 255, 255) if (side or white) else (20, 20, 24), bold=True)
            pw = max(ts.get_width() + 10, ts.get_height() + 4)
            ph = ts.get_height() + 4
            pill = pygame.Surface((pw, ph), pygame.SRCALPHA)
            pygame.draw.rect(pill, (*fill, 235), pill.get_rect(), border_radius=ph // 2)
            pill.blit(ts, ((pw - ts.get_width()) // 2, (ph - ts.get_height()) // 2))
            if k < 1:
                pill = pygame.transform.smoothscale(pill, (max(1, int(pw * k)), max(1, int(ph * k))))
            surface.blit(pill, (cx - pill.get_width() / 2, cy - pill.get_height() / 2))

        # while the hand plays: the finger's number pops up over its key
        if self.playing >= 0 and not b.numbers:
            for m in b.play[self.playing]:
                f = b.finger_of(self.playing, m)
                left_s = self.sounding.get(m, 0.0)
                if f is None or left_s <= 0:
                    continue
                white = m % 12 in _WHITE_PC
                if white and m in whites:
                    cx = left + (whites.index(m) + 0.5) * u
                else:
                    cx = left + (next((i for i, mm in blacks if mm == m), 0) + 1) * u
                k = min(1.0, left_s * 4)
                r = max(8, int(u * 0.3))
                cy = top - r - 6 - (1 - k) * 6
                side = b.side_of(m) or "right"
                bub = pygame.Surface((2 * r + 2, 2 * r + 2), pygame.SRCALPHA)
                pygame.draw.circle(bub, (*ACCENT[side], int(255 * k)), (r + 1, r + 1), r)
                ts = self._text(str(f), 13 if u >= 34 else 11, (255, 255, 255), bold=True)
                bub.blit(ts, (r + 1 - ts.get_width() // 2, r + 1 - ts.get_height() // 2))
                surface.blit(bub, (cx - r - 1, cy - r - 1))

        # finger numbers above their keys
        if b.numbers and b.hand:
            for side, fm in b.hand.items():
                for j, (m, f) in enumerate(sorted(fm.items(), key=lambda kv: kv[1])):
                    k = _ease((self.t - 0.35 - j * 0.08) / 0.3)
                    if k <= 0:
                        continue
                    white = m % 12 in _WHITE_PC
                    cx = (left + (whites.index(m) + 0.5) * u) if white and m in whites else \
                         (left + (next((i for i, mm in blacks if mm == m), 0) + 1) * u)
                    r = max(8, int(u * 0.3)) * k
                    cy = top - r - 6
                    pygame.draw.circle(surface, ACCENT[side], (int(cx), int(cy)), int(r))
                    ts = self._text(str(f), 13 if u >= 34 else 11, (255, 255, 255), bold=True)
                    if k > 0.6:
                        surface.blit(ts, (cx - ts.get_width() / 2, cy - ts.get_height() / 2))


# ── The page ─────────────────────────────────────────────────────────────────────────

def build_scene_step(step: dict, lesson_title: str, step_idx: int, total_steps: int,
                     nav: FloatLayout, on_done) -> FloatLayout:
    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    main = VStack(spacing=0, padding=0, width=1.0, height=1.0)
    root.add_child(main)
    main.add_child(nav)
    main.add_child(FloatLayout(width=1.0, height=1,
                               background_color=pygame.Color(120, 120, 128, 60)))

    win_h = ctx.ui.height if ctx.ui else 768
    bar_h = 60 if win_h >= 560 else 50
    scene = Scene(step, on_finished=on_done)
    canvas = PygameCanvas(target=scene, draw_border=False, width=1.0,
                          height=max(160, win_h - 53 - bar_h))
    main.add_child(canvas)

    bar = FloatLayout(width=1.0, height=bar_h, background_color=iOSTheme.secondary_background)
    btn_h = bar_h - 16
    back_btn = Button(text="‹", on_click=scene.back, anchor="left", x=12, y=0,
                      width=44, height=btn_h, font_size=20,
                      background_color=iOSTheme.fill, text_color=iOSTheme.label, border_radius=10)
    again_btn = Button(text="↺", on_click=scene.replay, anchor="left", x=62, y=0,
                       width=44, height=btn_h, font_size=18,
                       background_color=iOSTheme.fill, text_color=iOSTheme.label, border_radius=10)
    next_btn = Button(text=t("step_continue"), on_click=scene.next, anchor="right", x=-12, y=0,
                      width=170, height=btn_h, font_size=15,
                      background_color=ColorPalette.BLUE, text_color=pygame.Color(255, 255, 255),
                      border_radius=12)
    dots = PygameCanvas(on_draw=lambda s, r: _draw_dots(s, r, scene), draw_border=False,
                        anchor="center", x=0, y=0, width=200, height=bar_h)
    bar.add_child(back_btn)
    bar.add_child(again_btn)
    bar.add_child(dots)
    bar.add_child(next_btn)
    main.add_child(bar)

    def _sync():
        last = scene.idx == len(scene.beats) - 1
        if scene.waiting_for_player:
            next_btn.text = t("scene_skip")
            next_btn.background_color = iOSTheme.fill
            next_btn.text_color = iOSTheme.label
        else:
            next_btn.text = t("scene_start") if last else t("step_continue")
            next_btn.background_color = GREEN if last else ColorPalette.BLUE
            next_btn.text_color = pygame.Color(255, 255, 255)
        back_btn.enabled = scene.idx > 0
    scene.on_change = _sync
    _sync()
    return root


def _draw_dots(surface: pygame.Surface, rect: pygame.Rect, scene: Scene):
    n = len(scene.beats)
    if n <= 1:
        return
    gap = 14
    x = rect.centerx - (n - 1) * gap / 2
    for i in range(n):
        on = i == scene.idx
        col = ColorPalette.BLUE if on else (GREEN if i < scene.idx else iOSTheme.fill)
        if on:
            pygame.draw.rect(surface, col, pygame.Rect(int(x + i * gap - 8), rect.centery - 4, 16, 8),
                             border_radius=4)
        else:
            pygame.draw.circle(surface, col, (int(x + i * gap), rect.centery), 4)

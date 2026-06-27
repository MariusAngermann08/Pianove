from __future__ import annotations

import math
import pygame
import mido
from pylay.core.theme import iOSTheme
from pylay.core.scale import scaled_font_size

_WHITE_PC = frozenset({0, 2, 4, 5, 7, 9, 11})   # C D E F G A B

_DEFAULT_LOW  = 48   # C3
_DEFAULT_HIGH = 72   # C5
_MIDI_MIN     = 0
_MIDI_MAX     = 127

# Ideal height:width ratio for a piano key (standard key ≈ 150 mm × 23 mm)
_KEY_ASPECT = 5.5

# Total animation duration (seconds) for the cascade reveal
_ANIM_DUR = 0.70

# Storage keys
_SK_LOW  = "midi_range_low"
_SK_HIGH = "midi_range_high"

# State machine values
_S_IDLE     = 0   # no device
_S_CAL_LOW  = 1   # device connected, waiting for lowest key
_S_CAL_HIGH = 2   # lowest recorded, waiting for highest key
_S_ANIM     = 3   # cascade animation playing
_S_READY    = 4   # normal playing mode

# Device name fragment → (low, high) preset — bypasses calibration for known models
_KNOWN_RANGES: dict[str, tuple[int, int]] = {
    "dp-95": (12, 108), "dp-33": (12, 108), "dp-28": (12, 108),
    "dp 95": (12, 108), "dp 33": (12, 108), "dp 28": (12, 108),
    "grand":   (12, 108), "upright": (12, 108),
    "stage p": (12, 108), "stage piano": (12, 108),
    "76": (28, 103),
    "61": (36, 96),
    "49": (48, 96),
    "37": (48, 84),
    "25": (48, 72),
}

def _name_to_range(name: str) -> tuple[int, int] | None:
    low = name.lower()
    for frag, rng in _KNOWN_RANGES.items():
        if frag in low:
            return rng
    return None

def _build_note_lists(low: int, high: int) -> tuple[list[int], list[int], list[int]]:
    white = [n for n in range(low, high + 1) if n % 12 in _WHITE_PC]
    black = [n for n in range(low, high + 1) if n % 12 not in _WHITE_PC]
    white_set = set(white)
    indices: list[int] = []
    for b in black:
        lw = b - 1
        while lw >= low and lw % 12 not in _WHITE_PC:
            lw -= 1
        indices.append(white.index(lw) if lw >= low and lw in white_set else 0)
    return white, black, indices

def _snap_low(note: int) -> int:
    return (note // 12) * 12

def _snap_high(note: int) -> int:
    return note if note % 12 == 0 else (note // 12 + 1) * 12

def get_physical_inputs() -> list[str]:
    try:
        return [n for n in mido.get_input_names() if "Midi Through" not in n]
    except Exception as e:
        print(f"Error listing MIDI devices: {e}")
        return []

class MidiPanel:
    def __init__(self, device_state=None, key_played_state=None,
                 text_fn=None, storage=None):
        self.midi_in = None
        self.active_notes: set[int] = set()
        self._last_device_check = 0.0
        self._font_cache: dict[int, pygame.font.Font] = {}

        self.device_state    = device_state
        self.key_played_state = key_played_state
        self.text_fn         = text_fn
        self._storage        = storage

        # State machine
        self._state   = _S_IDLE
        self._cal_low: int | None = None
        self._anim_t  = 0.0

        # Display range
        self._display_low  = _DEFAULT_LOW
        self._display_high = _DEFAULT_HIGH
        self._white_notes: list[int] = []
        self._black_notes: list[int] = []
        self._black_indices: list[int] = []
        self._rebuild_keys()

        # Load persisted range
        self._saved_range: tuple[int, int] | None = self._load_range()

    def _load_range(self) -> tuple[int, int] | None:
        if not self._storage:
            return None
        lo = self._storage.get(_SK_LOW,  None)
        hi = self._storage.get(_SK_HIGH, None)
        if lo is not None and hi is not None:
            return (int(lo), int(hi))
        return None

    def _save_range(self, low: int, high: int):
        self._saved_range = (low, high)
        if self._storage:
            self._storage.set(_SK_LOW,  low)
            self._storage.set(_SK_HIGH, high)

    def reset_calibration(self):
        self._saved_range = None
        if self._storage:
            self._storage.remove(_SK_LOW)
            self._storage.remove(_SK_HIGH)
        if self.midi_in is not None:
            self._cal_low = None
            self._state   = _S_CAL_LOW

    def _rebuild_keys(self):
        self._white_notes, self._black_notes, self._black_indices = _build_note_lists(
            self._display_low, self._display_high
        )

    def _set_range(self, low: int, high: int):
        self._display_low  = max(_MIDI_MIN, low)
        self._display_high = min(_MIDI_MAX, high)
        self._rebuild_keys()

    def _reset_range(self):
        self._set_range(_DEFAULT_LOW, _DEFAULT_HIGH)

    def _expand_for_note(self, note: int):
        lo, hi = self._display_low, self._display_high
        if note < lo:
            lo = _snap_low(note)
        if note > hi:
            hi = _snap_high(note)
        if lo != self._display_low or hi != self._display_high:
            self._set_range(lo, hi)

    def close(self):
        if self.midi_in:
            try:
                self.midi_in.close()
            except Exception:
                pass
            self.midi_in = None
        self.active_notes.clear()
        self._cal_low = None
        self._state   = _S_IDLE
        self._reset_range()

    def _poll_devices(self):
        now = pygame.time.get_ticks() / 1000.0
        if now - self._last_device_check < 1.0:
            return
        self._last_device_check = now
        devices = get_physical_inputs()

        if self.midi_in is None:
            if not devices:
                return
            try:
                self.midi_in = mido.open_input(devices[0])
                print(f"Connected to MIDI device: {self.midi_in.name}")
                self._set_device_name(self.midi_in.name)
                if self._saved_range:
                    self._set_range(*self._saved_range)
                    self._state = _S_READY
                else:
                    preset = _name_to_range(self.midi_in.name)
                    if preset:
                        self._set_range(*preset)
                        self._save_range(*preset)
                        self._anim_t = 0.0
                        self._state  = _S_ANIM
                    else:
                        self._cal_low = None
                        self._state   = _S_CAL_LOW
            except Exception as e:
                print(f"Error opening MIDI device: {e}")

        elif self.midi_in.name not in mido.get_input_names():
            print(f"Disconnected: {self.midi_in.name}")
            self.close()
            self._set_device_name(self._txt("midi_not_connected"))

    def _poll_messages(self):
        if not self.midi_in:
            return
        try:
            for msg in self.midi_in.iter_pending():
                if msg.type == "note_on" and msg.velocity > 0:
                    self._on_note_on(msg.note, msg.velocity)
                elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                    self.active_notes.discard(msg.note)
                    from pianove.sound_engine_fs import stop as _stop
                    _stop(msg.note)
        except Exception as e:
            print(f"MIDI read error: {e}")
            self.close()
            self.active_notes.clear()

    def _on_note_on(self, note: int, velocity: int):
        if self._state == _S_CAL_LOW:
            self._cal_low = note
            self._state   = _S_CAL_HIGH
            return

        if self._state == _S_CAL_HIGH and self._cal_low is not None:
            lo = min(note, self._cal_low)
            hi = max(note, self._cal_low)
            if hi == lo:          # same key pressed twice — wait for a real high
                return
            self._set_range(_snap_low(lo), min(_MIDI_MAX, _snap_high(hi)))
            self._save_range(self._display_low, self._display_high)
            self._anim_t = 0.0
            self._state  = _S_ANIM
            return

        if self._state in (_S_READY, _S_ANIM):
            self._expand_for_note(note)
            self.active_notes.add(note)
            self._mark_key_played()
            from pianove.sound_engine_fs import play as _play
            _play(note, velocity)

    def _set_device_name(self, name: str):
        if self.device_state is not None:
            self.device_state.value = name

    def _mark_key_played(self):
        if self.key_played_state is not None and not self.key_played_state.value:
            self.key_played_state.value = True

    def _txt(self, key: str, **kwargs) -> str:
        if self.text_fn:
            return self.text_fn(key, **kwargs)
        return key.format(**kwargs) if kwargs else key

    def _get_font(self, base_size: int) -> pygame.font.Font:
        size = scaled_font_size(base_size)
        if size not in self._font_cache:
            self._font_cache[size] = pygame.font.SysFont(None, size)
        return self._font_cache[size]

    def _layout(self, rect: pygame.Rect):
        n_white  = max(1, len(self._white_notes))
        margin_x = max(4, int(rect.width * 0.01))
        status_h = max(22, int(rect.height * 0.12))
        pad      = max(4, int(rect.height * 0.02))
        avail_w  = max(60, rect.width - margin_x * 2)
        avail_h  = rect.height - status_h - 2 * pad

        white_w  = avail_w / n_white
        ideal_h  = white_w * _KEY_ASPECT
        key_h    = max(28, min(avail_h, ideal_h))
        black_w  = white_w * 0.58
        black_h  = key_h   * 0.62

        # Vertically centre the keys inside the available area
        top = rect.top + pad + int((avail_h - key_h) / 2)
        return margin_x, top, key_h, white_w, black_w, black_h, status_h

    def update(self, dt: float, rect: pygame.Rect):
        self._poll_devices()
        self._poll_messages()
        if self._state == _S_ANIM:
            self._anim_t += dt
            if self._anim_t >= _ANIM_DUR:
                self._state = _S_READY

    def handle_event(self, event: pygame.event.Event, rect: pygame.Rect) -> bool:
        return False

    def draw(self, surface: pygame.Surface, rect: pygame.Rect):
        surface.fill(iOSTheme.tertiary_background, rect)
        if   self._state == _S_IDLE:
            self._draw_idle(surface, rect)
        elif self._state == _S_CAL_LOW:
            self._draw_cal_low(surface, rect)
        elif self._state == _S_CAL_HIGH:
            self._draw_cal_high(surface, rect)
        elif self._state == _S_ANIM:
            self._draw_keys(surface, rect, min(1.0, self._anim_t / _ANIM_DUR))
        else:
            self._draw_keys(surface, rect, 1.0)

    def _blit_center(self, surface, rect, text, color, base_size, dy=0):
        font = self._get_font(base_size)
        surf = font.render(text, True, color)
        x = rect.centerx - surf.get_width()  // 2
        y = rect.centery - surf.get_height() // 2 + dy
        surface.blit(surf, (x, y))

    def _draw_idle(self, surface, rect):
        self._blit_center(surface, rect, self._txt("midi_none"), (180, 100, 100), 17)

    def _draw_cal_low(self, surface, rect):
        ms    = pygame.time.get_ticks()
        pulse = 0.5 + 0.5 * math.sin(ms / 380.0)
        gold  = iOSTheme.accent

        # Primary instruction
        self._blit_center(surface, rect, self._txt("midi_cal_low"), iOSTheme.label, 20, dy=-18)
        # Hint
        self._blit_center(surface, rect, self._txt("midi_cal_hint"), (110, 110, 110), 13, dy=18)

        # Pulsing "press left" indicator — glowing dot at bottom-left
        r  = int(7 + 4 * pulse)
        cx = rect.left + 22
        cy = rect.bottom - 28
        brightness = int(pulse * 255)
        glow_col = (
            min(255, gold.r + int((255 - gold.r) * (1 - pulse) * 0.4)),
            min(255, gold.g + int((255 - gold.g) * (1 - pulse) * 0.4)),
            min(255, gold.b),
        )
        pygame.draw.circle(surface, glow_col, (cx, cy), r + 4, 0)   # outer glow
        pygame.draw.circle(surface, gold,     (cx, cy), r)

        # Small "◄" arrow suggesting leftmost key
        arr_font = self._get_font(15)
        arr      = arr_font.render("◄", True, gold)
        surface.blit(arr, (cx + r + 6, cy - arr.get_height() // 2))

    def _draw_cal_high(self, surface, rect):
        ms    = pygame.time.get_ticks()
        pulse = 0.5 + 0.5 * math.sin(ms / 380.0)
        gold  = iOSTheme.accent

        # Primary instruction + hint
        self._blit_center(surface, rect, self._txt("midi_cal_high"), iOSTheme.label, 20, dy=-18)
        self._blit_center(surface, rect, self._txt("midi_cal_hint"), (110, 110, 110), 13, dy=18)

        margin = 22
        bar_y  = rect.centery + 46
        left_x = rect.left  + margin
        right_x= rect.right - margin

        # Background track
        pygame.draw.line(surface, (60, 60, 60), (left_x, bar_y), (right_x, bar_y), 2)

        # Low-key anchor — glowing dot on the left
        lw_r = 8
        pygame.draw.circle(surface, gold, (left_x, bar_y), lw_r)

        # Filled progress portion that pulses (suggests "extend to the right")
        fill_x = left_x + int((right_x - left_x) * (0.3 + 0.15 * pulse))
        pygame.draw.line(surface, gold, (left_x, bar_y), (fill_x, bar_y), 3)

        # Pulsing cursor at the right end
        cur_r = int(6 + 4 * pulse)
        cur_col = (
            min(255, gold.r + 60),
            min(255, gold.g + 60),
            min(255, gold.b + 60),
        )
        pygame.draw.circle(surface, cur_col, (right_x, bar_y), cur_r)

        # "►" arrow on the right side
        arr_font = self._get_font(15)
        arr      = arr_font.render("►", True, gold)
        surface.blit(arr, (right_x - arr.get_width() - cur_r - 4,
                           bar_y - arr.get_height() // 2))

    def _draw_keys(self, surface, rect, anim_progress: float):
        margin_x, top, key_h, white_w, black_w, black_h, status_h = self._layout(rect)
        active  = self.active_notes
        n_white = max(1, len(self._white_notes))

        # Each key cascades in with a slight left-to-right delay
        _CASCADE = 0.22   # fraction of total animation used for cascade offset

        def _eased(i: int) -> float:
            delay   = (i / n_white) * _CASCADE
            local_t = (anim_progress - delay) / (1.0 - _CASCADE)
            t       = max(0.0, min(1.0, local_t))
            return 1.0 - (1.0 - t) ** 3   # cubic ease-out

        # White keys
        white_draws: list[tuple[pygame.Rect, tuple]] = []
        for i, note in enumerate(self._white_notes):
            p   = _eased(i)
            kh  = max(1, int(key_h * p))
            ky  = top + int(key_h * (1.0 - p))   # keys rise upward from bottom
            x   = rect.left + margin_x + i * white_w
            kr  = pygame.Rect(int(x), ky, max(2, int(white_w) - 1), kh)
            col = (190, 60, 60) if note in active else (255, 255, 255)
            white_draws.append((kr, col))

        # Black keys (cascade index = their left white-key index)
        black_draws: list[tuple[pygame.Rect, tuple]] = []
        for idx, note in zip(self._black_indices, self._black_notes):
            p   = _eased(idx)
            bh  = max(1, int(black_h * p))
            by  = top + int(key_h * (1.0 - p))
            lx  = rect.left + margin_x + idx * white_w
            x   = lx + white_w - black_w / 2
            kr  = pygame.Rect(int(x), by, max(2, int(black_w)), bh)
            col = (140, 45, 45) if note in active else (20, 20, 20)
            black_draws.append((kr, col))

        for kr, col in white_draws:
            pygame.draw.rect(surface, col, kr)
            pygame.draw.rect(surface, (80, 80, 80), kr, 1)
        for kr, col in black_draws:
            pygame.draw.rect(surface, col, kr, border_radius=4)

        connected  = self.midi_in is not None
        label_text = (
            self._txt("midi_connected", name=self.midi_in.name)
            if connected else self._txt("midi_none")
        )
        label_color = (52, 199, 89) if connected else (255, 99, 99)
        font_size   = max(14, min(28, status_h - 4))
        font        = self._get_font(font_size)
        label       = font.render(label_text, True, label_color)
        label_y     = rect.bottom - status_h + (status_h - label.get_height()) // 2
        surface.blit(label, (rect.left + margin_x, label_y))

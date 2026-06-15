"""MIDI piano preview for onboarding — scales to the PygameCanvas clip rect."""

from __future__ import annotations

import pygame
import mido
from pylay.core.theme import iOSTheme
from pylay.core.scale import scaled_font_size

WHITE_NOTES = [48, 50, 52, 53, 55, 57, 59, 60, 62, 64, 65, 67, 69, 71, 72]
BLACK_NOTES = [49, 51, 54, 56, 58, 61, 63, 66, 68, 70]
BLACK_INDICES = [0, 1, 3, 4, 5, 7, 8, 10, 11, 12]


def get_physical_inputs():
    try:
        return [n for n in mido.get_input_names() if "Midi Through" not in n]
    except Exception as e:
        print(f"Error listing MIDI devices: {e}")
        return []


class MidiPanel:
    """Native pygame content for PygameCanvas (draw / handle_event / update)."""

    def __init__(self, device_state=None, key_played_state=None, text_fn=None):
        self.midi_in = None
        self.active_notes: set[int] = set()
        self._last_device_check = 0.0
        self._status_font: pygame.font.Font | None = None
        self._status_font_size: int = 0
        self.device_state = device_state
        self.key_played_state = key_played_state
        self.text_fn = text_fn

    def close(self):
        if self.midi_in:
            try:
                self.midi_in.close()
            except Exception:
                pass
            self.midi_in = None

    def _status_font_for(self, base_size: int) -> pygame.font.Font:
        size = scaled_font_size(base_size)
        if self._status_font is None or self._status_font_size != size:
            self._status_font = pygame.font.SysFont(None, size)
            self._status_font_size = size
        return self._status_font

    def _txt(self, key: str, **kwargs) -> str:
        if self.text_fn:
            return self.text_fn(key, **kwargs)
        return key.format(**kwargs) if kwargs else key

    def _note_active(self, note_num: int, active_notes: set[int]) -> bool:
        if note_num in active_notes:
            return True
        for active in active_notes:
            if active < 48 or active > 72:
                if (active - 48) % 12 == (note_num - 48) % 12:
                    return True
        return False

    def _layout_keys(self, rect: pygame.Rect):
        margin_x = max(8, int(rect.width * 0.02))
        status_h = max(22, int(rect.height * 0.12))
        top = rect.top + max(6, int(rect.height * 0.02))
        key_h = max(40, rect.bottom - status_h - top - 6)
        avail_w = max(60, rect.width - margin_x * 2)
        n_white = len(WHITE_NOTES)
        white_w = avail_w / n_white
        black_w = white_w / 2
        black_h = key_h * (200 / 300)
        return margin_x, top, key_h, white_w, black_w, black_h, status_h

    def _poll_devices(self):
        now = pygame.time.get_ticks() / 1000.0
        if now - self._last_device_check < 1.0:
            return
        self._last_device_check = now
        devices = get_physical_inputs()
        if self.midi_in is None:
            if devices:
                try:
                    self.midi_in = mido.open_input(devices[0])
                    print(f"Connected to MIDI device: {self.midi_in.name}")
                    self._set_device_name(self.midi_in.name)
                except Exception as e:
                    print(f"Error opening MIDI device: {e}")
        elif self.midi_in.name not in mido.get_input_names():
            print(f"Disconnected from MIDI device: {self.midi_in.name}")
            self.close()
            self.active_notes.clear()
            self._set_device_name(self._txt("midi_not_connected"))

    def _poll_messages(self):
        if not self.midi_in:
            return
        try:
            for msg in self.midi_in.iter_pending():
                if msg.type == "note_on":
                    if msg.velocity > 0:
                        self.active_notes.add(msg.note)
                        self._on_key_pressed()
                        from pianove.sound_engine_fs import play as _snd_play
                        _snd_play(msg.note, msg.velocity)
                    else:
                        self.active_notes.discard(msg.note)
                        from pianove.sound_engine_fs import stop as _snd_stop
                        _snd_stop(msg.note)
                elif msg.type == "note_off":
                    self.active_notes.discard(msg.note)
                    from pianove.sound_engine_fs import stop as _snd_stop
                    _snd_stop(msg.note)
        except Exception as e:
            print(f"Error reading MIDI messages: {e}")
            self.close()
            self.active_notes.clear()

    def _set_device_name(self, name: str):
        if self.device_state is not None:
            self.device_state.value = name

    def _on_key_pressed(self):
        if self.key_played_state is not None and not self.key_played_state.value:
            self.key_played_state.value = True

    def update(self, dt: float, rect: pygame.Rect):
        self._poll_devices()
        self._poll_messages()

    def handle_event(self, event: pygame.event.Event, rect: pygame.Rect) -> bool:
        return False

    def draw(self, surface: pygame.Surface, rect: pygame.Rect):
        surface.fill(iOSTheme.tertiary_background, rect)
        margin_x, top, key_h, white_w, black_w, black_h, status_h = self._layout_keys(
            rect
        )
        active = self.active_notes
        white_keys = []
        for i, note in enumerate(WHITE_NOTES):
            x = rect.left + margin_x + i * white_w
            key_rect = pygame.Rect(int(x), int(top), int(white_w), int(key_h))
            color = (190, 60, 60) if self._note_active(note, active) else (255, 255, 255)
            white_keys.append((key_rect, color))

        black_keys = []
        for idx, note in zip(BLACK_INDICES, BLACK_NOTES):
            left_white = rect.left + margin_x + idx * white_w
            x = left_white + white_w - black_w / 2
            key_rect = pygame.Rect(int(x), int(top), int(black_w), int(black_h))
            color = (140, 45, 45) if self._note_active(note, active) else (0, 0, 0)
            black_keys.append((key_rect, color))

        for key_rect, color in white_keys:
            pygame.draw.rect(surface, color, key_rect)
            pygame.draw.rect(surface, (0, 0, 0), key_rect, 2)
        for key_rect, color in black_keys:
            pygame.draw.rect(surface, color, key_rect, border_radius=10)
            pygame.draw.rect(surface, (0, 0, 0), key_rect, 2, border_radius=10)

        connected = self.midi_in is not None
        label_text = (
            self._txt("midi_connected", name=self.midi_in.name)
            if connected
            else self._txt("midi_none")
        )
        label_color = (52, 199, 89) if connected else (255, 99, 99)
        font_size = max(14, min(28, status_h - 4))
        font = self._status_font_for(font_size)
        label = font.render(label_text, True, label_color)
        label_y = rect.bottom - status_h + (status_h - label.get_height()) // 2
        surface.blit(label, (rect.left + margin_x, label_y))

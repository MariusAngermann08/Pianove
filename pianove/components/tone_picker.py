"""A row of skin-tone swatches: which skin tone the hands in lessons have."""
import pygame
import pygame.gfxdraw
from pylay import State
from pylay.core.theme import ColorPalette
from pylay.widgets.pygame_canvas import PygameCanvas

from pianove.hands import SKIN_TONES

_D = 24          # swatch diameter
_GAP = 10


class TonePicker(PygameCanvas):
    """Click a swatch to choose it; the chosen one wears a ring. `state` holds the tone's
    name (a key of SKIN_TONES)."""

    def __init__(self, state: State, **kwargs):
        n = len(SKIN_TONES)
        kwargs.setdefault("width", n * _D + (n - 1) * _GAP + 14)   # room for the ring
        kwargs.setdefault("height", _D + 10)
        super().__init__(draw_border=False, **kwargs)
        self._state = state

    def _centres(self, rect: pygame.Rect):
        x = rect.left + 6 + _D // 2
        for name in SKIN_TONES:
            yield name, (x, rect.centery)
            x += _D + _GAP

    def draw_content(self, surface: pygame.Surface, rect: pygame.Rect):
        r = _D // 2
        for name, (cx, cy) in self._centres(rect):
            if name == self._state.value:
                for k in (r + 4, r + 3):                       # the ring around the chosen tone
                    pygame.gfxdraw.aacircle(surface, cx, cy, k, ColorPalette.BLUE)
            pygame.gfxdraw.filled_circle(surface, cx, cy, r, SKIN_TONES[name])
            pygame.gfxdraw.aacircle(surface, cx, cy, r, SKIN_TONES[name])
            pygame.gfxdraw.aacircle(surface, cx, cy, r, (120, 120, 128, 90))   # a soft edge

    def handle_content_event(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.MOUSEBUTTONDOWN or getattr(event, "button", 1) != 1:
            return False
        for name, (cx, cy) in self._centres(self.rect):
            if (event.pos[0] - cx) ** 2 + (event.pos[1] - cy) ** 2 <= (_D // 2 + 4) ** 2:
                self._state.value = name
                return True
        return False

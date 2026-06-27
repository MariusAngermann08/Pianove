import pygame
from pylay.core.element import UIElement
from pylay.core.state import State
from pylay.core.theme import iOSTheme, ColorPalette
from typing import Callable, Optional, Union, Any

class Switch(UIElement):
    def __init__(self,
                 value: Union[bool, State] = False,
                 on_change: Optional[Callable[[bool], None]] = None,
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 width: Union[int, float] = 51,
                 height: Union[int, float] = 31,
                 active_color: Optional[pygame.Color] = None,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=width, height=height, **kwargs)
        self.on_change    = on_change
        self.active_color = active_color if active_color is not None else ColorPalette.GREEN
        self._state: Optional[State] = None
        if isinstance(value, State):
            self._state = value
            self.value = bool(value.value)
            value.bind(self._on_state_update)
        else:
            self.value = bool(value)

        self.toggle_percent = 1.0 if self.value else 0.0
        self._last_value    = self.value

    def _on_state_update(self, val: Any):
        self.value = bool(val)

    def update(self, dt: float):
        # Only call animate_to when the value actually changed
        if self.value != self._last_value:
            target = 1.0 if self.value else 0.0
            self.animate_to("toggle_percent", target, response=0.18, damping_fraction=0.80)
            self._last_value = self.value
        super().update(dt)

    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled or not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.value = not self.value
                if self._state:
                    self._state.value = self.value
                if self.on_change:
                    self.on_change(self.value)
                return True
        return False

    def render(self, surface: pygame.Surface):
        w, h = self.rect.width, self.rect.height
        if w <= 4 or h <= 4:
            return

        t = self.toggle_percent

        # Interpolate track color
        inactive = iOSTheme.fill_secondary if iOSTheme.dark else pygame.Color(220, 220, 220)
        active   = self.active_color
        r = max(0, min(255, int(inactive.r + (active.r - inactive.r) * t)))
        g = max(0, min(255, int(inactive.g + (active.g - inactive.g) * t)))
        b = max(0, min(255, int(inactive.b + (active.b - inactive.b) * t)))
        bg = pygame.Color(r, g, b)

        rx, ry = self.rect.left, self.rect.top
        radius = h // 2

        # Draw pill track directly on surface
        pygame.draw.rect(surface, bg, self.rect, border_radius=radius)

        # Draw knob
        knob_d   = h - 4
        knob_r   = knob_d // 2
        kx_start = rx + 2 + knob_r
        kx_end   = rx + w - 2 - knob_r
        knob_cx  = int(kx_start + (kx_end - kx_start) * t)
        knob_cy  = ry + 2 + knob_r
        pygame.draw.circle(surface, pygame.Color(255, 255, 255), (knob_cx, knob_cy), knob_r)

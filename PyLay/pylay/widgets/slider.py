import pygame
from pylay.core.element import UIElement
from pylay.core.state import State
from pylay.core.theme import iOSTheme, ColorPalette
from typing import Callable, Optional, Union, Any

class Slider(UIElement):
    """
    An iOS-style slider control. Hover/drag feedback via spring-animated track
    thickness and knob radius. Zero per-frame surface allocations.
    """
    def __init__(self,
                 value: Union[float, State] = 0.5,
                 min_val: float = 0.0,
                 max_val: float = 1.0,
                 on_change: Optional[Callable[[float], None]] = None,
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 width: Union[int, float] = 150,
                 height: Union[int, float] = 28,
                 active_color: Optional[pygame.Color] = None,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=width, height=height, **kwargs)
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.on_change = on_change
        self.active_color = active_color if active_color is not None else ColorPalette.BLUE
        self._state: Optional[State] = None
        if isinstance(value, State):
            self._state = value
            self.value = self._from_normalized(float(value.value))
            value.bind(self._on_state_update)
        else:
            self.value = self._from_normalized(float(value))

        self.is_dragging = False
        self.is_hovered  = False
        self.hover_highlight = 0.0
        self._last_highlight_state = False

    def _from_normalized(self, t: float) -> float:
        t = max(0.0, min(1.0, t))
        return self.min_val + t * (self.max_val - self.min_val)

    def _to_normalized(self) -> float:
        span = self.max_val - self.min_val
        if abs(span) < 1e-9:
            return 0.0
        return max(0.0, min(1.0, (self.value - self.min_val) / span))

    def _on_state_update(self, val: Any):
        self.value = self._from_normalized(float(val))

    def update(self, dt: float):
        want_highlight = self.is_hovered or self.is_dragging
        if want_highlight != self._last_highlight_state:
            self.animate_to("hover_highlight", 1.0 if want_highlight else 0.0,
                            response=0.20, damping_fraction=0.90)
            self._last_highlight_state = want_highlight
        super().update(dt)

    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled or not self.visible:
            return False

        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
            if self.is_dragging:
                self._update_value(event.pos[0])
                return True

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.is_dragging = True
                self._update_value(event.pos[0])
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_dragging:
                self.is_dragging = False
                return True

        return False

    def _update_value(self, mouse_x: int):
        rel = mouse_x - self.rect.left
        t = max(0.0, min(1.0, rel / max(1, self.rect.width)))
        self.value = self._from_normalized(t)
        if self._state:
            self._state.value = t
        if self.on_change:
            self.on_change(self.value)

    def render(self, surface: pygame.Surface):
        w, h = self.rect.width, self.rect.height
        if w <= 4 or h <= 4:
            return

        hv = self.hover_highlight
        rx, ry = self.rect.left, self.rect.top

        # Track geometry
        track_h = 4 + int(hv * 2)          # 4 → 6 px
        track_y = ry + (h - track_h) // 2

        # Background track
        bg_col = iOSTheme.fill_secondary if iOSTheme.dark else pygame.Color(220, 220, 220)
        pygame.draw.rect(surface, bg_col,
                         (rx, track_y, w, track_h),
                         border_radius=track_h // 2)

        # Filled progress
        fill_w = max(0, int(w * self._to_normalized()))
        if fill_w > 0:
            pygame.draw.rect(surface, self.active_color,
                             (rx, track_y, fill_w, track_h),
                             border_radius=track_h // 2)

        # Knob
        knob_r  = 8 + int(hv * 2)          # 8 → 10 px
        raw_kx  = rx + int(w * self._to_normalized())
        knob_cx = max(rx + knob_r, min(rx + w - knob_r, raw_kx))
        knob_cy = ry + h // 2

        pygame.draw.circle(surface, pygame.Color(160, 160, 160), (knob_cx, knob_cy + 1), knob_r + 1)
        pygame.draw.circle(surface, pygame.Color(255, 255, 255), (knob_cx, knob_cy), knob_r)

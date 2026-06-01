import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme, ColorPalette
from pylay.core.state import State
from typing import Optional, Union, Any, Callable

class Checkbox(UIElement):
    """
    An iOS-style check selector box.
    Fades and scales its checkmark dynamically using spring physics.
    Supports State binding out-of-the-box.
    """
    def __init__(self,
                 value: Union[bool, State] = False,
                 on_change: Optional[Callable[[bool], None]] = None,
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 size: int = 24,
                 active_color: Optional[pygame.Color] = None,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=size, height=size, **kwargs)
        
        self.on_change = on_change
        self.active_color = active_color if active_color is not None else ColorPalette.GREEN
        
        # State Binding
        self._state: Optional[State] = None
        if isinstance(value, State):
            self._state = value
            self.value_val = bool(value.value)
            value.bind(self._on_state_update)
        else:
            self.value_val = bool(value)
            
        # Animatable scale for checkmark popping effect (0.0 off, 1.0 on)
        self.check_scale = 1.0 if self.value_val else 0.0
        self._last_val = self.value_val
        
    def _on_state_update(self, val: Any):
        self.value_val = bool(val)
        
    def update(self, dt: float):
        if self.value_val != self._last_val:
            target = 1.0 if self.value_val else 0.0
            self.animate_to("check_scale", target, response=0.18, damping_fraction=0.7)
            self._last_val = self.value_val
        super().update(dt)
        
    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled or not self.visible:
            return False
            
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.value_val = not self.value_val
                if self._state:
                    self._state.value = self.value_val
                if self.on_change:
                    self.on_change(self.value_val)
                return True
                
        return False
        
    def render(self, surface: pygame.Surface):
        rx, ry = self.rect.left, self.rect.top
        size = self.rect.width
        cx, cy = rx + size // 2, ry + size // 2
        radius = size // 2
        
        # Track background box color based on checked percent
        t = self.check_scale
        inactive = iOSTheme.fill_tertiary
        active = self.active_color
        
        r = int(inactive.r + (active.r - inactive.r) * t)
        g = int(inactive.g + (active.g - inactive.g) * t)
        b = int(inactive.b + (active.b - inactive.b) * t)
        bg = pygame.Color(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
        
        # Draw filled circle
        pygame.draw.circle(surface, bg, (cx, cy), radius)
        
        # Draw a subtle border if not fully checked to make it pop
        if t < 0.95:
            border_col = iOSTheme.fill_secondary if iOSTheme.dark else pygame.Color(180, 180, 180)
            pygame.draw.circle(surface, border_col, (cx, cy), radius, 2)
            
        # Draw white checkmark with high-fidelity vector math scaling about circle center
        if t > 0.01:
            # Scale coordinates relative to center (cx, cy) using t
            p1 = (int(cx - 5 * t), int(cy - 1 * t))
            p2 = (int(cx - 1 * t), int(cy + 3 * t))
            p3 = (int(cx + 4 * t), int(cy - 4 * t))
            
            pygame.draw.line(surface, pygame.Color(255, 255, 255), p1, p2, width=2)
            pygame.draw.line(surface, pygame.Color(255, 255, 255), p2, p3, width=2)

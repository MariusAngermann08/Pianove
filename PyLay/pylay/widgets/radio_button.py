import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme, ColorPalette
from pylay.core.state import State
from typing import Optional, Union, Any, Callable

class RadioButton(UIElement):
    """
    An iOS-style circular Radio Button selector.
    Fades and scales its inner check dot dynamically using spring physics.
    Supports State binding for clean single-choice logic.
    """
    def __init__(self,
                 group_state: State,
                 choice_value: Any,
                 on_change: Optional[Callable[[Any], None]] = None,
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 size: int = 24,
                 active_color: Optional[pygame.Color] = None,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=size, height=size, **kwargs)
        
        self.group_state = group_state
        self.choice_value = choice_value
        self.on_change = on_change
        self.active_color = active_color if active_color is not None else ColorPalette.BLUE
        
        # Subscribe to group state
        self.group_state.bind(self._on_state_update)
        
        # Current active state
        self.is_selected = (self.group_state.value == self.choice_value)
        
        # Animatable inner dot scale (0.0 off, 1.0 on)
        self.dot_scale = 1.0 if self.is_selected else 0.0
        self._last_selected = self.is_selected
        
    def _on_state_update(self, val: Any):
        self.is_selected = (val == self.choice_value)
        
    def update(self, dt: float):
        if self.is_selected != self._last_selected:
            target = 1.0 if self.is_selected else 0.0
            self.animate_to("dot_scale", target, response=0.18, damping_fraction=0.7)
            self._last_selected = self.is_selected
        super().update(dt)
        
    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled or not self.visible:
            return False
            
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if not self.is_selected:
                    self.group_state.value = self.choice_value
                    if self.on_change:
                        self.on_change(self.choice_value)
                    return True
                    
        return False
        
    def render(self, surface: pygame.Surface):
        rx, ry = self.rect.left, self.rect.top
        size = self.rect.width
        cx, cy = rx + size // 2, ry + size // 2
        r_outer = size // 2
        
        # Draw outer ring
        t = self.dot_scale
        border_col = iOSTheme.fill_tertiary
        if t > 0.01:
            # Interpolate ring towards active color
            active = self.active_color
            r = int(border_col.r + (active.r - border_col.r) * t)
            g = int(border_col.g + (active.g - border_col.g) * t)
            b = int(border_col.b + (active.b - border_col.b) * t)
            border_col = pygame.Color(
                max(0, min(255, r)),
                max(0, min(255, g)),
                max(0, min(255, b))
            )
            
        # Draw outer circle
        pygame.draw.circle(surface, border_col, (cx, cy), r_outer, 2 if t < 0.9 else 2)
        
        # Draw inner filled dot based on spring scale
        if t > 0.01:
            r_inner = max(1, int((r_outer - 4) * t))
            pygame.draw.circle(surface, self.active_color, (cx, cy), r_inner)

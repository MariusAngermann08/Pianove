import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme, ColorPalette
from pylay.core.state import State
from typing import Optional, Union, Any

class ProgressBar(UIElement):
    """
    A physics-driven ProgressBar widget.
    Animates changes to the progress level smoothly using spring physics.
    Supports declarative bindings to State objects.
    """
    def __init__(self,
                 progress: Union[float, State] = 0.0,
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 width: Union[int, float] = 200,
                 height: Union[int, float] = 8,
                 active_color: Optional[pygame.Color] = None,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=width, height=height, **kwargs)
        
        self.active_color = active_color if active_color is not None else ColorPalette.BLUE
        
        # State Binding
        self._state: Optional[State] = None
        if isinstance(progress, State):
            self._state = progress
            self.target_progress = float(progress.value)
            progress.bind(self._on_state_update)
        else:
            self.target_progress = float(progress)
            
        # Animatable progress value (0.0 to 1.0)
        self.current_progress = self.target_progress
        
    def _on_state_update(self, val: Any):
        self.target_progress = max(0.0, min(1.0, float(val)))
        
    def update(self, dt: float):
        # Let the progress slide smoothly to target
        self.animate_to("current_progress", self.target_progress, response=0.3, damping_fraction=0.8)
        super().update(dt)
        
    def render(self, surface: pygame.Surface):
        rx, ry = self.rect.left, self.rect.top
        w, h = self.rect.width, self.rect.height
        if w <= 2 or h <= 2:
            return
            
        # Draw background track
        track_col = iOSTheme.fill_tertiary
        pygame.draw.rect(surface, track_col, self.rect, border_radius=h // 2)
        
        # Draw filled bar
        fill_w = int(w * max(0.0, min(1.0, self.current_progress)))
        if fill_w > 0:
            fill_rect = pygame.Rect(rx, ry, fill_w, h)
            pygame.draw.rect(surface, self.active_color, fill_rect, border_radius=h // 2)

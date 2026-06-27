import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme, ColorPalette
from pylay.core.state import State
from pylay.core.render_utils import make_aa_rect
from typing import Optional, Union, Any

class ProgressBar(UIElement):
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

        # Track and fill surface caches
        self._track_surf: Optional[pygame.Surface] = None
        self._track_key: Optional[tuple] = None
        self._fill_surf: Optional[pygame.Surface] = None
        self._fill_key: Optional[tuple] = None

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
        
    def _on_theme_changed(self):
        self._track_surf = None
        self._track_key = None
        self._fill_surf = None
        self._fill_key = None

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

        rad = h // 2
        track_col = iOSTheme.fill_tertiary

        # AA track — cached
        track_key = (w, h, track_col.r, track_col.g, track_col.b, track_col.a)
        if self._track_surf is None or self._track_key != track_key:
            self._track_surf = make_aa_rect(w, h, track_col, rad)
            self._track_key = track_key
        surface.blit(self._track_surf, (rx, ry))

        # AA fill — cached by fill width
        fill_w = int(w * max(0.0, min(1.0, self.current_progress)))
        if fill_w > 0:
            fill_key = (fill_w, h, self.active_color.r, self.active_color.g, self.active_color.b)
            if self._fill_surf is None or self._fill_key != fill_key:
                self._fill_surf = make_aa_rect(fill_w, h, self.active_color, rad)
                self._fill_key = fill_key
            surface.blit(self._fill_surf, (rx, ry))

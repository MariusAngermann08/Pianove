import pygame
from pylay.layouts.layout import Layout
from pylay.core.theme import iOSTheme
from typing import Optional, Union, Tuple

class FloatLayout(Layout):
    """
    A layout container that positions its children using float percentages or absolute offsets.
    It can be configured to render as an iOS card/panel with a glassmorphic blur,
    rounded corners, and dynamic themed backgrounds.
    """
    def __init__(self,
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 width: Union[int, float] = 1.0,
                 height: Union[int, float] = 1.0,
                 background_color: Optional[pygame.Color] = None,
                 border_radius: int = 12,
                 border_width: int = 0,
                 border_color: Optional[pygame.Color] = None,
                 padding: int = 0,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=width, height=height, **kwargs)
        
        self.background_color = background_color
        self.border_radius = border_radius
        self.border_width = border_width
        self.border_color = border_color
        self.padding = padding
        
        # High-performance background surface caching
        self._cached_bg_surface: Optional[pygame.Surface] = None
        self._cached_bg_size: Tuple[int, int] = (0, 0)
        self._cached_bg_color: Optional[pygame.Color] = None

    def _on_theme_changed(self):
        self._cached_bg_surface = None
        self._cached_bg_size = (0, 0)
        if hasattr(self, "_cached_bg_rgba"):
            del self._cached_bg_rgba
        
    def render(self, surface: pygame.Surface):
        # Determine active theme colors if not explicitly overridden
        bg_color = self.background_color
        if bg_color is None:
            # If parent is root (none) and occupies full window, use theme background.
            # Otherwise, use theme secondary_background (iOS Card color)
            if self.parent is None and self.width_spec == 1.0 and self.height_spec == 1.0:
                bg_color = iOSTheme.background
            else:
                bg_color = iOSTheme.secondary_background
                
        # Draw background card
        if bg_color.a == 0:
            # Fully transparent, skip rendering background
            pass
        elif bg_color.a == 255:
            # Fully opaque, render directly on screen
            pygame.draw.rect(surface, bg_color, self.rect, border_radius=self.border_radius)
        else:
            # Translucent background - use size-based caching to prevent memory leaks and lags!
            size = (self.rect.width, self.rect.height)
            if size[0] > 0 and size[1] > 0:
                current_rgba = (bg_color.r, bg_color.g, bg_color.b, bg_color.a)
                if (self._cached_bg_surface is None or 
                    self._cached_bg_size != size or 
                    not hasattr(self, "_cached_bg_rgba") or
                    self._cached_bg_rgba != current_rgba):
                    
                    self._cached_bg_surface = pygame.Surface(size, pygame.SRCALPHA)
                    pygame.draw.rect(self._cached_bg_surface, bg_color, (0, 0, size[0], size[1]), border_radius=self.border_radius)
                    self._cached_bg_size = size
                    self._cached_bg_rgba = current_rgba
                    
                surface.blit(self._cached_bg_surface, self.rect.topleft)
            
        # Draw border directly on main surface
        border_col = self.border_color
        if self.border_width > 0:
            if border_col is None:
                border_col = iOSTheme.fill_tertiary
            pygame.draw.rect(surface, border_col, self.rect, width=self.border_width, border_radius=self.border_radius)

import pygame
from pylay.core.element import UIElement
from pylay.core.state import State
from pylay.core.theme import iOSTheme, ColorPalette
from pylay.core.scale import scaled_font_size
from typing import Callable, Optional, Union, List, Any

class SegmentedControl(UIElement):
    """
    An iOS-style Segmented Control (Tab Bar).
    Smoothly slides a selector highlight pill under the selected item using spring physics.
    """
    def __init__(self,
                 segments: List[str],
                 selected_index: Union[int, State] = 0,
                 on_change: Optional[Callable[[int], None]] = None,
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 width: Union[int, float] = 300,
                 height: Union[int, float] = 36,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=width, height=height, **kwargs)
        self.segments = segments
        self.on_change = on_change
        self._state: Optional[State] = None
        if isinstance(selected_index, State):
            self._state = selected_index
            self.selected_index = int(selected_index.value)
            selected_index.bind(self._on_state_update)
        else:
            self.selected_index = int(selected_index)

        self.slider_index = float(self.selected_index)
        self._font = None
        self._font_px: int = 0

    def _on_state_update(self, val: Any):
        self.selected_index = int(val)

    def _on_scale_changed(self):
        self._font = None
        self._font_px = 0

    def _on_theme_changed(self):
        self._font = None
        self._font_px = 0

    def _get_font(self) -> pygame.font.Font:
        px = scaled_font_size(13)
        if self._font is None or self._font_px != px:
            if not pygame.font.get_init():
                pygame.font.init()
            self._font = pygame.font.SysFont("Arial", px, bold=True)
            self._font_px = px
        return self._font
        
    def update(self, dt: float):
        # Slide progress spring animation
        self.animate_to("slider_index", float(self.selected_index), response=0.22, damping_fraction=0.8)
        super().update(dt)
        
    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled or not self.visible:
            return False
            
        mouse_pos = pygame.mouse.get_pos()
        hovered = self.rect.collidepoint(mouse_pos)
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and hovered:
                # Determine which segment was clicked
                rel_x = mouse_pos[0] - self.rect.left
                seg_w = self.rect.width / len(self.segments)
                clicked_idx = int(rel_x / seg_w)
                clicked_idx = max(0, min(len(self.segments) - 1, clicked_idx))
                
                if clicked_idx != self.selected_index:
                    self.selected_index = clicked_idx
                    if self._state:
                        self._state.value = clicked_idx
                    if self.on_change:
                        self.on_change(clicked_idx)
                    return True
                    
        return False
        
    def render(self, surface: pygame.Surface):
        w, h = self.rect.width, self.rect.height
        if w <= 4 or h <= 4:
            return
            
        # Draw background track directly on main surface
        bg_color = iOSTheme.fill_secondary if iOSTheme.dark else pygame.Color(230, 230, 235)
        radius = h // 2
        pygame.draw.rect(surface, bg_color, self.rect, border_radius=radius)
        
        # Draw sliding selector highlight pill directly on main surface
        num_segs = len(self.segments)
        seg_w = w / num_segs
        
        # Pill has 2px padding inside track
        pill_w = seg_w - 4
        pill_h = h - 4
        pill_radius = pill_h // 2
        
        pill_x = self.rect.left + 2 + self.slider_index * seg_w
        pill_color = iOSTheme.secondary_background if iOSTheme.dark else pygame.Color(255, 255, 255)
        
        # Draw pill shadow (very subtle in dark mode)
        if not iOSTheme.dark:
            pygame.draw.rect(surface, pygame.Color(200, 200, 200, 100), (pill_x, self.rect.top + 2, pill_w, pill_h), border_radius=pill_radius)
        pygame.draw.rect(surface, pill_color, (pill_x, self.rect.top + 2, pill_w, pill_h), border_radius=pill_radius)
        
        # Render text labels on top directly on main surface
        font = self._get_font()
        for i, text in enumerate(self.segments):
            # Select contrasting color based on selection
            if i == self.selected_index:
                color = iOSTheme.label
            else:
                color = iOSTheme.secondary_label
                
            text_surf = font.render(text, True, color)
            text_rect = text_surf.get_rect()
            
            # Center in segment
            center_x = self.rect.left + i * seg_w + seg_w / 2
            center_y = self.rect.top + h / 2
            text_rect.center = (int(center_x), int(center_y))
            surface.blit(text_surf, text_rect)

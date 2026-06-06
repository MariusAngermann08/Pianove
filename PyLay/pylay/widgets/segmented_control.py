import pygame
from pylay.core.element import UIElement
from pylay.core.state import State
from pylay.core.theme import iOSTheme, ColorPalette
from pylay.core.scale import scaled_font_size
from pylay.core import font_loader
from pylay.core.render_utils import make_aa_rect
from typing import Callable, Optional, Union, List, Any, Optional, Tuple

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

        # AA surface caches
        self._track_surf: Optional[pygame.Surface] = None
        self._track_key: Optional[Tuple] = None
        self._pill_surf: Optional[pygame.Surface] = None
        self._pill_key: Optional[Tuple] = None

    def _on_state_update(self, val: Any):
        self.selected_index = int(val)

    def _on_scale_changed(self):
        self._font = None
        self._font_px = 0
        self._track_surf = None
        self._track_key = None
        self._pill_surf = None
        self._pill_key = None

    def _on_theme_changed(self):
        self._font = None
        self._font_px = 0
        self._track_surf = None
        self._track_key = None
        self._pill_surf = None
        self._pill_key = None

    def _get_font(self) -> pygame.font.Font:
        px = scaled_font_size(13)
        if self._font is None or self._font_px != px:
            self._font = font_loader.load_font(13, bold=True)
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
            
        # Draw AA background track — cached
        bg_color = iOSTheme.fill_secondary if iOSTheme.dark else pygame.Color(230, 230, 235)
        radius = h // 2
        track_key = (w, h, bg_color.r, bg_color.g, bg_color.b, bg_color.a)
        if self._track_surf is None or self._track_key != track_key:
            self._track_surf = make_aa_rect(w, h, bg_color, radius)
            self._track_key = track_key
        surface.blit(self._track_surf, self.rect.topleft)

        # Draw sliding AA pill
        num_segs = len(self.segments)
        seg_w = w / num_segs

        pill_w = max(1, int(seg_w) - 4)
        pill_h = h - 4
        pill_radius = pill_h // 2
        pill_x = self.rect.left + 2 + int(self.slider_index * seg_w)
        pill_color = iOSTheme.secondary_background if iOSTheme.dark else pygame.Color(255, 255, 255)

        # AA pill — rebuilt only when size or color changes
        pill_key = (pill_w, pill_h, pill_color.r, pill_color.g, pill_color.b)
        if self._pill_surf is None or self._pill_key != pill_key:
            self._pill_surf = make_aa_rect(pill_w, pill_h, pill_color, pill_radius)
            self._pill_key = pill_key
        surface.blit(self._pill_surf, (pill_x, self.rect.top + 2))
        
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

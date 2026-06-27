import pygame
import math
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme, ColorPalette
from pylay.core.state import State
from typing import Optional, Union, Callable, Any

class HamburgerButton(UIElement):
    def __init__(self,
                 open_state: Union[bool, State] = False,
                 on_toggle: Optional[Callable[[bool], None]] = None,
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 size: Optional[int] = None,
                 width: Union[int, float] = 40,
                 height: Union[int, float] = 40,
                 active_color: Optional[pygame.Color] = None,
                 **kwargs):
        btn_size = int(size if size is not None else max(int(width), int(height)))
        super().__init__(anchor=anchor, x=x, y=y, width=btn_size, height=btn_size, **kwargs)
        self.active_color = active_color
        
        self.on_toggle = on_toggle
        
        # State Binding
        self._state: Optional[State] = None
        if isinstance(open_state, State):
            self._state = open_state
            self.is_open = bool(open_state.value)
            open_state.bind(self._on_state_update)
        else:
            self.is_open = bool(open_state)
            
        # Animatable morph progression (0.0 = hamburger, 1.0 = X)
        self.open_progress = 1.0 if self.is_open else 0.0
        self._last_open = self.is_open

        self.is_hovered = False
        self.hover_highlight = 0.0

        # Cached surfaces — rebuilt only on size change
        self._hover_surf: Optional[pygame.Surface] = None
        self._hover_surf_size: Optional[tuple] = None
        self._mid_surf: Optional[pygame.Surface] = None
        self._mid_surf_size: Optional[tuple] = None
        
    def _on_state_update(self, val: Any):
        self.is_open = bool(val)
        
    def update(self, dt: float):
        if self.is_open != self._last_open:
            target = 1.0 if self.is_open else 0.0
            self.animate_to("open_progress", target, response=0.22, damping_fraction=0.7)
            self._last_open = self.is_open
            
        want_hover = self.is_hovered
        self.animate_to("hover_highlight", 1.0 if want_hover else 0.0, response=0.18, damping_fraction=0.8)
        super().update(dt)
        
    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled or not self.visible:
            return False
            
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
            
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.is_open = not self.is_open
                if self._state:
                    self._state.value = self.is_open
                if self.on_toggle:
                    self.on_toggle(self.is_open)
                return True
                
        return False
        
    def render(self, surface: pygame.Surface):
        rx, ry = self.rect.left, self.rect.top
        w, h = self.rect.width, self.rect.height
        cx, cy = rx + w // 2, ry + h // 2
        
        # Render a subtle iOS-style circular hover backdrop
        hv = self.hover_highlight
        if hv > 0.02:
            alpha = int(hv * 26)
            circle_col = pygame.Color(255, 255, 255, alpha) if iOSTheme.dark else pygame.Color(0, 0, 0, alpha)
            size_key = (w, h)
            if self._hover_surf is None or self._hover_surf_size != size_key:
                self._hover_surf = pygame.Surface((w, h), pygame.SRCALPHA)
                self._hover_surf_size = size_key
            self._hover_surf.fill((0, 0, 0, 0))
            pygame.draw.circle(self._hover_surf, circle_col, (w // 2, h // 2), w // 2)
            surface.blit(self._hover_surf, (rx, ry))
            
        t = self.open_progress
        line_w = int(w * 0.5)
        half_l = line_w / 2.0
        line_col = iOSTheme.label
        
        # Idle spacing between lines
        dy = 6.5
        
        # 1. Top Line (Rotates +45° and moves to center)
        theta_top = math.radians(45.0 * t)
        cos_t, sin_t = math.cos(theta_top), math.sin(theta_top)
        
        # Target y moves from cy-dy to cy
        y_top = cy - dy * (1.0 - t)
        
        dx_top = half_l * cos_t
        dy_top = half_l * sin_t
        
        p1_top = (int(cx - dx_top), int(y_top - dy_top))
        p2_top = (int(cx + dx_top), int(y_top + dy_top))
        
        # 2. Bottom Line (Rotates -45° and moves to center)
        theta_bot = math.radians(-45.0 * t)
        cos_b, sin_b = math.cos(theta_bot), math.sin(theta_bot)
        
        # Target y moves from cy+dy to cy
        y_bot = cy + dy * (1.0 - t)
        
        dx_bot = half_l * cos_b
        dy_bot = half_l * sin_b
        
        p1_bot = (int(cx - dx_bot), int(y_bot - dy_bot))
        p2_bot = (int(cx + dx_bot), int(y_bot + dy_bot))
        
        # Draw top and bottom lines
        pygame.draw.line(surface, line_col, p1_top, p2_top, width=3)
        pygame.draw.line(surface, line_col, p1_bot, p2_bot, width=3)
        
        # 3. Middle Line (Fades and shrinks)
        if t < 0.95:
            mid_alpha = max(0, min(255, int(255 * (1.0 - t))))
            mid_col = pygame.Color(line_col.r, line_col.g, line_col.b, mid_alpha)
            
            # Shrink width slightly as it disappears
            mid_half_l = half_l * (1.0 - t)
            
            p1_mid = (int(cx - mid_half_l), int(cy))
            p2_mid = (int(cx + mid_half_l), int(cy))
            
            # Translucent drawing requires an alpha surface
            if mid_alpha < 255:
                size_key = (w, h)
                if self._mid_surf is None or self._mid_surf_size != size_key:
                    self._mid_surf = pygame.Surface((w, h), pygame.SRCALPHA)
                    self._mid_surf_size = size_key
                self._mid_surf.fill((0, 0, 0, 0))
                pygame.draw.line(self._mid_surf, mid_col, (w // 2 - int(mid_half_l), h // 2), (w // 2 + int(mid_half_l), h // 2), 3)
                surface.blit(self._mid_surf, (rx, ry))
            else:
                pygame.draw.line(surface, line_col, p1_mid, p2_mid, width=3)

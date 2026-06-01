import pygame
import math
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme, ColorPalette
from pylay.core.state import State
from pylay.core.scale import scaled_font_size
from typing import List, Dict, Union, Optional, Tuple

class LineChart(UIElement):
    """
    A premium vector LineChart widget for OpenUI.
    Features:
    - Spring-animated loading animation (line morphs upward on load).
    - Dynamic horizontal hover tracking with spring inertia.
    - Glassmorphic metric tooltip that follows the mouse.
    - Sleek double-pass gradient area filling beneath the path.
    """
    def __init__(self,
                 data: List[float],
                 labels: Optional[List[str]] = None,
                 active_color: Optional[pygame.Color] = None,
                 title: str = "Metric Trend",
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 width: Union[int, float] = 400,
                 height: Union[int, float] = 220,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=width, height=height, **kwargs)
        self.data = data
        self.labels = labels if labels is not None else [str(i) for i in range(len(data))]
        self.active_color = active_color if active_color is not None else ColorPalette.BLUE
        self.title = title
        
        # Spring progress: 0.0 -> 1.0 (controls visual spline load-in)
        self.load_progress = 0.0
        self.animate_to("load_progress", 1.0, response=0.45, damping_fraction=0.75)
        
        # Interactive hover tracking state
        self.is_hovered = False
        self.hover_x = 0.0 # Raw mouse horizontal offset
        
        # Spring-driven tracking variables for the tooltip and dot
        self.tracker_x = 0.0
        self.tracker_y = 0.0
        self.tracker_alpha = 0.0
        
        self._font_title = None
        self._font_metrics = None
        self._font_px: int = 0

    def _on_scale_changed(self):
        self._font_title = self._font_metrics = None
        self._font_px = 0

    def _on_theme_changed(self):
        self._font_title = self._font_metrics = None
        self._font_px = 0

    def _get_fonts(self) -> Tuple[pygame.font.Font, pygame.font.Font]:
        px = scaled_font_size(13)
        if self._font_title is None or self._font_px != px:
            if not pygame.font.get_init():
                pygame.font.init()
            px_sm = scaled_font_size(11)
            for f in ["SF Pro Text", "Helvetica Neue", "Arial"]:
                try:
                    self._font_title   = pygame.font.SysFont(f, px,    bold=True)
                    self._font_metrics = pygame.font.SysFont(f, px_sm, bold=False)
                    break
                except Exception:
                    pass
            if self._font_title is None:
                self._font_title   = pygame.font.Font(None, px)
                self._font_metrics = pygame.font.Font(None, scaled_font_size(11))
            self._font_px = px
        return self._font_title, self._font_metrics

    def update(self, dt: float):
        super().update(dt)
        
        target_alpha = 1.0 if self.is_hovered else 0.0
        self.animate_to("tracker_alpha", target_alpha, response=0.22, damping_fraction=0.9)
        
        if self.is_hovered and len(self.data) > 0:
            # Map hover_x to closest data point index
            w = self.rect.width - 40
            seg_w = w / max(1, len(self.data) - 1)
            
            # Clamp relative local x coordinate
            lx = max(0, min(w, self.hover_x - 20))
            idx = int(round(lx / seg_w))
            idx = max(0, min(len(self.data) - 1, idx))
            
            # Solve exact dot coordinates
            min_val = min(self.data)
            max_val = max(self.data)
            val_range = max(1e-4, max_val - min_val)
            
            tx = 20 + idx * seg_w
            # Height mappings
            h_avail = self.rect.height - 70
            norm_val = (self.data[idx] - min_val) / val_range
            ty = self.rect.height - 20 - norm_val * h_avail * self.load_progress
            
            # Animate the tracker dot smoothly using springs
            self.animate_to("tracker_x", tx, response=0.18, damping_fraction=0.8)
            self.animate_to("tracker_y", ty, response=0.18, damping_fraction=0.8)
            self.current_hover_idx = idx
            
    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False
            
        pos = event.pos if hasattr(event, "pos") else pygame.mouse.get_pos()
        inside = self.rect.collidepoint(pos)
        
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = inside
            if inside:
                self.hover_x = pos[0] - self.rect.left
            return False
            
        return False
        
    def render(self, surface: pygame.Surface):
        w, h = self.rect.width, self.rect.height
        if w <= 10 or h <= 10:
            return
            
        rx, ry = self.rect.left, self.rect.top
        
        # 1. Card container background
        bg_col = iOSTheme.secondary_background
        pygame.draw.rect(surface, bg_col, self.rect, border_radius=16)
        
        # Border
        border_col = iOSTheme.fill_tertiary
        pygame.draw.rect(surface, border_col, self.rect, width=1, border_radius=16)
        
        # Title text
        f_title, f_metrics = self._get_fonts()
        title_surf = f_title.render(self.title, True, iOSTheme.label)
        surface.blit(title_surf, (rx + 20, ry + 16))
        
        if len(self.data) < 2:
            return
            
        # 2. Grid Coordinates Setup
        min_val = min(self.data)
        max_val = max(self.data)
        val_range = max(1e-4, max_val - min_val)
        
        # Available drawing bounds inside card
        pad_x = 20
        pad_y_top = 50
        pad_y_bottom = 20
        
        avail_w = w - (pad_x * 2)
        avail_h = h - pad_y_top - pad_y_bottom
        
        seg_w = avail_w / (len(self.data) - 1)
        
        # Renders the vertical grid guides and labels
        for idx in [0, len(self.data) // 2, len(self.data) - 1]:
            gx = rx + pad_x + idx * seg_w
            # Draw thin horizontal grid lines
            pygame.draw.line(surface, iOSTheme.fill_tertiary, (gx, ry + pad_y_top), (gx, ry + h - pad_y_bottom), width=1)
            
            # Bottom labels
            lbl_surf = f_metrics.render(self.labels[idx], True, iOSTheme.secondary_label)
            lbl_rect = lbl_surf.get_rect(center=(gx, ry + h - 10))
            surface.blit(lbl_surf, lbl_rect)
            
        # Draw baseline horizontal guide
        pygame.draw.line(surface, iOSTheme.fill_tertiary, (rx + pad_x, ry + h - pad_y_bottom), (rx + w - pad_x, ry + h - pad_y_bottom), width=1)
        
        # 3. Build Spline Points
        points: List[Tuple[float, float]] = []
        for i, val in enumerate(self.data):
            nx = rx + pad_x + i * seg_w
            
            # Apply animated load-in morph height
            norm_val = (val - min_val) / val_range
            ny = ry + h - pad_y_bottom - (norm_val * avail_h * self.load_progress)
            points.append((nx, ny))
            
        # 4. Draw Gradient Fill beneath path (using size-cached alpha surface)
        if len(points) >= 2:
            grad_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            
            # Make a closed polygon tracing the baseline path
            poly_points = [(p[0] - rx, p[1] - ry) for p in points]
            poly_points.append((points[-1][0] - rx, h - pad_y_bottom))
            poly_points.append((points[0][0] - rx, h - pad_y_bottom))
            
            # Color fills
            fill_col = pygame.Color(self.active_color.r, self.active_color.g, self.active_color.b, 35)
            pygame.draw.polygon(grad_surf, fill_col, poly_points)
            
            surface.blit(grad_surf, (rx, ry))
            
        # 5. Draw Primary Spline Line Path (Anti-aliased segment draws)
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i+1]
            pygame.draw.line(surface, self.active_color, p1, p2, width=3)
            
        # 6. Interactive Glowing Tracker Hover Dot & Tooltip
        ta = self.tracker_alpha
        if ta > 0.01:
            cx = rx + self.tracker_x
            cy = ry + self.tracker_y
            
            alpha_val = int(ta * 255)
            dot_glow = pygame.Color(self.active_color.r, self.active_color.g, self.active_color.b, int(ta * 70))
            dot_solid = pygame.Color(255, 255, 255, alpha_val)
            
            # Draw glow circle on a temporary alpha surface
            dot_surf = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.circle(dot_surf, dot_glow, (16, 16), 12)
            pygame.draw.circle(dot_surf, self.active_color, (16, 16), 6)
            pygame.draw.circle(dot_surf, dot_solid, (16, 16), 4)
            surface.blit(dot_surf, (cx - 16, cy - 16))
            
            # Floating Tooltip card
            if hasattr(self, "current_hover_idx"):
                idx = self.current_hover_idx
                val_text = f"{self.data[idx]}"
                lbl_text = self.labels[idx]
                
                # Metrics layouts
                val_surf = f_title.render(val_text, True, iOSTheme.label)
                lbl_surf = f_metrics.render(lbl_text, True, iOSTheme.secondary_label)
                
                tw = max(val_surf.get_width(), lbl_surf.get_width()) + 24
                th = 48
                
                # Keep tooltip in card bounds horizontally
                tx_left = cx - tw // 2
                tx_left = max(rx + 8, min(rx + w - tw - 8, tx_left))
                ty_top = cy - th - 12
                ty_top = max(ry + 8, ty_top) # Prevent top ceiling clips
                
                # Draw tooltip background with thin card outline
                tt_rect = pygame.Rect(tx_left, ty_top, tw, th)
                
                tt_bg = pygame.Color(35, 35, 40, int(ta * 230)) if iOSTheme.dark else pygame.Color(255, 255, 255, int(ta * 240))
                tt_border = pygame.Color(80, 80, 90, int(ta * 120)) if iOSTheme.dark else pygame.Color(200, 200, 210, int(ta * 180))
                
                tt_surf = pygame.Surface((tw, th), pygame.SRCALPHA)
                pygame.draw.rect(tt_surf, tt_bg, (0, 0, tw, th), border_radius=8)
                pygame.draw.rect(tt_surf, tt_border, (0, 0, tw, th), width=1, border_radius=8)
                
                # Blit text centered inside tooltip surface
                tt_surf.blit(val_surf, (12, 6))
                tt_surf.blit(lbl_surf, (12, 26))
                
                surface.blit(tt_surf, tt_rect.topleft)

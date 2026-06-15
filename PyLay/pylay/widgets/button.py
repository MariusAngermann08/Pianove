import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme, ColorPalette
from pylay.core.scale import scaled_font_size
from pylay.core import font_loader
from pylay.core.render_utils import make_aa_rect, make_shadow, SHADOW_BLUR
from typing import Callable, Optional, Union, Tuple

class Button(UIElement):
    """
    An iOS-inspired Button widget with spring-loaded physical scaling.
    Render cache: the button background + text is re-drawn only when size,
    color, or text changes — not every frame.

    Pass icon_fn (a Material Icon callable from Icon.as_icon_fn) to render an
    icon centered on the button instead of text.
    """
    def __init__(self,
                 text: str = "",
                 on_click: Optional[Callable[[], None]] = None,
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 width: Union[int, float] = 160,
                 height: Union[int, float] = 44,
                 background_color: Optional[pygame.Color] = None,
                 text_color: Optional[pygame.Color] = None,
                 border_radius: int = -1,
                 font_size: int = 16,
                 font_name: str = "Arial",
                 icon_fn: Optional[Callable] = None,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=width, height=height, **kwargs)

        self.disabled_blend = 0.0 if self.enabled else 1.0
        self.text             = text
        self.on_click         = on_click
        self.background_color = background_color
        self.text_color       = text_color
        self.border_radius    = border_radius
        self.font_size        = font_size
        self.font_name        = font_name
        self.icon_fn          = icon_fn

        self.is_pressed = False
        self.is_hovered = False

        # Spring-animated properties
        self.scale           = 1.0
        self.hover_highlight = 0.0

        self._font: Optional[pygame.font.Font] = None
        self._font_px: int = 0

        # Render cache — invalidated when size or color changes
        self._cached_surf: Optional[pygame.Surface] = None
        self._cache_key: Optional[Tuple] = None

        # Shadow surface cache
        self._shadow_surf: Optional[pygame.Surface] = None
        self._shadow_key: Optional[Tuple] = None

    def _on_theme_changed(self):
        self._cached_surf = None
        self._cache_key = None
        self._shadow_surf = None
        self._shadow_key = None
        if hasattr(self, "_ov_surf"):
            del self._ov_surf
        if hasattr(self, "_ov_size"):
            del self._ov_size

    def _on_scale_changed(self):
        self._font = None
        self._font_px = 0
        self._cached_surf = None
        self._cache_key = None
        self._shadow_surf = None
        self._shadow_key = None

    def _get_font(self) -> pygame.font.Font:
        px = scaled_font_size(self.font_size)
        if self._font is None or self._font_px != px:
            override = self.font_name if self.font_name != "Arial" else None
            self._font = font_loader.load_font(self.font_size, bold=True, override_name=override)
            self._font_px = px
        return self._font

    def update(self, dt: float):
        target_scale = 0.96 if self.is_pressed and self.enabled else 1.0
        target_hover = 1.0 if self.is_hovered and self.enabled else 0.0
        target_disabled = 0.0 if self.enabled else 1.0
        self.animate_to("scale",           target_scale, response=0.12, damping_fraction=0.55)
        self.animate_to("hover_highlight", target_hover, response=0.25, damping_fraction=1.0)
        self.animate_to("disabled_blend", target_disabled, response=0.22, damping_fraction=1.0)
        super().update(dt)

    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled or not self.visible:
            return False
        pos = event.pos if hasattr(event, "pos") else pygame.mouse.get_pos()
        hovered = self.rect.collidepoint(pos)

        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
            if self.is_pressed and not self.is_hovered:
                self.is_pressed = False
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and hovered:
            self.is_pressed = True
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.is_pressed:
            self.is_pressed = False
            if hovered and self.on_click:
                self.on_click()
            return True
        return False

    def _get_base_surf(self, w: int, h: int) -> pygame.Surface:
        """Return cached base surface (AA background + text). Re-renders only on change."""
        bg  = self.background_color if self.background_color is not None else iOSTheme.accent
        fg  = self.text_color       if self.text_color       is not None else pygame.Color(255, 255, 255)
        rad = self.border_radius if self.border_radius >= 0 else h // 2

        key = (w, h, bg.r, bg.g, bg.b, fg.r, fg.g, fg.b, rad, self.text,
               id(self.icon_fn), iOSTheme.dark)
        if key == self._cache_key and self._cached_surf is not None:
            return self._cached_surf

        # AA rounded rect via 2× render + smoothscale
        surf = make_aa_rect(w, h, bg, rad)
        if self.icon_fn is not None:
            self.icon_fn(surf, w // 2, h // 2, 1.0, fg)
        else:
            font = self._get_font()
            ts   = font.render(self.text, True, fg)
            surf.blit(ts, ts.get_rect(center=(w // 2, h // 2)))

        # Rebuild shadow at same time (same invalidation key)
        shadow_key = (w, h, rad)
        if self._shadow_key != shadow_key:
            self._shadow_surf = make_shadow(w, h, rad)
            self._shadow_key  = shadow_key

        self._cached_surf = surf
        self._cache_key   = key
        return surf

    def render(self, surface: pygame.Surface):
        w, h = self.rect.width, self.rect.height
        if w <= 4 or h <= 4:
            return

        base = self._get_base_surf(w, h)

        # Hover overlay — drawn directly on surface, no extra allocation
        hv = self.hover_highlight
        if hv > 0.02:
            alpha = int(hv * 38)
            col   = pygame.Color(255, 255, 255, alpha) if iOSTheme.dark else pygame.Color(0, 0, 0, alpha)
            rad   = self.border_radius if self.border_radius >= 0 else h // 2
            # Reuse a tiny persistent overlay surface (size-keyed, not per-frame alloc)
            ov_key = (w, h, rad)
            if not hasattr(self, "_ov_surf") or self._ov_size != ov_key:
                self._ov_surf = pygame.Surface((w, h), pygame.SRCALPHA)
                self._ov_size = ov_key
            self._ov_surf.fill((0, 0, 0, 0))
            pygame.draw.rect(self._ov_surf, col, (0, 0, w, h), border_radius=rad)

        sc = self.scale
        if abs(sc - 1.0) < 5e-3:
            surface.blit(base, self.rect.topleft)
            if hv > 0.02:
                surface.blit(self._ov_surf, self.rect.topleft)
        else:
            sw = max(1, int(w * sc))
            sh = max(1, int(h * sc))
            scaled = pygame.transform.smoothscale(base, (sw, sh))
            dest   = scaled.get_rect(center=self.rect.center)
            surface.blit(scaled, dest.topleft)
            if hv > 0.02:
                ov_scaled = pygame.transform.smoothscale(self._ov_surf, (sw, sh))
                surface.blit(ov_scaled, dest.topleft)

        # Disabled wash — spring-faded gray overlay
        db = self.disabled_blend
        if db > 0.02:
            rad = self.border_radius if self.border_radius >= 0 else h // 2
            wash = pygame.Surface((w, h), pygame.SRCALPHA)
            gray = 200 if iOSTheme.dark else 180
            wash_alpha = int(db * 165)
            pygame.draw.rect(
                wash,
                pygame.Color(gray, gray, gray, wash_alpha),
                (0, 0, w, h),
                border_radius=rad,
            )
            dest = self.rect.topleft
            if abs(sc - 1.0) >= 5e-3:
                sw = max(1, int(w * sc))
                sh = max(1, int(h * sc))
                dest = pygame.Rect(0, 0, sw, sh).move(
                    self.rect.centerx - sw // 2, self.rect.centery - sh // 2
                ).topleft
            surface.blit(wash, dest)

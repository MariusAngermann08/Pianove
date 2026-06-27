import os
import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme
from pylay.core import icons as _icons_mod
from typing import Optional, Union, Tuple

Color = Union[pygame.Color, Tuple[int, int, int], None]

_FONT_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    "..", "assets", "fonts", "MaterialIcons-Regular.ttf",
))

# Font cache keyed by pixel size
_FONT_CACHE: dict[int, pygame.font.Font] = {}

# Rendered surface cache keyed by (glyph, size, r, g, b)
_SURF_CACHE: dict[tuple, pygame.Surface] = {}


def _get_font(size: int) -> Optional[pygame.font.Font]:
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    try:
        font = pygame.font.Font(_FONT_PATH, size)
        _FONT_CACHE[size] = font
        return font
    except Exception:
        return None


def _render_glyph(glyph: str, size: int, color: pygame.Color) -> Optional[pygame.Surface]:
    key = (glyph, size, color.r, color.g, color.b)
    if key in _SURF_CACHE:
        return _SURF_CACHE[key]
    font = _get_font(size)
    if font is None:
        return None
    surf = font.render(glyph, True, color)
    _SURF_CACHE[key] = surf
    return surf


class Icon(UIElement):
    def __init__(
        self,
        name: str,
        size: int = 24,
        color: Color = None,
        anchor: str = "top_left",
        x: Union[int, float] = 0,
        y: Union[int, float] = 0,
        **kwargs,
    ):
        super().__init__(anchor=anchor, x=x, y=y, width=size, height=size, **kwargs)
        self.name  = name
        self.size  = size
        self.color = color
        self._surf: Optional[pygame.Surface] = None
        self._cache_key: Optional[tuple] = None

    def _on_theme_changed(self):
        self._surf = None
        self._cache_key = None

    def _on_scale_changed(self):
        self._surf = None
        self._cache_key = None

    def _resolved_color(self) -> pygame.Color:
        c = self.color if self.color is not None else iOSTheme.label
        if isinstance(c, pygame.Color):
            return c
        return pygame.Color(int(c[0]), int(c[1]), int(c[2]))

    def _ensure_surf(self):
        color = self._resolved_color()
        side  = max(1, min(self.rect.width, self.rect.height))
        key   = (self.name, side, color.r, color.g, color.b)
        if self._surf is not None and self._cache_key == key:
            return
        glyph = _icons_mod.ICONS.get(self.name)
        if glyph is None:
            import warnings
            warnings.warn(f"Icon: unknown icon name '{self.name}'", stacklevel=3)
            self._surf = None
            self._cache_key = key
            return
        self._surf      = _render_glyph(glyph, side, color)
        self._cache_key = key

    def render(self, surface: pygame.Surface):
        self._ensure_surf()
        if self._surf is None:
            return
        cx = self.rect.centerx - self._surf.get_width()  // 2
        cy = self.rect.centery - self._surf.get_height() // 2
        surface.blit(self._surf, (cx, cy))

    @staticmethod
    def as_icon_fn(name: str, base_size: int = 16):
        _cache: dict = {}

        def icon_fn(surf: pygame.Surface, cx: int, cy: int,
                    scale: float, color):
            if isinstance(color, pygame.Color):
                c = color
            else:
                c = pygame.Color(int(color[0]), int(color[1]), int(color[2]))
            sz  = max(8, int(base_size * scale))
            key = (sz, c.r, c.g, c.b)
            if key not in _cache:
                glyph = _icons_mod.ICONS.get(name)
                _cache[key] = _render_glyph(glyph, sz, c) if glyph else None
            s = _cache[key]
            if s:
                surf.blit(s, (cx - s.get_width() // 2, cy - s.get_height() // 2))

        return icon_fn

import os
import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme
from typing import Optional, Union, Tuple, Callable

Color = Union[pygame.Color, Tuple[int, int, int], None]

# Raw (unscaled) surface cache keyed by absolute path
_SURF_CACHE: dict = {}


def _to_pygame_color(color: Color) -> pygame.Color:
    if isinstance(color, pygame.Color):
        return color
    if color is None:
        return iOSTheme.label
    return pygame.Color(int(color[0]), int(color[1]), int(color[2]))


def _load_raw(path: str) -> Optional[pygame.Surface]:
    abs_path = os.path.abspath(path)
    if abs_path in _SURF_CACHE:
        return _SURF_CACHE[abs_path]
    if not os.path.isfile(abs_path):
        import warnings
        warnings.warn(f"ImageIcon: file not found: {abs_path}", stacklevel=3)
        _SURF_CACHE[abs_path] = None
        return None
    try:
        surf = pygame.image.load(abs_path).convert_alpha()
        _SURF_CACHE[abs_path] = surf
        return surf
    except Exception as exc:
        import warnings
        warnings.warn(f"ImageIcon: could not load '{abs_path}': {exc}", stacklevel=3)
        _SURF_CACHE[abs_path] = None
        return None


def _make_icon_surf(path: str, size: int, color: pygame.Color,
                    tint: bool) -> pygame.Surface:
    raw = _load_raw(path)
    if raw is None:
        return _make_placeholder(size, color)

    scaled = pygame.transform.smoothscale(raw, (size, size))

    if tint:
        out = scaled.copy()
        # BLEND_RGBA_MULT multiplies each channel; white pixels become `color`
        out.fill((color.r, color.g, color.b, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return out

    return scaled


def _make_placeholder(size: int, color: pygame.Color) -> pygame.Surface:
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    rad  = max(2, size // 6)
    sw   = max(1, size // 10)
    pad  = max(2, size // 8)
    pygame.draw.rect(surf, color, (0, 0, size, size), sw, border_radius=rad)
    pygame.draw.line(surf, color, (pad, pad), (size - pad, size - pad), sw)
    pygame.draw.line(surf, color, (size - pad, pad), (pad, size - pad), sw)
    return surf


class ImageIcon(UIElement):
    def __init__(
        self,
        path: str,
        size: int = 32,
        color: Color = None,
        tint: bool = True,
        anchor: str = "top_left",
        x: Union[int, float] = 0,
        y: Union[int, float] = 0,
        **kwargs,
    ):
        super().__init__(anchor=anchor, x=x, y=y, width=size, height=size, **kwargs)
        self.path  = path
        self.size  = size
        self.color = color
        self.tint  = tint
        self._surf: Optional[pygame.Surface] = None
        self._cache_key = None

    def _on_theme_changed(self):
        self._surf = None
        self._cache_key = None

    def _on_scale_changed(self):
        self._surf = None
        self._cache_key = None

    def _resolved_color(self) -> pygame.Color:
        return _to_pygame_color(self.color if self.color is not None else iOSTheme.label)

    def _ensure_surf(self):
        color = self._resolved_color()
        side  = max(1, min(self.rect.width, self.rect.height))
        key   = (self.path, side, color.r, color.g, color.b, self.tint)
        if self._surf is not None and self._cache_key == key:
            return
        self._surf      = _make_icon_surf(self.path, side, color, self.tint)
        self._cache_key = key

    def render(self, surface: pygame.Surface):
        self._ensure_surf()
        if self._surf is None:
            return
        cx = self.rect.centerx - self._surf.get_width()  // 2
        cy = self.rect.centery - self._surf.get_height() // 2
        surface.blit(self._surf, (cx, cy))

    @staticmethod
    def as_icon_fn(path: str, base_size: int = 16) -> Callable:
        _cache: dict = {}

        def icon_fn(surf: pygame.Surface, cx: int, cy: int,
                    scale: float, color: Color):
            c   = _to_pygame_color(color)
            sz  = max(8, int(base_size * scale))
            key = (sz, c.r, c.g, c.b)
            if key not in _cache:
                _cache[key] = _make_icon_surf(path, sz, c, tint=True)
            s = _cache[key]
            surf.blit(s, (cx - s.get_width() // 2, cy - s.get_height() // 2))

        return icon_fn

import os
import pygame
from pylay.core.scale import scaled_font_size
from typing import Optional

_ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")
_INTER_REG  = os.path.abspath(os.path.join(_ASSETS, "Inter-Regular.ttf"))
_INTER_BOLD = os.path.abspath(os.path.join(_ASSETS, "Inter-Bold.ttf"))

_SYS_FALLBACK = ["SF Pro Text", "Segoe UI", "Helvetica Neue", "Arial"]

_HAS_INTER_REG:  Optional[bool] = None
_HAS_INTER_BOLD: Optional[bool] = None


def _inter_available(bold: bool) -> bool:
    global _HAS_INTER_REG, _HAS_INTER_BOLD
    if bold:
        if _HAS_INTER_BOLD is None:
            _HAS_INTER_BOLD = os.path.exists(_INTER_BOLD)
        return _HAS_INTER_BOLD
    if _HAS_INTER_REG is None:
        _HAS_INTER_REG = os.path.exists(_INTER_REG)
    return _HAS_INTER_REG


def load_font(size_pt: int, bold: bool = False, override_name: Optional[str] = None) -> pygame.font.Font:
    """
    Load a font at the given point size. Resolution order:
    1. Explicit override_name (preserves backward-compat when widget passes font_name)
    2. Bundled Inter TTF (installed in pylay/assets/)
    3. Platform system font fallback list
    4. pygame default font
    """
    if not pygame.font.get_init():
        pygame.font.init()

    px = scaled_font_size(size_pt)

    if override_name:
        try:
            f = pygame.font.SysFont(override_name, px, bold=bold)
            if f:
                return f
        except Exception:
            pass

    if _inter_available(bold):
        path = _INTER_BOLD if bold else _INTER_REG
        try:
            return pygame.font.Font(path, px)
        except Exception:
            pass

    for name in _SYS_FALLBACK:
        try:
            f = pygame.font.SysFont(name, px, bold=bold)
            if f:
                return f
        except Exception:
            continue

    return pygame.font.Font(None, px)

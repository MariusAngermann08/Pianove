"""
Emoji rendering for PyLay.

Renders emoji glyphs via NotoColorEmoji + Pillow as shaped, tintable
pygame Surfaces. Because colour-emoji fonts are not renderable through
pygame.font / pygame.freetype directly, we lean on Pillow's FreeType
backend which supports the embedded bitmap tables in NotoColorEmoji.

The glyph is extracted as a pure alpha mask (shape only) and then
coloured to any RGB value at cache time — so emoji naturally follow the
app's theme and can be used like any other coloured icon.

Public API
----------
emoji_surface(char, size, color) -> pygame.Surface | None
    Returns a size×size SRCALPHA surface tinted to `color`, or None when
    Pillow / the font is unavailable.

is_available() -> bool
    Fast check: True when emoji rendering is ready to use.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import pygame

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------
_ready: Optional[bool]        = None   # None = not yet initialised
_font_obj                     = None   # PIL ImageFont (loaded once)
_cache: dict[tuple, pygame.Surface] = {}

_FONT_PATHS = [
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
    os.path.expanduser("~/.fonts/NotoColorEmoji.ttf"),
    "/usr/local/share/fonts/NotoColorEmoji.ttf",
]

# NotoColorEmoji bitmaps are embedded at this point size → 128 px cell
_NATIVE_PT   = 109
_NATIVE_PX   = 128
_GLYPH_PAD   = 2   # extra pixels kept around the cropped glyph


def _init() -> bool:
    global _ready, _font_obj
    if _ready is not None:
        return _ready

    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401 — kept in scope below
    except ImportError:
        _ready = False
        return False

    for path in _FONT_PATHS:
        if os.path.isfile(path):
            try:
                from PIL import ImageFont as _IFont
                _font_obj = _IFont.truetype(path, _NATIVE_PT)
                _ready = True
                return True
            except Exception:
                continue

    _ready = False
    return False


def is_available() -> bool:
    """Return True when Pillow and NotoColorEmoji are both usable."""
    return _init()


def clear_cache() -> None:
    """Discard all cached surfaces (call after a theme change)."""
    _cache.clear()


def emoji_surface(
    char: str,
    size: int,
    color: pygame.Color | Tuple[int, int, int] = (255, 255, 255),
) -> Optional[pygame.Surface]:
    """
    Render `char` as a pygame SRCALPHA surface of `size` × `size` pixels
    tinted to `color`.

    Returns None silently when Pillow or the font is unavailable — callers
    should fall back to a plain Unicode character or a drawn shape.
    """
    if not _init():
        return None

    r = color.r if isinstance(color, pygame.Color) else int(color[0])
    g = color.g if isinstance(color, pygame.Color) else int(color[1])
    b = color.b if isinstance(color, pygame.Color) else int(color[2])
    key = (char, size, r, g, b)
    if key in _cache:
        return _cache[key]

    try:
        from PIL import Image, ImageDraw

        # 1. Render glyph onto a native-size canvas
        canvas = Image.new("RGBA", (_NATIVE_PX, _NATIVE_PX), (0, 0, 0, 0))
        draw   = ImageDraw.Draw(canvas)
        draw.text((0, 0), char, font=_font_obj, embedded_color=True)

        # 2. Crop to the actual glyph bounding box with a small pad
        bbox = canvas.getbbox()
        if bbox is None:
            return None
        x0 = max(0, bbox[0] - _GLYPH_PAD)
        y0 = max(0, bbox[1] - _GLYPH_PAD)
        x1 = min(_NATIVE_PX, bbox[2] + _GLYPH_PAD)
        y1 = min(_NATIVE_PX, bbox[3] + _GLYPH_PAD)
        cropped = canvas.crop((x0, y0, x1, y1))

        # 3. Scale to requested size (square, preserving aspect inside the box)
        gw, gh   = cropped.size
        scale    = size / max(gw, gh)
        sw, sh   = max(1, int(gw * scale)), max(1, int(gh * scale))
        cropped  = cropped.resize((sw, sh), Image.LANCZOS)

        # 4. Centre on a size×size canvas
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ox  = (size - sw) // 2
        oy  = (size - sh) // 2
        out.paste(cropped, (ox, oy))

        # 5. Replace RGB with desired colour; keep alpha shape
        _, _, _, alpha = out.split()
        tinted = Image.merge("RGBA", (
            Image.new("L", (size, size), r),
            Image.new("L", (size, size), g),
            Image.new("L", (size, size), b),
            alpha,
        ))

        # 6. Convert PIL → pygame Surface
        raw  = tinted.tobytes("raw", "RGBA")
        surf = pygame.image.fromstring(raw, (size, size), "RGBA").convert_alpha()

        _cache[key] = surf
        return surf

    except Exception:
        return None

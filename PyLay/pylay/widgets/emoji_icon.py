import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme
from pylay.core.scale import scaled_px
from pylay.core import emoji as _emoji_mod
from typing import Optional, Union, Tuple

Color = Union[pygame.Color, Tuple[int, int, int], None]


class EmojiIcon(UIElement):
    """
    Displays a single emoji glyph as a tinted, scaled icon.

    The glyph is rendered via NotoColorEmoji + Pillow as a shaped alpha mask
    and coloured to `color` (defaults to the theme label colour). When Pillow
    or the font is unavailable the widget renders nothing — add a fallback
    Label with a plain Unicode character if needed.

    Parameters
    ----------
    char    : the emoji character, e.g. "🎵"
    size    : rendered size in pixels (actual pixels, already scaled by caller)
    color   : tint color; None → iOSTheme.label at render time (theme-aware)
    """

    def __init__(
        self,
        char: str,
        size: int = 32,
        color: Color = None,
        anchor: str = "top_left",
        x: Union[int, float] = 0,
        y: Union[int, float] = 0,
        **kwargs,
    ):
        super().__init__(anchor=anchor, x=x, y=y,
                         width=size, height=size, **kwargs)
        self.char  = char
        self.size  = size
        self.color = color
        self._surf: Optional[pygame.Surface] = None
        self._last_color: Optional[tuple] = None

    # ------------------------------------------------------------------
    def _on_theme_changed(self):
        # Color may reference iOSTheme.label which just changed
        self._surf = None
        self._last_color = None

    # ------------------------------------------------------------------
    def _resolved_color(self) -> pygame.Color:
        return self.color if self.color is not None else iOSTheme.label

    def _color_key(self) -> tuple:
        c = self._resolved_color()
        if isinstance(c, pygame.Color):
            return (c.r, c.g, c.b)
        return (int(c[0]), int(c[1]), int(c[2]))

    def _ensure_surf(self):
        key = self._color_key()
        if self._surf is not None and self._last_color == key:
            return
        self._surf       = _emoji_mod.emoji_surface(self.char, self.size, self._resolved_color())
        self._last_color = key

    # ------------------------------------------------------------------
    def render(self, surface: pygame.Surface):
        self._ensure_surf()
        if self._surf is None:
            return
        # Centre the glyph surface within self.rect
        cx = self.rect.centerx - self._surf.get_width()  // 2
        cy = self.rect.centery - self._surf.get_height() // 2
        surface.blit(self._surf, (cx, cy))

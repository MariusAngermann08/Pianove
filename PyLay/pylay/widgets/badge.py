import pygame
from pylay.layouts.float_layout import FloatLayout
from pylay.widgets.label import Label
from pylay.widgets.emoji_icon import EmojiIcon
from pylay.core.element import UIElement
from typing import Optional, Callable


_WHITE = pygame.Color(255, 255, 255)


class _InlineIcon(UIElement):
    """Renders an icon_fn callable (SideNav-style) as a fixed-size child widget."""

    def __init__(self, icon_fn: Callable, size: int, color: pygame.Color, **kwargs):
        super().__init__(width=size, height=size, **kwargs)
        self._icon_fn = icon_fn
        self._color   = color

    def render(self, surface: pygame.Surface):
        self._icon_fn(surface, self.rect.centerx, self.rect.centery, 1.0, self._color)


class Badge(FloatLayout):
    """
    A pill-shaped label. Three modes:

    - icon_fn + text: Material Icon pinned left, label beside it
    - icon + text:    emoji pinned left, label beside it
    - text only:      label centered inside the pill

    width=None auto-estimates from text length. Pass an explicit int to fix it.
    border_radius defaults to height // 2 for a perfect pill shape.
    """

    def __init__(
        self,
        text: str,
        color: pygame.Color,
        icon: str = "",
        icon_fn: Optional[Callable] = None,
        icon_size: int = 18,
        font_size: int = 13,
        height: int = 34,
        width: Optional[int] = None,
        text_color: Optional[pygame.Color] = None,
        border_radius: Optional[int] = None,
        **kwargs,
    ):
        tc = text_color if text_color is not None else _WHITE

        has_icon = bool(icon_fn or icon)
        if width is None:
            char_w = font_size * 0.62
            base = int(len(text) * char_w) + 24
            if has_icon:
                base += icon_size + 8
            width = max(60, base)

        if border_radius is None:
            border_radius = height // 2

        super().__init__(
            width=width, height=height,
            background_color=color,
            border_radius=border_radius,
            **kwargs,
        )

        if has_icon:
            if icon_fn is not None:
                self.add_child(_InlineIcon(
                    icon_fn, size=icon_size, color=tc,
                    anchor="left", x=10, y=0,
                ))
            else:
                self.add_child(EmojiIcon(
                    icon, size=icon_size, color=tc,
                    anchor="left", x=10, y=0,
                ))
            self.add_child(Label(
                text=text, font_size=font_size, bold=True, color=tc,
                anchor="left", x=icon_size + 14, y=0,
            ))
        else:
            self.add_child(Label(
                text=text, font_size=font_size, bold=True, color=tc,
                anchor="center", x=0, y=0,
            ))

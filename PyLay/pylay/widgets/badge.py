import pygame
from pylay.layouts.float_layout import FloatLayout
from pylay.widgets.label import Label
from pylay.widgets.emoji_icon import EmojiIcon
from typing import Optional, Union


_WHITE = pygame.Color(255, 255, 255)


class Badge(FloatLayout):
    """
    A pill-shaped label. Two modes:

    - icon + text: emoji pinned left, label beside it (e.g. streak counter)
    - text only:   label centered inside the pill (e.g. session count)

    width=None auto-estimates from text length. Pass an explicit int to fix it.
    border_radius defaults to height // 2 for a perfect pill shape.
    """

    def __init__(
        self,
        text: str,
        color: pygame.Color,
        icon: str = "",
        icon_size: int = 18,
        font_size: int = 13,
        height: int = 34,
        width: Optional[int] = None,
        text_color: Optional[pygame.Color] = None,
        border_radius: Optional[int] = None,
        **kwargs,
    ):
        tc = text_color if text_color is not None else _WHITE

        if width is None:
            char_w = font_size * 0.62
            base = int(len(text) * char_w) + 24
            if icon:
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

        if icon:
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

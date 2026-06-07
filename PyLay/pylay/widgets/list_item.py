import pygame
from pylay.layouts.float_layout import FloatLayout
from pylay.core.theme import iOSTheme
from pylay.widgets.label import Label
from pylay.widgets.button import Button
from typing import Optional, Union


class ListItem(FloatLayout):
    """
    Standard list row with leading / title / subtitle / trailing slots.

    leading  — optional widget pinned to the left (icon, emoji label, etc.)
    trailing — optional widget pinned to the right (Switch, Label, Button, …)
    on_click — wraps the whole row in an invisible tap target

    Defaults to iOSTheme.secondary_background + border_radius=10, matching
    the settings/info-row style. Pass background_color=pygame.Color(0,0,0,0)
    for transparent rows (e.g. rows inside a Card).
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        leading=None,
        trailing=None,
        on_click=None,
        height: int = 52,
        title_size: int = 14,
        leading_width: int = 36,
        width: Union[int, float] = 1.0,
        background_color: Optional[pygame.Color] = None,
        border_radius: int = 10,
        **kwargs,
    ):
        bg = background_color if background_color is not None else iOSTheme.secondary_background
        super().__init__(
            width=width, height=height,
            background_color=bg, border_radius=border_radius,
            **kwargs,
        )

        PAD = 16
        has_sub = bool(subtitle)
        text_x = PAD + leading_width if leading is not None else PAD

        if leading is not None:
            leading.anchor = "left"
            leading.x = PAD
            leading.y = 0
            self.add_child(leading)

        self.add_child(Label(
            text=title,
            font_size=title_size,
            color=iOSTheme.label,
            anchor="left",
            x=text_x,
            y=-8 if has_sub else 0,
        ))

        if has_sub:
            self.add_child(Label(
                text=subtitle,
                font_size=11,
                color=iOSTheme.secondary_label,
                anchor="left",
                x=text_x,
                y=10,
            ))

        if trailing is not None:
            trailing.anchor = "right"
            trailing.x = -PAD
            trailing.y = 0
            self.add_child(trailing)

        if on_click is not None:
            self.add_child(Button(
                text="", on_click=on_click,
                width=1.0, height=1.0,
                background_color=pygame.Color(0, 0, 0, 0),
                border_radius=border_radius,
            ))

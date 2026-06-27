import pygame
import pianove.context as ctx
from pylay import FloatLayout, VStack, Label, Button, EmojiIcon, ColorPalette, iOSTheme
from pianove.i18n import t


_CARD_H   = 80
_CARD_GAP = 12
_HEADER_H = 64


def _action_card(icon: str, title: str, subtitle: str, on_click) -> FloatLayout:
    card = FloatLayout(
        width=1.0, height=_CARD_H,
        background_color=iOSTheme.secondary_background,
        border_radius=14,
    )
    card.add_child(EmojiIcon(icon, size=30, color=ColorPalette.BLUE,
                             anchor="left", x=16, y=0))
    card.add_child(Label(text=title, font_size=15, bold=True,
                         color=iOSTheme.label,
                         anchor="left", x=60, y=-10))
    card.add_child(Label(text=subtitle, font_size=12,
                         color=iOSTheme.secondary_label,
                         anchor="left", x=60, y=12))
    card.add_child(Button(
        text=t("creator_open"),
        on_click=on_click,
        anchor="right", x=12, y=0,
        width=80, height=34, font_size=13,
        background_color=ColorPalette.BLUE,
        text_color=pygame.Color(255, 255, 255),
        border_radius=10,
    ))
    return card


def build():
    win_h  = ctx.ui.height if ctx.ui else 768
    list_h = max(200, win_h - _HEADER_H)

    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)

    header = FloatLayout(
        anchor="top_left", x=0, y=0,
        width=1.0, height=_HEADER_H,
        background_color=iOSTheme.background,
    )
    header.add_child(Label(
        text=t("creator_title"),
        font_size=20, bold=True,
        color=iOSTheme.label,
        anchor="left", x=20, y=0,
    ))
    root.add_child(header)

    scroll = VStack(
        spacing=_CARD_GAP, padding=16,
        anchor="top_left", x=0, y=_HEADER_H,
        width=1.0, height=list_h,
        background_color=iOSTheme.background,
    )

    scroll.add_child(Label(
        text=t("creator_lessons_section"),
        font_size=13, bold=True,
        color=iOSTheme.secondary_label,
        width=1.0, height=22,
    ))
    scroll.add_child(_action_card(
        "📝", t("creator_new_lesson"), t("creator_new_lesson_desc"),
        on_click=lambda: None,
    ))
    scroll.add_child(_action_card(
        "📂", t("creator_import_lesson"), t("creator_import_lesson_desc"),
        on_click=lambda: None,
    ))

    scroll.add_child(Label(
        text=t("creator_courses_section"),
        font_size=13, bold=True,
        color=iOSTheme.secondary_label,
        width=1.0, height=22,
    ))
    scroll.add_child(_action_card(
        "🎓", t("creator_new_course"), t("creator_new_course_desc"),
        on_click=lambda: None,
    ))

    scroll.add_child(Label(
        text=t("creator_publish_section"),
        font_size=13, bold=True,
        color=iOSTheme.secondary_label,
        width=1.0, height=22,
    ))
    scroll.add_child(_action_card(
        "📦", t("creator_export_pkg"), t("creator_export_pkg_desc"),
        on_click=lambda: None,
    ))

    root.add_child(scroll)
    return root

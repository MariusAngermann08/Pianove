import pygame
from pylay import Label, Button, FloatLayout, ColorPalette, iOSTheme
from pianove.i18n import t
from pianove.state import (
    name_state, experience_state, midi_device_state, language_state,
    summary_text, refresh_summary, storage,
)
from pianove.ui_utils import page_shell, ui_dims, set_continue_enabled
import pianove.context as ctx


def _save():
    storage.set("onboarding_complete", True)
    storage.set("name", name_state.value.strip())
    storage.set("experience", experience_state.value)
    storage.set("language", language_state.value)


def _go_home():
    _save()
    ctx.router.navigate("home", "right")


def build():
    U = ui_dims()
    refresh_summary()
    root, card, content, _ = page_shell(
        t("ready_title"),
        t("ready_subtitle"),
        page_id="ready",
        show_back=True,
        show_next=False,
    )

    content.add_child(
        Label(
            text=summary_text,
            font_size=U["summary_size"],
            color=iOSTheme.label,
            wrap_width=int(U["subtitle_wrap"] * 0.85),
            width=0.95,
            height=0.72,
        )
    )

    btn_row = FloatLayout(width=0.98, height=U["nav_height_frac"])
    btn_row.add_child(Button(
        text=t("ready_go_home"),
        on_click=_go_home,
        anchor="center",
        x=0,
        y=0,
        width=0.7,
        height=U["btn_h_frac"],
        font_size=U["btn_font"],
        background_color=ColorPalette.BLUE,
        text_color=pygame.Color(255, 255, 255),
    ))
    content.add_child(btn_row)

    return root

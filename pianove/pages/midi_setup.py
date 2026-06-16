import pygame
import pianove.context as ctx
from pylay import FloatLayout, VStack, Label, Button, PygameCanvas, ColorPalette, iOSTheme
from pianove.i18n import t
from pianove.state import midi_device_state, midi_panel
from pianove.ui_utils import ui_dims


def _go_back():
    ctx.router.navigate("home", "left")


def build():
    U    = ui_dims()
    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)

    # ── Top bar ───────────────────────────────────────────────────────────
    top_h   = 56
    top_bar = FloatLayout(
        anchor="top_left", x=0, y=0, width=1.0, height=top_h,
        background_color=iOSTheme.secondary_background,
    )
    top_bar.add_child(Button(
        text="< " + t("back"),
        on_click=_go_back,
        anchor="left", x=12, y=0,
        width=100, height=36,
        font_size=14,
        background_color=pygame.Color(0, 0, 0, 0),
        text_color=ColorPalette.BLUE,
        border_radius=8,
    ))
    top_bar.add_child(Label(
        text=t("settings_midi_setup"),
        font_size=16, bold=True,
        color=iOSTheme.label,
        anchor="center", x=0, y=0,
    ))
    root.add_child(top_bar)

    # ── Content ───────────────────────────────────────────────────────────
    content_y = top_h + 16
    content   = VStack(
        spacing=16, padding=20,
        anchor="top_left", x=0, y=content_y,
        width=1.0, height=max(100, ctx.ui.height - content_y),
        background_color=iOSTheme.background,
    )

    # Status label — reactive
    status_row = FloatLayout(
        width=1.0, height=44,
        background_color=iOSTheme.secondary_background,
        border_radius=10,
    )
    status_row.add_child(Label(
        text=t("midi_title"), font_size=14, bold=True,
        color=iOSTheme.label,
        anchor="left", x=16, y=0,
    ))
    status_row.add_child(Label(
        text=midi_device_state,          # live reactive binding
        font_size=13, color=iOSTheme.secondary_label,
        anchor="right", x=-16, y=0,
    ))
    content.add_child(status_row)

    # MIDI keyboard canvas
    canvas_h = max(100, ctx.ui.height - content_y - 44 - 60 - 80)
    content.add_child(PygameCanvas(
        target=midi_panel,
        width=1.0,
        height=canvas_h,
        draw_border=True,
    ))

    # Hint text
    content.add_child(Label(
        text=t("midi_no_keyboard"),
        font_size=13,
        color=iOSTheme.secondary_label,
        width=1.0,
    ))

    # Reconfigure keyboard range
    content.add_child(Button(
        text=t("midi_cal_reconfigure"),
        on_click=midi_panel.reset_calibration,
        width=1.0, height=40,
        font_size=13,
        background_color=iOSTheme.secondary_background,
        text_color=ColorPalette.BLUE,
        border_radius=8,
    ))

    # Done button
    content.add_child(Button(
        text=t("done"),
        on_click=_go_back,
        width=1.0, height=44,
        font_size=U["btn_font"],
        background_color=ColorPalette.BLUE,
        text_color=pygame.Color(255, 255, 255),
        border_radius=10,
    ))

    root.add_child(content)
    return root

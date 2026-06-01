import pygame
import pianove.context as ctx
from pylay import FloatLayout, VStack, Label, Button, Switch, OptionSelector, ColorPalette, iOSTheme
from pianove.i18n import t, language_state, available_languages
from pianove.state import name_state, midi_device_state, dark_mode_state, sound_enabled_state, creator_mode_state, storage
from pianove.ui_utils import ui_dims


def _section_header(text: str) -> Label:
    return Label(text=text, font_size=13, bold=True,
                 color=iOSTheme.secondary_label, width=1.0)


def _info_row(label: str, value) -> FloatLayout:
    """Static or reactive info row. Pass a State for live value."""
    row = FloatLayout(
        width=1.0, height=52,
        background_color=iOSTheme.secondary_background,
        border_radius=10,
    )
    row.add_child(Label(text=label, font_size=14, color=iOSTheme.label,
                        anchor="left", x=16, y=0))
    row.add_child(Label(text=value, font_size=13, color=iOSTheme.secondary_label,
                        anchor="right", x=-16, y=0))
    return row


def _tappable_row(label: str, detail: str, on_click) -> FloatLayout:
    """Row that acts as a tappable button — navigates somewhere."""
    row = FloatLayout(
        width=1.0, height=52,
        background_color=iOSTheme.secondary_background,
        border_radius=10,
    )
    row.add_child(Label(text=label, font_size=14, color=iOSTheme.label,
                        anchor="left", x=16, y=0))
    row.add_child(Label(text=detail + "  >", font_size=13,
                        color=iOSTheme.secondary_label,
                        anchor="right", x=-16, y=0))
    # Invisible full-area button to catch clicks
    row.add_child(Button(
        text="", on_click=on_click,
        width=1.0, height=1.0,
        background_color=pygame.Color(0, 0, 0, 0),
        border_radius=10,
    ))
    return row


def _reset():
    storage.remove("onboarding_complete")
    storage.remove("name")
    storage.remove("experience")
    storage.remove("language")
    storage.remove("dark_mode")
    name_state.value = ""
    language_state.value = "en"
    dark_mode_state.value = True   # triggers _on_dark_mode_change → theme update
    ctx.router.navigate("language", "left")


def build():
    U      = ui_dims()
    scroll = VStack(spacing=10, padding=16, width=1.0, height=1.0,
                    background_color=iOSTheme.background)

    # ── Profile ────────────────────────────────────────────────────────────
    scroll.add_child(_section_header(t("settings_profile")))
    scroll.add_child(_info_row(t("settings_name_label"),
                               name_state.value.strip() or "—"))

    # ── MIDI ───────────────────────────────────────────────────────────────
    scroll.add_child(_section_header(t("settings_midi")))
    scroll.add_child(_info_row(t("settings_midi"), midi_device_state))
    scroll.add_child(_tappable_row(
        t("settings_midi_setup"), "",
        on_click=lambda: ctx.router.navigate("midi_setup", "right"),
    ))

    sound_row = FloatLayout(
        width=1.0, height=52,
        background_color=iOSTheme.secondary_background,
        border_radius=10,
    )
    sound_row.add_child(Label(
        text=t("settings_midi_sound"), font_size=14,
        color=iOSTheme.label, anchor="left", x=16, y=0,
    ))
    sound_row.add_child(Label(
        text=t("settings_midi_sound_desc"), font_size=11,
        color=iOSTheme.secondary_label, anchor="left", x=16, y=14,
    ))
    sound_row.add_child(Switch(
        value=sound_enabled_state,
        anchor="right", x=-16, y=0,
        enabled=True,
    ))
    scroll.add_child(sound_row)

    # ── Language ───────────────────────────────────────────────────────────
    scroll.add_child(_section_header(t("settings_language")))
    langs = available_languages()
    lang_options = [(t(f"lang_{l}") if l in ("en", "de") else l.upper(), l)
                    for l in langs]
    scroll.add_child(OptionSelector(
        options=lang_options,
        value=language_state,
        width=1.0,
        row_height=U["option_row_h"],
        spacing=4,
        font_size=U["option_font"],
    ))

    # ── Appearance ─────────────────────────────────────────────────────────
    scroll.add_child(_section_header(t("settings_appearance")))
    dark_row = FloatLayout(
        width=1.0, height=52,
        background_color=iOSTheme.secondary_background,
        border_radius=10,
    )
    dark_row.add_child(Label(text=t("settings_dark_mode"), font_size=14,
                             color=iOSTheme.label, anchor="left", x=16, y=0))
    dark_row.add_child(Switch(
        value=dark_mode_state,
        anchor="right", x=-16, y=0,
        enabled=True,
    ))
    scroll.add_child(dark_row)

    # ── Content Creator ────────────────────────────────────────────────────
    scroll.add_child(_section_header(t("settings_creator_section")))
    creator_row = FloatLayout(
        width=1.0, height=52,
        background_color=iOSTheme.secondary_background,
        border_radius=10,
    )
    creator_row.add_child(Label(text=t("settings_creator_mode"), font_size=14,
                               color=iOSTheme.label, anchor="left", x=16, y=-6))
    creator_row.add_child(Label(text=t("settings_creator_mode_desc"), font_size=11,
                               color=iOSTheme.secondary_label, anchor="left", x=16, y=14))
    creator_row.add_child(Switch(
        value=creator_mode_state,
        anchor="right", x=-16, y=0,
        enabled=True,
    ))
    scroll.add_child(creator_row)

    # ── Reset ──────────────────────────────────────────────────────────────
    scroll.add_child(_section_header(t("settings_reset_desc")))
    scroll.add_child(Button(
        text=t("settings_reset"),
        on_click=_reset,
        width=1.0, height=44,
        font_size=U["btn_font"],
        background_color=pygame.Color(255, 59, 48),
        text_color=pygame.Color(255, 255, 255),
        border_radius=10,
    ))

    return scroll

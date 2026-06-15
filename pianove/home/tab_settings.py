import pygame
import pianove.context as ctx
from pylay import FloatLayout, VStack, Label, Button, Switch, OptionSelector, ListItem, Avatar, ColorPalette, iOSTheme, Slider
from pianove.i18n import t, language_state, available_languages
from pianove.state import name_state, midi_device_state, dark_mode_state, sound_enabled_state, sound_volume_state, creator_mode_state, storage
from pianove.ui_utils import ui_dims
from pianove.components import section_subheader as _section_header, RED


def _reset():
    storage.remove("onboarding_complete")
    storage.remove("name")
    storage.remove("experience")
    storage.remove("language")
    storage.remove("dark_mode")
    name_state.value = ""
    language_state.value = "en"
    dark_mode_state.value = True
    ctx.router.navigate("language", "left")


def build():
    U      = ui_dims()
    scroll = VStack(spacing=10, padding=16, width=1.0, height=1.0,
                    background_color=iOSTheme.background)

    # ── Profile ────────────────────────────────────────────────────────────
    _name = name_state.value.strip()
    _initials = "".join(w[0] for w in _name.split()[:2]) if _name else "?"
    scroll.add_child(_section_header(t("settings_profile")))
    scroll.add_child(ListItem(
        title=t("settings_name_label"),
        leading=Avatar(initials=_initials, size=32, color=ColorPalette.BLUE),
        trailing=Label(text=_name or "—", font_size=13,
                       color=iOSTheme.secondary_label),
        leading_width=44,
    ))

    # ── MIDI ───────────────────────────────────────────────────────────────
    scroll.add_child(_section_header(t("settings_midi")))
    scroll.add_child(ListItem(
        title=t("settings_midi"),
        trailing=Label(text=midi_device_state, font_size=13,
                       color=iOSTheme.secondary_label),
    ))
    scroll.add_child(ListItem(
        title=t("settings_midi_setup"),
        trailing=Label(text="  >", font_size=13, color=iOSTheme.secondary_label),
        on_click=lambda: ctx.router.navigate("midi_setup", "right"),
    ))
    scroll.add_child(ListItem(
        title=t("settings_midi_sound"),
        subtitle=t("settings_midi_sound_desc"),
        trailing=Switch(value=sound_enabled_state, enabled=True),
    ))
    scroll.add_child(ListItem(
        title=t("settings_midi_volume"),
        trailing=Slider(
            value=sound_volume_state,
            min_val=0.0, max_val=1.0,
            width=160, height=28,
            active_color=ColorPalette.BLUE,
        ),
    ))

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
    scroll.add_child(ListItem(
        title=t("settings_dark_mode"),
        trailing=Switch(value=dark_mode_state, enabled=True),
    ))

    # ── Content Creator ────────────────────────────────────────────────────
    scroll.add_child(_section_header(t("settings_creator_section")))
    scroll.add_child(ListItem(
        title=t("settings_creator_mode"),
        subtitle=t("settings_creator_mode_desc"),
        trailing=Switch(value=creator_mode_state, enabled=True),
    ))

    # ── Reset ──────────────────────────────────────────────────────────────
    scroll.add_child(_section_header(t("settings_reset_desc")))
    scroll.add_child(Button(
        text=t("settings_reset"),
        on_click=_reset,
        width=1.0, height=44,
        font_size=U["btn_font"],
        background_color=RED,
        text_color=pygame.Color(255, 255, 255),
        border_radius=10,
    ))

    return scroll

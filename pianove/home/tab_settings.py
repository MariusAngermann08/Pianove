import pygame
import pianove.context as ctx
from pylay import (FloatLayout, VStack, Label, Button, Switch, ListItem, Avatar, ColorPalette,
                   iOSTheme, Slider, SegmentedControl, Stepper, State)
from pylay.widgets.icon import Icon
from pianove.i18n import t, language_state, available_languages
from pianove.state import (name_state, midi_device_state, dark_mode_state, sound_enabled_state,
                           sound_volume_state, creator_mode_state, hand_tone_state,
                           mic_input_state, mic_sensitivity_state, storage)
from pianove.components.tone_picker import TonePicker
from pianove.ui_utils import ui_dims
from pianove.components import section_subheader as _section_header, RED

_ACCENT = ColorPalette.BLUE        # one colour for every switch and slider in the app


def _reset():
    storage.remove("onboarding_complete")
    storage.remove("name")
    storage.remove("experience")
    storage.remove("language")
    storage.remove("dark_mode")
    name_state.value = ""
    language_state.value = "en"
    dark_mode_state.value = True
    ctx.home_page = None
    ctx.router.navigate("language", "left")


def _reload():
    if ctx.inner_router:
        ctx.inner_router.reload_current_page()


def _switch(state_or_value, on_change=None) -> Switch:
    return Switch(value=state_or_value, on_change=on_change, enabled=True, active_color=_ACCENT)


def _value_label(state: State, fmt) -> Label:
    """A label that shows a slider's value as it moves."""
    shown = State(fmt(state.value))
    state.bind(lambda v: setattr(shown, "value", fmt(v)))
    return Label(text=shown, font_size=13, color=iOSTheme.secondary_label)


def _slider_row(state: State, fmt) -> FloatLayout:
    row = FloatLayout(width=230, height=28)
    row.add_child(Slider(value=state, min_val=0.0, max_val=1.0, width=170, height=28,
                         active_color=_ACCENT, anchor="left", x=0, y=0))
    lbl = _value_label(state, fmt)
    lbl.anchor, lbl.x_spec, lbl.y_spec = "right", 0, 0
    row.add_child(lbl)
    return row


def build():
    U      = ui_dims()
    scroll = VStack(spacing=8, padding=16, width=1.0, height=1.0,
                    background_color=iOSTheme.background)

    # ── profile and goal ───────────────────────────────────────────────────────
    _name = name_state.value.strip()
    _initials = "".join(w[0] for w in _name.split()[:2]).upper() if _name else "?"
    scroll.add_child(_section_header(t("settings_profile")))
    scroll.add_child(ListItem(
        title=t("settings_name_label"),
        leading=Avatar(initials=_initials, size=32, color=_ACCENT),
        trailing=Label(text=_name or "—", font_size=14, color=iOSTheme.secondary_label),
        leading_width=44,
    ))
    from pianove.progress import GOAL_OPTIONS, daily_goal_minutes, set_daily_goal_minutes
    goal = daily_goal_minutes()
    scroll.add_child(ListItem(
        title=t("settings_goal"),
        subtitle=t("settings_goal_desc"),
        trailing=Stepper(options=GOAL_OPTIONS,
                         value=goal if goal in GOAL_OPTIONS else 10,
                         fmt_fn=lambda v: t("settings_goal_value", n=v),
                         on_change=set_daily_goal_minutes, width=170, height=32),
        height=60,
    ))

    # ── keyboard, microphone and sound ─────────────────────────────────────────
    scroll.add_child(_section_header(t("settings_playing")))
    device = FloatLayout(width=210, height=28)
    device.add_child(Label(text=midi_device_state, font_size=14, color=iOSTheme.secondary_label,
                           anchor="right", x=-26, y=0))
    device.add_child(Icon("chevron_right", size=20, color=iOSTheme.secondary_label,
                          anchor="right", x=0, y=0))
    scroll.add_child(ListItem(
        title=t("settings_midi_setup"),
        subtitle=t("settings_midi_setup_desc"),
        trailing=device,
        on_click=lambda: ctx.router.navigate("midi_setup", "right"),
        height=60,
    ))
    scroll.add_child(ListItem(
        title=t("settings_keys"),
        subtitle=t("settings_keys_desc"),
        height=60,
    ))
    from pianove import sound_engine_fs
    no_sound = sound_engine_fs.unavailable_reason
    scroll.add_child(ListItem(
        title=t("settings_midi_sound"),
        subtitle=(t("settings_no_sound", reason=no_sound) if no_sound
                  else t("settings_midi_sound_desc")),
        trailing=_switch(sound_enabled_state),
        height=60,
    ))
    scroll.add_child(ListItem(
        title=t("settings_midi_volume"),
        trailing=_slider_row(sound_volume_state, lambda v: f"{int(round(float(v) * 100))} %"),
    ))

    def _mic(on):
        mic_input_state.value = bool(on)
        _reload()                         # the sensitivity only shows with the microphone on
    scroll.add_child(ListItem(
        title=t("settings_mic_input"),
        subtitle=t("settings_mic_input_desc"),
        trailing=_switch(bool(mic_input_state.value), _mic),
        height=60,
    ))
    if mic_input_state.value:
        scroll.add_child(ListItem(
            title=t("settings_mic_sensitivity"),
            trailing=_slider_row(mic_sensitivity_state, lambda v: f"{int(round(float(v) * 100))} %"),
        ))

    # ── lessons ────────────────────────────────────────────────────────────────
    scroll.add_child(_section_header(t("settings_lessons")))

    def _hands(on):
        storage.set("show_hands", bool(on))
        ctx.lesson_hands_vis = bool(on)
    scroll.add_child(ListItem(
        title=t("settings_show_hands"),
        subtitle=t("settings_show_hands_desc"),
        trailing=_switch(bool(storage.get("show_hands", True)), _hands),
        height=60,
    ))
    scroll.add_child(ListItem(
        title=t("settings_hand_tone"),
        subtitle=t("settings_hand_tone_desc"),
        trailing=TonePicker(hand_tone_state),
        height=60,
    ))

    # ── language and appearance ────────────────────────────────────────────────
    scroll.add_child(_section_header(t("settings_language")))
    langs = available_languages()
    _lang_keys = {"en": "lang_english", "de": "lang_german"}
    names = [t(_lang_keys[l]) if l in _lang_keys else l.upper() for l in langs]
    cur = langs.index(language_state.value) if language_state.value in langs else 0
    scroll.add_child(SegmentedControl(
        segments=names,
        selected_index=State(cur),
        on_change=lambda i: setattr(language_state, "value", langs[i]),
        width=1.0, height=40,
    ))

    scroll.add_child(_section_header(t("settings_appearance")))
    scroll.add_child(ListItem(
        title=t("settings_dark_mode"),
        trailing=_switch(dark_mode_state),
    ))

    # ── making lessons ─────────────────────────────────────────────────────────
    scroll.add_child(_section_header(t("settings_creator_section")))
    scroll.add_child(ListItem(
        title=t("settings_creator_mode"),
        subtitle=t("settings_creator_mode_desc"),
        trailing=_switch(creator_mode_state),
        height=60,
    ))

    scroll.add_child(_section_header(t("settings_reset_desc")))
    scroll.add_child(Button(
        text=t("settings_reset"),
        on_click=_reset,
        width=1.0, height=44,
        font_size=U["btn_font"],
        background_color=iOSTheme.fill,
        text_color=RED,
        border_radius=10,
    ))

    return scroll

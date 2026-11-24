"""Your instrument: the one place that says how you play Pianove and lets you change it.

A MIDI keyboard (shown live, its range, and whether Pianove should make the sound), an
acoustic piano through the microphone, or no instrument (the computer keys and the keys
on screen)."""
import pygame
import pianove.context as ctx
from pylay import (FloatLayout, VStack, Label, Button, PygameCanvas, ColorPalette, iOSTheme,
                   SegmentedControl, Slider, State)
from pianove.i18n import t
from pianove.state import (midi_device_state, midi_panel, mic_input_state, mic_sensitivity_state,
                           sound_enabled_state, storage)
from pianove.ui_utils import ui_dims

_MODES = ["midi", "mic", "none"]


def instrument() -> str:
    """How you play: "midi", "mic" (an acoustic piano) or "none" (computer keys, mouse)."""
    if mic_input_state.value:
        return "mic"
    return storage.get("instrument", "midi") if storage.get("instrument") in _MODES else "midi"


def instrument_summary() -> str:
    """One line for Settings: what you play on right now."""
    mode = instrument()
    if mode == "mic":
        return t("instr_mic_short")
    if mode == "none" and not midi_panel.connected:
        return t("instr_none_short")
    return str(midi_device_state.value)


def _go_back():
    ctx.router.navigate("home", "left")


def _set_mode(i: int):
    mode = _MODES[i]
    storage.set("instrument", mode)
    if (mode == "mic") != bool(mic_input_state.value):
        mic_input_state.value = mode == "mic"        # switches the input and reloads the page
    else:
        ctx.router.refresh()


def _card(height: int) -> FloatLayout:
    return FloatLayout(width=1.0, height=height, background_color=iOSTheme.secondary_background,
                       border_radius=12)


def build():
    U    = ui_dims()
    root = FloatLayout(width=1.0, height=1.0, background_color=iOSTheme.background)
    mode = instrument()

    top_h   = 56
    top_bar = FloatLayout(anchor="top_left", x=0, y=0, width=1.0, height=top_h,
                          background_color=iOSTheme.secondary_background)
    top_bar.add_child(Button(text=t("back"), on_click=_go_back, anchor="left", x=12, y=0,
                             width=72, height=34, font_size=14, background_color=iOSTheme.fill,
                             text_color=iOSTheme.label, border_radius=8))
    top_bar.add_child(Label(text=t("instr_title"), font_size=16, bold=True, color=iOSTheme.label,
                            anchor="center", x=0, y=0))
    root.add_child(top_bar)

    content_y = top_h + 12
    content = VStack(spacing=14, padding=20, anchor="top_left", x=0, y=content_y,
                     width=1.0, height=max(100, ctx.ui.height - content_y),
                     background_color=iOSTheme.background)

    content.add_child(SegmentedControl(
        segments=[t("instr_midi"), t("instr_mic"), t("instr_none")],
        selected_index=State(_MODES.index(mode)), on_change=_set_mode,
        width=1.0, height=40))

    canvas_h = max(110, min(220, ctx.ui.height - content_y - 420))
    if mode == "midi":
        status = _card(44)
        status.add_child(Label(text=t("instr_connected_label"), font_size=14, bold=True,
                               color=iOSTheme.label, anchor="left", x=16, y=0))
        status.add_child(Label(text=midi_device_state, font_size=13, color=iOSTheme.secondary_label,
                               anchor="right", x=-16, y=0))
        content.add_child(status)
        content.add_child(PygameCanvas(target=midi_panel, width=1.0, height=canvas_h, draw_border=True))
        content.add_child(Button(text=t("midi_cal_reconfigure"), on_click=midi_panel.reset_calibration,
                                 width=1.0, height=38, font_size=13, background_color=iOSTheme.fill,
                                 text_color=iOSTheme.label, border_radius=10))
        content.add_child(sound_question())
    elif mode == "mic":
        note = _card(64)
        note.add_child(Label(text=t("instr_mic_how"), font_size=14, color=iOSTheme.label,
                             anchor="left", x=16, y=-10))
        note.add_child(Label(text=t("instr_mic_beta"), font_size=12, color=iOSTheme.secondary_label,
                             anchor="left", x=16, y=12))
        content.add_child(note)
        content.add_child(PygameCanvas(target=midi_panel, width=1.0, height=canvas_h, draw_border=True))
        fine = _card(52)
        fine.add_child(Label(text=t("instr_mic_fine"), font_size=13, color=iOSTheme.secondary_label,
                             anchor="left", x=16, y=0))
        fine.add_child(Slider(value=mic_sensitivity_state, min_val=0.0, max_val=1.0, width=220,
                              height=28, active_color=ColorPalette.BLUE, anchor="right", x=-16, y=0))
        content.add_child(fine)
    else:
        keys = _card(118)
        keys.add_child(Label(text=t("instr_none_how"), font_size=14, bold=True, color=iOSTheme.label,
                             anchor="top_left", x=16, y=14))
        for k, line in enumerate((t("instr_none_white"), t("instr_none_black"), t("instr_none_octave"))):
            keys.add_child(Label(text=line, font_size=13, color=iOSTheme.secondary_label,
                                 anchor="top_left", x=16, y=42 + k * 22))
        content.add_child(keys)
        content.add_child(PygameCanvas(target=midi_panel, width=1.0, height=canvas_h, draw_border=True))
        content.add_child(Label(text=t("instr_none_later"), font_size=13,
                                color=iOSTheme.secondary_label, width=1.0))

    content.add_child(Button(text=t("done"), on_click=_go_back, width=1.0, height=44,
                             font_size=U["btn_font"], background_color=ColorPalette.BLUE,
                             text_color=pygame.Color(255, 255, 255), border_radius=10))
    root.add_child(content)
    return root


def needs_sound_question() -> bool:
    """A keyboard is connected and nobody has said yet whether it makes a sound itself."""
    return (instrument() == "midi" and bool(getattr(midi_panel, "connected", False))
            and not storage.get("sound_asked"))


def sound_question(on_answer=None) -> FloatLayout:
    """Instead of a switch called "MIDI Sound Output": ask what happens when you play.
    Shown on this page, and once on Home when a keyboard is first connected."""
    card = _card(106)
    card.add_child(Label(text=t("instr_hear_q"), font_size=14, bold=True, color=iOSTheme.label,
                         anchor="top_left", x=16, y=14))
    on = bool(sound_enabled_state.value)
    sub = (t("instr_hear_why") if not storage.get("sound_asked")
           else t("instr_hear_now_pianove") if on else t("instr_hear_now_keyboard"))
    card.add_child(Label(text=sub,
                         font_size=12, color=iOSTheme.secondary_label, anchor="top_left", x=16, y=38))

    def _answer(own_speakers: bool):
        storage.set("sound_asked", True)
        sound_enabled_state.value = not own_speakers
        (on_answer or ctx.router.refresh)()
    for k, (label, val) in enumerate(((t("instr_hear_yes"), True), (t("instr_hear_no"), False))):
        chosen = (not on) == val and storage.get("sound_asked")
        card.add_child(Button(text=label, on_click=lambda v=val: _answer(v),
                              anchor="bottom_left" if k == 0 else "bottom_right",
                              x=16 if k == 0 else -16, y=-12, width=0.46, height=32,
                              font_size=13,
                              background_color=ColorPalette.BLUE if chosen else iOSTheme.fill,
                              text_color=pygame.Color(255, 255, 255) if chosen else iOSTheme.label,
                              border_radius=8))
    return card

from pylay import PygameCanvas, Button, Label, ColorPalette, iOSTheme
from pianove.i18n import t
from pianove.state import midi_key_played, midi_panel, midi_skip_state, mic_input_state
from pianove.ui_utils import page_shell, set_continue_enabled, ui_dims

_continue_btn = None


def _sync(_=None):
    if _continue_btn:
        set_continue_enabled(_continue_btn, midi_key_played.value or midi_skip_state.value)


midi_key_played.bind(_sync)
midi_skip_state.bind(_sync)


def build():
    global _continue_btn
    U = ui_dims()
    root, card, content, next_btn = page_shell(
        t("midi_title"),
        t("midi_subtitle"),
        page_id="midi",
        show_back=True,
        continue_enabled=midi_key_played.value or midi_skip_state.value,
    )

    content.add_child(
        PygameCanvas(
            target=midi_panel,
            width=0.98,
            height=0.72 if mic_input_state.value else 0.46,  # room for the microphone button
            draw_border=True,
        )
    )

    # Subtle skip section — visually separated from the keyboard
    content.add_child(Label(
        text=t("midi_no_keyboard"),
        font_size=U["option_font"] - 1,
        color=iOSTheme.secondary_label,
        width=0.98,
    ))
    content.add_child(Button(
        text=t("midi_skip"),
        on_click=lambda: setattr(midi_skip_state, "value", True),
        width=0.98,
        height=U["field_h_frac"] * 0.75,
        font_size=U["option_font"] - 1,
        background_color=iOSTheme.secondary_background,
        text_color=ColorPalette.BLUE,
        border_radius=8,
    ))
    if not mic_input_state.value:
        # an acoustic piano: hear it instead (the keyboard above starts listening)
        content.add_child(Button(
            text=t("midi_use_mic"),
            on_click=lambda: setattr(mic_input_state, "value", True),
            width=0.98,
            height=U["field_h_frac"] * 0.75,
            font_size=U["option_font"] - 1,
            background_color=iOSTheme.secondary_background,
            text_color=ColorPalette.BLUE,
            border_radius=8,
        ))

    _continue_btn = next_btn
    _sync()
    return root

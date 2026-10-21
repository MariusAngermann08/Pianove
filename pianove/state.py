from locales import TEXT
from pylay import State, Storage
from pylay.core.theme import iOSTheme
from pianove.i18n import language_state, t
from pianove.midi.panel import MidiPanel
from pianove.hands import DEFAULT_SKIN

storage = Storage("pianove")

name_state           = State(storage.get("name", ""))
experience_state     = State(storage.get("experience", "none"))
dark_mode_state      = State(bool(storage.get("dark_mode", True)))
sound_enabled_state  = State(bool(storage.get("midi_sound", False)))
sound_volume_state   = State(float(storage.get("midi_volume", 1.0)))
creator_mode_state   = State(bool(storage.get("creator_mode", False)))
hand_tone_state      = State(storage.get("hand_tone", DEFAULT_SKIN))
beta_features_state  = State(bool(storage.get("beta_features", False)))
mic_input_state      = State(bool(storage.get("mic_input", False)))
mic_sensitivity_state = State(float(storage.get("mic_sensitivity", 0.5)))   # slider 0..1
midi_device_state    = State("")
midi_key_played      = State(False)
midi_skip_state      = State(False)
welcome_greeting     = State("")
summary_text         = State("")

midi_device_state.value = t("midi_not_connected")


def _on_dark_mode_change(val):
    import pianove.context as ctx
    iOSTheme.dark = bool(val)
    iOSTheme.update_theme()
    storage.set("dark_mode", bool(val))
    if ctx.router:
        ctx.router.reload_current_page(delay=0.20)


def _on_sound_enabled_change(val):
    from pianove.sound_engine_fs import set_enabled
    set_enabled(bool(val))
    storage.set("midi_sound", bool(val))


def _on_sound_volume_change(val):
    from pianove.sound_engine_fs import set_volume
    set_volume(float(val))
    storage.set("midi_volume", float(val))


def _on_creator_mode_change(val):
    storage.set("creator_mode", bool(val))
    import pianove.context as ctx
    if ctx.router:
        ctx.router.reload_current_page(delay=0.10)


dark_mode_state.bind(_on_dark_mode_change)
sound_enabled_state.bind(_on_sound_enabled_change)
sound_volume_state.bind(_on_sound_volume_change)
creator_mode_state.bind(_on_creator_mode_change)
hand_tone_state.bind(lambda val: storage.set("hand_tone", val))


def _on_beta_features_change(val):
    storage.set("beta_features", bool(val))
    import pianove.context as ctx
    if ctx.router:
        ctx.router.reload_current_page(delay=0.10)


beta_features_state.bind(_on_beta_features_change)

midi_panel = MidiPanel(
    device_state=midi_device_state,
    key_played_state=midi_key_played,
    text_fn=t,
    storage=storage,
)


def _on_mic_input_change(val):
    from pianove.midi.panel import INPUT_MIC, INPUT_MIDI
    storage.set("mic_input", bool(val))
    midi_panel.set_input_mode(INPUT_MIC if val else INPUT_MIDI)
    import pianove.context as ctx
    if ctx.router and ctx.router.active_page_name:
        ctx.router.reload_current_page(delay=0.10)


def _on_mic_sensitivity_change(val):
    storage.set("mic_sensitivity", float(val))
    midi_panel.set_mic_sensitivity(0.5 * 4.0 ** float(val))    # 0.5× .. 1× (middle) .. 2×


mic_input_state.bind(_on_mic_input_change)
mic_sensitivity_state.bind(_on_mic_sensitivity_change)


def _own_note(note, playing):
    midi_panel.hear_own_note(note, playing)


def hook_sound_engine():
    """Lets the microphone input ignore the notes Pianove plays itself (call once the
    sound engine is imported)."""
    from pianove.sound_engine_fs import add_note_hook
    add_note_hook(_own_note)


def _sync_welcome_greeting(name):
    n = name.strip() or t("friend")
    welcome_greeting.value = t("welcome_title", name=n)


def experience_label() -> str:
    return t(f"exp_{experience_state.value}")


def refresh_summary():
    name = name_state.value.strip() or t("dash")
    summary_text.value = (
        f"{t('summary_name')}\n{name}\n\n"
        f"{t('summary_experience')}\n{experience_label()}\n\n"
        f"{t('summary_midi')}\n{midi_device_state.value}"
    )


def on_language_change(_=None):
    import pianove.context as ctx
    if midi_device_state.value in (
        TEXT["en"]["midi_not_connected"],
        TEXT["de"]["midi_not_connected"],
    ) or not midi_panel.connected:
        midi_device_state.value = t("midi_not_connected")
    _sync_welcome_greeting(name_state.value)
    refresh_summary()
    if ctx.router and ctx.router.active_page_name:
        ctx.router.reload_current_page(delay=0.20)


name_state.bind(_sync_welcome_greeting)
name_state.bind(lambda _: refresh_summary())
experience_state.bind(lambda _: refresh_summary())
midi_device_state.bind(lambda _: refresh_summary())
language_state.bind(on_language_change)

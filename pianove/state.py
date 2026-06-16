from locales import TEXT
from pylay import State, Storage
from pylay.core.theme import iOSTheme
from pianove.i18n import language_state, t
from pianove.midi.panel import MidiPanel

storage = Storage("pianove")

name_state           = State(storage.get("name", ""))
experience_state     = State(storage.get("experience", "none"))
dark_mode_state      = State(bool(storage.get("dark_mode", True)))
sound_enabled_state  = State(bool(storage.get("midi_sound", False)))
sound_volume_state   = State(float(storage.get("midi_volume", 1.0)))
creator_mode_state   = State(bool(storage.get("creator_mode", False)))
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

midi_panel = MidiPanel(
    device_state=midi_device_state,
    key_played_state=midi_key_played,
    text_fn=t,
    storage=storage,
)


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
    ) or not midi_panel.midi_in:
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

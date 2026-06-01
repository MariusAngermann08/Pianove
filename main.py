import pianove  # sets up sys.path for PyLay + PyLute

from pylay import App, PageRouter
from pylay.core.theme import iOSTheme
import pianove.context as ctx
from pianove.state import midi_panel, storage
from pianove.i18n import language_state
from pianove.pages import language, name, welcome, experience, midi, ready, home, lesson, midi_setup, song_setup, song_score

WIDTH, HEIGHT = 1024, 768

# Restore persisted settings before any page builds
if storage.get("language"):
    language_state.value = storage.get("language")
iOSTheme.dark = bool(storage.get("dark_mode", True))
iOSTheme.update_theme()

ui = App(
    title="Pianove",
    width=WIDTH,
    height=HEIGHT,
    dark_mode=iOSTheme.dark,
    managed_display=True,
)
ctx.ui = ui

# Boot the synthesiser AFTER App() so pygame.mixer is already initialised.
# Apply the persisted setting; pre-generation starts in a background thread.
from pianove.sound_engine import init as _sound_init, set_enabled as _sound_set
_sound_init()
_sound_set(bool(storage.get("midi_sound", False)))


def _on_resize(w: int, h: int):
    if ctx.router and ctx.router.active_page_name:
        ctx.router.reload_current_page()


ui.on_resize = _on_resize

initial_page = "home" if storage.get("onboarding_complete") else "language"

router = PageRouter(
    pages={
        "language":   language.build,
        "name":       name.build,
        "welcome":    welcome.build,
        "experience": experience.build,
        "midi":       midi.build,
        "ready":      ready.build,
        "home":       home.build,
        "lesson":     lesson.build,
        "song_setup":  song_setup.build,
        "midi_setup":  midi_setup.build,
        "song_score":  song_score.build,
    },
    initial_page=initial_page,
    anchor="top_left",
    x=0,
    y=0,
    width=1.0,
    height=1.0,
)
ctx.router = router
ui.root.add_child(router)

if __name__ == "__main__":
    try:
        ui.run()
    finally:
        midi_panel.close()

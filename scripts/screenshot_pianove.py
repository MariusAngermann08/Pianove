"""
Capture Pianove app screenshots for docs.
Run from the project root: python scripts/screenshot_pianove.py
"""
import os
import sys
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs" / "img"
OUT.mkdir(parents=True, exist_ok=True)

import pianove  # sets up sys.path for PyLay + PyLute
import pygame
pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=256)

from pylay import App, PageRouter
from pylay.core.theme import iOSTheme
from pylay.core import _dirty
import pianove.context as ctx
from pianove.state import storage, name_state, experience_state, midi_device_state
from pianove.i18n import language_state

# ── seed clean state ──────────────────────────────────────────────────────────
language_state.value = "en"
storage.set("language", "en")
name_state.value = "Alex"
experience_state.value = "beginner"
iOSTheme.dark = True
iOSTheme.update_theme()

# Seed some progress so home tab looks realistic
storage.set("onboarding_complete", True)
storage.set("completed_lessons", ["welcome", "c_major_scale", "five_note_melody"])
today = date.today()
storage.set("lesson_dates", [
    (today - timedelta(days=i)).isoformat() for i in range(3)
])
storage.set("total_minutes", 47)

# ── import Für Elise ──────────────────────────────────────────────────────────
FUR_ELISE = r"C:\Users\MariusAngermann\Downloads\fur-elise-easy-ver.mxl"
fur_elise_song = None
if os.path.exists(FUR_ELISE):
    from pianove.song_store import import_song, list_songs
    existing = [s for s in list_songs() if "elise" in s.get("title", "").lower()
                or "elise" in os.path.basename(s.get("filepath", "")).lower()]
    fur_elise_song = existing[0] if existing else import_song(FUR_ELISE)
    print(f"Für Elise: {fur_elise_song['title']} ({fur_elise_song['id']})")

# ── app ───────────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1024, 768
ui = App(title="Pianove — Screenshots", width=WIDTH, height=HEIGHT,
         dark_mode=True, managed_display=True)
ctx.ui = ui

from pianove.sound_engine_fs import init as _si, set_enabled as _se
_si(); _se(False)

midi_device_state.value = "No MIDI keyboard connected"

from pianove.pages import language, name, welcome, experience, midi, ready
from pianove.pages import home, lesson, midi_setup, song_setup, song_score, boot

router = PageRouter(
    pages={
        "boot":       lambda: boot.build(next_page="language"),
        "language":   language.build,
        "name":       name.build,
        "welcome":    welcome.build,
        "experience": experience.build,
        "midi":       midi.build,
        "ready":      ready.build,
        "home":       home.build,
        "lesson":     lesson.build,
        "song_setup": song_setup.build,
        "midi_setup": midi_setup.build,
        "song_score": song_score.build,
    },
    initial_page="language",
    anchor="top_left", x=0, y=0, width=1.0, height=1.0,
)
ctx.router = router
ui.root.add_child(router)

# ── setup functions run before each navigation ────────────────────────────────
def _go_name():
    name_state.value = "Alex"

def _go_midi():
    pass  # navigate to the onboarding midi page

def _go_home():
    pass

def _go_lesson():
    ctx.current_lesson_id    = "first_song"
    ctx.current_course_id    = "beginner_path"
    ctx.current_course_index = 7
    ctx.lesson_step_idx      = 2   # exercise step (skip text + notation_demo)
    ctx.lesson_current_idx   = 6   # 6 notes already played → shown in green
    ctx.lesson_section_idx   = 0
    ctx.lesson_phase         = "practice"
    ctx.lesson_keyboard_vis  = True

def _go_score():
    if fur_elise_song:
        ctx.score_song_id = fur_elise_song["id"]

# (delay_frames, page, setup_fn, output_filename)
SHOTS = [
    (45,  "language",   None,        "ss-onboarding-language.png"),
    (45,  "name",       _go_name,    "ss-onboarding-name.png"),
    (45,  "midi",       _go_midi,    "ss-onboarding-midi.png"),
    (60,  "home",       _go_home,    "ss-home.png"),
    (80,  "lesson",     _go_lesson,  "ss-lesson.png"),
    (120, "song_score", _go_score,   "ss-song-score.png"),
]

# ── loop ──────────────────────────────────────────────────────────────────────
ui.root.layout(ui.screen.get_rect())
_dirty.mark()
ui.screen.fill(iOSTheme.background)
ui.root.draw(ui.screen)
pygame.display.flip()

# prime the first page
delay, page, setup, fname = SHOTS[0]
if setup: setup()
router.navigate(page)
fire_at   = delay
shot_idx  = 0
frame     = 0

print("Taking screenshots …")
running = True
while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False

    dt = min(ui.clock.tick(60) / 1000.0, 0.05)
    ui.root.update(dt)
    if ui.root._layout_requested:
        ui.root.layout(ui.screen.get_rect())
        ui.root._layout_requested = False
    _dirty.mark()
    ui.screen.fill(iOSTheme.background)
    ui.root.draw(ui.screen)
    pygame.display.flip()
    frame += 1

    if frame >= fire_at:
        path = OUT / fname
        pygame.image.save(ui.screen, str(path))
        print(f"  OK  {path.name}")
        shot_idx += 1
        if shot_idx >= len(SHOTS):
            running = False
        else:
            delay, page, setup, fname = SHOTS[shot_idx]
            if setup: setup()
            router.navigate(page)
            fire_at = frame + delay

from pianove.state import midi_panel
midi_panel.close()
pygame.quit()
print("Done.")

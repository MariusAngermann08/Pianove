"""
Capture the Pianove screenshots used by the README and the docs site.

Runs the real app off-screen (no window, no audio, no MIDI device needed) with a
throw-away home folder, seeds a little progress so the pages look lived in, imports the
Chopin waltz that ships in the repository, walks through the screens and saves a PNG of
each to docs/img/.

    python scripts/screenshot_pianove.py              # every shot
    python scripts/screenshot_pianove.py home lesson  # only shots whose name contains these
    python scripts/screenshot_pianove.py --size 1280x800 --out /tmp/shots

Needs the app's own dependencies (pygame, pyfluidsynth with libfluidsynth); nothing in
your real ~/.pianove is read or changed.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
ap.add_argument("only", nargs="*", help="only shots whose name contains one of these")
ap.add_argument("--size", default="1280x800", help="window size, WIDTHxHEIGHT")
ap.add_argument("--out", default=str(ROOT / "docs" / "img"), help="where the PNGs go")
ap.add_argument("--lang", default="en", help="app language (en, de)")
args = ap.parse_args()

WIDTH, HEIGHT = (int(v) for v in args.size.lower().split("x"))
OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)

# A fresh home folder: storage, imported songs and creator packages all live under it.
_home = tempfile.mkdtemp(prefix="pianove_shots_")
os.environ.update(HOME=_home, USERPROFILE=_home)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(ROOT))

import pianove  # noqa: E402  (sets up sys.path for PyLay + PyLute)
import pygame  # noqa: E402

pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=256)

from pylay import App, PageRouter  # noqa: E402
from pylay.core import _dirty  # noqa: E402
from pylay.core.theme import iOSTheme  # noqa: E402
import pianove.context as ctx  # noqa: E402
from pianove.state import (storage, name_state, experience_state,  # noqa: E402
                           midi_device_state, creator_mode_state, beta_features_state)
from pianove.i18n import language_state  # noqa: E402

# ── seed a believable user ─────────────────────────────────────────────────────
language_state.value = args.lang
storage.set("language", args.lang)
name_state.value = "Alex"
storage.set("name", "Alex")
experience_state.value = "beginner"
iOSTheme.dark = True
iOSTheme.update_theme()

storage.set("onboarding_complete", True)
storage.set("completed_lessons", ["welcome", "c_major_scale", "five_note_melody"])
today = date.today()
storage.set("lesson_dates", [(today - timedelta(days=i)).isoformat() for i in range(5)])
storage.set("total_minutes", 147)

from pianove.song_store import import_song  # noqa: E402


def _melody_xml(title: str, composer: str, bars: list[str], time=(4, 4)) -> str:
    """A one-staff MusicXML file from bars written as "E4:q E4:q F4:h" (q, h, w, e)."""
    dur = {"e": (1, "eighth"), "q": (2, "quarter"), "h": (4, "half"), "w": (8, "whole")}
    meas = []
    for i, bar in enumerate(bars, 1):
        notes = []
        for tok in bar.split():
            pitch, v = tok.split(":")
            d, typ = dur[v]
            step, octave = pitch[0], pitch[-1]
            alter = "<alter>1</alter>" if "#" in pitch else ""
            notes.append(f"<note><pitch><step>{step}</step>{alter}<octave>{octave}</octave>"
                         f"</pitch><duration>{d}</duration><type>{typ}</type></note>")
        attrs = ("<attributes><divisions>2</divisions><key><fifths>0</fifths></key>"
                 f"<time><beats>{time[0]}</beats><beat-type>{time[1]}</beat-type></time>"
                 "<clef><sign>G</sign><line>2</line></clef></attributes>") if i == 1 else ""
        meas.append(f'<measure number="{i}">{attrs}{"".join(notes)}</measure>')
    return ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="3.1">'
            f"<work><work-title>{title}</work-title></work><identification>"
            f'<creator type="composer">{composer}</creator></identification>'
            '<part-list><score-part id="P1"><part-name>Piano</part-name></score-part>'
            f'</part-list><part id="P1">{"".join(meas)}</part></score-partwise>')


# A few public-domain melodies next to the Chopin waltz, so the Songs tab looks used.
_DEMO_SONGS = {
    "ode_to_joy.musicxml": ("Ode to Joy", "Ludwig van Beethoven", [
        "E4:q E4:q F4:q G4:q", "G4:q F4:q E4:q D4:q", "C4:q C4:q D4:q E4:q", "E4:q D4:q D4:h",
        "E4:q E4:q F4:q G4:q", "G4:q F4:q E4:q D4:q", "C4:q C4:q D4:q E4:q", "D4:q C4:q C4:h",
        "D4:q D4:q E4:q C4:q", "D4:q E4:e F4:e E4:q C4:q", "D4:q E4:e F4:e E4:q D4:q",
        "C4:q D4:q G3:h", "E4:q E4:q F4:q G4:q", "G4:q F4:q E4:q D4:q", "C4:q C4:q D4:q E4:q",
        "D4:q C4:q C4:h"]),
    "twinkle.musicxml": ("Twinkle, Twinkle, Little Star", "Traditional", [
        "C4:q C4:q G4:q G4:q", "A4:q A4:q G4:h", "F4:q F4:q E4:q E4:q", "D4:q D4:q C4:h",
        "G4:q G4:q F4:q F4:q", "E4:q E4:q D4:h", "G4:q G4:q F4:q F4:q", "E4:q E4:q D4:h",
        "C4:q C4:q G4:q G4:q", "A4:q A4:q G4:h", "F4:q F4:q E4:q E4:q", "D4:q D4:q C4:h"]),
}
for _fname, (_title, _composer, _bars) in _DEMO_SONGS.items():
    _path = Path(_home) / _fname
    _path.write_text(_melody_xml(_title, _composer, _bars), encoding="utf-8")
    import_song(str(_path))
waltz = import_song(str(ROOT / "waltz-in-a-minorchopin.mxl"))

# ── the app, built the way main.py builds it ───────────────────────────────────
ui = App(title="Pianove", width=WIDTH, height=HEIGHT, dark_mode=True, managed_display=True)
ctx.ui = ui

from pianove.sound_engine_fs import init as _sound_init, set_enabled as _sound_set  # noqa: E402

_sound_init()
_sound_set(False)

# A pretend MIDI keyboard, so the pages show a connected device rather than a warning.
import pianove.midi.panel as _panel  # noqa: E402
from pianove.state import midi_panel  # noqa: E402


class _FakePort:
    name = "Digital Piano"

    def iter_pending(self):
        return iter(())

    def close(self):
        pass


_panel.get_physical_inputs = lambda: [_FakePort.name]
_panel.mido.open_input = lambda *_a, **_k: _FakePort()
_panel.mido.get_input_names = lambda: [_FakePort.name]
midi_panel._saved_range = (36, 96)            # a 61-key keyboard, already calibrated
midi_device_state.value = _FakePort.name

from pianove.pages import (language, name, welcome, experience, midi, ready,  # noqa: E402
                           home, lesson, midi_setup, song_setup, song_score, boot,
                           lesson_editor, course_editor)

router = PageRouter(
    pages={
        "boot": lambda: boot.build(next_page="home"),
        "language": language.build, "name": name.build, "welcome": welcome.build,
        "experience": experience.build, "midi": midi.build, "ready": ready.build,
        "home": home.build, "lesson": lesson.build, "song_setup": song_setup.build,
        "midi_setup": midi_setup.build, "song_score": song_score.build,
        "lesson_editor": lesson_editor.build, "course_editor": course_editor.build,
    },
    initial_page="boot", anchor="top_left", x=0, y=0, width=1.0, height=1.0,
)
ctx.router = router
ui.root.add_child(router)


# ── helpers ────────────────────────────────────────────────────────────────────
def tick(frames: int = 1):
    for _ in range(frames):
        pygame.event.pump()
        ui.root.update(1 / 60)
        if ui.root._layout_requested:
            ui.root.layout(ui.screen.get_rect())
            ui.root._layout_requested = False
        _dirty.mark()
        ui.screen.fill(iOSTheme.background)
        ui.root.draw(ui.screen)
        pygame.display.flip()


def click(x: int, y: int, frames: int = 20):
    """A tap at (x, y), sent through the app's own event handling."""
    for kind in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        kw = {"pos": (x, y)}
        if kind == pygame.MOUSEMOTION:
            kw.update(rel=(0, 0), buttons=(0, 0, 0))
        else:
            kw["button"] = 1
        ui.process_event(pygame.event.Event(kind, **kw))
        tick(2)
    tick(frames)


def scroll(x: int, y: int, dy: int, frames: int = 40):
    pygame.mouse.set_pos((x, y))
    for _ in range(abs(dy)):
        ui.process_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1 if dy > 0 else 1,
                                            precise_x=0.0, precise_y=-1.0 if dy > 0 else 1.0,
                                            flipped=False))
        tick(1)
    tick(frames)


def go(page: str, frames: int = 60):
    if router.active_page_name == page:       # same page again: leave it, to build it anew
        router.navigate("midi_setup")
        tick(5)
    router.navigate(page)
    tick(frames)


def home_tab(page: str, frames: int = 50):
    """Open a tab of the home screen (home, songs, lessons, practice, creator, settings)."""
    from pianove.home import container
    keys = ["home", "songs", "lessons", "practice"] + (["creator"] if creator_mode_state.value else [])
    if page in keys:
        container._active_tab.value = keys.index(page)
    ctx.home_page = page
    router.navigate("home")
    tick(10)
    if ctx.inner_router and ctx.inner_router.active_page_name != page:
        ctx.inner_router.navigate(page)
    tick(frames)


def set_theme(dark: bool):
    iOSTheme.dark = dark
    iOSTheme.update_theme()
    ui.apply_theme(dark)


def save(name: str):
    path = OUT / f"{name}.png"
    pygame.image.save(ui.screen, str(path))
    print(f"  saved  {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")


def start_lesson(lesson_id: str, course_id: str | None, index: int, step: int,
                 beat: int = 0, played: int = 0):
    ctx.current_song_id = None
    ctx.practice_mode = False
    ctx.current_lesson_id = lesson_id
    ctx.current_course_id = course_id
    ctx.current_course_index = index
    ctx.lesson_step_idx = step
    ctx.lesson_beat_idx = beat
    ctx.lesson_current_idx = played
    ctx.lesson_section_idx = 0
    ctx.lesson_phase = "practice"
    ctx.lesson_completed = False
    ctx.lesson_keyboard_vis = True
    ctx.lesson_test_return = None


# ── the shots ──────────────────────────────────────────────────────────────────
def shot_onboarding():
    go("language"); save("ss-onboarding-language")
    go("name"); save("ss-onboarding-name")
    go("experience"); save("ss-onboarding-experience")
    go("midi"); save("ss-onboarding-midi")


def shot_home():
    home_tab("home", 80); save("ss-home")


def shot_home_light():
    set_theme(False)
    home_tab("home", 80); save("ss-home-light")
    set_theme(True)


def shot_songs():
    home_tab("songs"); save("ss-songs")


def shot_song_path():
    ctx.current_song_id = waltz["id"]
    go("song_setup", 80); save("ss-song-path")


def shot_song_score():
    ctx.score_song_id = waltz["id"]
    go("song_score", 120); save("ss-song-score")


def shot_song_play():
    beta_features_state.value = True
    ctx.lesson_hands_vis = True
    ctx.current_song_id = waltz["id"]
    ctx.song_range = None
    ctx.path_step = None
    ctx.current_song_hand = "both"
    ctx.lesson_current_idx = 0
    ctx.lesson_section_idx = 0
    ctx.lesson_completed = False
    ctx.lesson_phase = "practice"
    go("lesson", 120); save("ss-song-play")
    ctx.current_song_id = None


def shot_lessons():
    home_tab("lessons"); save("ss-lessons")


def shot_course():
    from pianove.home import tab_lessons
    from pianove.lesson_loader import list_courses
    course = next(c for c in list_courses() if c["id"] == "beginner_path")
    home_tab("lessons", 20)
    tab_lessons._open_course(course)
    tick(50); save("ss-course")


def shot_theory():
    from pianove.pages import theory
    scenes = []
    init = theory.Scene.__init__

    def _keep(self, *a, **kw):
        init(self, *a, **kw)
        scenes.append(self)
    theory.Scene.__init__ = _keep
    beta_features_state.value = True
    start_lesson("c_major_scale", "beginner_path", 1, step=0)
    go("lesson", 10)
    theory.Scene.__init__ = init
    scenes[-1]._start_beat(3)                 # "The thumb passes under": the hand plays
    tick(150); save("ss-lesson-theory")


def shot_lesson():
    beta_features_state.value = True
    ctx.lesson_hands_vis = True
    start_lesson("five_note_melody", "beginner_path", 2, step=1, played=5)
    go("lesson", 150); save("ss-lesson")


def shot_practice():
    home_tab("practice"); save("ss-practice")


def shot_settings():
    home_tab("settings"); save("ss-settings")


def shot_midi_setup():
    go("midi_setup", 60); save("ss-midi-setup")


def shot_creator():
    creator_mode_state.value = True
    home_tab("creator", 60); save("ss-creator")


def shot_lesson_editor():
    creator_mode_state.value = True
    from pianove import creator_store as cs
    lid = cs.duplicate_lesson("first_song", author="Alex")
    from pianove.pages.lesson_editor import open_lesson
    open_lesson(lid)
    tick(60)
    click(140, 232, 100)                      # the first screen of the scene: its editor
    save("ss-lesson-editor")


def shot_course_editor():
    creator_mode_state.value = True
    from pianove import creator_store as cs
    cid = cs.new_course("My first course", author="Alex")
    from pianove.pages.course_editor import open_course
    open_course(cid)
    tick(80); save("ss-course-editor")


SHOTS = {name[5:]: fn for name, fn in list(globals().items()) if name.startswith("shot_")}

# boot screen first, so everything that loads lazily is in place
ui.root.layout(ui.screen.get_rect())
tick(30)
print(f"Taking screenshots at {WIDTH}x{HEIGHT} into {OUT}")
for key, fn in SHOTS.items():
    if args.only and not any(o in key for o in args.only):
        continue
    try:
        fn()
    except Exception as exc:  # one broken screen should not stop the rest
        import traceback
        traceback.print_exc()
        print(f"  FAILED {key}: {exc}")

midi_panel.close()
pygame.quit()
print("Done.")

"""
Record the clips for the Pianove promo video from the real app.

The app runs off-screen with a throw-away home folder and the same demo data as the
screenshots. Time is driven frame by frame (no wall clock), so every clip comes out the
same on every machine. Each clip is written as a near-lossless video at the size it is
shown at, plus every key the app sounded, with its time, so compose.py can play exactly
those notes on the soundtrack.

    python scripts/promo/record.py OUT_DIR
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "promo_clips")
OUT.mkdir(parents=True, exist_ok=True)

FPS = 30
DT = 1.0 / FPS
VIEW_W, VIEW_H = 1350, 844          # how big the app is shown in the video (16:10)
SS = 1                              # recorded at that size: the layouts are made for it
W, H = VIEW_W * SS, VIEW_H * SS

_home = tempfile.mkdtemp(prefix="pianove_promo_")
os.environ.update(HOME=_home, USERPROFILE=_home, SDL_VIDEODRIVER="dummy",
                  SDL_AUDIODRIVER="dummy", PYGAME_HIDE_SUPPORT_PROMPT="1")
sys.path.insert(0, str(ROOT))

import pianove  # noqa: E402,F401
import pygame  # noqa: E402
from pylay import App, PageRouter  # noqa: E402
from pylay.core import _dirty  # noqa: E402
from pylay.core.theme import iOSTheme  # noqa: E402
import pianove.context as ctx  # noqa: E402
from pianove.state import storage, name_state, experience_state, midi_device_state  # noqa: E402
from pianove.i18n import language_state  # noqa: E402

# ── the same lived-in user as the screenshots ───────────────────────────────────
language_state.value = "en"
storage.set("language", "en")
name_state.value = "Alex"
storage.set("name", "Alex")
experience_state.value = "basics"
storage.set("experience", "basics")
storage.set("onboarding_complete", True)
storage.set("completed_lessons", ["welcome", "c_major_scale", "five_note_melody"])
today = date.today()
storage.set("lesson_dates", [(today - timedelta(days=i)).isoformat() for i in (0, 2, 4)])
_minutes = [18, 0, 25, 12, 31, 9, 17]
storage.set("practice_log", {(today - timedelta(days=6 - i)).isoformat(): m * 60.0
                             for i, m in enumerate(_minutes) if m})
storage.set("daily_goal_minutes", 15)
iOSTheme.dark = True
iOSTheme.update_theme()
from pianove.ui_utils import apply_score_colors  # noqa: E402
apply_score_colors()

from pianove.song_store import import_song  # noqa: E402
waltz = import_song(str(ROOT / "waltz-in-a-minorchopin.mxl"))

ui = App(title="Pianove", width=W, height=H, dark_mode=True, managed_display=True)
ctx.ui = ui

# ── every note the app sounds, with the clip's time ─────────────────────────────
from pianove import sound_engine_fs as se  # noqa: E402

clip = {"t": 0.0, "events": []}         # current clip time and its notes


def _on(m, v=80):
    clip["events"].append([round(clip["t"], 4), 1, int(m), int(v)])


def _off(m):
    clip["events"].append([round(clip["t"], 4), 0, int(m), 0])


from pianove import sound as _sound  # noqa: E402

for _m in (se, _sound):                 # the app plays through pianove.sound
    _m.play = _on
    _m.play_raw = _on
    _m.stop = _off
    _m.init = lambda: None
    _m.set_sustain_pedal = lambda v: None

# a connected keyboard, so the status line is green
import pianove.midi.panel as _panel  # noqa: E402
from pianove.state import midi_panel  # noqa: E402


class _Port:
    name = "Digital Piano"

    def iter_pending(self):
        return iter(())

    def close(self):
        pass


_panel.get_physical_inputs = lambda: [_Port.name]
_panel.mido.open_input = lambda *a, **k: _Port()
_panel.mido.get_input_names = lambda: [_Port.name]
midi_panel._saved_range = (36, 96)
midi_device_state.value = _Port.name

# listening plays on the video's clock, with each note at its exact time in the piece
from pianove.pages import lesson as _lesson  # noqa: E402

_lesson._LISTEN_THREADED = False
_lesson._listen_clock = lambda: clip["t"]
_listen_start = {"t": None}


def _listen_on(t, m, v):
    clip["events"].append([round(_listen_start["t"] + t, 4), 1, int(m), int(v)])


def _listen_off(t, m):
    clip["events"].append([round(_listen_start["t"] + t, 4), 0, int(m), 0])


_lesson._listen_on = _listen_on
_lesson._listen_off = _listen_off

from pianove.pages import (home, lesson, song_setup, song_score, lesson_editor,  # noqa: E402
                           course_editor, midi)

router = PageRouter(
    pages={"home": home.build, "lesson": lesson.build, "song_setup": song_setup.build,
           "song_score": song_score.build, "lesson_editor": lesson_editor.build,
           "course_editor": course_editor.build, "midi": midi.build},
    initial_page="home", anchor="top_left", x=0, y=0, width=1.0, height=1.0,
)
ctx.router = router
ui.root.add_child(router)
from pianove import keyboard_input  # noqa: E402
ui.event_filter = keyboard_input.handle


def tick():
    pygame.event.pump()
    ui.root.update(DT)
    if ui.root._layout_requested:
        ui.root.layout(ui.screen.get_rect())
        ui.root._layout_requested = False
    _dirty.mark()
    ui.screen.fill(iOSTheme.background)
    ui.root.draw(ui.screen)


def walk(el):
    yield el
    for c in getattr(el, "children", []):
        yield from walk(c)


def find(type_name):
    from pylay.widgets.pygame_canvas import PygameCanvas
    for w in walk(ui.root):
        if type(w).__name__ == type_name:
            return w
        if isinstance(w, PygameCanvas) and type(getattr(w, "target", None)).__name__ == type_name:
            return w.target
    return None


def settle(frames=20):
    clip["t"] = 0.0
    for _ in range(frames):
        tick()


def record(name: str, seconds: float, per_frame=None, frames_for: float | None = None):
    """Run the app for `seconds`, writing frames (for the first `frames_for` seconds)
    to NAME.mkv and the notes it sounded to NAME.json."""
    clip["t"], clip["events"] = 0.0, []
    n_frames = int(round(seconds * FPS))
    n_video = int(round((frames_for if frames_for is not None else seconds) * FPS))
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{VIEW_W}x{VIEW_H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", "8", "-pix_fmt", "yuv444p",
         str(OUT / f"{name}.mkv")], stdin=subprocess.PIPE)
    for i in range(n_frames):
        clip["t"] = i * DT
        if per_frame:
            per_frame(clip["t"])
        tick()
        if i < n_video:
            frame = ui.screen if SS == 1 else pygame.transform.smoothscale(ui.screen, (VIEW_W, VIEW_H))
            enc.stdin.write(pygame.image.tostring(frame, "RGB"))
    enc.stdin.close()
    enc.wait()
    (OUT / f"{name}.json").write_text(json.dumps({"seconds": seconds, "events": clip["events"]}))
    print(f"  {name}: {n_video / FPS:.1f}s video, {len(clip['events'])} note events")


def still(name: str):
    """A full-resolution picture, for slow camera moves in compose.py."""
    pygame.image.save(ui.screen, str(OUT / f"{name}.png"))
    print(f"  {name}: still")


def go(page: str, animated: bool = True):
    if router.active_page_name == page:
        router.navigate("midi", animated=False)
        settle(3)
    router.navigate(page, animated=animated)


def start_lesson(lesson_id, course_id, index, step):
    ctx.current_song_id = None
    ctx.practice_mode = False
    ctx.current_lesson_id, ctx.current_course_id = lesson_id, course_id
    ctx.current_course_index, ctx.lesson_step_idx = index, step
    ctx.lesson_beat_idx = 0
    ctx.lesson_current_idx = ctx.lesson_section_idx = 0
    ctx.lesson_phase, ctx.lesson_completed = "practice", False
    ctx.lesson_keyboard_vis, ctx.lesson_hands_vis = True, True
    ctx.lesson_test_return = None


ui.root.layout(ui.screen.get_rect())
settle(10)
print(f"Recording at {W}x{H} → {VIEW_W}x{VIEW_H}, {FPS} fps, into {OUT}")


# 1 ── a theory scene: the hand shows the thumb passing under, then the player copies it
def clip_theory():
    from pianove.pages import theory
    scenes = []
    init = theory.Scene.__init__

    def keep(self, *a, **k):
        init(self, *a, **k)
        scenes.append(self)
    theory.Scene.__init__ = keep
    start_lesson("c_major_scale", "beginner_path", 1, 0)
    go("lesson")
    settle(2)
    theory.Scene.__init__ = init
    scene = scenes[-1]
    scene._start_beat(3)
    plan = {"next": None, "i": 0, "held": None}

    def player(t):
        if scene.phase == "try" and plan["next"] is None:
            plan["next"] = t + 0.5
        if plan["held"] and t >= plan["held"][1]:
            midi_panel.release(plan["held"][0])
            plan["held"] = None
        if plan["next"] is not None and t >= plan["next"] and scene.waiting_for_player:
            notes = sorted(scene.beat.tries[scene.try_i]) if scene.try_i < len(scene.beat.tries) else []
            if notes:
                midi_panel.press(notes[0], 72)
                plan["held"] = (notes[0], t + 0.42)
                plan["next"] = t + 0.62
    record("theory", 9.0, player)


# 2 ── a lesson piece: the music waits, notes turn green as the player plays them
def clip_exercise():
    start_lesson("five_note_melody", "beginner_path", 2, 1)
    go("lesson")
    settle(30)
    piano = find("_LessonPiano")
    state = {"next": 0.7, "held": None}

    def player(t):
        if state["held"] and t >= state["held"][1]:
            for m in state["held"][0]:
                midi_panel.release(m)
            state["held"] = None
        if t >= state["next"]:
            notes = sorted(piano._sv.expected_midis())
            for m in notes:
                midi_panel.press(m, 76)
            state["held"] = (notes, t + 0.34)
            state["next"] = t + 0.5
    record("exercise", 8.0, player)


# 3 ── Chopin, played by Pianove with both hands; the music runs on after the picture
def clip_chopin():
    ctx.current_song_id = waltz["id"]
    ctx.song_range, ctx.path_step = None, None
    ctx.current_song_hand = "both"
    ctx.lesson_current_idx = ctx.lesson_section_idx = 0
    ctx.lesson_completed, ctx.lesson_phase = False, "listen"
    ctx.lesson_hands_vis = True
    go("lesson")
    settle(30)
    sv = find("_StaffView")
    started = {"done": False}

    def player(t):
        if not started["done"] and t >= 0.4:
            started["done"] = True
            _listen_start["t"] = t
            sv.toggle_play()
    record("chopin", 32.0, player, frames_for=12.0)
    sv.stop_listening()


# 4 ── stills for slow camera moves
def stills():
    ctx.current_song_id = waltz["id"]
    go("song_setup")
    settle(60)
    still("song_path")

    from pianove.home import container
    container._active_tab.value = 0
    ctx.home_page = "home"
    go("home", animated=False)          # no slide: only the chart and the goal ring move
    record("home", 3.0)

    from pianove import creator_store as cs
    lid = cs.duplicate_lesson("first_song", author="Alex")
    from pianove.pages.lesson_editor import open_lesson
    open_lesson(lid)
    settle(60)
    rect = None
    for w in walk(ui.root):           # the first screen of the scene, in the outline
        if type(w).__name__ in ("ItemRow", "Button") and "Mary" in str(getattr(w, "text", "")):
            rect = w.rect
            break
    if rect is None:
        rect = pygame.Rect(int(140 * W / 1280), int(232 * H / 800), 2, 2)   # as in the screenshots
    for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        ui.process_event(pygame.event.Event(kind, pos=rect.center, button=1))
        settle(3)
    settle(90)
    still("editor")

    # no instrument: the status line tells you to use the computer keys
    midi_panel.close()
    _panel.get_physical_inputs = lambda: []
    _panel.mido.get_input_names = lambda: []
    midi_device_state.value = "—"
    start_lesson("welcome", "beginner_path", 0, 1)
    go("lesson")
    settle(60)
    piano = find("_LessonPiano")
    seq = {"next": 0.6, "held": None}

    def keys(t):                      # played on the computer keyboard (A S D F G …)
        if seq["held"] and t >= seq["held"][1]:
            ui.process_event(pygame.event.Event(pygame.KEYUP, scancode=seq["held"][0],
                                                key=0, mod=0, unicode=""))
            seq["held"] = None
        if t >= seq["next"]:
            m = sorted(piano._sv.expected_midis())[0]
            inv = {v: k for k, v in keyboard_input._KEYS.items()}
            sc = inv.get(m - keyboard_input.base_c)
            if sc is not None:
                ui.process_event(pygame.event.Event(pygame.KEYDOWN, scancode=sc, key=0, mod=0,
                                                    unicode=""))
                seq["held"] = (sc, t + 0.3)
            seq["next"] = t + 0.52
    record("computer_keys", 6.0, keys)


for fn in (clip_theory, clip_exercise, clip_chopin, stills):
    fn()
print("Done.")

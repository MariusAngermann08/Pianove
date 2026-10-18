"""The animated hands: they render, reach every key of a plan with the right finger, never
leave keys that are still held unless the next note is due, and drop a finger's colour
the moment its note is done. Plus the pieces around them: key presses as events, and the
skin-tone picker.

Run:  python -m pytest tests/test_hands.py -q      (or just: python tests/test_hands.py)
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((10, 10))

import pianove  # noqa: E402,F401  (puts PyLay and PyLute on the path)
from pianove.fingering import key_x, is_black  # noqa: E402
from pianove.hands import (HandsOverlay, KeyboardGeometry, SKIN_TONES, solve_hand,  # noqa: E402
                           hand_joints, tip_point, _key_point)

KB = KeyboardGeometry(left=10, white_w=40, top=4, key_h=100, black_h=62,
                      first_white_x=key_x(36), bottom=236)

# C D E with 1 2 3, then the thumb passes under to F while the left hand joins on C3
PLAN = [{"right": {60: 1}}, {"right": {62: 2}}, {"right": {64: 3}},
        {"right": {65: 1}, "left": {48: 5}}]


def _run(overlay, steps, frames=40, active=frozenset(), **kw):
    surf = pygame.Surface((1200, 240))
    for step in steps:
        for _ in range(frames):
            overlay.update(1 / 60, step, active, **kw)
        overlay.draw(surf, KB)
    return surf


def test_hands_reach_every_step():
    ov = HandsOverlay(PLAN)
    surf = _run(ov, range(len(PLAN)))
    rh, lh = ov.hands["right"], ov.hands["left"]
    assert abs(rh.tip_x(1) - key_x(65)) < 0.05          # the thumb went under to F4
    assert abs(lh.tip_x(5) - key_x(48)) < 0.05          # the left little finger is on C3
    assert rh.glow[1].value > 0.9 and lh.glow[5].value > 0.9
    drawn = sum(surf.get_at((x, 150))[:3] != (0, 0, 0) for x in range(0, 1200, 4))
    assert drawn > 20                                   # the hands are on the canvas


def test_pressing_a_key_dips_its_finger():
    ov = HandsOverlay(PLAN)
    _run(ov, [2], active=frozenset({64}))
    rh = ov.hands["right"]
    assert rh.press[3].value > 0.9 and rh.press[2].value < 0.1


def test_a_hand_with_no_notes_stays_hidden():
    ov = HandsOverlay([{"right": {60: 1}}])
    _run(ov, [0])
    assert ov.hands["left"].alpha.value < 0.01


# a leap: C4 with the thumb, then G5 with the little finger, far out of reach
LEAP = [{"right": {60: 1}}, {"right": {79: 5}}]


def test_hand_waits_while_a_key_is_held():
    ov = HandsOverlay(LEAP)
    _run(ov, [0], active=frozenset({60}))
    _run(ov, [1], active=frozenset({60}))              # C4 still held, practice mode
    rh = ov.hands["right"]
    assert abs(rh.tip_x(1) - key_x(60)) < 0.1          # the thumb stays on its key
    _run(ov, [1], active=frozenset())                  # let go: now the hand moves
    assert abs(rh.tip_x(5) - key_x(79)) < 0.1


def test_hand_leaps_when_the_note_is_due():
    ov = HandsOverlay(LEAP)
    _run(ov, [0], active=frozenset({60}))
    # timed play: the next step has started, so the held key must go
    _run(ov, [1], active=frozenset({60}), lead=0.1, step_time=0.5)
    assert abs(ov.hands["right"].tip_x(5) - key_x(79)) < 0.1


def test_colour_leaves_with_its_note_at_once():
    ov = HandsOverlay(LEAP)
    _run(ov, [0])
    rh = ov.hands["right"]
    assert rh.glow[1].value > 0.9
    ov.update(1 / 60, 1, frozenset())
    assert rh.glow[1].value == 0.0                      # no lingering colour on the old finger


def _reach_error(side, fingers):
    """How far each fingertip ends up from its key, in white-key widths."""
    targets = {f: _key_point(m, -0.97, f, 0.475) for f, m in fingers.items()}
    place = solve_hand(side, targets, None)
    worst = 0.0
    for f, (up, _) in hand_joints(side, place, targets).items():
        if f in targets:
            x, y = tip_point(side, place, f, up)
            near, far = targets[f][3], targets[f][4]
            worst = max(worst, abs(x - targets[f][0]) + max(0.0, y - near, far - y))
    return worst


def test_common_shapes_are_reached():
    shapes = [
        ("right", {1: 60, 2: 62, 3: 64, 4: 65, 5: 67}),     # five-finger position
        ("right", {1: 60, 3: 64, 5: 67}),                   # triad
        ("right", {1: 60, 5: 72}),                          # octave
        ("right", {1: 61, 3: 66, 5: 70}),                   # black-key triad
        ("left", {5: 48, 3: 52, 1: 55}),                    # left-hand triad
        ("left", {5: 36, 1: 48}),                           # left-hand octave
        ("left", {5: 45, 2: 52, 1: 57}),                    # a waltz chord
    ]
    for side, fingers in shapes:
        err = _reach_error(side, fingers)
        assert err < 0.2, (side, fingers, err)


def test_skin_tone_changes_the_hand():
    a = _run(HandsOverlay([{"right": {60: 1}}], skin="light"), [0])
    b = _run(HandsOverlay([{"right": {60: 1}}], skin="dark"), [0])
    assert pygame.image.tobytes(a, "RGB") != pygame.image.tobytes(b, "RGB")
    assert set(SKIN_TONES) == {"light", "medium_light", "medium", "medium_dark", "dark"}


def test_quick_repeated_key_is_not_lost():
    from pianove.midi.panel import MidiPanel
    panel = MidiPanel()
    panel._state = 4                                    # ready to play
    panel.take_note_ons()
    import pianove.sound_engine_fs as se
    play = se.play
    se.play = lambda *a, **k: None
    try:
        panel._on_note_on(60, 80)
        panel.active_notes.discard(60)                  # let go…
        panel._on_note_on(60, 80)                       # …and pressed again, same frame
    finally:
        se.play = play
    assert panel.take_note_ons() == [60, 60]
    assert panel.take_note_ons() == []


def test_tone_picker_chooses_on_click():
    from pylay import State
    from pianove.components.tone_picker import TonePicker
    state = State("medium_light")
    picker = TonePicker(state)
    picker.rect = pygame.Rect(0, 0, 200, 34)
    centres = dict(picker._centres(picker.rect))
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=centres["dark"], button=1)
    assert picker.handle_content_event(ev)
    assert state.value == "dark"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
    print("hands ok")

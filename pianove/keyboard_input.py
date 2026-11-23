"""Play on the computer keyboard, like on a small piano (the layout most music programs use):

    keys     W E   T Y U   O P            black keys
            A S D F G H J K L ; '         white keys: C D E F G A B C D E F
    Z / X   one octave down / up

Keys are matched by their position, not by the letter printed on them, so the same
fingers play the same notes on QWERTY, QWERTZ and AZERTY keyboards. It is on wherever
notes are played: lessons, songs, sight-reading and the keyboard setup pages.
"""
from __future__ import annotations

import pygame

import pianove.context as ctx

# scancode → semitones above the octave's C
_KEYS = {
    pygame.KSCAN_A: 0,  pygame.KSCAN_W: 1,  pygame.KSCAN_S: 2,  pygame.KSCAN_E: 3,
    pygame.KSCAN_D: 4,  pygame.KSCAN_F: 5,  pygame.KSCAN_T: 6,  pygame.KSCAN_G: 7,
    pygame.KSCAN_Y: 8,  pygame.KSCAN_H: 9,  pygame.KSCAN_U: 10, pygame.KSCAN_J: 11,
    pygame.KSCAN_K: 12, pygame.KSCAN_O: 13, pygame.KSCAN_L: 14, pygame.KSCAN_P: 15,
    pygame.KSCAN_SEMICOLON: 16, pygame.KSCAN_APOSTROPHE: 17,
}
_OCT_DOWN, _OCT_UP = pygame.KSCAN_Z, pygame.KSCAN_X
_PAGES = {"lesson", "midi", "midi_setup"}       # where the keys play notes

base_c = 60                     # the note under A: middle C, moved by Z / X
_held: dict[int, int] = {}      # scancode → note sounding


def _playing_page() -> bool:
    return ctx.router is not None and ctx.router.active_page_name in _PAGES


def handle(event: pygame.event.Event) -> bool:
    """For PyLay's App.event_filter: True when the event played (or let go of) a note."""
    global base_c
    if event.type not in (pygame.KEYDOWN, pygame.KEYUP):
        return False
    from pianove.state import midi_panel
    sc = getattr(event, "scancode", None)
    if event.type == pygame.KEYUP:
        note = _held.pop(sc, None)
        if note is not None:
            midi_panel.release(note)
            return True
        return False
    if not _playing_page() or event.mod & (pygame.KMOD_CTRL | pygame.KMOD_ALT | pygame.KMOD_META):
        return False
    if sc in (_OCT_DOWN, _OCT_UP):
        base_c = max(24, min(96, base_c + (12 if sc == _OCT_UP else -12)))
        return True
    if sc not in _KEYS:
        return False
    if sc in _held:                 # the key repeats while held: still the same note
        return True
    note = base_c + _KEYS[sc]
    _held[sc] = note
    midi_panel.press(note)
    return True


def release_all():
    from pianove.state import midi_panel
    for note in _held.values():
        midi_panel.release(note)
    _held.clear()

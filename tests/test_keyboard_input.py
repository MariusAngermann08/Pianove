"""Playing without an instrument: the computer keyboard and the keys on screen."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402
import pianove  # noqa: E402,F401
import pianove.context as ctx  # noqa: E402
from pianove import keyboard_input  # noqa: E402
from pianove.state import midi_panel  # noqa: E402


def _key(kind, scancode, mod=0):
    return pygame.event.Event(kind, scancode=scancode, key=0, mod=mod, unicode="")


def setup_function():
    keyboard_input.release_all()
    keyboard_input.base_c = 60
    midi_panel.take_note_ons()


def test_keys_play_notes_on_a_playing_page(monkeypatch):
    monkeypatch.setattr(ctx, "router", SimpleNamespace(active_page_name="lesson"))
    assert keyboard_input.handle(_key(pygame.KEYDOWN, pygame.KSCAN_A))      # C4
    assert keyboard_input.handle(_key(pygame.KEYDOWN, pygame.KSCAN_E))      # D#4
    assert midi_panel.take_note_ons() == [60, 63]
    assert {60, 63} <= midi_panel.active_notes
    assert keyboard_input.handle(_key(pygame.KEYDOWN, pygame.KSCAN_A))      # key repeat: nothing new
    assert midi_panel.take_note_ons() == []
    keyboard_input.handle(_key(pygame.KEYUP, pygame.KSCAN_A))
    assert 60 not in midi_panel.active_notes


def test_octave_keys(monkeypatch):
    monkeypatch.setattr(ctx, "router", SimpleNamespace(active_page_name="lesson"))
    keyboard_input.handle(_key(pygame.KEYDOWN, pygame.KSCAN_X))
    keyboard_input.handle(_key(pygame.KEYDOWN, pygame.KSCAN_K))             # C one octave up, +12
    assert midi_panel.take_note_ons() == [84]


def test_other_pages_and_shortcuts_are_left_alone(monkeypatch):
    monkeypatch.setattr(ctx, "router", SimpleNamespace(active_page_name="lesson_editor"))
    assert not keyboard_input.handle(_key(pygame.KEYDOWN, pygame.KSCAN_A))  # typing in the editor
    monkeypatch.setattr(ctx, "router", SimpleNamespace(active_page_name="lesson"))
    assert not keyboard_input.handle(_key(pygame.KEYDOWN, pygame.KSCAN_S, pygame.KMOD_CTRL))
    assert midi_panel.take_note_ons() == []

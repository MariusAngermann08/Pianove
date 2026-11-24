"""A metronome click for playing in tempo: a short wooden tick, louder on the first beat
of the bar. Made with numpy and played through pygame's mixer, so it works without
FluidSynth too. Switched on and off in a song's settings (storage["metronome"])."""
from __future__ import annotations

import numpy as np
import pygame

_sounds: dict[bool, pygame.mixer.Sound] = {}


def _make(accent: bool) -> pygame.mixer.Sound | None:
    if not pygame.mixer.get_init():
        return None
    rate, _, channels = pygame.mixer.get_init()
    n = int(rate * 0.045)
    t = np.arange(n) / rate
    freq = 1900.0 if accent else 1350.0
    wave = np.sin(2 * np.pi * freq * t) * np.exp(-t * 95.0)
    wave *= 0.55 if accent else 0.38
    pcm = (wave * 32767).astype(np.int16)
    if channels > 1:
        pcm = np.repeat(pcm[:, None], channels, axis=1)
    return pygame.sndarray.make_sound(np.ascontiguousarray(pcm))


def click(accent: bool = False):
    try:
        if accent not in _sounds:
            snd = _make(accent)
            if snd is None:
                return
            _sounds[accent] = snd
        _sounds[accent].play()
    except Exception:          # no audio device: the metronome stays silent
        pass


def enabled() -> bool:
    from pianove.state import storage
    return bool(storage.get("metronome", False))


def set_enabled(on: bool):
    from pianove.state import storage
    storage.set("metronome", bool(on))

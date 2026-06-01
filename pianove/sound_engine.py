"""
Built-in piano synthesizer — pygame.mixer + numpy only.
No FluidSynth, no soundfont files, no external C libraries required.

Additive synthesis: fundamental + 6 harmonics, each with its own exponential
decay, so lower notes sustain longer and higher partials fade first — the
characteristic behaviour of a real piano string.

Public API
----------
    init()              — pre-generate note cache (call after App() is created)
    play(note, vel)     — note-on  (MIDI 0-127, velocity 0-127)
    stop(note)          — note-off with short fade to avoid click
    set_enabled(bool)   — global on/off (wired to the settings toggle)
"""

import threading
import numpy as np
import pygame

_POLYPHONY = 32   # mixer channels reserved for piano

_enabled     = False
_cache: dict[int, "pygame.mixer.Sound"] = {}
_cache_lock  = threading.Lock()
_active: dict[int, "pygame.mixer.Channel"] = {}   # note → active channel


# ── Synthesis ─────────────────────────────────────────────────────────────────

def _midi_freq(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def _build_sound(midi_note: int) -> "pygame.mixer.Sound":
    info = pygame.mixer.get_init()
    sr   = info[0] if info else 44100

    freq     = _midi_freq(midi_note)
    # Lower notes sustain longer (3.0 s for C7, 5.5 s for C1)
    duration = 3.0 + max(0, 127 - midi_note) / 127.0 * 2.5
    n        = int(sr * duration)
    t        = np.linspace(0.0, duration, n, endpoint=False)

    # Additive synthesis: (harmonic, amplitude, decay-rate multiplier)
    # Higher partials decay faster — gives a bright attack, mellow sustain
    partials = [
        (1, 1.00, 1.0),
        (2, 0.45, 1.7),
        (3, 0.20, 2.4),
        (4, 0.10, 3.1),
        (5, 0.06, 3.9),
        (6, 0.03, 4.8),
        (7, 0.015, 5.8),
    ]
    # Base decay time-constant: 0.5 s (high notes) to 4.0 s (low notes)
    base_tc = 0.5 + max(0, 127 - midi_note) / 127.0 * 3.5

    wave = np.zeros(n, dtype=np.float64)
    for h, amp, dr in partials:
        tc    = base_tc / dr
        wave += amp * np.sin(2.0 * np.pi * h * freq * t) * np.exp(-t / tc)

    # 3 ms linear attack ramp — prevents the hard click on note onset
    ramp = min(int(sr * 0.003), n)
    wave[:ramp] *= np.linspace(0.0, 1.0, ramp)

    # Normalise then scale to int16 with 15 % headroom
    peak = np.max(np.abs(wave))
    if peak > 0:
        wave *= 28000.0 / peak
    samples = wave.astype(np.int16)

    # Interleave into (n, 2) stereo array
    stereo      = np.empty((n, 2), dtype=np.int16)
    stereo[:, 0] = samples
    stereo[:, 1] = samples

    return pygame.sndarray.make_sound(stereo)


# ── Cache ─────────────────────────────────────────────────────────────────────

def _ensure(midi_note: int) -> "pygame.mixer.Sound":
    with _cache_lock:
        if midi_note not in _cache:
            _cache[midi_note] = _build_sound(midi_note)
        return _cache[midi_note]


def _warm():
    """Pre-generate C2–C7 (the typical playing range) in a background thread."""
    for note in range(36, 97):
        _ensure(note)


# ── Public API ────────────────────────────────────────────────────────────────

def init():
    """Reserve mixer channels and start background note pre-generation."""
    pygame.mixer.set_num_channels(_POLYPHONY)
    threading.Thread(target=_warm, daemon=True).start()


def play(midi_note: int, velocity: int = 80):
    if not _enabled:
        return
    snd = _ensure(midi_note)
    vol = max(0.05, min(1.0, velocity / 100.0))
    ch  = snd.play()
    if ch is not None:
        ch.set_volume(vol)
        # Stop any previous instance of the same note (re-strike)
        old = _active.get(midi_note)
        if old is not None:
            old.fadeout(30)
        _active[midi_note] = ch


def stop(midi_note: int):
    ch = _active.pop(midi_note, None)
    if ch is not None:
        ch.fadeout(80)   # 80 ms fade avoids an audible click on note-off


def set_enabled(val: bool):
    global _enabled
    _enabled = bool(val)
    if not _enabled:
        for ch in list(_active.values()):
            ch.fadeout(80)
        _active.clear()

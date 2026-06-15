"""
FluidSynth-backed piano sound engine.

Replaces the additive-synthesis engine with real sampled grand piano sound
via pyFluidSynth + GeneralUser GS soundfont (GM program 0 = Acoustic Grand Piano).

Public API is identical to sound_engine.py:
    init()              — start loading soundfont in background thread
    play(note, vel)     — note-on  (MIDI 0-127, velocity 0-127)
    stop(note)          — note-off
    set_enabled(bool)   — global on/off (wired to the settings toggle)
"""

import os
import sys
import pathlib
import threading

# ── Tell pyFluidSynth where our bundled DLL lives ─────────────────────────────
_BIN_DIR = str(pathlib.Path(__file__).parent.parent / "bin")
if hasattr(os, "add_dll_directory"):          # Python 3.8+ on Windows
    os.add_dll_directory(_BIN_DIR)
os.environ["PATH"] = _BIN_DIR + os.pathsep + os.environ.get("PATH", "")

import fluidsynth  # pyfluidsynth

# ── Paths ─────────────────────────────────────────────────────────────────────
_SF2_PATH = str(
    pathlib.Path(__file__).parent / "assets" / "soundfonts" / "GeneralUser-GS.sf2"
)

_CHANNEL = 0   # MIDI channel for piano
_PROGRAM = 0   # GM program 0 = Acoustic Grand Piano
_BANK    = 0

_fs:      "fluidsynth.Synth | None" = None
_sfid:    int = -1
_enabled: bool = False
_ready:   bool = False      # True once soundfont is loaded and audio is live
_lock     = threading.Lock()


# ── Internal ──────────────────────────────────────────────────────────────────

def _load():
    global _fs, _sfid, _ready
    try:
        fs = fluidsynth.Synth(gain=0.6)
        fs.start(driver="dsound")
        sfid = fs.sfload(_SF2_PATH)
        if sfid == -1:
            fs.delete()
            print("[sound_engine_fs] Could not load soundfont — audio disabled",
                  file=sys.stderr)
            return
        fs.program_select(_CHANNEL, sfid, _BANK, _PROGRAM)
        with _lock:
            _fs    = fs
            _sfid  = sfid
            _ready = True
    except Exception as exc:
        print(f"[sound_engine_fs] Init failed — audio disabled: {exc}",
              file=sys.stderr)


# ── Public API ────────────────────────────────────────────────────────────────

def init():
    """Start loading soundfont in a background thread (non-blocking)."""
    threading.Thread(target=_load, daemon=True).start()


def play(midi_note: int, velocity: int = 80):
    if not _enabled or not _ready:
        return
    with _lock:
        if _fs is not None:
            _fs.noteon(_CHANNEL, midi_note, max(1, min(127, velocity)))


def play_raw(midi_note: int, velocity: int = 80):
    """Play regardless of the enabled toggle — for boot/intro sounds."""
    if not _ready:
        return
    with _lock:
        if _fs is not None:
            _fs.noteon(_CHANNEL, midi_note, max(1, min(127, velocity)))


def stop(midi_note: int):
    if not _ready:
        return
    with _lock:
        if _fs is not None:
            _fs.noteoff(_CHANNEL, midi_note)


def set_volume(normalized: float):
    """Set output gain. normalized is 0.0–1.0, mapped to FluidSynth gain 0.0–2.0."""
    gain = max(0.0, min(2.0, float(normalized) * 2.0))
    with _lock:
        if _fs is not None:
            _fs.setting("synth.gain", gain)


def set_enabled(val: bool):
    global _enabled
    _enabled = bool(val)
    if not _enabled and _ready:
        with _lock:
            if _fs is not None:
                for note in range(128):
                    _fs.noteoff(_CHANNEL, note)

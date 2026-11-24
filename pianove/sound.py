"""Pianove's piano sound: the one place the rest of the app plays notes through.

On the desktop that is FluidSynth with the bundled Salamander grand (sound_engine_fs).
A build for another platform can put a different engine behind the same functions here,
so nothing else in the app has to change.
"""
from pianove.sound_engine_fs import (init, play, play_raw, stop, set_sustain_pedal,  # noqa: F401
                                     set_volume, set_enabled, shutdown, add_note_hook,
                                     is_ready)


def all_off():
    """Silence everything."""
    set_sustain_pedal(0)
    for note in range(128):
        stop(note)


def unavailable_reason() -> str:
    """Why there is no piano sound ("" when there is, or while it is still loading)."""
    from pianove import sound_engine_fs
    return sound_engine_fs.unavailable_reason

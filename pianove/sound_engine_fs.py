import os
import sys
import pathlib
import threading

_BIN_DIR = str(pathlib.Path(__file__).parent.parent / "bin")
if hasattr(os, "add_dll_directory"):          # Python 3.8+ on Windows
    os.add_dll_directory(_BIN_DIR)
os.environ["PATH"] = _BIN_DIR + os.pathsep + os.environ.get("PATH", "")

import fluidsynth  # pyfluidsynth

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
_pending_gain: float = 100.0  # applied on load if set_volume was called early


_PLATFORM_DRIVERS: "dict[str, list[str]]" = {
    "win32":  ["dsound"],
    "darwin": ["coreaudio"],
}
_LINUX_DRIVERS = ["pulseaudio", "alsa", "jack", "oss"]


def _load():
    global _fs, _sfid, _ready
    try:
        fs = fluidsynth.Synth(gain=_pending_gain)
        candidates = _PLATFORM_DRIVERS.get(sys.platform, _LINUX_DRIVERS)
        for driver in candidates:
            fs.start(driver=driver)
            if fs.audio_driver:   # NULL means the driver failed to init
                break
            fs.audio_driver = None
        if not fs.audio_driver:
            raise RuntimeError(f"No working audio driver found (tried: {candidates})")
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



def init():
    threading.Thread(target=_load, daemon=True).start()


def play(midi_note: int, velocity: int = 80):
    if not _enabled or not _ready:
        return
    with _lock:
        if _fs is not None:
            _fs.noteon(_CHANNEL, midi_note, max(1, min(127, velocity)))


def play_raw(midi_note: int, velocity: int = 80):
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
    global _pending_gain
    gain = max(0.0, min(100.0, float(normalized) * 100.0))
    _pending_gain = gain
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

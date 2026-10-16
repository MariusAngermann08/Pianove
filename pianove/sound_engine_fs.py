import atexit
import json
import os
import shutil
import subprocess
import sys
import pathlib
import threading
import time

_BIN_DIR = str(pathlib.Path(__file__).parent.parent / "bin")
if hasattr(os, "add_dll_directory"):          # Python 3.8+ on Windows
    os.add_dll_directory(_BIN_DIR)
os.environ["PATH"] = _BIN_DIR + os.pathsep + os.environ.get("PATH", "")

import fluidsynth  # pyfluidsynth

_SF2_PATH = str(
    pathlib.Path(__file__).parent / "assets" / "soundfonts" / "SalamanderC5-Light.sf2"
)

_CHANNEL = 0   # MIDI channel for piano
_PROGRAM = 0   # GM program 0 = Acoustic Grand Piano
_BANK    = 0

_fs:      "fluidsynth.Synth | None" = None
_sfid:    int = -1
_enabled: bool = False
_ready:   bool = False      # True once soundfont is loaded and audio is live
_lock     = threading.Lock()

# fluidsynth's "synth.gain" setting only accepts values in [0.0, 10.0] — anything
# outside that range is silently rejected by libfluidsynth, which leaves the gain
# stuck at its built-in default (0.2, very quiet) no matter what the UI slider is
# set to. Map the 0..1 UI slider onto a safe, non-clipping chunk of that range.
_MAX_GAIN = 5.0
_pending_gain: float = _MAX_GAIN  # applied on load if set_volume was called early


_PLATFORM_DRIVERS: "dict[str, list[str]]" = {
    "win32":  ["dsound"],
    "darwin": ["coreaudio"],
}
_LINUX_DRIVERS = ["pulseaudio", "alsa", "jack", "oss"]


def _load():
    global _fs, _sfid, _ready
    try:
        # audio.realtime-prio defaults to a non-zero value in libfluidsynth, which
        # makes it try to bump the audio thread to a real-time scheduling priority.
        # Without elevated privileges (CAP_SYS_NICE / an rtprio ulimit) that call
        # always fails, and it logs a "failed to set high priority" warning on
        # every startup. Telling it not to try avoids the failure outright — audio
        # still plays fine at normal priority.
        fs = fluidsynth.Synth(gain=_pending_gain, **{"audio.realtime-prio": 0})
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
        _unmute_pipewire_stream()
    except Exception as exc:
        print(f"[sound_engine_fs] Init failed — audio disabled: {exc}",
              file=sys.stderr)


def _unmute_pipewire_stream():
    """WirePlumber (PipeWire's session manager) persists a per-application
    stream volume across launches, keyed by application name. If some earlier
    run — or the user's mixer — ever turned "FluidSynth" down, that saved
    volume silently attenuates us on every future launch, on top of the
    system's master volume and completely independent of synth.gain / the
    in-app slider. Best-effort: find our own stream and force it back to
    100%, so the in-app slider is the only thing left attenuating our output.
    """
    if sys.platform != "linux" or not (shutil.which("pw-dump") and shutil.which("wpctl")):
        return
    pid = os.getpid()
    for _ in range(30):  # the stream can take a moment to register after start()
        try:
            raw = subprocess.run(["pw-dump"], capture_output=True, text=True,
                                  timeout=2).stdout
            nodes = json.loads(raw)
        except Exception:
            return
        for node in nodes:
            props = (node.get("info") or {}).get("props") or {}
            if (props.get("application.name") == "FluidSynth"
                    and props.get("application.process.id") == pid
                    and props.get("media.class") == "Stream/Output/Audio"):
                try:
                    subprocess.run(["wpctl", "set-volume", str(node["id"]), "1.0"],
                                   timeout=2, capture_output=True)
                except Exception:
                    pass
                return
        time.sleep(0.1)



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


def set_sustain_pedal(value: int):
    """Forward a raw damper/sustain pedal (MIDI CC 64) value, 0-127.

    FluidSynth handles the actual hold behaviour internally once it sees this
    CC: notes keep ringing after note-off while the pedal is above the
    half-way point, and release together when it's lifted — no extra state
    needed on our side.
    """
    if not _ready:
        return
    with _lock:
        if _fs is not None:
            _fs.cc(_CHANNEL, 64, max(0, min(127, int(value))))


def set_volume(normalized: float):
    global _pending_gain
    gain = max(0.0, min(_MAX_GAIN, float(normalized) * _MAX_GAIN))
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
                _fs.cc(_CHANNEL, 64, 0)  # release the damper pedal so nothing keeps ringing
                for note in range(128):
                    _fs.noteoff(_CHANNEL, note)


def shutdown():
    """Release the audio driver/device.

    Without this, the audio driver (and the ALSA/PulseAudio device handle it
    holds) stays open for as long as the process lives — if the app is closed
    or crashes without calling delete(), the sound card can be left locked so
    no other application (or Pianove itself, on the next launch) can open it.
    """
    global _fs, _ready
    with _lock:
        if _fs is not None:
            try:
                _fs.delete()
            except Exception as exc:
                print(f"[sound_engine_fs] Error during shutdown: {exc}",
                      file=sys.stderr)
            _fs = None
        _ready = False


atexit.register(shutdown)

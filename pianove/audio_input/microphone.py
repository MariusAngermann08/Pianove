"""The microphone side of the piano sound detection engine.

Opens an input device (through sounddevice/PortAudio when it is installed, otherwise
through SDL's own capture in pygame), runs the detector on its own thread so the UI's
frame rate never matters, and hands the notes it hears to whoever calls poll().

The microphone is only kept open while someone polls it: a few seconds after the last
poll (no page with a keyboard on screen) it is closed again, and the next poll opens it.
"""
from __future__ import annotations

import queue
import threading
import time
from collections import deque

import numpy as np

from pianove.audio_input.detector import NoteEvent, PianoNoteDetector

_IDLE_CLOSE_S = 5.0          # close the microphone this long after the last poll
_BLOCK = 256                 # samples per capture block (~6 ms at 44.1 kHz)


def _sounddevice():
    try:
        import sounddevice as sd
        return sd
    except Exception:        # not installed, or PortAudio missing
        return None


def list_input_devices() -> list[str]:
    sd = _sounddevice()
    if sd is not None:
        try:
            return [d["name"] for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]
        except Exception:
            pass
    try:
        from pygame._sdl2 import audio as sdl_audio
        return list(sdl_audio.get_audio_device_names(True))
    except Exception:
        return []


class _SoundDeviceStream:
    def __init__(self, device, on_block):
        sd = _sounddevice()
        info = sd.query_devices(device, "input")
        self.name = info["name"]
        self.sample_rate = int(info["default_samplerate"]) or 44100

        def _cb(indata, frames, t, status):
            on_block(indata[:, 0].copy())

        self._stream = sd.InputStream(device=device, channels=1, dtype="float32",
                                      samplerate=self.sample_rate, blocksize=_BLOCK,
                                      latency="low", callback=_cb)
        self._stream.start()

    def close(self):
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass


class _SDLStream:
    def __init__(self, device, on_block):
        import pygame
        from pygame._sdl2 import audio as sdl_audio
        if not pygame.get_init():
            pygame.init()
        names = list(sdl_audio.get_audio_device_names(True))
        if not names:
            raise RuntimeError("no capture device")
        self.name = device if device in names else names[0]
        self.sample_rate = 44100

        def _cb(_dev, mem):
            on_block(np.frombuffer(mem, dtype=np.float32).copy())

        self._dev = sdl_audio.AudioDevice(devicename=self.name, iscapture=True,
                                          frequency=self.sample_rate,
                                          audioformat=sdl_audio.AUDIO_F32, numchannels=1,
                                          chunksize=_BLOCK, allowed_changes=0, callback=_cb)
        self._dev.pause(0)

    def close(self):
        try:
            self._dev.pause(1)
            self._dev.close()
        except Exception:
            pass


class Microphone:
    """Listens to a piano through a microphone. Thread-safe; poll() from the UI thread."""

    def __init__(self, device: str | int | None = None, sensitivity: float = 1.0):
        self.device = device
        self._sensitivity = float(sensitivity)
        self._stream = None
        self._detector: PianoNoteDetector | None = None
        self._blocks: queue.Queue = queue.Queue(maxsize=400)
        self._events: deque[NoteEvent] = deque(maxlen=256)
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_poll = 0.0
        self._last_attempt = -1e9
        self._mutes: list[tuple[int, float]] = []
        self.name = ""
        self.error = ""
        self.level = 0.0
        self.active_notes: frozenset[int] = frozenset()

    # -- opening and closing --

    @property
    def is_open(self) -> bool:
        return self._stream is not None

    def open(self) -> bool:
        if self._stream is not None:
            return True
        now = time.monotonic()
        if now - self._last_attempt < 2.0:          # don't hammer a missing device
            return False
        self._last_attempt = now
        errors = []
        for backend in (_SoundDeviceStream, _SDLStream):
            if backend is _SoundDeviceStream and _sounddevice() is None:
                continue
            try:
                self._drain_blocks()
                stream = backend(self.device, self._on_block)
                break
            except Exception as e:                    # try the next way in
                errors.append(f"{backend.__name__}: {e}")
        else:
            self.error = "; ".join(errors) or "no audio input available"
            return False
        with self._lock:
            self._detector = PianoNoteDetector(stream.sample_rate, sensitivity=self._sensitivity)
        self._stream = stream
        self._last_poll = time.monotonic()            # don't count as idle straight away
        self.name = stream.name
        self.error = ""
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, daemon=True, name="piano-ears")
        self._worker.start()
        return True

    def close(self):
        self._stop.set()
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.close()
        if self._worker is not None and self._worker is not threading.current_thread():
            self._worker.join(timeout=1.0)
        self._worker = None
        with self._lock:
            self._detector = None
        self.active_notes = frozenset()
        self.level = 0.0

    # -- what the UI calls --

    def poll(self) -> list[NoteEvent]:
        """Every note struck or let go since the last poll (opens the microphone if needed)."""
        self._last_poll = time.monotonic()
        if self._stream is None:
            self.open()
        out = []
        while self._events:
            out.append(self._events.popleft())
        return out

    def mute(self, note: int, seconds: float):
        """Pianove is about to play this key through the speakers: don't hear it as played."""
        with self._lock:
            self._mutes.append((note, seconds))

    @property
    def sensitivity(self) -> float:
        return self._sensitivity

    @sensitivity.setter
    def sensitivity(self, value: float):
        self._sensitivity = float(value)
        with self._lock:
            if self._detector is not None:
                self._detector.sensitivity = self._sensitivity

    # -- the listening thread --

    def _on_block(self, block: np.ndarray):
        try:
            self._blocks.put_nowait(block)
        except queue.Full:                            # the worker fell behind: drop the oldest
            try:
                self._blocks.get_nowait()
                self._blocks.put_nowait(block)
            except Exception:
                pass

    def _drain_blocks(self):
        while True:
            try:
                self._blocks.get_nowait()
            except queue.Empty:
                return

    def _run(self):
        while not self._stop.is_set():
            if time.monotonic() - self._last_poll > _IDLE_CLOSE_S:
                threading.Thread(target=self.close, daemon=True).start()
                return
            try:
                block = self._blocks.get(timeout=0.1)
            except queue.Empty:
                continue
            with self._lock:
                det = self._detector
                if det is not None:
                    for note, secs in self._mutes:
                        det.mute(note, secs)
                    self._mutes.clear()
            if det is None:
                continue
            try:
                events = det.process(block)
            except Exception as e:                    # never let one bad block end listening
                print(f"[microphone] detector error: {e}")
                continue
            self._events.extend(events)
            self.level = det.level
            self.active_notes = frozenset(det.active_notes)

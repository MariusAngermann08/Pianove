"""Your take: what you played in tempo (and what Pianove played with you), to listen back
to and to keep as an audio file.

A take is a list of (seconds, 1 on / 0 off, key, velocity, staff) from the lesson page.
Listening uses the same player as a song's "Listen"; saving renders the notes offline
with FluidSynth and the bundled piano into a WAV file in ~/Music/Pianove (or ~/Pianove).
"""
from __future__ import annotations

import re
import wave
from datetime import datetime
from pathlib import Path

_last: dict = {"take": [], "title": ""}
_playing: list = [None]


def keep(take: list, title: str):
    _last["take"] = sorted(take, key=lambda e: (e[0], e[1]))
    _last["title"] = title


def has_take() -> bool:
    return any(e[1] for e in _last["take"])


def _events(take):
    if not take:
        return [], 0.0
    t0 = min(e[0] for e in take)
    events = [(round(t - t0, 4), k, m, v, si) for t, k, m, v, si in take]
    total = max(e[0] for e in events) + 1.5
    return events, total


def play():
    """Listen to the last take (again from the start)."""
    stop()
    from pianove.pages.lesson import _Player
    events, total = _events(_last["take"])
    if not events:
        return
    p = _Player(events, total)
    p.play()
    _playing[0] = p


def stop():
    p, _playing[0] = _playing[0], None
    if p is not None:
        p.close()


def is_playing() -> bool:
    return _playing[0] is not None and _playing[0].playing


def folder() -> Path:
    music = Path.home() / "Music"
    return (music if music.is_dir() else Path.home()) / "Pianove"


def save(rate: int = 44100) -> Path:
    """Render the last take to a WAV file and return its path."""
    import numpy as np
    import fluidsynth                                    # FluidSynth renders it offline
    from pianove.sound_engine_fs import _SF2_PATH
    events, total = _events(_last["take"])
    if not events:
        raise ValueError("nothing was recorded")
    fs = fluidsynth.Synth(samplerate=float(rate), gain=0.6)
    sf = fs.sfload(_SF2_PATH)
    fs.program_select(0, sf, 0, 0)
    chunks, pos = [], 0
    for t, kind, key, vel, _ in events:
        target = int(round(t * rate))
        if target > pos:
            chunks.append(np.asarray(fs.get_samples(target - pos), dtype=np.int16))
            pos = target
        if kind:
            fs.noteon(0, int(key), max(1, min(127, int(vel or 80))))
        else:
            fs.noteoff(0, int(key))
    end = int(round(total * rate))
    if end > pos:
        chunks.append(np.asarray(fs.get_samples(end - pos), dtype=np.int16))
    fs.delete()
    audio = np.concatenate(chunks).astype(np.float32)
    peak = float(np.abs(audio).max() or 1.0)
    audio = (audio * min(1.0, 0.89 * 32767 / peak)).astype(np.int16)
    out = folder()
    out.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^\w\- ]+", "", _last["title"] or "Pianove").strip() or "Pianove"
    path = out / f"{name} {datetime.now():%Y-%m-%d %H-%M}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(audio.tobytes())
    return path

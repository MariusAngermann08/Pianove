"""The piano sound detection engine: it hears the keys played on a piano through a
microphone — single notes, chords, a key struck again, a piano out of tune, quiet or
loud — and nothing in a room where nobody plays. Plus the microphone input in the
keyboard panel: heard notes count as key presses, and Pianove's own notes don't.

The recordings are made with FluidSynth (pyfluidsynth) from the bundled grand piano and,
where installed, other soundfonts; those tests are skipped without it.

Run:  python -m pytest tests/test_audio_input.py -q      (or just: python tests/test_audio_input.py)
For the full benchmark:  python scripts/eval_audio_detection.py
"""
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np  # noqa: E402

import pianove  # noqa: E402,F401  (puts PyLay and PyLute on the path)
import piano_audio as pa  # noqa: E402
from pianove.audio_input.detector import (  # noqa: E402
    GRID, PianoNoteDetector, Spectrum, load_templates)

SR = 44100

try:
    import pytest
    needs_synth = pytest.mark.skipif(not pa.have_fluidsynth(), reason="pyfluidsynth not installed")
except ImportError:                      # plain `python tests/test_audio_input.py`
    def needs_synth(fn):
        return fn


def _heard(audio, **kw):
    return pa.run_detector(audio, SR, **kw)


def _scale(t0=0.3, step=0.45, vel=80):
    return [(t0 + i * step, t0 + i * step + step * 0.9, m, vel)
            for i, m in enumerate([60, 62, 64, 65, 67, 69, 71, 72])]


def test_spectrum_puts_a_tone_on_its_key():
    spec = Spectrum(SR)
    t = np.arange(spec.win) / SR
    for f, midi in ((440.0, 69), (261.63, 60), (110.0, 45), (2093.0, 96)):
        P = spec(np.sin(2 * np.pi * f * t).astype(np.float32))
        assert abs(GRID[int(np.argmax(P))] - midi) < 0.34, (f, GRID[int(np.argmax(P))])


def test_templates_ship_with_the_app():
    W = load_templates()
    assert W is not None and np.all(np.isfinite(W)) and W.min() >= 0


def test_silence_and_room_noise_play_nothing():
    rng = np.random.default_rng(0)
    assert _heard(np.zeros(SR * 3, np.float32)) == []
    hiss = (rng.standard_normal(SR * 6) * 0.01).astype(np.float32)
    assert _heard(hiss) == []
    hum = (0.02 * np.sin(2 * np.pi * 50 * np.arange(SR * 6) / SR)).astype(np.float32)
    assert _heard(hum + hiss) == []


@needs_synth
def test_a_scale_is_heard_note_for_note():
    notes = _scale()
    for name, sf2 in pa.soundfonts().items():
        x = pa.room(pa.render(notes, sf2), SR, snr_db=35, rt60=0.3, mic=True, seed=1)
        s = pa.score(notes, _heard(x))
        assert s["r"] == 1.0 and s["p"] >= 0.88, (name, s["misses"], s["false"])
        assert s["latency_ms"] < 120, (name, s["latency_ms"])


@needs_synth
def test_chords_are_heard_together():
    notes = []
    for i, chord in enumerate([(60, 64, 67), (57, 60, 64), (53, 57, 60, 65), (55, 59, 62, 67), (48, 55, 64)]):
        notes += [(0.3 + i * 0.9, 1.1 + i * 0.9, m, 85) for m in chord]
    x = pa.room(pa.render(notes, pa.BUNDLED_SF2), SR, snr_db=35, rt60=0.3, mic=True, seed=2)
    s = pa.score(notes, _heard(x))
    assert s["r"] >= 0.9 and s["p"] >= 0.9, (s["misses"], s["false"])


@needs_synth
def test_a_key_struck_again_counts_again():
    notes = [(0.3 + i * 0.3, 0.3 + i * 0.3 + 0.27, 67, 85) for i in range(4)]
    notes += [(2.0 + i * 0.3, 2.0 + i * 0.3 + 0.27, 52, 85) for i in range(4)]
    s = pa.score(notes, _heard(pa.render(notes, pa.BUNDLED_SF2)))
    assert s["tp"] >= 7 and s["p"] >= 0.85, (s["misses"], s["false"])


@needs_synth
def test_loud_or_quiet_the_same_notes():
    notes = _scale()
    x = pa.render(notes, pa.BUNDLED_SF2)
    for gain_db in (-30, 0, 18):
        y = pa.room(x, SR, snr_db=40, gain_db=gain_db, seed=3)
        s = pa.score(notes, _heard(y))
        assert s["r"] == 1.0 and s["p"] >= 0.88, (gain_db, s["misses"], s["false"])


@needs_synth
def test_a_piano_out_of_tune_is_still_heard_right():
    rng = random.Random(5)
    notes = [(0.3 + i * 0.4, 0.65 + i * 0.4, rng.randint(48, 84), 80) for i in range(40)]
    x = pa.render(notes, pa.BUNDLED_SF2, cents=-38)
    det = PianoNoteDetector(SR)
    heard = []
    for i in range(0, len(x), 512):
        heard += [(e.onset, e.note, e.time) for e in det.process(x[i:i + 512]) if e.on]
    assert 2 ** (-45 / 1200) * 440 < det.a4 < 2 ** (-30 / 1200) * 440, det.a4
    later = [n for n in notes if n[0] > 6.0]                   # once it has followed the tuning
    s = pa.score(later, [h for h in heard if h[0] > 5.9])
    assert s["r"] >= 0.95 and s["p"] >= 0.9, (s["misses"], s["false"])


@needs_synth
def test_muted_keys_are_not_reported():
    notes = _scale()
    x = pa.render(notes, pa.BUNDLED_SF2)
    det = PianoNoteDetector(SR)
    det.mute(64, 30.0)
    heard = []
    for i in range(0, len(x), 512):
        heard += [e.note for e in det.process(x[i:i + 512]) if e.on]
    assert 64 not in heard and 62 in heard and 65 in heard


@needs_synth
def test_knowing_what_comes_next_still_hears_wrong_notes():
    notes = _scale()
    x = pa.room(pa.render(notes, pa.BUNDLED_SF2), SR, snr_db=30, rt60=0.3, mic=True, seed=4)
    for expected in ({60, 62, 64, 65, 67, 69, 71, 72}, {30, 90}):   # the right keys, the wrong ones
        det = PianoNoteDetector(SR)
        det.expect(expected)
        heard = []
        for i in range(0, len(x), 512):
            heard += [(e.onset, e.note, e.time) for e in det.process(x[i:i + 512]) if e.on]
        s = pa.score(notes, heard)
        assert s["r"] >= 0.99 and s["p"] >= 0.85, (expected, s)


# --- the keyboard panel with the microphone as input ------------------------------------

class _FakeMic:
    def __init__(self):
        self.events, self.muted, self.is_open, self.name, self.level = [], [], True, "Test mic", 0.1
        self.sensitivity = 1.0

    def poll(self):
        out, self.events = self.events, []
        return out

    def open(self):
        return True

    def close(self):
        pass

    def mute(self, note, seconds):
        self.muted.append((note, seconds))


def test_panel_takes_heard_notes_as_key_presses():
    import pygame
    pygame.init()
    from pianove.audio_input.detector import NoteEvent
    from pianove.midi import panel as P
    import pianove.sound_engine_fs as se

    played = []
    orig_play = se.play
    se.play = lambda note, vel=80: played.append(note)
    try:
        mp = P.MidiPanel(text_fn=lambda k, **kw: k)
        mp.set_input_mode(P.INPUT_MIC)
        mic = mp.mic = _FakeMic()
        mp._poll_devices()
        assert mp.connected and mp.status_text() == "mic_listening"
        mic.events = [NoteEvent(True, 60, 90, 0.0, 0.05), NoteEvent(True, 64, 80, 0.0, 0.05)]
        mp._poll_messages()
        assert mp.active_notes == {60, 64}
        assert mp.take_note_ons() == [60, 64]
        assert played == []                      # the piano sounds by itself
        mic.events = [NoteEvent(False, 60, 0, 0.5, 0.5)]
        mp._poll_messages()
        assert mp.active_notes == {64}
        mp.hear_own_note(72, True)
        mp.hear_own_note(72, False)
        assert [n for n, _ in mic.muted] == [72, 72] and mic.muted[0][1] > mic.muted[1][1]
        mp.set_input_mode(P.INPUT_MIDI)
        assert not mp.connected and mp.active_notes == set()
    finally:
        se.play = orig_play


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            if getattr(fn, "pytestmark", None) and not pa.have_fluidsynth():
                print("skip", name)
                continue
            fn()
            print("ok  ", name)

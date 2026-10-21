"""Piano recordings made up for testing the note detector: notes rendered through
FluidSynth with a soundfont, then made to sound more like a microphone in a room
(noise, reverb, a cheap mic's frequency response, a slightly out-of-tune piano).

Also the scoring: which of the notes played were heard, and what was heard that
was never played.
"""
from __future__ import annotations

import glob
import json
import os
import random

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
BUNDLED_SF2 = os.path.join(ROOT, "pianove", "assets", "soundfonts", "SalamanderC5-Light.sf2")

# other pianos to test with (Debian/Ubuntu packages fluid-soundfont-gm, timgm6mb-soundfont,
# musescore-general-soundfont-small, csound-soundfont) — whichever are installed
SYSTEM_SOUNDFONTS = {
    "fluidr3":   "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "timgm6mb":  "/usr/share/sounds/sf2/TimGM6mb.sf2",
    "musescore": "/usr/share/sounds/sf3/MuseScore_General_Lite.sf3",
    "gmbank":    "/usr/share/sounds/sf2/sf_GMbank.sf2",
}


def soundfonts() -> dict[str, str]:
    out = {"salamander": BUNDLED_SF2} if os.path.exists(BUNDLED_SF2) else {}
    out.update({k: v for k, v in SYSTEM_SOUNDFONTS.items() if os.path.exists(v)})
    return out


def have_fluidsynth() -> bool:
    try:
        import fluidsynth  # noqa: F401
        return True
    except Exception:
        return False


# a note: (onset seconds, offset seconds, midi, velocity)

def render(notes, sf2: str, sr: int = 44100, tail: float = 1.0, cents: float = 0.0,
           pedal: list[tuple[float, int]] | None = None, reverb: bool = True) -> np.ndarray:
    """The notes played on the soundfont's piano, mono float32 in -1..1.
    cents detunes the whole piano; pedal is [(time, 0..127)] for the damper pedal."""
    import fluidsynth
    fs = fluidsynth.Synth(samplerate=float(sr), gain=0.4)
    fs.setting("synth.reverb.active", 1 if reverb else 0)
    fs.setting("synth.chorus.active", 0)
    sfid = fs.sfload(sf2)
    fs.program_select(0, sfid, 0, 0)
    if cents:
        fs.pitch_bend(0, int(round(cents / 200.0 * 8192)))   # default bend range: 2 semitones
    ev = []
    for on, off, m, v in notes:
        ev.append((on, 1, m, v))
        ev.append((off, 0, m, 0))
    for t, val in pedal or []:
        ev.append((t, 2, 64, val))
    ev.sort(key=lambda e: (e[0], e[1]))       # releases before strikes at the same time
    end = max((e[0] for e in ev), default=0.0) + tail
    chunks, pos = [], 0
    for t, kind, m, v in ev:
        n = int(round(t * sr)) - pos
        if n > 0:
            chunks.append(fs.get_samples(n))
            pos += n
        if kind == 1:
            fs.noteon(0, m, v)
        elif kind == 0:
            fs.noteoff(0, m)
        else:
            fs.cc(0, m, v)
    n = int(round(end * sr)) - pos
    if n > 0:
        chunks.append(fs.get_samples(n))
    fs.delete()
    pcm = np.concatenate(chunks).astype(np.float32).reshape(-1, 2).mean(axis=1) / 32768.0
    return pcm


def room(x: np.ndarray, sr: int, snr_db: float | None = 30.0, rt60: float = 0.0,
         mic: bool = False, gain_db: float = 0.0, seed: int = 0) -> np.ndarray:
    """The recording as a microphone in a room would pick it up."""
    rng = np.random.default_rng(seed)
    y = x.astype(np.float64)
    if rt60 > 0:                                      # diffuse reverb: decaying noise
        n = int(rt60 * sr)
        t = np.arange(n) / sr
        ir = rng.standard_normal(n) * np.exp(-6.9 * t / rt60)
        ir[0] = 0.0
        ir *= 0.25 / np.sqrt(np.sum(ir ** 2))
        ir[0] = 1.0
        nfft = 1 << int(np.ceil(np.log2(len(y) + n)))
        y = np.fft.irfft(np.fft.rfft(y, nfft) * np.fft.rfft(ir, nfft), nfft)[:len(y)]
    if mic:                                            # small mic: weak bass, a presence bump
        nfft = 1 << int(np.ceil(np.log2(len(y))))
        f = np.fft.rfftfreq(nfft, 1.0 / sr)
        resp = (f / 150.0) ** 2 / (1 + (f / 150.0) ** 2)          # 2nd-order high-pass
        resp *= 1 + 0.6 * np.exp(-0.5 * ((np.log2(np.maximum(f, 1) / 3500.0)) / 0.5) ** 2)
        resp /= 1 + (f / 12000.0) ** 4                              # roll-off up top
        y = np.fft.irfft(np.fft.rfft(y, nfft) * resp, nfft)[:len(y)]
    if snr_db is not None:                             # pink-ish room noise
        w = rng.standard_normal(len(y))
        nfft = 1 << int(np.ceil(np.log2(len(y))))
        f = np.fft.rfftfreq(nfft, 1.0 / sr)
        pink = np.fft.irfft(np.fft.rfft(w, nfft) / np.sqrt(np.maximum(f, 20.0)), nfft)[:len(y)]
        sig = np.sqrt(np.mean(y ** 2)) + 1e-12
        pink *= sig / (np.sqrt(np.mean(pink ** 2)) + 1e-12) * 10 ** (-snr_db / 20)
        y = y + pink
    y *= 10 ** (gain_db / 20)
    return np.clip(y, -1, 1).astype(np.float32)


# --- what to play ---------------------------------------------------------------------

def single_notes(rng: random.Random, n=60, low=21, high=108):
    notes, t = [], 0.3
    for _ in range(n):
        m = rng.randint(low, high)
        d = rng.uniform(0.25, 0.9)
        notes.append((t, t + d, m, rng.randint(35, 115)))
        t += d + rng.uniform(0.05, 0.4)
    return notes


_CHORD_SHAPES = [(0, 4, 7), (0, 3, 7), (0, 4, 7, 12), (0, 7), (0, 4), (0, 3), (0, 12),
                 (0, 5, 9), (0, 3, 8), (0, 4, 7, 10), (0, 2), (0, 7, 16), (-12, 0, 4, 7)]


def chords(rng: random.Random, n=40, low=36, high=88):
    notes, t = [], 0.3
    for _ in range(n):
        shape = rng.choice(_CHORD_SHAPES)
        root = rng.randint(low - min(shape), high - max(shape))
        d = rng.uniform(0.4, 1.2)
        v = rng.randint(45, 110)
        for s in shape:
            notes.append((t + rng.uniform(0, 0.012), t + d, root + s, max(1, min(127, v + rng.randint(-10, 10)))))
        t += d + rng.uniform(0.1, 0.4)
    return notes


def fast_runs(rng: random.Random, n=8, low=48, high=84):
    """Scales played quickly (8 to 10 notes a second), legato."""
    notes, t = [], 0.3
    major = [0, 2, 4, 5, 7, 9, 11]
    for _ in range(n):
        root = rng.randint(low, high - 14)
        step = rng.uniform(0.1, 0.125)
        seq = [root + 12 * (i // 7) + major[i % 7] for i in range(15)]
        if rng.random() < 0.5:
            seq = seq[::-1]
        v = rng.randint(55, 100)
        for i, m in enumerate(seq):
            notes.append((t + i * step, t + (i + 1) * step + 0.03, m, v))
        t += len(seq) * step + 0.6
    return notes


def repeated_notes(rng: random.Random, n=30, low=40, high=90):
    """The same key struck again while it still sounds."""
    notes, t = [], 0.3
    for _ in range(n):
        m = rng.randint(low, high)
        gap = rng.uniform(0.18, 0.35)
        for k in range(3):
            notes.append((t + k * gap, t + k * gap + gap * 0.92, m, rng.randint(55, 105)))
        t += 3 * gap + 0.5
    return notes


def lesson_notes(tempo_bpm: float = 80.0):
    """Every exercise of the built-in lessons, played one note per beat."""
    from pianove.song_store import _pitch_to_midi
    notes, t, beat = [], 0.3, 60.0 / tempo_bpm
    for path in sorted(glob.glob(os.path.join(ROOT, "pianove", "lessons", "*", "steps.json"))):
        with open(path, encoding="utf-8") as f:
            steps = json.load(f)
        for st in steps:
            for bar in st.get("bars") or []:
                for item in bar:
                    names = item if isinstance(item, list) else [item]
                    ms = []
                    for nm in names:
                        try:
                            ms.append(_pitch_to_midi(nm))
                        except Exception:
                            pass
                    for m in ms:
                        notes.append((t, t + beat * 0.9, m, 75))
                    t += beat
    return notes


def song_notes(path: str, max_seconds: float = 40.0, tempo_scale: float = 1.0):
    """A MusicXML piece as the importer reads it."""
    from pianove.song_store import _parse_musicxml
    d = _parse_musicxml(path)
    spb = 60.0 / (d.get("bpm") or 100.0) / tempo_scale
    starts = np.concatenate([[0.0], np.cumsum(d["bar_lens"])[:-1]])
    seen, notes = set(), []
    for hand in ("rh", "lh"):
        for b, bar in enumerate(d[f"bars_{hand}"]):
            for i, nm in enumerate(bar):
                if d[f"ties_{hand}"][b][i]:
                    continue
                from pianove.song_store import _pitch_to_midi
                m = _pitch_to_midi(nm)
                on = (starts[b] + d[f"onsets_{hand}"][b][i]) * spb + 0.3
                off = on + max(0.08, d[f"durs_{hand}"][b][i] * spb * 0.95)
                if on > max_seconds or (round(on, 3), m) in seen:
                    continue
                seen.add((round(on, 3), m))
                notes.append((on, off, m, int(d[f"vels_{hand}"][b][i] or 64)))
    notes.sort()
    return notes


# --- scoring ---------------------------------------------------------------------------

def score(reference, detected, tol: float = 0.1, latency_max: float = 0.25):
    """Note-level precision/recall/F1. reference: [(onset, offset, midi, vel)];
    detected: [(onset_estimate, midi, decided_at)]. A detection counts for a played note
    of the same key whose onset is within tol of its onset estimate."""
    ref = sorted(((r[0], r[2]) for r in reference))
    det = sorted(detected)
    used = [False] * len(det)
    by_note: dict[int, list[int]] = {}
    for j, d in enumerate(det):
        by_note.setdefault(d[1], []).append(j)
    tp, lat, misses = 0, [], []
    for on, m in ref:
        best, bd = None, tol + 1e-9
        for j in by_note.get(m, []):
            if not used[j] and abs(det[j][0] - on) <= bd:
                best, bd = j, abs(det[j][0] - on)
        if best is None:
            misses.append((round(on, 3), m))
        else:
            used[best] = True
            tp += 1
            lat.append(det[best][2] - on)
    fp = [(round(det[j][0], 3), det[j][1]) for j in range(len(det)) if not used[j]]
    p = tp / max(1, len(det))
    r = tp / max(1, len(ref))
    f = 2 * p * r / max(1e-9, p + r)
    return {"p": p, "r": r, "f": f, "n_ref": len(ref), "n_det": len(det), "tp": tp,
            "latency_ms": 1000 * float(np.median(lat)) if lat else float("nan"),
            "latency_p90_ms": 1000 * float(np.percentile(lat, 90)) if lat else float("nan"),
            "misses": misses, "false": fp}


def run_detector(audio: np.ndarray, sr: int, block: int = 512, **kw):
    """Feeds the recording to the detector in small blocks, as a microphone would."""
    from pianove.audio_input.detector import PianoNoteDetector
    det = PianoNoteDetector(sample_rate=sr, **kw)
    out = []
    for i in range(0, len(audio), block):
        for e in det.process(audio[i:i + block]):
            if e.on:
                out.append((e.onset, e.note, e.time))
    return out

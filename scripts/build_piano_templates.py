"""Measures the 88 keys' spectra for the piano sound detection engine and saves them to
pianove/audio_input/piano_templates.npz.

Every key is played at a few strengths on several sampled pianos — the bundled Salamander
grand (a Yamaha C5) and the system soundfonts tests/piano_audio.py knows (FluidR3,
TimGM6mb, MuseScore General, the Csound GM bank) — and its spectrum, as the detector sees
it, is averaged over the first quarter second after the strike and over the pianos. Only
the bins where the string's partials can be are kept (no hammer thump, no noise).

Run:  python scripts/build_piano_templates.py [soundfont.sf2 ...]   (default: all found)
"""
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import pianove  # noqa: E402,F401
from pianove.audio_input import detector as D  # noqa: E402
from piano_audio import render, soundfonts  # noqa: E402

VELOCITIES = (45, 75, 105)


def build_templates(soundfonts, sr: int = 44100, gamma: float = D.PianoNoteDetector.gamma,
                    variants: bool = False) -> np.ndarray:
    """keys × bins, averaged over the soundfonts' pianos — or with variants=True, one
    set per piano (pianos × keys × bins)."""
    out = []
    for sf2 in soundfonts:
        out.append(_measure(sf2, sr, gamma))
    if variants:
        return np.stack(out).astype(np.float32)
    W = np.mean(out, axis=0)
    return (W / (W.sum(axis=1, keepdims=True) + 1e-12)).astype(np.float32)


def _measure(sf2: str, sr: int, gamma: float) -> np.ndarray:
    spec = D.Spectrum(sr)
    hop = int(round(D.HOP_S * sr))
    W = np.zeros((D.N_KEYS, D.N_BINS), dtype=np.float64)
    gap, dur = 1.2, 0.8
    notes = []
    for j, v in enumerate(VELOCITIES):
        for i, m in enumerate(range(D.LOW, D.HIGH + 1)):
            t = (j * D.N_KEYS + i) * gap + 0.2
            notes.append((t, t + dur, m, v))
    x = render(notes, sf2, sr=sr, reverb=False)
    for t, _, m, _v in notes:
        frames = []
        for end in np.arange(t + 0.03, t + 0.28, hop / sr):
            e = int(round(end * sr))
            if e - spec.win < 0 or e > len(x):
                continue
            frames.append(spec(x[e - spec.win:e]))
        if not frames:
            continue
        S = np.mean(frames, axis=0) * D.partial_mask(m)    # only the string, no thump
        S = S / (S.max() + 1e-12)
        S = np.maximum(S - 3e-3, 0.0) ** gamma               # leave out what is barely there
        W[m - D.LOW] += S / (S.sum() + 1e-12)
    return W / (W.sum(axis=1, keepdims=True) + 1e-12)


if __name__ == "__main__":
    fonts = sys.argv[1:] or list(soundfonts().values())
    W = build_templates(fonts)
    np.savez_compressed(D.TEMPLATES_PATH, W=W.astype(np.float16))
    print(f"saved {W.shape} from {', '.join(os.path.basename(f) for f in fonts)} to {D.TEMPLATES_PATH}")

"""The piano sound detection engine: hears which keys are played from a microphone.

Every 10 ms the last ~0.12 s of sound is turned into a spectrum on a musical scale
(three bins per semitone). That spectrum is explained as a mix of the 88 keys' own
spectra (templates measured from sampled grand pianos, see
scripts/build_piano_templates.py), a few smooth shapes that soak up hammer thumps, and
the room's noise floor — non-negative least squares in the KL sense, solved a few
multiplicative steps per frame from where the last frame left off. How strongly each
key is in the mix over time tells when it is struck (a sharp rise), struck again (a
second rise while it still rings) and let go (it fades away). A key that only gets the
spill of a louder key — its octave, its fifth above the octave, its neighbour — has to
stand well clear of that spill before it counts.

Thresholds are measured against the room's own noise and the loudness of the playing,
so the microphone's gain doesn't matter. The piano's tuning is followed too: an old
upright a third of a semitone flat is still heard on the right keys.

Pure numpy, no audio device here — feed it samples with process() (see microphone.py).
How well it does: scripts/eval_audio_detection.py.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

LOW, HIGH = 21, 108                     # A0 .. C8
N_KEYS = HIGH - LOW + 1

BINS_PER_SEMITONE = 3
GRID_LO = 15.0                          # MIDI number of the lowest bin (≈ 19 Hz)
F_MAX = 10000.0                         # nothing above this is looked at
WIN_S = 0.12                            # analysis window, seconds
HOP_S = 0.01

TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "piano_templates.npz")


def midi_to_hz(m, a4: float = 440.0):
    return a4 * 2.0 ** ((np.asarray(m, dtype=np.float64) - 69.0) / 12.0)


def hz_to_midi(f, a4: float = 440.0):
    return 69.0 + 12.0 * np.log2(np.asarray(f, dtype=np.float64) / a4)


GRID_HI = float(hz_to_midi(F_MAX))
N_BINS = int(np.floor((GRID_HI - GRID_LO) * BINS_PER_SEMITONE)) + 1
GRID = GRID_LO + np.arange(N_BINS) / BINS_PER_SEMITONE      # MIDI number of every bin


@dataclass
class NoteEvent:
    on: bool          # struck (True) or let go (False)
    note: int         # MIDI number
    velocity: int     # 1..127 for a strike, 0 for a release
    onset: float      # when it happened, seconds into the stream (best estimate)
    time: float       # when it was decided (stream seconds) — onset + the detector's latency


class Spectrum:
    """Windowed FFT magnitude → the musical-scale spectrum."""

    def __init__(self, sample_rate: int, a4: float = 440.0):
        self.sr = int(sample_rate)
        self.win = int(round(WIN_S * self.sr))
        self.nfft = 1 << int(np.ceil(np.log2(2 * self.win)))
        self.window = np.hanning(self.win).astype(np.float32)
        self.window /= self.window.sum()            # a full-scale sine reads 0.5
        self.freqs = np.fft.rfftfreq(self.nfft, 1.0 / self.sr)
        self.set_tuning(a4)

    def set_tuning(self, a4: float):
        self.a4 = float(a4)
        df = self.sr / self.nfft
        centres = midi_to_hz(GRID, a4)
        edges = midi_to_hz(np.append(GRID - 0.5 / BINS_PER_SEMITONE, GRID[-1] + 0.5 / BINS_PER_SEMITONE), a4)
        lo = np.ceil(edges[:-1] / df).astype(int)
        hi = np.floor(edges[1:] / df).astype(int)
        nyq = len(self.freqs) - 1
        self._valid = centres < 0.47 * self.sr
        # low bins are narrower than an FFT bin: interpolate; above that, take the peak
        wide = (hi >= lo) & self._valid
        first = int(np.argmax(wide)) if wide.any() else N_BINS
        self._interp_n = first
        self._interp_f = centres[:first]
        last = int(np.max(np.nonzero(wide)[0])) + 1 if wide.any() else first
        self._pool_n = last
        self._starts = np.clip(lo[first:last], 0, nyq)
        self._end = int(min(nyq, hi[last - 1])) + 1 if last > first else 0

    def __call__(self, frame: np.ndarray) -> np.ndarray:
        x = frame - frame.mean()
        mag = np.abs(np.fft.rfft(x * self.window, self.nfft)).astype(np.float32)
        self.mag = mag
        out = np.zeros(N_BINS, dtype=np.float32)
        if self._interp_n:
            out[:self._interp_n] = np.interp(self._interp_f, self.freqs, mag)
        if self._pool_n > self._interp_n:
            out[self._interp_n:self._pool_n] = np.maximum.reduceat(mag[:self._end], self._starts)
        return out


# --- the keys' spectra -----------------------------------------------------------------

def inharmonicity(m):
    """Typical stiffness coefficient B of a piano string (partial k sits at k·f0·√(1+B·k²))."""
    m = np.asarray(m, dtype=np.float64)
    return 10 ** np.where(m > 40, -4.0 + (m - 40) * 0.028, -4.0 + (40 - m) * 0.012)


def partial_mask(m: int, partials: int = 24) -> np.ndarray:
    """The bins where key m's string partials can be (allowing for any piano's stiffness
    and the analysis window's spread), 1 there and 0 elsewhere."""
    f0 = float(midi_to_hz(m))
    lobe = 2.0 / WIN_S                                     # Hann main lobe half-width, Hz
    mask = np.zeros(N_BINS, dtype=np.float32)
    for k in range(1, partials + 1):
        lo_f = k * f0 * np.sqrt(1 + inharmonicity(m) * 0.3 * k * k)
        hi_f = k * f0 * np.sqrt(1 + inharmonicity(m) * 3.0 * k * k)
        if lo_f > F_MAX:
            break
        lo = hz_to_midi(max(1.0, lo_f - lobe)) - 0.4
        hi = hz_to_midi(hi_f + lobe) + 0.4
        mask[(GRID >= lo) & (GRID <= hi)] = 1.0
    return mask


def synthetic_templates(sample_rate: int = 44100, gamma: float = 0.5) -> np.ndarray:
    """Templates from a textbook piano tone, for when the measured ones are missing."""
    spec = Spectrum(sample_rate)
    t = np.arange(spec.win) / spec.sr
    rng = np.random.default_rng(7)
    W = np.zeros((N_KEYS, N_BINS), dtype=np.float32)
    for i, m in enumerate(range(LOW, HIGH + 1)):
        f0, B = float(midi_to_hz(m)), float(inharmonicity(m))
        x = np.zeros_like(t)
        for k in range(1, 40):
            fk = k * f0 * np.sqrt(1 + B * k * k)
            if fk > F_MAX:
                break
            a = k ** -1.1 * (0.4 if (k == 1 and m < 45) else 1.0)
            x += a * np.sin(2 * np.pi * fk * t + rng.uniform(0, 2 * np.pi))
        W[i] = spec(x.astype(np.float32)) ** gamma
    return W


def load_templates() -> np.ndarray | None:
    try:
        with np.load(TEMPLATES_PATH) as z:
            W = z["W"].astype(np.float32)
        return W if W.shape[-2:] == (N_KEYS, N_BINS) else None
    except Exception:
        return None


def _noise_templates() -> np.ndarray:
    """Broad bumps, each about an octave wide: hammer thumps, hiss, hum."""
    centres = np.linspace(GRID_LO, GRID_HI, 14)
    width = (centres[1] - centres[0]) * 0.9
    return np.exp(-0.5 * ((GRID[None, :] - centres[:, None]) / width) ** 2).astype(np.float32)


def _shadow_matrices() -> tuple[np.ndarray, np.ndarray]:
    """Where a struck key's energy spills onto other keys when the templates don't fit a
    piano exactly: onto the keys of its partials (an octave, an octave and a fifth, …),
    and onto its neighbours and the neighbours of its higher partials."""
    S_part = np.zeros((N_KEYS, N_KEYS), dtype=np.float32)
    S_near = np.zeros((N_KEYS, N_KEYS), dtype=np.float32)
    steps = [int(round(12 * np.log2(k))) for k in range(2, 9)]       # 12 19 24 28 31 34 36
    for n in range(N_KEYS):
        for d in steps:
            if n + d < N_KEYS:
                S_part[n, n + d] = 1.0
        for d in [-2, -1, 1, 2] + [s + o for s in steps[2:] for o in (-1, 1)]:
            if 0 <= n + d < N_KEYS and not S_part[n, n + d]:
                S_near[n, n + d] = 1.0
    return S_part, S_near


_S_PART, _S_NEAR = _shadow_matrices()


# --- the detector ------------------------------------------------------------------------

class PianoNoteDetector:
    """Streaming polyphonic piano transcription. Feed mono samples (float, -1..1) of any
    block size to process(); it returns the notes struck and let go since the last call."""

    # hearing the keys in the sound
    gamma = 0.5            # magnitude compression before the decomposition
    iters = 12             # multiplicative updates per frame
    sparsity = 0.02        # L1 weight on the keys' activations (relative)
    carry = 0.8            # how much of the last frame's mix the next one starts from
    seed = 0.3             # … and how much of each key's own fit
    floor_blocks = 8       # noise floor: the quietest of the last 8 blocks
    floor_block_frames = 50  #            of half a second each
    floor_mult = 2.0       # the floor's minimum, scaled up to the noise's typical level
    abs_floor = 3e-7       # quietest magnitude worth hearing (≈ -124 dBFS: digital silence)
    # deciding what was played
    on_noise = 1.0         # a strike must stand this far above the noise
    on_rel = 0.35          # … and not be lost under the loudest key ringing now
    on_peak = 0.14         # … nor far below the loudest playing of the last seconds
    shadow_part = 0.5      # a key on a louder key's partial must reach this share of it
    shadow_near = 1.0      # … and a key next to a louder key (or its partials) this share
    own_shadow = 0.5       # … and next to Pianove's own notes from the speakers, this share
    rise = 1.6             # how much a key must grow over the last frames to count as struck
    restrike = 1.2         # … to count as struck again while it still rings
    min_gap = 14           # frames after a strike before the same key can be struck again
    confirm = 5            # frames a strike must hold before it is reported
    off_ratio = 0.06       # let go when it fades to this share of its peak
    off_noise = 2.0        # … or sinks this close to the noise
    onset_shift = 0.045    # the analysis sees a strike this long after it happens

    def __init__(self, sample_rate: int = 44100, templates: np.ndarray | None = None,
                 sensitivity: float = 1.0, track_tuning: bool = True, **params):
        for k, v in params.items():
            if not hasattr(type(self), k):
                raise TypeError(f"unknown parameter {k}")
            setattr(self, k, v)
        self.sr = int(sample_rate)
        self.hop = int(round(HOP_S * self.sr))
        self.spec = Spectrum(self.sr)
        self.win = self.spec.win
        W = templates if templates is not None else load_templates()
        if W is None:
            W = synthetic_templates(self.sr, self.gamma)
        W = np.asarray(W, dtype=np.float32).copy()
        if W.ndim == 2:
            W = W[None]                                # variants × keys × bins
        self.n_var = W.shape[0]
        W = W.reshape(-1, N_BINS)
        W[:, ~self.spec._valid] = 0.0
        W /= W.sum(axis=1, keepdims=True) + 1e-12
        self.n_key_cols = W.shape[0]
        N = _noise_templates()
        N[:, ~self.spec._valid] = 0.0
        N /= N.sum(axis=1, keepdims=True) + 1e-12
        self.W = np.vstack([W, N]).T.copy()           # bins × (keys + noise)
        self.Wt = self.W.T.copy()
        self._colsum = self.Wt.sum(axis=1)
        self._proj = 1.0 / (np.einsum("ij,ij->i", self.Wt, self.Wt) + 1e-12)   # one template's own fit
        self.n_comp = self.W.shape[1]
        self.sensitivity = float(sensitivity)
        self.track_tuning = track_tuning
        self.record: list | None = None               # set to [] to keep every frame's analysis
        self.reset()

    # -- state --

    def reset(self):
        self._buf = np.zeros(self.win, dtype=np.float32)
        self._since = 0                                  # samples since the last frame
        self._t = 0                                      # samples consumed
        self.h = np.zeros(self.n_comp, dtype=np.float32)
        self.floor = None
        self._mins = None
        self._cur_min = None
        self._block_n = 0
        self._hist = np.zeros((8, N_KEYS), dtype=np.float32)   # recent activations
        self.active = np.zeros(N_KEYS, dtype=bool)
        self._peak = np.zeros(N_KEYS, dtype=np.float32)
        self._valley = np.zeros(N_KEYS, dtype=np.float32)
        self._age = np.zeros(N_KEYS, dtype=np.int32)              # frames since struck
        self._pending = np.zeros(N_KEYS, dtype=np.int16)          # frames a strike has held
        self._pend_onset = np.zeros(N_KEYS, dtype=np.float64)
        self._low_frames = np.zeros(N_KEYS, dtype=np.int16)
        self._loud = 0.0                                          # loudest playing, decaying
        self.level = 0.0                                          # input level 0..1 (for a meter)
        self._tune_acc = np.zeros(3)
        self._tune_n = 0
        self.a4 = 440.0
        self.spec.set_tuning(self.a4)
        self._muted: dict[int, float] = {}                        # key → until (stream s)

    @property
    def active_notes(self) -> set[int]:
        return {LOW + int(i) for i in np.nonzero(self.active)[0]}

    def mute(self, note: int, seconds: float):
        """Don't report this key for the next few seconds (Pianove is playing it through
        the speakers). A later call replaces the earlier one, so a key muted while it
        sounds can be let go with a short tail once it stops."""
        if 0 <= note - LOW < N_KEYS:
            self._muted[note] = self._t / self.sr + seconds

    # -- feeding --

    def process(self, samples) -> list[NoteEvent]:
        x = np.asarray(samples, dtype=np.float32).ravel()
        events: list[NoteEvent] = []
        pos = 0
        while pos < len(x):
            take = min(len(x) - pos, self.hop - self._since)
            self._buf[:-take] = self._buf[take:]
            self._buf[-take:] = x[pos:pos + take]
            self._since += take
            self._t += take
            pos += take
            if self._since >= self.hop:
                self._since = 0
                now = self._t / self.sr
                a, noise = self._analyse()
                if self.record is not None:
                    self.record.append((now, a, noise))
                self._decide(now, a, noise, events)
        return events

    # -- hearing --

    def _analyse(self) -> tuple[np.ndarray, np.ndarray]:
        """How strongly each key sounds in the newest frame, and how strongly the room's
        noise alone would seem to sound it."""
        P = self.spec(self._buf)
        self.level = max(float(np.max(np.abs(self._buf[-self.hop:]))), self.level * 0.9)

        # the room's noise floor, bin by bin: the quietest each bin has been lately
        # (minimum statistics over a few seconds — music never stays put that long)
        if self._mins is None:
            self._mins = np.repeat(P[None, :], self.floor_blocks, axis=0)
            self._cur_min = P.copy()
        self._cur_min = np.minimum(self._cur_min, P)
        self._block_n += 1
        if self._block_n >= self.floor_block_frames:
            self._mins[:-1] = self._mins[1:]
            self._mins[-1] = self._cur_min
            self._cur_min = P.copy()
            self._block_n = 0
        self.floor = np.minimum(self._mins.min(axis=0), self._cur_min)
        bg = (self.floor_mult * np.maximum(self.floor, self.abs_floor)) ** self.gamma
        V = P ** self.gamma
        excess = np.maximum(V - bg, 0.0)
        K = self.n_key_cols
        noise = ((self.Wt[:K] @ bg) * self._proj[:K]).reshape(self.n_var, N_KEYS).min(axis=0)

        # the mix of keys (and noise shapes) that explains the sound best
        W, Wt = self.W, self.Wt
        h = self.h * self.carry
        total = float(excess.sum())
        if total > 1e-9:
            h = np.maximum(h, self.seed * (Wt @ excess) * self._proj) + 1e-9
            lam = np.zeros(self.n_comp, dtype=np.float32)
            lam[:K] = self.sparsity * total / N_KEYS
            denom = self._colsum + lam
            for _ in range(self.iters):
                h *= (Wt @ (V / (W @ h + bg + 1e-9))) / denom
        else:
            h[:] = 0.0
        self.h = h
        a = h[:K].reshape(self.n_var, N_KEYS).sum(axis=0)
        if self.track_tuning and total > 1e-9 and float(np.max(a / (noise + 1e-12))) > 8:
            self._follow_tuning()
        return a, noise

    # -- deciding --

    def _decide(self, now: float, a: np.ndarray, noise: np.ndarray, events: list[NoteEvent]):
        hist = self._hist
        sens = self.sensitivity
        self._loud = max(float(a.max()), self._loud * (1 - HOP_S / 4.0))   # fades over ~4 s
        recent_min = hist[-6:].min(axis=0)

        cand = ((a * sens > self.on_noise * noise) & (a * sens > self.on_rel * float(a.max()))
                & (a * sens > self.on_peak * self._loud))
        if cand.any() and (self.shadow_part or self.shadow_near):
            spill = np.maximum(self.shadow_part * (a[:, None] * _S_PART).max(axis=0),
                               self.shadow_near * (a[:, None] * _S_NEAR).max(axis=0))
            cand &= a * sens > spill
        if self._muted:
            # Pianove's own notes from the speakers: anything else must stand well clear of them
            own = [k - LOW for k, until in self._muted.items() if until > now]
            if own:
                cand &= a * sens > self.own_shadow * float(a[own].max())
        fresh = cand & ~self.active & (a > self.rise * recent_min)
        self._age += 1
        again = (cand & self.active & (self._age >= self.min_gap)
                 & (a > self.restrike * self._valley) & (a > 1.05 * hist[-1]))
        # a ringing key's peak, and the lowest it has fallen to since
        grew = a >= self._peak
        self._peak = np.where(grew, a, self._peak)
        self._valley = np.where(grew, a, np.minimum(self._valley, a))

        rising = fresh | again
        holding = (self._pending > 0) & cand
        self._pend_onset[rising & (self._pending == 0)] = now - self.onset_shift
        self._pending = np.where(rising | holding, self._pending + 1, 0).astype(np.int16)

        for i in np.nonzero(self._pending >= self.confirm)[0]:
            note = LOW + int(i)
            self._pending[i] = 0
            was_active = self.active[i]
            self.active[i] = True
            self._peak[i] = self._valley[i] = a[i]
            self._age[i] = 0
            self._low_frames[i] = 0
            if self._muted.get(note, -1.0) > now:
                continue
            if was_active:
                events.append(NoteEvent(False, note, 0, self._pend_onset[i], now))
            events.append(NoteEvent(True, note, self._velocity(a[i]), self._pend_onset[i], now))

        # notes fading out
        low = self.active & ((a < self.off_ratio * self._peak) | (a * sens < self.off_noise * noise))
        self._low_frames = np.where(low, self._low_frames + 1, 0).astype(np.int16)
        for i in np.nonzero(self._low_frames >= 3)[0]:
            self.active[i] = False
            self._low_frames[i] = 0
            events.append(NoteEvent(False, LOW + int(i), 0, now, now))
        self._peak[~self.active] = 0.0
        self._valley[~self.active] = 0.0

        hist[:-1] = hist[1:]
        hist[-1] = a

    def _velocity(self, a: float) -> int:
        db = 20 * np.log10(max(a, 1e-12) / max(self._loud, 1e-9))
        return int(np.clip(100 + 2.0 * db, 20, 127))

    def _follow_tuning(self):
        """Where the clear spectral peaks between 100 Hz and 1.2 kHz sit relative to the
        semitones tells how the piano is tuned; once a few seconds of playing agree, the
        scale is shifted to match."""
        mag, f = self.spec.mag, self.spec.freqs
        lo, hi = np.searchsorted(f, 100.0), np.searchsorted(f, 1200.0)
        c = mag[lo:hi]
        pk = np.nonzero((c[1:-1] > c[:-2]) & (c[1:-1] >= c[2:]) & (c[1:-1] > 0.2 * c.max()))[0] + 1
        if not len(pk):
            return
        l, m_, r = (np.log(c[pk - 1] + 1e-12), np.log(c[pk] + 1e-12), np.log(c[pk + 1] + 1e-12))
        off = 0.5 * (l - r) / (l - 2 * m_ + r - 1e-12)
        freq = (lo + pk + np.clip(off, -0.5, 0.5)) * (f[1] - f[0])
        semis = hz_to_midi(freq, self.a4)
        ang = 2 * np.pi * (semis - np.round(semis))
        w = c[pk]
        self._tune_acc += np.array([np.sum(w * np.cos(ang)), np.sum(w * np.sin(ang)), np.sum(w)])
        self._tune_n += 1
        if self._tune_n < 150:                       # ~1.5 s of clear playing
            return
        x, y, total = self._tune_acc
        self._tune_acc[:] = 0.0
        self._tune_n = 0
        if np.hypot(x, y) < 0.6 * total:             # the peaks don't agree
            return
        cents = 100 * np.arctan2(y, x) / (2 * np.pi)
        if abs(cents) < 3:
            return
        a4 = self.a4 * 2 ** (0.7 * cents / 1200)     # most of the way, not all at once
        if 415 < a4 < 466:
            self.a4 = a4
            self.spec.set_tuning(a4)

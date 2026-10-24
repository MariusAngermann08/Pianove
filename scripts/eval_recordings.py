"""How well the piano sound detection engine hears real recordings.

The recordings themselves stay private (they can hold voices and rooms): they are looked
for in ~/.pianove/recordings (or $PIANOVE_RECORDINGS) as mono WAV files. What was played
in them is in tests/recordings/<name>.json, section by section:

  notes       the keys struck, [onset seconds, midi]: scored like eval_audio_detection
  no_piano    silence, talking, the phone being handled: every note heard here is fake
  unlabelled  not scored, only counted

Run:  python scripts/eval_recordings.py
      python scripts/eval_recordings.py --show-errors
      python scripts/eval_recordings.py --param on_noise=1.5 --param rise=2.0
"""
import argparse
import glob
import json
import os
import sys
import time
import wave

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import pianove  # noqa: E402,F401
import piano_audio as pa  # noqa: E402

LABELS = os.path.join(ROOT, "tests", "recordings")
AUDIO = os.environ.get("PIANOVE_RECORDINGS", os.path.join(os.path.expanduser("~"), ".pianove", "recordings"))
TOL = 0.15                     # hand-placed onsets: a little looser than the synthetic test


def load_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path) as w:
        sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"{path}: 16-bit WAV expected")
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
    return x.reshape(-1, ch).mean(axis=1), sr


def _value(s: str):
    try:
        return int(s)
    except ValueError:
        return float(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-errors", action="store_true")
    ap.add_argument("--param", action="append", default=[], help="detector parameter, name=value")
    ap.add_argument("--only", default="", help="recording names, comma separated")
    args = ap.parse_args()
    params = {k: _value(v) for k, v in (p.split("=", 1) for p in args.param)}

    files = sorted(glob.glob(os.path.join(LABELS, "*.json")))
    if args.only:
        files = [f for f in files if os.path.splitext(os.path.basename(f))[0] in args.only.split(",")]
    tot = dict(ref=0, tp=0, det=0, fake=0, quiet_s=0.0)
    t_audio = t_cpu = 0.0
    for path in files:
        with open(path, encoding="utf-8") as f:
            rec = json.load(f)
        audio = os.path.join(AUDIO, rec["audio"])
        if not os.path.exists(audio):
            print(f"{rec['audio']}: not in {AUDIO}, skipped")
            continue
        x, sr = load_wav(audio)
        t0 = time.perf_counter()
        det = pa.run_detector(x, sr, **params)
        t_cpu += time.perf_counter() - t0
        t_audio += len(x) / sr

        print(f"\n{rec['audio']}  ({len(x) / sr:.0f} s)")
        print(f"  {'section':34} {'played':>6} {'heard':>6} {'R':>6} {'extra':>6} {'P':>6}")
        for sec in rec["sections"]:
            a, b = sec["start"], sec["end"]
            inside = [d for d in det if a <= d[0] < b]
            name = sec["name"][:34]
            if sec["kind"] == "notes":
                ref = [(t, t + 0.5, m, 64) for t, m in sec["notes"]]
                s = pa.score(ref, inside, tol=TOL)
                print(f"  {name:34} {s['n_ref']:6d} {s['tp']:6d} {s['r']:6.2f} {len(s['false']):6d} {s['p']:6.2f}")
                tot["ref"] += s["n_ref"]
                tot["tp"] += s["tp"]
                tot["det"] += s["n_det"]
                if args.show_errors:
                    print("      missed:", s["misses"][:14])
                    print("      extra: ", s["false"][:14])
            elif sec["kind"] == "no_piano":
                per_min = 60.0 * len(inside) / max(1e-9, b - a)
                print(f"  {name:34} {'-':>6} {'-':>6} {'':6} {len(inside):6d}   ({per_min:.0f} fake notes/min)")
                tot["fake"] += len(inside)
                tot["quiet_s"] += b - a
                if args.show_errors:
                    print("      fake:  ", [(round(d[0], 2), d[1]) for d in inside][:14])
            else:
                print(f"  {name:34} {'':6} {len(inside):6d} notes heard (not scored)")

    if not tot["ref"] and not tot["quiet_s"]:
        print("\nNo recordings found.")
        return
    P = tot["tp"] / max(1, tot["det"])
    R = tot["tp"] / max(1, tot["ref"])
    print(f"\nALL  played notes: recall={R:.3f} precision={P:.3f} F1={2 * P * R / max(1e-9, P + R):.3f}"
          f"   no piano: {60.0 * tot['fake'] / max(1e-9, tot['quiet_s']):.0f} fake notes/min"
          f"   speed={t_audio / max(1e-9, t_cpu):.0f}x real time (one core)")


if __name__ == "__main__":
    main()

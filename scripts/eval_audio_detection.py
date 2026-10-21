"""How well the piano sound detection engine hears what is played.

Plays pieces on several soundfont pianos (the bundled one and any installed system
soundfonts), optionally through a simulated room and microphone, runs the detector over
the sound as a live stream and scores the keys it reports against the keys played.

Run:  python scripts/eval_audio_detection.py              (everything)
      python scripts/eval_audio_detection.py --quick      (fewer pieces and rooms)
      python scripts/eval_audio_detection.py --show-errors
"""
import argparse
import os
import random
import sys
import time
from multiprocessing import Pool

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import pianove  # noqa: E402,F401
import piano_audio as pa  # noqa: E402

PIECES = {
    "single":   lambda: pa.single_notes(random.Random(1), 60),
    "chords":   lambda: pa.chords(random.Random(2), 40),
    "runs":     lambda: pa.fast_runs(random.Random(3), 8),
    "repeated": lambda: pa.repeated_notes(random.Random(4), 25),
    "lessons":  lambda: pa.lesson_notes()[:220],
    "chopin":   lambda: pa.song_notes(os.path.join(ROOT, "waltz-in-a-minorchopin.mxl"), 40),
}

ROOMS = {
    "clean":     dict(snr_db=None),
    "room":      dict(snr_db=30, rt60=0.4, mic=True, gain_db=-6, seed=1),
    "noisy":     dict(snr_db=18, rt60=0.6, mic=True, gain_db=6, seed=2),
    "detuned":   dict(snr_db=30, rt60=0.3, mic=True, seed=3),     # the piano is 35 cents flat
}


def _run_case(job):
    piece, room, fname, sf2, sr = job
    notes = PIECES[piece]()
    x = pa.render(notes, sf2, sr=sr, cents=-35.0 if room == "detuned" else 0.0)
    x = pa.room(x, sr, **ROOMS[room])
    t0 = time.perf_counter()
    det = pa.run_detector(x, sr)
    return pa.score(notes, det), len(x) / sr, time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--pieces", default="")
    ap.add_argument("--rooms", default="")
    ap.add_argument("--fonts", default="")
    ap.add_argument("--show-errors", action="store_true")
    ap.add_argument("--sr", type=int, default=44100)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = ap.parse_args()

    pieces = args.pieces.split(",") if args.pieces else (
        ["single", "chords", "lessons", "chopin"] if args.quick else list(PIECES))
    rooms = args.rooms.split(",") if args.rooms else (["clean", "room"] if args.quick else list(ROOMS))
    fonts = pa.soundfonts()
    if args.fonts:
        fonts = {k: v for k, v in fonts.items() if k in args.fonts.split(",")}

    jobs = [(piece, room, fname, sf2, args.sr) for piece in pieces for room in rooms
            for fname, sf2 in fonts.items()]
    with Pool(args.jobs) as pool:
        results = pool.map(_run_case, jobs)
    rows, t_audio, t_cpu = [], 0.0, 0.0
    print(f"{'piece':9} {'room':8} {'piano':11} {'notes':>5} {'P':>6} {'R':>6} {'F1':>6} {'lat ms':>7}")
    for (piece, room, fname, _, _), (s, secs, cpu) in zip(jobs, results):
        rows.append((piece, room, fname, s))
        t_audio += secs
        t_cpu += cpu
        print(f"{piece:9} {room:8} {fname:11} {s['n_ref']:5d} {s['p']:6.3f} {s['r']:6.3f} "
              f"{s['f']:6.3f} {s['latency_ms']:7.0f}")
        if args.show_errors:
            print("     missed:", s["misses"][:14])
            print("     false: ", s["false"][:14])
    tp = sum(r[3]["tp"] for r in rows)
    nr = sum(r[3]["n_ref"] for r in rows)
    nd = sum(r[3]["n_det"] for r in rows)
    P, R = tp / max(1, nd), tp / max(1, nr)
    print(f"\nALL  notes={nr}  precision={P:.3f}  recall={R:.3f}  F1={2 * P * R / max(1e-9, P + R):.3f}"
          f"  median latency={np.nanmedian([r[3]['latency_ms'] for r in rows]):.0f} ms"
          f"  speed={t_audio / max(1e-9, t_cpu):.0f}x real time (one core)")
    for room in rooms:
        sub = [r[3] for r in rows if r[1] == room]
        tp = sum(s["tp"] for s in sub); nr = sum(s["n_ref"] for s in sub); nd = sum(s["n_det"] for s in sub)
        P, R = tp / max(1, nd), tp / max(1, nr)
        print(f"  {room:8} P={P:.3f} R={R:.3f} F1={2 * P * R / max(1e-9, P + R):.3f}")
    for piece in pieces:
        sub = [r[3] for r in rows if r[0] == piece]
        tp = sum(s["tp"] for s in sub); nr = sum(s["n_ref"] for s in sub); nd = sum(s["n_det"] for s in sub)
        P, R = tp / max(1, nd), tp / max(1, nr)
        print(f"  {piece:8} P={P:.3f} R={R:.3f} F1={2 * P * R / max(1e-9, P + R):.3f}")


if __name__ == "__main__":
    main()

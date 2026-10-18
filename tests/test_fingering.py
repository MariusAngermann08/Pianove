"""Checks the automatic fingering against fingerings any piano teacher would write.

Run:  python -m pytest tests/test_fingering.py -q      (or just: python tests/test_fingering.py)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pianove.fingering import Step, finger_hand  # noqa: E402

_SEMI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(p: str) -> int:
    name, rest, acc = p[0], p[1:], 0
    while rest and rest[0] in "#b":
        acc += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    return (int(rest) + 1) * 12 + _SEMI[name] + acc


def line(pitches: str, dt: float = 0.3) -> list[Step]:
    """A legato line: space-separated notes, chords joined with '+'."""
    return [Step(tuple(midi(p) for p in tok.split("+")), i * dt, dt)
            for i, tok in enumerate(pitches.split())]


def fingers(pitches: str, hand: str = "right", dt: float = 0.3) -> list:
    steps = line(pitches, dt)
    out = finger_hand(steps, hand)
    res = []
    for st, f in zip(steps, out):
        fs = [f[m] for m in sorted(st.notes)]
        res.append(fs[0] if len(fs) == 1 else tuple(fs))
    return res


CASES = [
    # (name, notes, hand, accepted fingerings)
    ("C major scale RH", "C4 D4 E4 F4 G4 A4 B4 C5", "right",
     [[1, 2, 3, 1, 2, 3, 4, 5]]),
    ("C major scale RH down", "C5 B4 A4 G4 F4 E4 D4 C4", "right",
     [[5, 4, 3, 2, 1, 3, 2, 1]]),
    ("C major 2 octaves RH", "C4 D4 E4 F4 G4 A4 B4 C5 D5 E5 F5 G5 A5 B5 C6", "right",
     [[1, 2, 3, 1, 2, 3, 4, 1, 2, 3, 1, 2, 3, 4, 5]]),
    ("C major scale LH", "C3 D3 E3 F3 G3 A3 B3 C4", "left",
     [[5, 4, 3, 2, 1, 3, 2, 1]]),
    ("C major scale LH down", "C4 B3 A3 G3 F3 E3 D3 C3", "left",
     [[1, 2, 3, 1, 2, 3, 4, 5]]),
    ("G major scale RH", "G4 A4 B4 C5 D5 E5 F#5 G5", "right",
     [[1, 2, 3, 1, 2, 3, 4, 5]]),
    ("D major scale RH", "D4 E4 F#4 G4 A4 B4 C#5 D5", "right",
     [[1, 2, 3, 1, 2, 3, 4, 5]]),
    ("F major scale RH", "F4 G4 A4 Bb4 C5 D5 E5 F5", "right",
     [[1, 2, 3, 4, 1, 2, 3, 4]]),
    ("five-finger position", "C4 D4 E4 F4 G4 F4 E4 D4 C4", "right",
     [[1, 2, 3, 4, 5, 4, 3, 2, 1]]),
    ("five-finger position LH", "C3 D3 E3 F3 G3 F3 E3 D3 C3", "left",
     [[5, 4, 3, 2, 1, 2, 3, 4, 5]]),
    ("C major arpeggio RH", "C4 E4 G4 C5 E5 G5 C6", "right",
     [[1, 2, 3, 1, 2, 3, 5]]),
    ("C major triad RH", "C4+E4+G4", "right", [[(1, 3, 5)]]),
    ("C major triad LH", "C3+E3+G3", "left", [[(5, 3, 1)]]),
    ("octave RH", "C4+C5", "right", [[(1, 5)]]),
    ("chord progression RH", "C4+E4+G4 C4+F4+A4 B3+D4+G4 C4+E4+G4", "right",
     [[(1, 3, 5), (1, 3, 5), (1, 2, 5), (1, 3, 5)],
      [(1, 3, 5), (1, 3, 5), (1, 2, 4), (1, 3, 5)]]),
    # chromatic: the beginner's 1-3, or the fast 1-2-3-4 groups
    ("chromatic RH", "C4 C#4 D4 D#4 E4 F4 F#4 G4", "right",
     [[1, 3, 1, 3, 1, 2, 3, 1], [1, 2, 3, 4, 1, 2, 3, 4]]),
    ("Für Elise", "E5 D#5 E5 D#5 E5 B4 D5 C5 A4", "right",
     [[5, 4, 5, 4, 5, 2, 4, 3, 1], [4, 3, 4, 3, 4, 1, 3, 2, 1]]),
    ("Ode to Joy", "E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 E4 D4 D4", "right",
     [[3, 3, 4, 5, 5, 4, 3, 2, 1, 1, 2, 3, 3, 2, 2]]),
    ("Alberti bass LH", "C3 G3 E3 G3 C3 G3 E3 G3", "left",
     [[5, 1, 3, 1, 5, 1, 3, 1]]),
    ("waltz bass LH", "C3 E3+G3 E3+G3 G2 F3+G3 F3+G3 C3 E3+G3 E3+G3", "left",
     [[5, (3, 1), (3, 1), 5, (2, 1), (2, 1), 5, (3, 1), (3, 1)],
      [5, (2, 1), (2, 1), 5, (2, 1), (2, 1), 5, (2, 1), (2, 1)],
      [5, (3, 1), (3, 1), 5, (3, 2), (3, 2), 5, (3, 1), (3, 1)]]),
]


def run() -> int:
    bad = 0
    for name, notes, hand, accepted in CASES:
        got = fingers(notes, hand)
        ok = got in accepted
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name:26s} {got}" + ("" if ok else f"   want {accepted[0]}"))
    print(f"\n{len(CASES) - bad}/{len(CASES)} as a teacher would finger them")
    return bad


def test_teacher_fingerings():
    assert run() == 0


if __name__ == "__main__":
    sys.exit(1 if run() else 0)

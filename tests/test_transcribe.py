"""Writing down what was played against a metronome."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pianove.transcribe import quantize, split_hands  # noqa: E402

BPM = 60          # one beat per second: times read as beats


def _played(notes, wobble=0.0):
    """[(beat, length, midi)] → presses with a little timing wobble."""
    out = []
    for i, (b, ln, m) in enumerate(notes):
        w = wobble if i % 2 else -wobble
        out.append((b + w, b + ln - 0.08, m))
    return out


def test_quarters_and_halves_in_bars():
    bars, types = quantize(_played([(0, 1, 60), (1, 1, 62), (2, 2, 64), (4, 4, 65)], 0.05), BPM)
    assert bars == [["C4", "D4", "E4"], ["F4"]]
    assert types == [["quarter", "quarter", "half"], ["whole"]]


def test_eighths_dots_and_rests():
    played = [(0, 1.5, 60), (1.5, 0.5, 62), (2, 0.4, 64), (4, 1, 65)]   # E4 let go early: a rest
    bars, types = quantize(_played(played, 0.03), BPM)
    from pianove import exercise_format as ef
    assert bars[0][:3] == ["C4", "D4", "E4"] and all(e == "r" for e in bars[0][3:])
    assert types[0][:2] == ["dotted_quarter", "eighth"]
    assert ef.used(types[0]) == 4.0                  # the silence is written out as rests
    assert bars[1] == ["F4"]


def test_chord_and_tie_over_the_bar_line():
    played = [(0, 3, 60), (0.03, 3, 64), (0.05, 3, 67), (3, 2, 72)]
    bars, types = quantize(_played(played), BPM)
    assert bars[0] == ["C4+E4+G4", "C5~"]
    assert bars[1] == ["C5"]
    assert types[0] == ["dotted_half", "quarter"] and types[1] == ["quarter"]


def test_triplets():
    third = 1 / 3
    played = [(0, third, 60), (third, third, 62), (2 * third, third, 64), (1, 1, 65), (2, 2, 67)]
    bars, types = quantize(_played(played, 0.02), BPM)
    assert bars[0] == ["C4", "D4", "E4", "F4", "G4"]
    assert types[0] == ["triplet_eighth"] * 3 + ["quarter", "half"]


def test_hands_split_at_middle_c():
    right, left = split_hands([(0, 1, 60), (0, 1, 48), (1, 2, 64)])
    assert [m for _, _, m in right] == [60, 64] and [m for _, _, m in left] == [48]

"""Exercises with written note values, rests and chords, and the old exercises (no note
values) still played exactly as before."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "PyLay"))
sys.path.insert(0, str(ROOT / "PyLute"))

from pianove import exercise_format as ef  # noqa: E402


def _exercises():
    for d in sorted((ROOT / "pianove" / "lessons").iterdir()):
        f = d / "steps.json"
        if f.exists():
            for s in json.loads(f.read_text(encoding="utf-8")):
                if s.get("type") == "exercise":
                    yield d.name, s


def test_old_exercises_play_as_before():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from pianove.pages import lesson as L
    n = 0
    for name, ex in _exercises():
        time = tuple(ex["time"])
        bars = ex["bars"]
        pitches, types, onsets = ef.music(ex)
        assert pitches == bars, name
        old = L._step_positions(bars, None, None, None, None, None, None, time)
        new = L._step_positions(pitches, None, types, None, onsets, None, None, time)
        assert old == new, name
        for i in range(len(bars)):
            blen = L._bar_len_q(None, i, time)
            assert (L._bar_notes(None, None, None, 0, i, bars[i], time, blen)
                    == L._bar_notes(types, onsets, None, 0, i, pitches[i], time, blen)), (name, i)
        n += 1
    assert n >= 16


def test_note_values_rests_and_chords():
    ex = {"time": [3, 4],
          "bars": [["C4", "r", "E4"], ["C4+E4+G4", "D4"]],
          "types": [["quarter", "quarter", "quarter"], ["half", "quarter"]]}
    pitches, types, onsets = ef.music(ex)
    assert pitches == [["C4", "E4"], ["C4", "E4", "G4", "D4"]]
    assert onsets == [[0.0, 2.0], [0.0, 0.0, 0.0, 2.0]]
    assert types[1] == ["half", "half", "half", "quarter"]

    from pianove.pages import lesson as L
    starts = L._step_positions(pitches, None, types, None, onsets, None, None, (3, 4))
    assert starts == [0.0, 2.0, 3.0, 5.0]          # the rest leaves a gap; the chord is one step


def test_values():
    assert ef.quarters("dotted_half") == 3.0
    assert ef.bar_length([6, 8]) == 3.0
    assert ef.fill_rests(3.5) == ["half", "quarter", "eighth"]
    assert ef.types_of({"time": [4, 4], "bars": [["C4", "D4", "E4", "F4", "G4"]]}) == [["eighth"] * 5]
    assert not ef.has_types({"bars": [["C4"]], "types": [["quarter", "half"]]})

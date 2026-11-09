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


_RICH = {"time": [4, 4], "tempo": 100,
         "bars": [["C4~", "C4", "E4", "D4", "C4", "G4~"], ["G4", "r", "C4+E4"]],
         "types": [["quarter", "quarter", "triplet_eighth", "triplet_eighth", "triplet_eighth", "quarter"],
                   ["half", "triplet_quarter", "triplet_half"]],
         "lh": {"bars": [["C3"], ["G2", "C3"]], "types": [["whole"], ["half", "half"]]}}


def test_ties_triplets_and_two_hands():
    rh = ef.staff_music(*ef.parts(_RICH)[0])
    assert rh["ties"] == [[False, True, False, False, False, False], [True, False, False]]
    assert rh["durs"][0][0] == 2.0                 # C4 tied to C4: two beats
    assert rh["durs"][0][5] == 3.0                 # G4 tied over the bar line
    assert rh["onsets"][0][3] == round(2 + 1 / 3, 6)
    assert rh["trip"][0] == [False, False, True, True, True, False]
    assert rh["types"][1] == ["half", "half", "half"]
    assert ef.tempo_of(_RICH) == 100 and ef.tempo_of({}) == ef.DEFAULT_TEMPO


def test_player_draws_ties_and_triplets():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((10, 10))
    from pianove.pages import lesson as L
    from pylute.tuplet import Tuplet
    rh = ef.staff_music(*ef.parts(_RICH)[0])
    lh = ef.staff_music(*ef.parts(_RICH)[1])
    meta = {k: (rh[k], lh[k]) for k in ("durs", "ties", "trip")}
    meta["vels"] = (None, None)
    sv = L._StaffView(bars=rh["pitches"], phase="practice", bass_bars=lh["pitches"], time=(4, 4),
                      types=rh["types"], bass_types=lh["types"], onsets=rh["onsets"],
                      bass_onsets=lh["onsets"], meta=meta, notation=True, width=800, height=400)
    # tied notes aren't struck again; the chord and both staves make single steps
    assert [sorted(n.pitch for n in st) for st in sv._step_list] == [
        ["C3", "C4"], ["E4"], ["D4"], ["C4"], ["G4"], ["G2"], ["C3"], ["C4", "E4"]]
    bars = sv._score.staffs[0].bars
    assert sum(isinstance(e, Tuplet) for e in bars[0].events) == 1
    assert sum(isinstance(e, Tuplet) for e in bars[1].events) == 1      # rest + chord triplet
    tied = [n for b in bars for e in b.events for n in (getattr(e, "notes", None) or [e])
            if getattr(n, "tied_to", None) is not None]
    assert len(tied) == 2
    sv.rect = pygame.Rect(0, 0, 800, 400)
    sv._build_offscreen()                         # draws without an error

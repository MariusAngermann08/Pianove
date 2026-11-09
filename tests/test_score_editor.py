"""The exercise score editor's editing (no drawing)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "PyLay"))
sys.path.insert(0, str(ROOT / "PyLute"))

from pianove.score_editor import ScoreModel  # noqa: E402


def _model(bars=None, types=None, time=(4, 4)):
    step = {"type": "exercise", "time": list(time), "bars": bars if bars is not None else [[]]}
    if types is not None:
        step["types"] = types
    return step, ScoreModel(step)


def test_letters_enter_notes_near_the_last_one():
    step, m = _model()
    m.letter("a")                            # an empty staff: near G4, its middle
    assert step["bars"] == [["A4"]]
    step, m = _model([["C4"]], [["quarter"]])
    for ch in "defgabc":
        m.letter(ch)
    assert step["bars"] == [["C4", "D4", "E4", "F4"], ["G4", "A4", "B4", "C5"]]
    assert step["types"] == [["quarter"] * 4, ["quarter"] * 4]
    assert m.sel == (1, 3)


def test_a_full_bar_moves_on_to_the_next():
    step, m = _model([["C4", "D4", "E4"]], [["quarter"] * 3], time=(3, 4))
    m.select(0, 0)
    m.set_value("half")                      # C4 becomes a half note: E4 no longer fits
    assert step["bars"] == [["C4", "D4"], ["E4"]]
    assert step["types"] == [["half", "quarter"], ["quarter"]]


def test_values_dots_and_rests():
    step, m = _model()
    m.set_value("half")
    m.toggle_dot()
    m.letter("c")
    m.rest()                                 # 3 + 3 beats: the rest moves on to bar 2
    assert step["bars"] == [["C5"], ["r"]]           # C nearest the staff's middle G4
    assert step["types"] == [["dotted_half"], ["dotted_half"]]
    m.set_value("quarter")                   # just entered: the value is for the next notes
    assert step["types"][1] == ["dotted_half"]
    m.select(1, 0)                           # picked: the value changes it (the dot stays)
    m.set_value("quarter")
    assert step["types"][1] == ["dotted_quarter"]


def test_chords_from_keys_struck_together_and_shift_letters():
    step, m = _model()
    m.key_note(60, now=10.00)
    m.key_note(64, now=10.01)
    m.key_note(67, now=10.02)
    m.key_note(62, now=11.00)
    assert step["bars"][0] == ["C4+E4+G4", "D4"]
    m.letter("f", add=True)                  # Shift+F: F above the selected D
    assert step["bars"][0] == ["C4+E4+G4", "D4+F4"]
    m.select(0, 0)                           # a key played after picking a note: a new note
    m.key_note(72)
    assert step["bars"][0] == ["C4+E4+G4", "C5", "D4+F4"]


def test_transpose_delete_undo_redo():
    step, m = _model([["C4", "E4"]], [["quarter", "quarter"]])
    m.select(0, 1)
    m.transpose(1)
    assert step["bars"][0] == ["C4", "F4"]
    m.transpose(-12)
    assert step["bars"][0] == ["C4", "F3"]
    m.delete()
    assert step["bars"][0] == ["C4"] and m.sel == (0, 0)
    m.undo()
    assert step["bars"][0] == ["C4", "F3"]
    m.undo()
    m.undo()
    assert step["bars"][0] == ["C4", "E4"]
    m.redo()
    assert step["bars"][0] == ["C4", "F4"]


def test_new_time_signature_rebars():
    step, m = _model([["C4", "D4", "E4", "F4"], ["G4", "A4"]], [["quarter"] * 4, ["quarter"] * 2])
    m.set_time([3, 4])
    assert step["bars"] == [["C4", "D4", "E4"], ["F4", "G4", "A4"]]
    assert step["time"] == [3, 4]


def test_bars_and_playing():
    step, m = _model([["C4", "r"], ["E4"]], [["half", "quarter"], ["whole"]])
    m.select(0, -1)
    sched = m.schedule(bpm=60)
    # C4 at 0 s for 2 beats; the rest and the empty last beat of bar 1 are silent; E4 at 4 s
    assert [(round(s, 2), mids, where) for s, _, mids, where in sched] == [
        (0.0, [60], (0, 0, 0)), (4.0, [64], (0, 1, 0))]
    m.add_bar()
    assert step["bars"] == [["C4", "r"], [], ["E4"]]
    m.delete_bar()
    assert step["bars"] == [["C4", "r"], ["E4"]]



def test_ties():
    step, m = _model([["C4"]], [["half"]])
    m.tie()                                  # no C4 after it: one is added, tied to
    assert step["bars"][0] == ["C4~", "C4"] and step["types"][0] == ["half", "half"]
    m.select(0, 0)
    m.tie()                                  # tied already: untied
    assert step["bars"][0] == ["C4", "C4"]
    m.tie()                                  # the next entry has C4: just tied
    assert step["bars"][0] == ["C4~", "C4"] and m.sel == (0, 1)
    assert m.schedule(bpm=60) == []          # from the tie's second half: nothing is struck
    m.select(0, -1)
    sched = m.schedule(bpm=60)
    assert [(s, round(e / 0.95, 2), mids) for s, e, mids, _ in sched] == [(0.0, 4.0, [60])]


def test_triplets():
    step, m = _model()
    m.set_value("eighth")
    m.toggle_triplet()
    for ch in "cde":
        m.letter(ch)
    m.toggle_triplet()
    m.set_value("half")
    m.letter("g")
    assert step["types"][0] == ["triplet_eighth"] * 3 + ["half"]
    m.letter("a")                            # 1 + 2 + 2 > 4: the A goes on to bar 2
    assert step["bars"] == [["C5", "D5", "E5", "G5"], ["A5"]]


def test_two_hands_and_dragging():
    step, m = _model([["C4", "E4"]], [["half", "half"]])
    m.set_hands(True)
    assert step["lh"] == {"bars": [[]], "types": [[]]}
    m.set_staff(1)
    m.set_value("whole")
    m.letter("c")
    assert step["lh"]["bars"] == [["C3"]]        # a bass staff starts near D3
    m.letter("g")                                # a second whole: a new bar, on both staves
    assert step["lh"]["bars"] == [["C3"], ["G2"]] and step["bars"] == [["C4", "E4"], []]
    m.select(0, 1, staff=0)
    m.drag_start()
    m.drag_to(2, key=1)                          # E4 two staff steps up in G major: G4
    m.drag_to(3, key=1)                          # one more: A4 (one undo step for the drag)
    m.drag_end()
    assert step["bars"][0] == ["C4", "A4"]
    m.undo()
    assert step["bars"][0] == ["C4", "E4"]
    m.select(0, 0, staff=1)
    m.drag_start()
    m.drag_to(-4, key=1)                         # four steps down from C3, in G major: F#2
    m.drag_end()
    assert step["lh"]["bars"][0] == ["F#2"]
    sched = m.schedule(bpm=60)
    starts = sorted((round(s, 2), w[0]) for s, _, _, w in sched)
    assert starts == [(0.0, 0), (0.0, 1), (2.0, 0), (4.0, 1)]
    m.set_hands(False)
    assert "lh" not in step

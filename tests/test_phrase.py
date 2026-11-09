"""A screen's music written once: old screens become phrases without changing how they
play, and a phrase gives the player its notes, rhythm, fingers and staff."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pianove import phrase  # noqa: E402


def _beats():
    for d in sorted((ROOT / "pianove" / "lessons").iterdir()):
        f = d / "steps.json"
        if f.exists():
            for s in json.loads(f.read_text(encoding="utf-8")):
                for b in s.get("beats", []):
                    yield d.name, b


def test_built_in_screens_compile_back_to_what_they_play():
    n = 0
    for name, beat in _beats():
        if not beat.get("play"):
            continue
        b = copy.deepcopy(beat)
        phrase.ensure_music(b)
        phrase.compile_beat(b)
        norm = lambda xs: [sorted(x.split("+")) for x in xs]
        assert norm(b["play"]) == norm(beat["play"]), name
        assert b["rhythm"] == [[float(k), 1.0] for k in range(len(beat["play"]))], name
        if beat.get("fingers"):
            assert b["fingers"] == beat["fingers"], name
        n += 1
    assert n > 30


def test_kinds():
    assert phrase.kind_of({"play": ["C4"]}) == "listen"
    assert phrase.kind_of({"try": ["C4"]}) == "find"
    assert phrase.kind_of({"hand": {"right": {"C4": 1}}}) == "hand"
    assert phrase.kind_of({"say": {"en": "hi"}}) == "explain"
    assert phrase.kind_of({"kind": "hand", "play": ["C4"]}) == "hand"


def test_a_phrase_with_rhythm_both_hands_and_fingers():
    beat = {"staff": {"clef": "treble", "notes": []}, "try": "play", "music": {
        "time": [3, 4], "tempo": 90,
        "bars": [["C4@1~", "C4@1", "r"], ["E4@3", "G4@5"]],
        "types": [["quarter", "quarter", "quarter"], ["half", "quarter"]],
        "lh": {"bars": [["C3@5"], ["G2@1"]], "types": [["dotted_half"], ["dotted_half"]]}}}
    phrase.compile_beat(beat)
    assert beat["play"] == ["C3+C4", "G2+E4", "G4"]
    assert beat["rhythm"] == [[0.0, 3.0], [3.0, 3.0], [5.0, 1.0]]   # C4 tied: two beats, C3 three
    assert beat["fingers"] == ["5+1", "1+3", 5]
    assert beat["left"] == ["G2", "C3"]
    assert beat["tempo"] == 90
    assert beat["staff"]["notes"] == beat["play"] and beat["staff"]["clef"] == "grand"


def test_the_player_reads_a_compiled_phrase():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    sys.path.insert(0, str(ROOT / "PyLay"))
    import pianove  # noqa: F401
    from pianove.pages.theory import _Beat
    beat = {"music": {"time": [4, 4], "bars": [["C4@1", "E4@3", "G4@5"]],
                      "types": [["half", "quarter", "quarter"]]}}
    phrase.compile_beat(beat)
    b = _Beat(beat, "")
    assert b.rhythm == [(0.0, 2.0), (2.0, 1.0), (3.0, 1.0)]
    assert b.finger_of(1, 64) == 3 and b.side_of(64) == "right"

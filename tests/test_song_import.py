"""The MusicXML importer keeps the whole piece as it sounds: every voice, tuplets, short
notes, ties, double sharps, tremolos, tempo changes and dynamics.

Run:  python -m pytest tests/test_song_import.py -q      (or just: python tests/test_song_import.py)
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pianove  # noqa: E402,F401  (puts PyLay and PyLute on the path)
from pianove.song_store import _parse_musicxml  # noqa: E402


def _note(step, octave, dur, ntype, staff=1, voice=1, alter=0, extra="", chord=False):
    return (f"<note>{'<chord/>' if chord else ''}<pitch><step>{step}</step>"
            f"{f'<alter>{alter}</alter>' if alter else ''}<octave>{octave}</octave></pitch>"
            f"<duration>{dur}</duration>{extra}<voice>{voice}</voice><type>{ntype}</type>"
            f"<staff>{staff}</staff></note>")


SCORE = f"""<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1"><work><work-title>Test</work-title></work>
<part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
<part id="P1">
<measure number="1">
  <attributes><divisions>12</divisions><key><fifths>0</fifths></key>
    <time><beats>2</beats><beat-type>4</beat-type></time><staves>2</staves></attributes>
  <direction><sound tempo="100" dynamics="50"/></direction>
  {_note("C", 5, 4, "eighth", extra="<time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>")}
  {_note("D", 5, 4, "eighth", extra="<time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>")}
  {_note("E", 5, 4, "eighth", extra="<time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>")}
  {_note("F", 5, 3, "32nd", alter=2)}
  {_note("G", 5, 9, "eighth", extra="<dot/>")}
  <backup><duration>24</duration></backup>
  {_note("A", 4, 24, "half", voice=2)}
  <backup><duration>24</duration></backup>
  {_note("C", 3, 24, "half", staff=2, voice=5, extra='<tie type="start"/>')}
</measure>
<measure number="2">
  <direction><sound tempo="120"/></direction>
  {_note("C", 3, 24, "half", staff=2, voice=5, extra='<tie type="stop"/>')}
  <backup><duration>24</duration></backup>
  {_note("B", 4, 12, "quarter", extra='<notations><ornaments><tremolo type="start">2</tremolo></ornaments></notations>')}
  {_note("D", 5, 12, "quarter", extra='<notations><ornaments><tremolo type="stop">2</tremolo></ornaments></notations>')}
</measure>
</part></score-partwise>"""


def _parsed():
    path = os.path.join(tempfile.mkdtemp(), "test.musicxml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(SCORE)
    return _parse_musicxml(path)


def test_every_voice_tuplet_and_short_note_is_kept():
    d = _parsed()
    bar = list(zip(d["bars_rh"][0], d["onsets_rh"][0], d["durs_rh"][0]))
    assert [p for p, _, _ in bar] == ["C5", "D5", "E5", "G5", "G5", "A4"]
    assert [round(o, 3) for _, o, _ in bar][:3] == [0.0, 0.333, 0.667]   # a triplet
    assert bar[3][0] == "G5" and bar[3][1] == 1.0 and bar[3][2] == 0.25   # F double sharp, a 32nd
    assert bar[5] == ("A4", 0.0, 2.0)                                     # the second voice


def test_ties_hold_instead_of_striking_again():
    d = _parsed()
    assert d["durs_lh"][0] == [4.0] and d["ties_lh"][0] == [False]       # held through both bars
    assert d["ties_lh"][1] == [True]                                      # drawn, not struck


def test_tremolo_tempo_and_dynamics():
    d = _parsed()
    trem = list(zip(d["bars_rh"][1], d["onsets_rh"][1]))
    assert [p for p, _ in trem] == ["B4", "D5"] * 4                       # 16ths, alternating
    assert [o for _, o in trem] == [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75]
    assert d["tempos"] == [[0.0, 100.0], [2.0, 120.0]]
    assert d["vels_rh"][0][0] == 45                                       # 50 % of forte (90)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
    print("import ok")

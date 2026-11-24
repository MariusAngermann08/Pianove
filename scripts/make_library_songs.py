"""Write the songs Pianove brings along (pianove/assets/songs/*.musicxml).

Public-domain tunes in simple arrangements for two hands: the melody in the right hand,
one bass note (or two) per bar in the left. They are written here in a short form and
turned into ordinary MusicXML, so they import like any song you add yourself.

    python scripts/make_library_songs.py

Notes are "C4:q" (pitch:length), "r:h" a rest, "C3+G3:w" a chord. Lengths: w h q e s
(whole … sixteenth), with a "d" in front for dotted (dh = dotted half). Every bar is
checked against the time signature.
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "pianove" / "assets" / "songs"

DIV = 4                                         # divisions per quarter: a sixteenth is 1
_LEN = {"w": (16, "whole"), "h": (8, "half"), "q": (4, "quarter"), "e": (2, "eighth"),
        "s": (1, "16th")}

# (file, title, composer, key fifths, (beats, beat type), quarter notes a minute, right, left)
SONGS = [
    ("01_mary_had_a_little_lamb", "Mary Had a Little Lamb", "Traditional", 0, (4, 4), 100,
     ["E4:q D4:q C4:q D4:q", "E4:q E4:q E4:h", "D4:q D4:q D4:h", "E4:q G4:q G4:h",
      "E4:q D4:q C4:q D4:q", "E4:q E4:q E4:q E4:q", "D4:q D4:q E4:q D4:q", "C4:w"],
     ["C3:w", "C3:w", "G3:w", "C3:w", "C3:w", "C3:w", "G3:w", "C3:w"]),

    ("02_twinkle_twinkle_little_star", "Twinkle, Twinkle, Little Star", "Traditional", 0, (4, 4), 100,
     ["C4:q C4:q G4:q G4:q", "A4:q A4:q G4:h", "F4:q F4:q E4:q E4:q", "D4:q D4:q C4:h",
      "G4:q G4:q F4:q F4:q", "E4:q E4:q D4:h", "G4:q G4:q F4:q F4:q", "E4:q E4:q D4:h",
      "C4:q C4:q G4:q G4:q", "A4:q A4:q G4:h", "F4:q F4:q E4:q E4:q", "D4:q D4:q C4:h"],
     ["C3:w", "F3:h C3:h", "F3:h C3:h", "G3:h C3:h", "C3:h F3:h", "C3:h G3:h",
      "C3:h F3:h", "C3:h G3:h", "C3:w", "F3:h C3:h", "F3:h C3:h", "G3:h C3:h"]),

    ("03_alle_meine_entchen", "Alle meine Entchen", "Traditional", 0, (4, 4), 100,
     ["C4:q D4:q E4:q F4:q", "G4:h G4:h", "A4:q A4:q A4:q A4:q", "G4:w",
      "A4:q A4:q A4:q A4:q", "G4:w", "F4:q F4:q F4:q F4:q", "E4:h E4:h",
      "D4:q D4:q D4:q D4:q", "C4:w"],
     ["C3:w", "C3:w", "F3:w", "C3:w", "F3:w", "C3:w", "F3:w", "C3:w", "G3:w", "C3:w"]),

    ("04_frere_jacques", "Frère Jacques", "Traditional", 0, (4, 4), 104,
     ["C4:q D4:q E4:q C4:q", "C4:q D4:q E4:q C4:q", "E4:q F4:q G4:h", "E4:q F4:q G4:h",
      "G4:e A4:e G4:e F4:e E4:q C4:q", "G4:e A4:e G4:e F4:e E4:q C4:q",
      "C4:q G3:q C4:h", "C4:q G3:q C4:h"],
     ["C3:h G3:h", "C3:h G3:h", "C3:h G3:h", "C3:h G3:h", "C3:h G3:h", "C3:h G3:h",
      "C3:w", "C3:w"]),

    ("05_ode_to_joy", "Ode to Joy", "Ludwig van Beethoven", 0, (4, 4), 100,
     ["E4:q E4:q F4:q G4:q", "G4:q F4:q E4:q D4:q", "C4:q C4:q D4:q E4:q", "E4:dq D4:e D4:h",
      "E4:q E4:q F4:q G4:q", "G4:q F4:q E4:q D4:q", "C4:q C4:q D4:q E4:q", "D4:dq C4:e C4:h",
      "D4:q D4:q E4:q C4:q", "D4:q E4:e F4:e E4:q C4:q", "D4:q E4:e F4:e E4:q D4:q",
      "C4:q D4:q G3:h",
      "E4:q E4:q F4:q G4:q", "G4:q F4:q E4:q D4:q", "C4:q C4:q D4:q E4:q", "D4:dq C4:e C4:h"],
     ["C3:w", "G3:w", "C3:w", "G3:w", "C3:w", "G3:w", "C3:w", "G3:h C3:h",
      "G3:h C3:h", "G3:h C3:h", "G3:w", "C3:h G2:h",
      "C3:w", "G3:w", "C3:w", "G3:h C3:h"]),

    ("06_jingle_bells", "Jingle Bells", "James Lord Pierpont", 0, (4, 4), 116,
     ["E4:q E4:q E4:h", "E4:q E4:q E4:h", "E4:q G4:q C4:dq D4:e", "E4:w",
      "F4:q F4:q F4:dq F4:e", "F4:q E4:q E4:q E4:e E4:e", "E4:q D4:q D4:q E4:q", "D4:h G4:h",
      "E4:q E4:q E4:h", "E4:q E4:q E4:h", "E4:q G4:q C4:dq D4:e", "E4:w",
      "F4:q F4:q F4:q F4:q", "F4:q E4:q E4:q E4:e E4:e", "G4:q G4:q F4:q D4:q", "C4:w"],
     ["C3:w", "C3:w", "C3:w", "C3:w", "F3:w", "C3:w", "G3:w", "G3:w",
      "C3:w", "C3:w", "C3:w", "C3:w", "F3:w", "C3:w", "G3:w", "C3:w"]),

    ("07_when_the_saints", "When the Saints Go Marching In", "Traditional", 0, (4, 4), 112,
     ["r:q C4:q E4:q F4:q", "G4:w", "r:q C4:q E4:q F4:q", "G4:w",
      "r:q C4:q E4:q F4:q", "G4:h E4:h", "C4:h E4:h", "D4:w",
      "r:q E4:q E4:q D4:q", "C4:dh E4:q", "G4:h G4:q F4:q", "F4:w",
      "r:q C4:q E4:q F4:q", "G4:h E4:h", "C4:h D4:h", "C4:w"],
     ["r:w", "C3:w", "C3:w", "C3:w", "C3:w", "C3:w", "C3:w", "G3:w",
      "C3:w", "C3:w", "C3:w", "F3:w", "C3:w", "C3:w", "G3:w", "C3:w"]),

    ("08_amazing_grace", "Amazing Grace", "Traditional", 0, (3, 4), 80,
     ["r:h G3:q", "C4:h E4:e C4:e", "E4:h D4:q", "C4:h A3:q", "G3:h G3:q",
      "C4:h E4:e C4:e", "E4:h D4:q", "G4:dh", "G4:h E4:q", "G4:h E4:e C4:e",
      "E4:h D4:q", "C4:h A3:q", "G3:h G3:q", "C4:h E4:e C4:e", "E4:h D4:q", "C4:dh"],
     ["r:dh", "C3:dh", "C3:dh", "F3:dh", "C3:dh", "C3:dh", "G3:dh", "C3:dh", "C3:dh",
      "C3:dh", "G3:dh", "F3:dh", "C3:dh", "C3:dh", "G3:dh", "C3:dh"]),

    ("09_greensleeves", "Greensleeves", "Traditional", 0, (3, 4), 88,
     ["r:h A4:q", "C5:h D5:q", "E5:dq F5:e E5:q", "D5:h B4:q", "G4:dq A4:e B4:q",
      "C5:h A4:q", "A4:dq G#4:e A4:q", "B4:h G#4:q", "E4:h A4:q", "C5:h D5:q",
      "E5:dq F5:e E5:q", "D5:h B4:q", "G4:dq A4:e B4:q", "C5:dq B4:e A4:q",
      "G#4:dq F#4:e G#4:q", "A4:dh"],
     ["r:dh", "A3:dh", "C3:dh", "G3:dh", "E3:dh", "A3:dh", "E3:dh", "E3:dh", "A3:dh",
      "A3:dh", "C3:dh", "G3:dh", "E3:dh", "A3:dh", "E3:dh", "A3:dh"]),

    ("10_minuet_in_g", "Minuet in G", "Christian Petzold", 1, (3, 4), 96,
     ["D5:q G4:e A4:e B4:e C5:e", "D5:q G4:q G4:q", "E5:q C5:e D5:e E5:e F#5:e",
      "G5:q G4:q G4:q", "C5:q D5:e C5:e B4:e A4:e", "B4:q C5:e B4:e A4:e G4:e",
      "F#4:q G4:e A4:e B4:e G4:e", "A4:dh",
      "D5:q G4:e A4:e B4:e C5:e", "D5:q G4:q G4:q", "E5:q C5:e D5:e E5:e F#5:e",
      "G5:q G4:q G4:q", "C5:q D5:e C5:e B4:e A4:e", "B4:q C5:e B4:e A4:e G4:e",
      "A4:q B4:e A4:e G4:e F#4:e", "G4:dh"],
     ["G3:h A3:q", "B3:dh", "C4:dh", "B3:dh", "A3:dh", "G3:dh", "D3:dh", "D3:dh",
      "G3:h A3:q", "B3:dh", "C4:dh", "B3:dh", "A3:dh", "G3:dh", "D3:dh", "G3:dh"]),

    ("11_fur_elise", "Für Elise (theme)", "Ludwig van Beethoven", 0, (3, 8), 50,
     ["r:q E5:s D#5:s", "E5:s D#5:s E5:s B4:s D5:s C5:s", "A4:e r:s C4:s E4:s A4:s",
      "B4:e r:s E4:s G#4:s B4:s", "C5:e r:s E4:s E5:s D#5:s",
      "E5:s D#5:s E5:s B4:s D5:s C5:s", "A4:e r:s C4:s E4:s A4:s",
      "B4:e r:s E4:s C5:s B4:s", "A4:dq"],
     ["r:dq", "r:dq", "A2:dq", "E3:dq", "A3:dq", "r:dq", "A2:dq", "E3:dq", "A2:dq"]),

    ("12_canon_in_d", "Canon in D", "Johann Pachelbel", 2, (4, 4), 60,
     ["F#5:h E5:h", "D5:h C#5:h", "B4:h A4:h", "B4:h C#5:h",
      "D5:h C#5:h", "B4:h A4:h", "G4:h F#4:h", "G4:h E4:h",
      "D4:q F#4:q A4:q G4:q", "F#4:q D4:q F#4:q E4:q", "D4:q B3:q D4:q A4:q",
      "G4:q B4:q A4:q G4:q", "F#4:w"],
     ["D3:h A2:h", "B2:h F#2:h", "G2:h D2:h", "G2:h A2:h",
      "D3:h A2:h", "B2:h F#2:h", "G2:h D2:h", "G2:h A2:h",
      "D3:h A2:h", "B2:h F#2:h", "G2:h D2:h", "G2:h A2:h", "D3:w"]),
]

MINOR = {"09_greensleeves", "11_fur_elise"}


def _length(code: str) -> tuple[int, str, bool]:
    dotted = code.startswith("d")
    units, name = _LEN[code[1:] if dotted else code]
    return (units * 3 // 2 if dotted else units), name, dotted


def _pitch_xml(p: str, fifths: int) -> str:
    step, rest = p[0], p[1:]
    alter = rest.count("#") - rest.count("b")
    octave = rest.strip("#b")
    acc = ""
    if alter and not (fifths >= 1 and step == "F" or fifths >= 2 and step == "C"):
        acc = "<accidental>sharp</accidental>" if alter > 0 else "<accidental>flat</accidental>"
    alt = f"<alter>{alter}</alter>" if alter else ""
    return f"<pitch><step>{step}</step>{alt}<octave>{octave}</octave></pitch>", acc


def _notes(bar: str, staff: int, voice: int, fifths: int) -> tuple[str, int]:
    out, total = [], 0
    for tok in bar.split():
        pitches, code = tok.split(":")
        units, name, dotted = _length(code)
        dot = "<dot/>" if dotted else ""
        for k, p in enumerate(pitches.split("+")):
            chord = "<chord/>" if k else ""
            if p == "r":
                body, acc = "<rest/>", ""
            else:
                body, acc = _pitch_xml(p, fifths)
            out.append(f"<note>{chord}{body}<duration>{units}</duration><voice>{voice}</voice>"
                       f"<type>{name}</type>{dot}{acc}<staff>{staff}</staff></note>")
        total += units
    return "".join(out), total


def song_xml(title, composer, fifths, time, bpm, rh, lh, minor=False) -> str:
    assert len(rh) == len(lh), title
    bar_units = DIV * 4 * time[0] // time[1]
    measures = []
    for i, (r, l) in enumerate(zip(rh, lh), 1):
        right, ru = _notes(r, 1, 1, fifths)
        left, lu = _notes(l, 2, 2, fifths)
        assert ru == bar_units and lu == bar_units, f"{title} bar {i}: {ru}/{lu} ≠ {bar_units}"
        head = ""
        if i == 1:
            mode = "<mode>minor</mode>" if minor else ""
            head = (f"<attributes><divisions>{DIV}</divisions><key><fifths>{fifths}</fifths>{mode}</key>"
                    f"<time><beats>{time[0]}</beats><beat-type>{time[1]}</beat-type></time>"
                    "<staves>2</staves><clef number=\"1\"><sign>G</sign><line>2</line></clef>"
                    "<clef number=\"2\"><sign>F</sign><line>4</line></clef></attributes>"
                    f"<direction placement=\"above\"><direction-type><metronome><beat-unit>"
                    f"quarter</beat-unit><per-minute>{bpm}"
                    f"</per-minute></metronome></direction-type><sound tempo=\"{bpm}\"/></direction>")
        measures.append(f'<measure number="{i}">{head}{right}<backup><duration>{bar_units}'
                        f'</duration></backup>{left}</measure>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" '
            '"http://www.musicxml.org/dtds/partwise.dtd">\n'
            '<score-partwise version="3.1">'
            f"<work><work-title>{escape(title)}</work-title></work>"
            f'<identification><creator type="composer">{escape(composer)}</creator>'
            '<creator type="arranger">Pianove</creator><rights>Public domain</rights></identification>'
            '<part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>'
            f'<part id="P1">{"".join(measures)}</part></score-partwise>\n')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, title, composer, fifths, time, bpm, rh, lh in SONGS:
        minor = name in MINOR
        (OUT / f"{name}.musicxml").write_text(song_xml(title, composer, fifths, time, bpm, rh, lh, minor),
                                              encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()

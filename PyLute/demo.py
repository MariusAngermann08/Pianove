import pygame as pg
import sys
import pylute

pg.init()
screen = pg.display.set_mode((1200, 800), pg.RESIZABLE)
pg.display.set_caption("OpenScore")
clock = pg.time.Clock()

# Usage: python demo.py [file.xml|file.mxl]
if len(sys.argv) > 1:
    score = pylute.load_musicxml(sys.argv[1], surface=screen)
    while True:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                sys.exit()
        screen.fill((255, 255, 255))
        score.draw()
        pg.display.update()
        clock.tick(60)

score = pylute.Score(
    surface=screen,
    staffs=2,
    length=1100,
    bars=8,
    clef_types=["treble", "bass"],
    key="G",
    time=(4, 4),
)

def add(staff, *events):
    """Add a sequence of ('n', ntype, pitch) or ('r', rtype) tuples."""
    for ev in events:
        if ev[0] == "n":
            score.addNote(ntype=ev[1], pitch=ev[2], staff_index=staff)
        else:
            score.addRest(rtype=ev[1], staff_index=staff)

# Treble
add(0,
    # Bar 1: four quarter notes
    ("n", "quarter",        "G4"), ("n", "quarter",       "A4"),
    ("n", "quarter",        "B4"), ("n", "quarter",        "D5"),
    # Bar 2: eight eighth notes — beamed
    ("n", "eighth",         "G4"), ("n", "eighth",         "A4"),
    ("n", "eighth",         "B4"), ("n", "eighth",         "C5"),
    ("n", "eighth",         "D5"), ("n", "eighth",         "E5"),
    ("n", "eighth",         "D5"), ("n", "eighth",         "B4"),
    # Bar 3: half + four eighths
    ("n", "half",           "G4"),
    ("n", "eighth",         "B4"), ("n", "eighth",         "D5"),
    ("n", "eighth",         "G5"), ("n", "eighth",         "F#5"),
    # Bar 4: sixteenth run + quarter + quarter  — 0.5+0.25+0.25 = 1.0
    ("n", "sixteenth",      "G5"), ("n", "sixteenth",      "F#5"),
    ("n", "sixteenth",      "E5"), ("n", "sixteenth",      "D5"),
    ("n", "sixteenth",      "C5"), ("n", "sixteenth",      "B4"),
    ("n", "sixteenth",      "A4"), ("n", "sixteenth",      "G4"),
    ("n", "quarter",        "G4"), ("n", "quarter",        "D5"),
    # Bar 5: dotted-quarter + eighth rhythm (x2)  — 0.375+0.125+0.375+0.125 = 1.0
    ("n", "dotted_quarter", "D5"), ("n", "eighth",         "E5"),
    ("n", "dotted_quarter", "F#5"), ("n", "eighth",        "G5"),
    # Bar 6: dotted half + quarter  — 0.75+0.25 = 1.0
    ("n", "dotted_half",    "G5"), ("n", "quarter",        "F#5"),
    # Bar 7: three eighths + eighth rest + two quarters  — 0.375+0.125+0.5 = 1.0
    ("n", "eighth",         "G5"), ("n", "eighth",         "F#5"),
    ("n", "eighth",         "E5"), ("r", "eighth"),
    ("n", "quarter",        "D5"), ("n", "quarter",        "B4"),
    # Bar 8: dotted-quarter + eighth + half  — 0.375+0.125+0.5 = 1.0
    ("n", "dotted_quarter", "G4"), ("n", "eighth",         "A4"),
    ("n", "half",           "B4"),
)

# Bass
add(1,
    # Bar 1
    ("n", "whole",          "G2"),
    # Bar 2
    ("n", "half",           "D3"), ("n", "half",           "G3"),
    # Bar 3
    ("n", "quarter",        "G2"), ("n", "quarter",        "B2"),
    ("n", "quarter",        "D3"), ("n", "quarter",        "G3"),
    # Bar 4
    ("n", "whole",          "D2"),
    # Bar 5: dotted-half + quarter  — 0.75+0.25 = 1.0
    ("n", "dotted_half",    "G2"), ("n", "quarter",        "D3"),
    # Bar 6: whole
    ("n", "whole",          "G2"),
    # Bar 7
    ("n", "quarter",        "D3"), ("n", "quarter",        "F#3"),
    ("n", "quarter",        "A3"), ("n", "quarter",        "D4"),
    # Bar 8: dotted-quarter + eighth + half  — 0.375+0.125+0.5 = 1.0
    ("n", "dotted_quarter", "G2"), ("n", "eighth",         "A2"),
    ("n", "half",           "D3"),
)

while True:
    for event in pg.event.get():
        if event.type == pg.QUIT:
            sys.exit()

    screen.fill((255, 255, 255))
    score.draw()
    pg.display.update()
    clock.tick(60)

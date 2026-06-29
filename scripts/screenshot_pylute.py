"""
Capture PyLute score screenshot for docs.
Run from the project root: python scripts/screenshot_pylute.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "PyLute"))

OUT = ROOT / "docs" / "img"
OUT.mkdir(parents=True, exist_ok=True)

import pygame as pg
import pylute

W, H = 1024, 600
pg.init()
screen = pg.display.set_mode((W, H))
pg.display.set_caption("PyLute Score")
clock = pg.time.Clock()

score = pylute.Score(
    surface=screen,
    staffs=2,
    length=W - 40,
    bars=8,
    clef_types=["treble", "bass"],
    key="G",
    time=(4, 4),
)

def add(staff, *events):
    for ev in events:
        if ev[0] == "n":
            score.addNote(ntype=ev[1], pitch=ev[2], staff_index=staff)
        else:
            score.addRest(rtype=ev[1], staff_index=staff)

# Treble — same as demo.py
add(0,
    ("n", "quarter",        "G4"), ("n", "quarter",       "A4"),
    ("n", "quarter",        "B4"), ("n", "quarter",        "D5"),
    ("n", "eighth",         "G4"), ("n", "eighth",         "A4"),
    ("n", "eighth",         "B4"), ("n", "eighth",         "C5"),
    ("n", "eighth",         "D5"), ("n", "eighth",         "E5"),
    ("n", "eighth",         "D5"), ("n", "eighth",         "B4"),
    ("n", "half",           "G4"),
    ("n", "eighth",         "B4"), ("n", "eighth",         "D5"),
    ("n", "eighth",         "G5"), ("n", "eighth",         "F#5"),
    ("n", "sixteenth",      "G5"), ("n", "sixteenth",      "F#5"),
    ("n", "sixteenth",      "E5"), ("n", "sixteenth",      "D5"),
    ("n", "sixteenth",      "C5"), ("n", "sixteenth",      "B4"),
    ("n", "sixteenth",      "A4"), ("n", "sixteenth",      "G4"),
    ("n", "quarter",        "G4"), ("n", "quarter",        "D5"),
    ("n", "dotted_quarter", "D5"), ("n", "eighth",         "E5"),
    ("n", "dotted_quarter", "F#5"), ("n", "eighth",        "G5"),
    ("n", "dotted_half",    "G5"), ("n", "quarter",        "F#5"),
    ("n", "eighth",         "G5"), ("n", "eighth",         "F#5"),
    ("n", "eighth",         "E5"), ("r", "eighth"),
    ("n", "quarter",        "D5"), ("n", "quarter",        "B4"),
    ("n", "dotted_quarter", "G4"), ("n", "eighth",         "A4"),
    ("n", "half",           "B4"),
)

# Bass
add(1,
    ("n", "whole",          "G2"),
    ("n", "half",           "D3"), ("n", "half",           "G3"),
    ("n", "quarter",        "G2"), ("n", "quarter",        "B2"),
    ("n", "quarter",        "D3"), ("n", "quarter",        "G3"),
    ("n", "whole",          "D2"),
    ("n", "dotted_half",    "G2"), ("n", "quarter",        "D3"),
    ("n", "whole",          "G2"),
    ("n", "quarter",        "D3"), ("n", "quarter",        "F#3"),
    ("n", "quarter",        "A3"), ("n", "quarter",        "D4"),
    ("n", "dotted_quarter", "G2"), ("n", "eighth",         "A2"),
    ("n", "half",           "D3"),
)

print("Taking PyLute screenshot …")
frame = 0
CAPTURE_AT = 10

running = True
while running:
    for ev in pg.event.get():
        if ev.type == pg.QUIT:
            running = False

    screen.fill((255, 255, 255))
    score.draw()
    pg.display.update()
    clock.tick(60)
    frame += 1

    if frame >= CAPTURE_AT:
        path = OUT / "ss-pylute.png"
        pg.image.save(screen, str(path))
        print(f"  ✓  {path.name}")
        running = False

pg.quit()
print("Done.")

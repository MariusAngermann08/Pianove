# PyLute

Music notation renderer built on [pygame](https://www.pygame.org/). Renders sheet music from MusicXML files or programmatic note input directly into a pygame surface.

## Installation

PyLute is not yet published to PyPI. Clone the [Pianove repository](https://github.com/MariusAngermann08/Pianove) and import directly from the `PyLute/` directory, or add it to your project path:

```bash
git clone https://github.com/MariusAngermann08/Pianove.git
```

```python
import sys
sys.path.insert(0, "path/to/Pianove/PyLute")
import pylute
```

Requires **Python ≥ 3.10** and **pygame-ce ≥ 2.4** (`pip install pygame-ce`).

## Quick start

```python
import pygame as pg
import pylute

pg.init()
screen = pg.display.set_mode((1200, 600), pg.RESIZABLE)

score = pylute.Score(surface=screen, staffs=1, bars=4, key="C", time=(4, 4))
score.addNote("quarter", "C4")
score.addNote("quarter", "E4")
score.addNote("quarter", "G4")
score.addNote("quarter", "C5")

clock = pg.time.Clock()
while True:
    for event in pg.event.get():
        if event.type == pg.QUIT:
            pg.quit(); exit()
        if event.type == pg.VIDEORESIZE:
            score.surface = pg.display.set_mode(event.size, pg.RESIZABLE)
    screen.fill((255, 255, 255))
    score.draw()
    pg.display.flip()
    clock.tick(60)
```

## Load a MusicXML file

```python
score = pylute.load_musicxml("bach_prelude.xml", surface=screen)
```

## Features

- Whole, half, quarter, eighth, sixteenth, 32nd notes and rests (all dotted variants)
- Chord notes (simultaneous pitches, notehead offset for 2nds, accidental staggering)
- Ties across barlines
- Tuplets / triplets with bracket and number
- Dynamics: pp, p, mp, mf, f, ff, fff, sfz, fp, …
- Articulations: staccato, accent, tenuto, marcato, fermata
- Key signatures (all major/minor keys)
- Time signatures
- Treble and bass clef; piano grand staff with brace
- Beaming for eighth/sixteenth/32nd note groups
- Ledger lines above and below the staff
- Responsive layout — reflows on window resize
- MusicXML import (`.xml`, `.musicxml`, `.mxl`)
- PyLay integration via `ScoreCanvas` (scrollable) and `ScorePager` (paged)

## What is not yet supported

- Multiple voices on a single staff
- Slurs
- Repeat barlines / da capo
- Multi-instrument scores (first part only)
- Grace notes
- Lyrics

## API reference

Full documentation: [mariusangermann08.github.io/Pianove/pylute.html](https://mariusangermann08.github.io/Pianove/pylute.html)

## License

GNU General Public License v3.0 — see [`LICENSE`](../LICENSE).

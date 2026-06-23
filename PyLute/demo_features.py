import sys
import pygame as pg
sys.path.insert(0, ".")

import pylute
from pylute import Score, Note, Rest, Chord, Tuplet, Dynamic, Articulation

pg.init()
W, H = 1540, 960
screen = pg.display.set_mode((W, H), pg.RESIZABLE)
pg.display.set_caption("PyLute v0.1 — New Features Demo")
clock = pg.time.Clock()

BG      = (252, 250, 246)
PILL_FG = (185, 65, 20)
PILL_BG = (255, 247, 241)
PILL_BD = (210, 100, 50)

score = Score(
    surface         = screen,
    staffs          = 2,
    bars            = 8,
    clef_types      = ["treble", "bass"],
    key             = "C",
    time            = (4, 4),
    bars_per_system = 4,
)
score.title    = "New Features Showcase"
score.composer = "PyLute v0.1"

T = score.staffs[0]
B = score.staffs[1]


def ch(pitches, ntype, staff=None):
    s = staff or T
    return Chord([Note(ntype, p, s) for p in pitches], staff=s)

def n(pitch, ntype, staff=None, dyn=None, arts=None):
    s    = staff or T
    note = Note(ntype, pitch, s)
    if dyn:
        note.expressions.append(Dynamic(dyn, staff=s))
    if arts:
        for a in ([arts] if isinstance(arts, str) else arts):
            above = note._stem_dir() == "down"
            note.expressions.append(Articulation(a, staff=s, above=above))
    return note

def tri(pitches, staff=None):
    s = staff or T
    return Tuplet([Note("quarter", p, s) for p in pitches], actual=3, normal=2, staff=s)


# bars 0-1: chord notes
T.bars[0].events += [
    ch(["C4","E4","G4"], "quarter"),
    ch(["F4","A4","C5"], "quarter"),
    ch(["G4","B4","D5"], "quarter"),
    ch(["E4","G4","C5"], "quarter"),
]
B.bars[0].events += [n("C3","half",B), n("G2","half",B)]

T.bars[1].events += [
    ch(["C4","E4","G4","C5"], "quarter"),
    ch(["C4","D4","G4"],      "quarter"),  # C-D is a 2nd, notehead gets offset
    ch(["F4","G4","A4"],      "quarter"),
    ch(["G3","B3","D4","G4"], "quarter"),
]
B.bars[1].events += [
    n("C3","quarter",B), n("D3","quarter",B),
    n("F2","quarter",B), n("G2","quarter",B),
]

# bars 2-3: cross-bar tie on B4
n_start = n("B4", "dotted_half")
n_end   = n("B4", "half")
n_start.tied_to  = n_end
n_end.tied_from  = True

T.bars[2].events += [n_start, n("G4","quarter")]
T.bars[3].events += [n_end, n("D5","quarter"), n("G4","quarter")]
B.bars[2].events += [n("G2","whole",B)]
B.bars[3].events += [n("E3","half",B), n("B2","half",B)]

# bars 4-5: tuplets
T.bars[4].events += [tri(["C5","E5","G5"]), tri(["G4","A4","B4"])]
B.bars[4].events += [n("C3","whole",B)]

T.bars[5].events += [tri(["G5","E5","C5"]), n("G4","quarter"), n("C5","quarter")]
B.bars[5].events += [n("G2","half",B), n("C3","half",B)]

# bar 6: articulations
T.bars[6].events += [
    n("C5", "quarter", arts="staccato"),
    n("E5", "quarter", arts="accent"),
    n("G5", "quarter", arts="tenuto"),
    n("G5", "quarter", arts="fermata"),
]
B.bars[6].events += [n("C3","whole",B)]

# bar 7: 32nd note run + ff resolution
_run = ["C4","D4","E4","F4","G4","A4","B4","C5",
        "D5","E5","F5","G5","F5","E5","D5","C5"]
for p in _run:
    T.bars[7].events.append(Note("thirty_second", p, T))
T.bars[7].events.append(n("C5", "half", dyn="ff"))
B.bars[7].events += [n("G2","half",B), n("C3","half",B)]


LABELS = [
    (0, "Chord Notes"),
    (1, "4-note  ·  2nd offset"),
    (2, "Cross-bar Tie"),
    (4, "Tuplets"),
    (6, "Articulations"),
    (7, "32nd Notes"),
]

_lf = None

def _font(space):
    global _lf
    sz = max(11, int(space * 1.5))
    if _lf is None or _lf.size("X")[1] != sz:
        _lf = pg.font.SysFont("Segoe UI,Arial", sz, bold=True)
    return _lf


def draw_labels():
    tops  = score.system_y_tops()
    space = score.staffs[0].space
    font  = _font(space)
    pad   = (7, 3)

    for bar_idx, text in LABELS:
        if bar_idx >= len(score.staffs[0].bars):
            continue
        bar = score.staffs[0].bars[bar_idx]
        if bar.barspace == 0:
            continue
        sys_idx = bar_idx // score.bars_per_system
        if sys_idx >= len(tops):
            continue

        x = int(bar.bar_start_x) + 5
        y = int(tops[sys_idx]) - int(space * 2.2)

        surf = font.render(text, True, PILL_FG)
        tw, th = surf.get_size()
        pill = pg.Rect(x - pad[0], y - pad[1], tw + pad[0]*2, th + pad[1]*2)
        pg.draw.rect(screen, PILL_BG, pill, border_radius=5)
        pg.draw.rect(screen, PILL_BD, pill, width=1, border_radius=5)
        screen.blit(surf, (x, y))


while True:
    for event in pg.event.get():
        if event.type == pg.QUIT:
            sys.exit()
        if event.type == pg.VIDEORESIZE:
            W, H   = event.size
            screen = pg.display.set_mode((W, H), pg.RESIZABLE)
            score.surface = screen
            for st in score.staffs:
                st.surface = screen
            if score.brace:
                score.brace.surface = screen

    screen.fill(BG)
    score.draw()
    draw_labels()
    pg.display.update()
    clock.tick(60)

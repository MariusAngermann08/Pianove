"""
Capture PyLay showcase screenshots (one per tab) for docs.
Run from the project root: python scripts/screenshot_pylay.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "PyLay"))

OUT = ROOT / "docs" / "img"
OUT.mkdir(parents=True, exist_ok=True)

import pygame
import pylay as pl
from pylay.core.theme import iOSTheme
from pylay.core import _dirty

from showcase import build_root, dark_st, tab_st

pl.set_window_size(1024, 768)
app = pl.App(title="PyLay Showcase", width=1024, height=768, dark_mode=True)
dark_st.bind(lambda v: app.apply_theme(dark=bool(v)))
app.root = build_root()
app.root.layout(app.screen.get_rect())

# (tab_index, settle_frames, filename)
SHOTS = [
    (0, 60,  "ss-pylay-controls.png"),
    (1, 45,  "ss-pylay-forms.png"),
    (2, 45,  "ss-pylay-lists.png"),
    (3, 45,  "ss-pylay-display.png"),
    (4, 45,  "ss-pylay-extras.png"),
]

_dirty.mark()
app.screen.fill(iOSTheme.background)
app.root.draw(app.screen)
pygame.display.flip()

print("Taking PyLay screenshots ...")
frame    = 0
shot_idx = 0
tab_idx, settle, fname = SHOTS[0]
tab_st.value = tab_idx
fire_at = settle

running = True
while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False

    dt = min(app.clock.tick(60) / 1000.0, 0.05)
    app.root.update(dt)
    if app.root._layout_requested:
        app.root.layout(app.screen.get_rect())
        app.root._layout_requested = False
    _dirty.mark()
    app.screen.fill(iOSTheme.background)
    app.root.draw(app.screen)
    pygame.display.flip()
    frame += 1

    if frame >= fire_at:
        path = OUT / fname
        pygame.image.save(app.screen, str(path))
        print(f"  OK  {path.name}")
        shot_idx += 1
        if shot_idx >= len(SHOTS):
            running = False
        else:
            tab_idx, settle, fname = SHOTS[shot_idx]
            tab_st.value = tab_idx
            fire_at = frame + settle

pygame.quit()
print("Done.")

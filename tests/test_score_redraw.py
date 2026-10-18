"""Redrawing only the bars whose notes changed colour must give exactly the picture a full
redraw gives: nothing beside a bar drawn twice, nothing left behind.

Run:  python -m pytest tests/test_score_redraw.py -q      (or just: python tests/test_score_redraw.py)
"""
import os
import sys
import tempfile

_home = tempfile.mkdtemp(prefix="pianove_test_")             # the song store writes here
os.environ.update(USERPROFILE=_home, HOME=_home)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((10, 10))

import pianove  # noqa: E402,F401
from pianove.pages.lesson import _StaffView  # noqa: E402
from pianove.song_store import import_song, get_song_bars_split, get_song_rhythm  # noqa: E402


def test_partial_redraw_matches_full_redraw():
    song = import_song(os.path.join(ROOT, "waltz-in-a-minorchopin.mxl"))
    rh, lh = get_song_bars_split(song["id"])
    r = get_song_rhythm(song["id"])
    n = 8
    sv = _StaffView(bars=rh[:n], bass_bars=lh[:n], phase="practice", bpm=120, time=(3, 4),
                    types=r["types_rh"][:n], bass_types=r["types_lh"][:n],
                    onsets=r["onsets_rh"][:n], bass_onsets=r["onsets_lh"][:n],
                    bar_lens=r["bar_lens"][:n], width=1664, height=838)
    sv.rect = pygame.Rect(0, 98, 1664, 838)
    sv.update_content(1 / 60)                                 # built and drawn whole
    for i in range(18):                                       # play, with a slip now and then
        if i % 5 == 2:
            sv.mark_wrong()
            sv.update_content(1 / 60)
        sv.advance()
        sv.update_content(1 / 60)
    partial = pygame.surfarray.array3d(sv._offscreen).astype(int)
    sv._full_redraw = True
    sv._dirty = True
    sv.update_content(1 / 60)
    full = pygame.surfarray.array3d(sv._offscreen).astype(int)
    assert int(np.abs(partial - full).max()) == 0


if __name__ == "__main__":
    test_partial_redraw_matches_full_redraw()
    print("score redraw ok")

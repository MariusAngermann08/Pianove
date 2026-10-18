"""PyLute draws tuplets that contain rests, even ones that start with a rest (as imported
songs have them), instead of crashing on the rest's missing stem.

Run:  python -m pytest tests/test_pylute_tuplet.py -q      (or just: python tests/test_pylute_tuplet.py)
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame  # noqa: E402

pygame.init()

import pianove  # noqa: E402,F401  (puts PyLute on the path)
from pylute import Score, Note, Tuplet  # noqa: E402
from pylute.rest import Rest  # noqa: E402


def _draw(events):
    surf = pygame.Surface((900, 300))
    surf.fill((255, 255, 255))
    score = Score(surface=surf, staffs=1, bars=1, key="C", time=(4, 4))
    staff = score.staffs[0]
    staff.bars[0].events.extend(events(staff))
    score.draw()
    return surf


def test_tuplet_starting_with_a_rest():
    _draw(lambda st: [Tuplet([Rest("eighth", st), Note("eighth", "E4", st), Note("eighth", "G4", st)],
                             3, 2, staff=st),
                      Note("quarter", "C5", st), Note("half", "C4", st)])


def test_tuplet_of_rests_only():
    _draw(lambda st: [Tuplet([Rest("eighth", st), Rest("eighth", st), Rest("eighth", st)], 3, 2, staff=st),
                      Note("quarter", "C5", st), Note("half", "C4", st)])


if __name__ == "__main__":
    test_tuplet_starting_with_a_rest()
    test_tuplet_of_rests_only()
    print("tuplets ok")

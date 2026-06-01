import pygame as pg
import pathlib

FONT_PATH = str(pathlib.Path(__file__).parent.parent / "assets" / "Bravura.otf")
FONT_SIZE  = 70   # mutable — updated by set_font_size()
_font      = None


def get_font_size():
    return FONT_SIZE


def set_font_size(size):
    global FONT_SIZE, _font
    size = max(28, int(size))
    if size != FONT_SIZE:
        FONT_SIZE = size
        _font     = None


def get_font():
    global _font
    if _font is None:
        _font = pg.freetype.Font(FONT_PATH, FONT_SIZE)
    return _font


def make_font(size):
    return pg.freetype.Font(FONT_PATH, size)

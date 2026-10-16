import pygame as pg
import pathlib

FONT_PATH = str(pathlib.Path(__file__).parent / "assets" / "Bravura.otf")
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


_scaled_fonts = {}


def make_font(size):
    # Brace._build() calls this once per system on every redraw (each system
    # resets its cached font), which without caching re-reads Bravura.otf from
    # disk every time — a real cost on long, multi-system pieces.
    font = _scaled_fonts.get(size)
    if font is None:
        font = pg.freetype.Font(FONT_PATH, size)
        _scaled_fonts[size] = font
    return font

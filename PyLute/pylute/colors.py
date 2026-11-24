"""The colours a score is drawn in: ink for everything printed, paper behind it.

    import pylute
    pylute.colors.set_colors(ink=(232, 232, 237), paper=(28, 28, 30))   # a dark sheet
    pylute.colors.set_colors()                                           # back to black on white

Notes given a colour of their own (note.color) keep it. Read at draw time, so a change
applies from the next redraw."""

INK = (0, 0, 0)
PAPER = (255, 255, 255)


def set_colors(ink=(0, 0, 0), paper=(255, 255, 255)):
    global INK, PAPER
    INK, PAPER = tuple(ink), tuple(paper)

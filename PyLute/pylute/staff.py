import pygame as pg

DEBUG = "[OpenScore-Debug]"

class Staff:
    def __init__(self, surface, score):
        self.surface = surface
        self.score = score
        self.lines = []
        self.bars = []
        self.position = [0, 0]
        self.length = 300
        self.space = 20
        self.clef_type = "treble"

    def updateLines(self):
        self.lines.clear()
        for i in range(5):
            self.lines.append([self.position[0], self.position[1] + (self.space * i)])

    def draw_lines(self):
        if self.surface:
            for line in self.lines:
                pg.draw.line(
                    surface=self.surface,
                    color=(0, 0, 0),
                    start_pos=(line[0], line[1]),
                    end_pos=(line[0] + self.length, line[1])
                )

    def draw(self):
        if self.surface:
            self.draw_lines()
            for bar in self.bars:
                bar.calculateMetrics()
                bar.draw()
        else:
            print(f"{DEBUG} <Staff> object needs :surface: to be drawn")

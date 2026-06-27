import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme
from typing import Union


class Divider(UIElement):
    def __init__(self, width: Union[int, float] = 1.0, **kwargs):
        super().__init__(width=width, height=1, **kwargs)

    def render(self, surface: pygame.Surface):
        pygame.draw.rect(surface, iOSTheme.fill_tertiary, self.rect)

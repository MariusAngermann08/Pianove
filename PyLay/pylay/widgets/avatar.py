import pygame
from pylay.core.element import UIElement
from pylay.core.theme import ColorPalette
from pylay.core import font_loader
from typing import Optional


class Avatar(UIElement):
    """
    A filled circle showing up to two initials in white.
    Useful for profile rows, user headings, and comment threads.
    """

    def __init__(
        self,
        initials: str,
        size: int = 40,
        color: Optional[pygame.Color] = None,
        **kwargs,
    ):
        super().__init__(width=size, height=size, **kwargs)
        self.initials = initials[:2].upper()
        self.color    = color if color is not None else ColorPalette.BLUE
        self._font    = None
        self._font_px = 0

    def render(self, surface: pygame.Surface):
        r  = min(self.rect.width, self.rect.height) // 2
        cx = self.rect.centerx
        cy = self.rect.centery

        pygame.draw.circle(surface, self.color, (cx, cy), r)

        target_px = max(8, int(r * 0.7))
        if self._font is None or self._font_px != target_px:
            self._font    = font_loader.load_font(int(r * 0.55), bold=True)
            self._font_px = target_px

        text_surf = self._font.render(self.initials, True, pygame.Color(255, 255, 255))
        text_rect = text_surf.get_rect(center=(cx, cy))
        surface.blit(text_surf, text_rect)

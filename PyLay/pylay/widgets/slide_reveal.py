import pygame
from pylay.core.element import UIElement
from pylay.core.physics import Spring
from typing import Optional, Union


class SlideReveal(UIElement):
    def __init__(self,
                 child: Optional[UIElement] = None,
                 max_height: int = 200,
                 visible: bool = True,
                 response: float = 0.38,
                 damping_fraction: float = 1.0,
                 separator_color: tuple = (190, 190, 198),
                 **kwargs):
        # Always force height to max_height so the parent layout reserves the slot.
        kwargs['height'] = max_height
        super().__init__(**kwargs)

        self._max_h = max_height
        self._sep_color = separator_color
        initial = float(max_height if visible else 0)
        self._spring = Spring(value=initial,
                              response=response,
                              damping_fraction=damping_fraction)
        self._spring.target = initial

        if child is not None:
            self.add_child(child)

    def reveal(self, visible: bool) -> None:
        self._spring.target = float(self._max_h if visible else 0)

    def set_max_height(self, max_height: int, animate: bool = True) -> None:
        """Change how far the panel opens, up to the height it was created with (the slot
        it reserves keeps that size). When open, it springs to the new height."""
        self._max_h = max_height
        if self._spring.target > 0:
            if animate:
                self._spring.target = float(max_height)
            else:
                self._spring.snap_to(float(max_height))

    @property
    def reveal_height(self) -> int:
        return round(self._spring.value)

    def update(self, dt: float) -> None:
        self._spring.update(dt)
        # super() advances _active_animations (unused here) and recurses children
        super().update(dt)

    def handle_event(self, event: pygame.event.Event) -> bool:
        reveal_h = round(self._spring.value)
        if reveal_h <= 0:
            return False
        # Block events that fall above the revealed area
        if hasattr(event, 'pos'):
            if event.pos[1] < self.rect.bottom - reveal_h:
                return False
        return super().handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        # round() instead of int() eliminates 1-px jitter as the spring settles
        reveal_h = round(self._spring.value)
        if reveal_h <= 0:
            return

        sep_y = self.rect.bottom - reveal_h

        # Clip children to the full revealed area first
        clip = pygame.Rect(self.rect.left, sep_y, self.rect.width, reveal_h)
        old_clip = surface.get_clip()
        effective = (clip.clip(old_clip)
                     if old_clip.width > 0 and old_clip.height > 0
                     else clip)
        surface.set_clip(effective)
        for child in self.children:
            child.draw(surface)
        surface.set_clip(old_clip)

        # Separator drawn on top (outside clip) so it never steals a pixel of content
        pygame.draw.line(surface, self._sep_color,
                         (self.rect.left, sep_y), (self.rect.right, sep_y), 1)

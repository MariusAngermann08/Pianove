import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme
from typing import Callable, Optional, Union, Any

# Callback signatures for embedding arbitrary pygame content
DrawCallback = Callable[[pygame.Surface, pygame.Rect], None]
EventCallback = Callable[[pygame.event.Event, pygame.Rect], bool]
UpdateCallback = Callable[[float, pygame.Rect], None]


class PygameCanvas(UIElement):
    """
    A layout slot for native pygame drawing inside the OpenGUI tree.

    Use this to embed existing pygame code (games, instruments, custom widgets)
    without rewriting them as OpenGUI components.

    Integration options (pick one):
      1. Pass callables: on_draw, on_event, on_update
      2. Pass a target object with draw(surface, rect), handle_event(event, rect),
         and optionally update(dt, rect)
      3. Subclass and override draw_content / handle_content_event / update_content
    """

    def __init__(self,
                 on_draw: Optional[DrawCallback] = None,
                 on_event: Optional[EventCallback] = None,
                 on_update: Optional[UpdateCallback] = None,
                 target: Optional[Any] = None,
                 draw_border: bool = True,
                 anchor: str = "top_left",
                 x: Union[int, float] = 0,
                 y: Union[int, float] = 0,
                 width: Union[int, float] = 200,
                 height: Union[int, float] = 200,
                 **kwargs):
        super().__init__(anchor=anchor, x=x, y=y, width=width, height=height, **kwargs)
        # Use *_callback names — do not assign to self.on_event (shadows UIElement.on_event)
        self.draw_callback = on_draw
        self.event_callback = on_event
        self.update_callback = on_update
        self.target = target
        self.draw_border = draw_border
        self.clips_to_bounds = True

    def _on_theme_changed(self):
        pass

    def update(self, dt: float):
        if self.update_callback:
            self.update_callback(dt, self.rect)
        elif self.target is not None and hasattr(self.target, "update"):
            self.target.update(dt, self.rect)
        else:
            self.update_content(dt)
        super().update(dt)

    def update_content(self, dt: float):
        """Override for subclass-based custom content."""
        pass

    def on_event(self, event: pygame.event.Event) -> bool:
        if self.event_callback:
            return bool(self.event_callback(event, self.rect))
        if self.target is not None and hasattr(self.target, "handle_event"):
            return bool(self.target.handle_event(event, self.rect))
        return self.handle_content_event(event)

    def handle_content_event(self, event: pygame.event.Event) -> bool:
        """Override for subclass-based custom content."""
        return False

    def render(self, surface: pygame.Surface):
        w, h = self.rect.width, self.rect.height
        if w <= 2 or h <= 2:
            return

        if self.draw_border:
            inner = self.rect.inflate(-2, -2)
            pygame.draw.rect(surface, iOSTheme.tertiary_background, inner, border_radius=10)
            pygame.draw.rect(surface, iOSTheme.fill_tertiary, inner, width=1, border_radius=10)
            clip_rect = inner.inflate(-4, -4)
        else:
            clip_rect = self.rect

        old_clip = surface.get_clip()
        surface.set_clip(clip_rect.clip(old_clip) if old_clip.width > 0 else clip_rect)

        if self.draw_callback:
            self.draw_callback(surface, clip_rect)
        elif self.target is not None and hasattr(self.target, "draw"):
            self.target.draw(surface, clip_rect)
        else:
            self.draw_content(surface, clip_rect)

        surface.set_clip(old_clip)

    def draw_content(self, surface: pygame.Surface, rect: pygame.Rect):
        """Override for subclass-based custom content."""
        pass

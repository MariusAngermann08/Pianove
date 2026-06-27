import pygame
import sys
import time
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme
from pylay.core.scale import set_window_size, REF_WIDTH, REF_HEIGHT
from pylay.core import _dirty
from pylay.layouts.float_layout import FloatLayout
from typing import Callable, Optional, Union, Iterable

class App:
    def __init__(self,
                 title: str = "OpenUI Application",
                 width: int = 960,
                 height: int = 680,
                 dark_mode: bool = True,
                 managed_display: bool = True):
        self.managed_display = managed_display
        self.width = width
        self.height = height
        self._pending_resize = None
        self._resize_time = 0.0
        self.on_resize: Optional[Callable[[int, int], None]] = None
        self._display_flags = pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF

        if not pygame.get_init():
            pygame.init()

        iOSTheme.dark = dark_mode
        iOSTheme.update_theme()

        self.screen: Optional[pygame.Surface] = None
        self.clock = pygame.time.Clock()

        if managed_display:
            pygame.display.set_caption(title)
            self.screen = pygame.display.set_mode(
                (self.width, self.height), self._display_flags
            )
            set_window_size(self.width, self.height, REF_WIDTH, REF_HEIGHT)
        else:
            self.screen = None

        self.root: UIElement = FloatLayout(
            anchor="top_left", x=0, y=0, width=1.0, height=1.0,
            background_color=iOSTheme.background,
        )
        self._frame_was_idle: bool = False

    @property
    def background_color(self):
        return self.root.background_color

    @background_color.setter
    def background_color(self, color):
        self.root.background_color = color

    def attach(self, surface: pygame.Surface):
        self.screen = surface
        self.width, self.height = surface.get_size()
        set_window_size(self.width, self.height, REF_WIDTH, REF_HEIGHT)
        self.root.layout(surface.get_rect())

    def set_root(self, root_element: UIElement):
        self.root = root_element
        self.root.background_color = iOSTheme.background
        if self.screen:
            self.root.layout(self.screen.get_rect())

    def apply_theme(self, dark: Optional[bool] = None):
        if dark is not None:
            iOSTheme.dark = dark
        iOSTheme.update_theme()
        self.root.background_color = iOSTheme.background
        self.root.invalidate_theme_caches()
        _dirty.mark()
        if self.screen:
            self.root.layout(self.screen.get_rect())
        else:
            self.root.layout()

    def toggle_theme(self):
        self.apply_theme(not iOSTheme.dark)

    def process_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT and self.managed_display:
            return False

        # pygame 1.x resize
        if event.type == pygame.VIDEORESIZE:
            self._pending_resize = (event.w, event.h)
            self._resize_time = time.time()
            return True

        # pygame 2.x resize — fires after SDL has already updated the window;
        # queue it the same way so set_mode() + layout() run in frame().
        _WR = getattr(pygame, "WINDOWRESIZED", None)
        if _WR and event.type == _WR:
            self._pending_resize = (event.x, event.y)
            self._resize_time = time.time()
            return True

        # Any user interaction must wake the draw loop for at least one frame
        # (hover animations, cursor updates, and spring transitions all start here).
        _dirty.mark()
        self.root.handle_event(event)
        return True

    def process_events(self, events: Optional[Iterable[pygame.event.Event]] = None) -> bool:
        if events is None:
            events = pygame.event.get()
        for event in events:
            if not self.process_event(event):
                return False
        return True

    def frame(self, dt: Optional[float] = None, *, clear: bool = True) -> float:
        if self.screen is None:
            raise RuntimeError(
                "No display surface. Call app.attach(screen) or use managed_display=True."
            )

        if dt is None:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)

        if self._pending_resize and (time.time() - self._resize_time) > 0.04:
            w, h = self._pending_resize
            self.width, self.height = w, h
            self.screen = pygame.display.set_mode((w, h), self._display_flags)
            set_window_size(w, h, REF_WIDTH, REF_HEIGHT)
            self.root.invalidate_scale_caches()
            self.root.layout(self.screen.get_rect())
            self._pending_resize = None
            _dirty.mark()
            if self.on_resize:
                self.on_resize(w, h)

        self.root.update(dt)

        # Deferred layout: collapse all layout requests into one pass per frame
        if self.root._layout_requested:
            self.root.layout(self.screen.get_rect())
            self.root._layout_requested = False

        # Idle skip: when no springs are active AND no State changed, the frame is visually
        # identical to the previous one — skip fill + draw + flip entirely (DOUBLEBUF safe).
        state_dirty = _dirty.consume()
        self._frame_was_idle = (self.root._subtree_animations == 0) and not state_dirty
        if not self._frame_was_idle:
            if clear:
                self.screen.fill(iOSTheme.background)
            self.root.draw(self.screen)

        return dt

    def _draw_initial_frame(self):
        self.screen.fill(iOSTheme.background)
        self.root.draw(self.screen)
        pygame.display.flip()

    def run(self):
        if not self.managed_display:
            raise RuntimeError(
                "app.run() requires managed_display=True. "
                "Use app.attach(screen) and call app.frame() inside your own loop."
            )
        if self.screen is None:
            raise RuntimeError("No display surface available.")

        self.root.layout(self.screen.get_rect())
        # Always show content on the very first frame before the idle-skip logic runs.
        self._draw_initial_frame()

        running = True
        while running:
            if not self.process_events():
                running = False
                continue
            self.frame(clear=True)
            if not self._frame_was_idle:
                pygame.display.flip()

        pygame.quit()
        sys.exit()

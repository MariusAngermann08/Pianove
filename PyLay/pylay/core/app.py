import pygame
import sys
import time
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme
from pylay.core.scale import set_window_size, REF_WIDTH, REF_HEIGHT
from pylay.layouts.float_layout import FloatLayout
from typing import Callable, Optional, Union, Iterable

class App:
    """
    OpenGUI application host — works in two modes:

    **Managed display (default)** — creates the window and runs the main loop:
        app = App(title="My App", width=1024, height=768)
        app.root.add_child(...)
        app.run()

    **Embedded in your pygame loop** — you own the window, events, and flip:
        pygame.init()
        screen = pygame.display.set_mode((1024, 768))
        app = App(managed_display=False, dark_mode=True)
        app.attach(screen)
        app.root.add_child(...)

        running = True
        while running:
            dt = clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                app.process_event(event)
            app.frame(dt)
            pygame.display.flip()
    """

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

    @property
    def background_color(self):
        return self.root.background_color

    @background_color.setter
    def background_color(self, color):
        self.root.background_color = color

    def attach(self, surface: pygame.Surface):
        """Bind an externally managed pygame display surface (embedded mode)."""
        self.screen = surface
        self.width, self.height = surface.get_size()
        set_window_size(self.width, self.height, REF_WIDTH, REF_HEIGHT)
        self.root.layout(surface.get_rect())

    def set_root(self, root_element: UIElement):
        """Replace the root layout container."""
        self.root = root_element
        self.root.background_color = iOSTheme.background
        if self.screen:
            self.root.layout(self.screen.get_rect())

    def apply_theme(self, dark: Optional[bool] = None):
        """Switch light/dark theme and refresh all cached widget surfaces."""
        if dark is not None:
            iOSTheme.dark = dark
        iOSTheme.update_theme()
        self.root.background_color = iOSTheme.background
        self.root.invalidate_theme_caches()
        if self.screen:
            self.root.layout(self.screen.get_rect())
        else:
            self.root.layout()

    def toggle_theme(self):
        """Toggle dark/light system colors on-the-fly."""
        self.apply_theme(not iOSTheme.dark)

    def process_event(self, event: pygame.event.Event) -> bool:
        """
        Feed one pygame event into the UI tree.
        Returns False if the host should quit (QUIT in managed display mode).
        """
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

        self.root.handle_event(event)
        return True

    def process_events(self, events: Optional[Iterable[pygame.event.Event]] = None) -> bool:
        """Process a batch of events. Returns False if the host should quit."""
        if events is None:
            events = pygame.event.get()
        for event in events:
            if not self.process_event(event):
                return False
        return True

    def frame(self, dt: Optional[float] = None, *, clear: bool = True) -> float:
        """
        Advance animations and draw one frame onto the attached surface.
        Returns the delta time used (seconds).
        """
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
            if self.on_resize:
                self.on_resize(w, h)

        self.root.update(dt)

        if clear:
            self.screen.fill(iOSTheme.background)
        self.root.draw(self.screen)
        return dt

    def run(self):
        """Start the built-in main loop (managed display mode)."""
        if not self.managed_display:
            raise RuntimeError(
                "app.run() requires managed_display=True. "
                "Use app.attach(screen) and call app.frame() inside your own loop."
            )
        if self.screen is None:
            raise RuntimeError("No display surface available.")

        self.root.layout(self.screen.get_rect())
        running = True
        while running:
            if not self.process_events():
                running = False
                continue
            self.frame(clear=True)
            pygame.display.flip()

        pygame.quit()
        sys.exit()

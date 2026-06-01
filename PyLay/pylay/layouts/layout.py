import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme
from typing import Optional

class Layout(UIElement):
    """
    Base Layout class. Containers designed to hold and arrange other UIElements.

    Features:
    - clips_to_bounds enabled by default
    - Automatic spring-physics scrollview when children overflow the container
    - Scroll state is maintained separately from child rects (no rect mutation)
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.clips_to_bounds = True

        # Scroll state — scroll_offset is the canonical rendered offset (pixels)
        self.scroll_offset = 0.0     # current spring value (float)
        self.scroll_target = 0.0     # where user wants to scroll to
        self.scroll_max    = 0.0     # maximum scrollable distance
        self.scroll_active = False
        self.on_scroll     = None    # optional callback(target: float) fired on user scroll

    # ------------------------------------------------------------------
    # Layout — overflow detection after children are placed
    # ------------------------------------------------------------------
    def layout(self, parent_rect: Optional[pygame.Rect] = None, skip_self: bool = False,
               _skip_bounds_refresh: bool = False):
        super().layout(parent_rect, skip_self=skip_self)
        if not _skip_bounds_refresh:
            self._refresh_scroll_bounds()

    def _refresh_scroll_bounds(self):
        """Detect whether children overflow and update scroll limits."""
        if not self.children:
            self.scroll_active = False
            self.scroll_max = 0.0
            return

        pad = getattr(self, "padding", 0)
        # Skip children that manage their own scroll (e.g. ScrollableCanvas, PageRouter)
        # so they don't falsely trigger scroll on parent containers.
        candidates = [c for c in self.children
                      if c.visible and not getattr(c, "manages_own_scroll", False)]
        if not candidates:
            self.scroll_active = False
            self.scroll_max = 0.0
            return
        max_bottom = max(
            (c.rect.bottom for c in candidates),
            default=self.rect.top
        )
        overflow = max_bottom - (self.rect.bottom - pad)
        if overflow > 2:
            self.scroll_max    = float(overflow)
            self.scroll_active = True
            self.scroll_target = min(self.scroll_max, max(0.0, self.scroll_target))
        else:
            self.scroll_max    = 0.0
            self.scroll_active = False
            self.scroll_target = 0.0
            self.scroll_offset = 0.0

    # ------------------------------------------------------------------
    # Update — spring-drive the scroll offset
    # ------------------------------------------------------------------
    def update(self, dt: float):
        if self.scroll_active:
            self.animate_to("scroll_offset", self.scroll_target,
                            response=0.22, damping_fraction=0.85)
        super().update(dt)

    # ------------------------------------------------------------------
    # Helpers — recursive rect shift for the entire subtree
    # ------------------------------------------------------------------
    @staticmethod
    def _shift_tree(nodes, dy: int):
        for c in nodes:
            c.rect.y += dy
            if c.children:
                Layout._shift_tree(c.children, dy)

    # ------------------------------------------------------------------
    # Events — intercept scroll wheel; adjust hit-test y for scrolled children
    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False

        # Scroll wheel — only inside our rect
        if self.scroll_active:
            if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
                if event.button == 4:
                    self.scroll_target = max(0.0, self.scroll_target - 60)
                    if self.on_scroll:
                        self.on_scroll(self.scroll_target)
                    return True
                if event.button == 5:
                    self.scroll_target = min(self.scroll_max, self.scroll_target + 60)
                    if self.on_scroll:
                        self.on_scroll(self.scroll_target)
                    return True
            if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll_target = max(0.0, min(
                    self.scroll_max,
                    self.scroll_target - event.y * 60,
                ))
                if self.on_scroll:
                    self.on_scroll(self.scroll_target)
                return True

        # Children — temporarily shift entire subtree for hit-testing
        shift = int(self.scroll_offset) if self.scroll_active else 0
        if shift:
            Layout._shift_tree(self.children, -shift)
        try:
            for child in reversed(self.children):
                if child.handle_event(event):
                    return True
        finally:
            if shift:
                Layout._shift_tree(self.children, shift)

        return self.on_event(event)

    # ------------------------------------------------------------------
    # Draw — clips children; applies scroll via surface offset (no rect mutation)
    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface):
        if not self.visible:
            return

        self.render(surface)

        old_clip = surface.get_clip()
        # Always clip Layout children to container bounds
        new_clip = self.rect.clip(old_clip) if old_clip.width > 0 else self.rect
        surface.set_clip(new_clip)

        shift = int(self.scroll_offset) if self.scroll_active else 0
        if shift:
            Layout._shift_tree(self.children, -shift)
        try:
            for child in self.children:
                child.draw(surface)
        finally:
            if shift:
                Layout._shift_tree(self.children, shift)

        # Scrollbar — drawn inside our own clip so it never bleeds into sibling widgets
        if self.scroll_active and self.scroll_max > 0:
            h       = self.rect.height
            bar_h   = max(20, int(h * h / (h + self.scroll_max)))
            bar_y   = self.rect.top + int(self.scroll_offset / self.scroll_max * (h - bar_h))
            bar_x   = self.rect.right - 5
            bar_col = pygame.Color(100, 100, 108) if iOSTheme.dark else pygame.Color(180, 180, 188)
            pygame.draw.rect(surface, bar_col,
                             pygame.Rect(bar_x, bar_y, 4, bar_h), border_radius=2)

        surface.set_clip(old_clip)

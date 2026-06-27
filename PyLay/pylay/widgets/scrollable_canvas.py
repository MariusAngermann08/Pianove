import pygame
from pylay.widgets.pygame_canvas import PygameCanvas
from pylay.core.theme import iOSTheme
from typing import Optional


class ScrollableCanvas(PygameCanvas):
    SCROLL_STEP = 80
    BAR_W       = 4
    BAR_MIN_H   = 20

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.manages_own_scroll: bool  = True   # prevents parent Layout interception
        self.scroll_offset: float = 0.0
        self.scroll_target: float = 0.0
        self.scroll_max:    float = 0.0
        self.scroll_active: bool  = False

        self._offscreen:   Optional[pygame.Surface] = None
        self._offscreen_w: int = 0
        self._offscreen_h: int = 0
        self._canvas_h:    int = 0

    def _get_content_h(self, canvas_w: int) -> int:
        if self.target is not None and hasattr(self.target, "content_height"):
            return max(1, self.target.content_height(canvas_w))
        return max(1, self.rect.height)

    def _needs_rebuild(self, canvas_w: int, content_h: int) -> bool:
        if self._offscreen is None:
            return True
        if self._offscreen_w != canvas_w or self._offscreen_h != content_h:
            return True
        return bool(self.target is not None and getattr(self.target, "dirty", False))

    def _rebuild(self, canvas_w: int, content_h: int):
        self._offscreen   = pygame.Surface((canvas_w, content_h))
        self._offscreen_w = canvas_w
        self._offscreen_h = content_h
        if self.target is not None and hasattr(self.target, "draw"):
            self.target.draw(self._offscreen, self._offscreen.get_rect())
        if self.target is not None:
            self.target.dirty = False

    def _update_scroll_state(self, canvas_w: int, canvas_h: int):
        content_h = self._get_content_h(canvas_w)
        if content_h > canvas_h:
            self.scroll_max    = float(content_h - canvas_h)
            self.scroll_active = True
            self.scroll_target = max(0.0, min(self.scroll_max, self.scroll_target))
        else:
            self.scroll_max    = 0.0
            self.scroll_active = False
            self.scroll_target = 0.0
            self.scroll_offset = 0.0

    def update(self, dt: float):
        if self._canvas_h > 0:
            cw = max(1, self.rect.width)
            self._update_scroll_state(cw, self._canvas_h)
        if self.scroll_active:
            self.animate_to("scroll_offset", self.scroll_target,
                            response=0.22, damping_fraction=0.85)
        super().update(dt)

    def on_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                if event.button == 4:
                    self.scroll_target = max(0.0, self.scroll_target - self.SCROLL_STEP)
                    return True
                if event.button == 5:
                    self.scroll_target = min(
                        self.scroll_max,
                        self.scroll_target + self.SCROLL_STEP,
                    )
                    return True

        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                delta = -event.y * self.SCROLL_STEP
                self.scroll_target = max(0.0, min(
                    self.scroll_target + delta,
                    self.scroll_max if self.scroll_max > 0 else self.scroll_target + delta,
                ))
                return True

        return False

    def render(self, surface: pygame.Surface):
        safe = self.rect.clip(surface.get_rect())
        if safe.width < 1 or safe.height < 1:
            return

        # Use the widget's full (unclipped) width as the canonical offscreen width.
        # This keeps the offscreen stable during horizontal slide transitions in PageRouter.
        cw = max(1, self.rect.width)
        ch = safe.height
        self._canvas_h = ch

        content_h = self._get_content_h(cw)
        self._update_scroll_state(cw, ch)

        if self._needs_rebuild(cw, content_h):
            self._rebuild(cw, content_h)

        if self._offscreen is None:
            return

        scroll_y  = int(self.scroll_offset)
        visible_h = min(ch, max(0, content_h - scroll_y))

        # x_src: which column of the offscreen is at the left edge of the visible area.
        # Non-zero when the widget is partially off-screen left (parallax slide-out).
        x_src = max(0, safe.left - self.rect.left)

        old_clip = surface.get_clip()
        surface.set_clip(safe)
        try:
            if visible_h > 0:
                surface.blit(
                    self._offscreen,
                    (safe.left, safe.top),
                    pygame.Rect(x_src, scroll_y, safe.width, visible_h),
                )
            if visible_h < ch:
                gap = pygame.Rect(safe.left, safe.top + visible_h, safe.width, ch - visible_h)
                pygame.draw.rect(surface, (255, 255, 255), gap)
        finally:
            surface.set_clip(old_clip)

        # Scrollbar — only draw when fully visible (not during parallax animation)
        if self.scroll_active and self.scroll_max > 0 and x_src == 0:
            bar_h = max(self.BAR_MIN_H, int(ch * ch / content_h))
            bar_y = safe.top + int(scroll_y / self.scroll_max * (ch - bar_h))
            bar_rect = pygame.Rect(safe.right - self.BAR_W - 2, bar_y,
                                   self.BAR_W, bar_h)
            pygame.draw.rect(surface, iOSTheme.fill_tertiary, bar_rect, border_radius=2)

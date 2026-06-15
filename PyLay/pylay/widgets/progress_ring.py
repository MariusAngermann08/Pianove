import pygame
import math
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme, ColorPalette
from typing import Optional

_SS = 3  # supersampling factor — render at 3× then smooth-scale down


class ProgressRing(UIElement):
    """
    Circular progress indicator with anti-aliased edges and round line-caps.

    Renders at 3× resolution on a SRCALPHA surface, then smooth-scales to the
    target size so edges blend cleanly against any background.

    progress — 0.0 to 1.0
    size     — diameter in pixels (width == height)
    stroke   — ring line thickness in pixels
    """

    def __init__(
        self,
        progress: float,
        size: int = 48,
        active_color: Optional[pygame.Color] = None,
        stroke: int = 5,
        **kwargs,
    ):
        super().__init__(width=size, height=size, **kwargs)
        self.progress     = progress
        self.active_color = active_color if active_color is not None else ColorPalette.BLUE
        self.stroke       = stroke
        self._surf        = None
        self._surf_key    = None

    def _rebuild(self, w: int, h: int):
        p   = max(0.0, min(1.0, self.progress))
        ss  = self.stroke * _SS
        sw, sh = w * _SS, h * _SS

        ring = pygame.Surface((sw, sh), pygame.SRCALPHA)
        ring.fill((0, 0, 0, 0))

        cx, cy = sw // 2, sh // 2
        r      = min(sw, sh) // 2 - ss // 2 - 1
        if r < 1:
            return ring

        arc_rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
        cap_r    = max(1, ss // 2)

        # ── Track: circle outline — no seam, perfectly clean ─────────────────
        pygame.draw.circle(ring, iOSTheme.fill, (cx, cy), r, ss)

        # ── Active arc + round caps ───────────────────────────────────────────
        if p > 0.005:
            sweep   = math.tau * p
            start_a = math.pi / 2 - sweep

            pygame.draw.arc(ring, self.active_color, arc_rect,
                            start_a, math.pi / 2, ss)

            # Trailing cap — skip when nearly full
            if p < 0.995:
                ex = cx + int(round(r * math.cos(start_a)))
                ey = cy - int(round(r * math.sin(start_a)))
                pygame.draw.circle(ring, self.active_color, (ex, ey), cap_r)

        return ring

    def render(self, surface: pygame.Surface):
        w, h = self.rect.width, self.rect.height
        if w < 4 or h < 4:
            return

        p = max(0.0, min(1.0, self.progress))
        key = (w, h, self.stroke, round(p, 3),
               self.active_color.r, self.active_color.g, self.active_color.b,
               iOSTheme.dark)

        if self._surf is None or self._surf_key != key:
            raw          = self._rebuild(w, h)
            self._surf   = pygame.transform.smoothscale(raw, (w, h))
            self._surf_key = key

        surface.blit(self._surf, self.rect.topleft)

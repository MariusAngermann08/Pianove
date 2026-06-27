import pygame
from pylay.core.element import UIElement
from pylay.core.theme import iOSTheme, ColorPalette
from pylay.core.scale import scaled_font_size, scaled_px
from pylay.core import font_loader
from typing import Any, Callable, List, Optional, Union


class Stepper(UIElement):
    def __init__(
        self,
        options: List[Any],
        value: Any = None,
        fmt_fn: Optional[Callable[[Any], str]] = None,
        on_change: Optional[Callable[[Any], None]] = None,
        label_suffix: str = "",
        active_color: Optional[pygame.Color] = None,
        width: Union[int, float] = 160,
        height: Union[int, float] = 36,
        **kwargs,
    ):
        super().__init__(width=width, height=height, **kwargs)
        self._options = list(options)
        self._fmt_fn = fmt_fn or str
        self._on_change = on_change
        self._suffix = label_suffix
        self._active_color = active_color or ColorPalette.BLUE

        # Resolve starting index
        try:
            self._idx = self._options.index(value) if value in self._options else 0
        except (TypeError, ValueError):
            self._idx = 0

        # Spring-animated press feedback per button
        self._press_minus:    float = 0.0
        self._press_plus:     float = 0.0
        self._pressing_minus: bool  = False
        self._pressing_plus:  bool  = False
        self._font: Optional[pygame.font.Font] = None
        self._font_px: int = 0

    @property
    def value(self) -> Any:
        return self._options[self._idx]

    def _on_scale_changed(self):
        self._font = None
        self._font_px = 0

    def _on_theme_changed(self):
        self._font = None
        self._font_px = 0

    def _get_font(self) -> pygame.font.Font:
        px = scaled_font_size(14)
        if self._font is None or self._font_px != px:
            self._font = font_loader.load_font(14, bold=True)
            self._font_px = px
        return self._font

    def _btn_size(self) -> int:
        return min(self.rect.height, scaled_px(32))

    def _minus_rect(self) -> pygame.Rect:
        sz = self._btn_size()
        cy = self.rect.centery
        return pygame.Rect(self.rect.left, cy - sz // 2, sz, sz)

    def _plus_rect(self) -> pygame.Rect:
        sz = self._btn_size()
        cy = self.rect.centery
        return pygame.Rect(self.rect.right - sz, cy - sz // 2, sz, sz)

    def update(self, dt: float):
        self.animate_to("_press_minus",
                        1.0 if self._pressing_minus else 0.0,
                        response=0.15, damping_fraction=0.75)
        self.animate_to("_press_plus",
                        1.0 if self._pressing_plus else 0.0,
                        response=0.15, damping_fraction=0.75)
        super().update(dt)

    def on_event(self, event: pygame.event.Event) -> bool:
        if not self.enabled or not self.visible:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._minus_rect().collidepoint(event.pos):
                self._pressing_minus = True
                self._step(-1)
                return True
            if self._plus_rect().collidepoint(event.pos):
                self._pressing_plus = True
                self._step(+1)
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._pressing_minus = False
            self._pressing_plus  = False

        return False

    def _step(self, delta: int):
        self._idx = (self._idx + delta) % len(self._options)
        if self._on_change:
            self._on_change(self.value)

    def render(self, surface: pygame.Surface):
        if self.rect.width < 60 or self.rect.height < 16:
            return

        font   = self._get_font()
        sz     = self._btn_size()
        mr     = self._minus_rect()
        pr     = self._plus_rect()
        cy     = self.rect.centery
        color  = self._active_color

        at_min = self._idx == 0
        at_max = self._idx == len(self._options) - 1

        m_scale  = 1.0 - self._press_minus * 0.12
        m_r      = int(sz * m_scale // 2)
        m_cx, m_cy = mr.centerx, mr.centery
        m_col    = iOSTheme.fill_secondary if at_min else color
        pygame.draw.circle(surface, m_col, (m_cx, m_cy), m_r)
        bar_w = max(4, int(sz * 0.40 * m_scale))
        bar_h = max(1, int(sz * 0.12 * m_scale))
        pygame.draw.rect(surface, pygame.Color(255, 255, 255),
                         (m_cx - bar_w // 2, m_cy - bar_h // 2, bar_w, bar_h),
                         border_radius=1)

        p_scale  = 1.0 - self._press_plus * 0.12
        p_r      = int(sz * p_scale // 2)
        p_cx, p_cy = pr.centerx, pr.centery
        p_col    = iOSTheme.fill_secondary if at_max else color
        pygame.draw.circle(surface, p_col, (p_cx, p_cy), p_r)
        bar_w2 = max(4, int(sz * 0.40 * p_scale))
        bar_h2 = max(1, int(sz * 0.12 * p_scale))
        pygame.draw.rect(surface, pygame.Color(255, 255, 255),
                         (p_cx - bar_w2 // 2, p_cy - bar_h2 // 2, bar_w2, bar_h2),
                         border_radius=1)
        pygame.draw.rect(surface, pygame.Color(255, 255, 255),
                         (p_cx - bar_h2 // 2, p_cy - bar_w2 // 2, bar_h2, bar_w2),
                         border_radius=1)

        txt   = self._fmt_fn(self.value) + self._suffix
        tsurf = font.render(txt, True, iOSTheme.label)
        lx    = mr.right
        rx    = pr.left
        cx    = (lx + rx) // 2
        surface.blit(tsurf, (cx - tsurf.get_width() // 2,
                              cy - tsurf.get_height() // 2))
